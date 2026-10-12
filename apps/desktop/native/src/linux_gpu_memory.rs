//! Optional Linux memory providers. No link-time NVIDIA dependency or privileged queries.
#![cfg_attr(test, allow(dead_code))] // NAPI-only providers; the test build removes host exports.
use std::ffi::{c_char, c_void, CStr};
use std::os::fd::AsRawFd;

use napi_derive::napi;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Request {
    pci_address: Option<String>,
    render_node: Option<String>,
    driver: Option<String>,
    vendor_id: Option<u32>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct MemoryDevice {
    pci_address: Option<String>,
    render_node: Option<String>,
    name: Option<String>,
    kind: &'static str,
    total_mib: Option<f64>,
    used_mib: Option<f64>,
    free_mib: Option<f64>,
    source: &'static str,
    reason: Option<&'static str>,
}

impl MemoryDevice {
    fn unknown(request: &Request, source: &'static str, reason: &'static str) -> Self {
        Self {
            pci_address: request.pci_address.clone(),
            render_node: request.render_node.clone(),
            name: None,
            kind: "unknown",
            total_mib: None,
            used_mib: None,
            free_mib: None,
            source,
            reason: Some(reason),
        }
    }
}

#[repr(C)]
#[derive(Default)]
struct NvmlMemory {
    total: u64,
    free: u64,
    used: u64,
}
type NvmlHandle = *mut c_void;
type Shutdown = unsafe extern "C" fn() -> u32;
type HandleByPci = unsafe extern "C" fn(*const c_char, *mut NvmlHandle) -> u32;
type DeviceName = unsafe extern "C" fn(NvmlHandle, *mut c_char, u32) -> u32;
type DeviceMemory = unsafe extern "C" fn(NvmlHandle, *mut NvmlMemory) -> u32;

struct Nvml {
    library: *mut c_void,
    shutdown: Shutdown,
    handle_by_pci: HandleByPci,
    name: DeviceName,
    memory: DeviceMemory,
}
fn nvml_reason(code: u32) -> &'static str {
    match code {
        3 => "unsupported", // NVML_ERROR_NOT_SUPPORTED
        4 => "permission-denied",
        9 | 12 => "driver-unavailable", // driver not loaded / library not found
        _ => "probe-failed",
    }
}

impl Nvml {
    fn open() -> Result<Self, &'static str> {
        // All pointers remain owned by this session; shutdown precedes dlclose.
        unsafe {
            let library = libc::dlopen(
                c"libnvidia-ml.so.1".as_ptr(),
                libc::RTLD_NOW | libc::RTLD_LOCAL,
            );
            if library.is_null() {
                return Err("driver-unavailable");
            }
            macro_rules! symbol {
                ($name:expr, $type:ty) => {{
                    let ptr = libc::dlsym(library, $name.as_ptr());
                    if ptr.is_null() {
                        libc::dlclose(library);
                        return Err("unsupported");
                    }
                    std::mem::transmute::<*mut c_void, $type>(ptr)
                }};
            }
            let init = symbol!(c"nvmlInit_v2", unsafe extern "C" fn() -> u32);
            let shutdown = symbol!(c"nvmlShutdown", Shutdown);
            let handle_by_pci = symbol!(c"nvmlDeviceGetHandleByPciBusId_v2", HandleByPci);
            let name = symbol!(c"nvmlDeviceGetName", DeviceName);
            let memory = symbol!(c"nvmlDeviceGetMemoryInfo", DeviceMemory);
            let code = init();
            if code != 0 {
                libc::dlclose(library);
                return Err(nvml_reason(code));
            }
            Ok(Self {
                library,
                shutdown,
                handle_by_pci,
                name,
                memory,
            })
        }
    }
    fn read(&self, request: &Request) -> MemoryDevice {
        let mut result = MemoryDevice::unknown(request, "nvml", "unknown");
        let Some(address) = request
            .pci_address
            .as_deref()
            .and_then(|s| std::ffi::CString::new(s).ok())
        else {
            return result;
        };
        unsafe {
            let mut handle = std::ptr::null_mut();
            let code = (self.handle_by_pci)(address.as_ptr(), &mut handle);
            if code != 0 {
                result.reason = Some(nvml_reason(code));
                return result;
            }
            let mut name = [0 as c_char; 256];
            if (self.name)(handle, name.as_mut_ptr(), name.len() as u32) == 0 {
                // Enforce termination even if a faulty driver fills the buffer.
                name[255] = 0;
                result.name = Some(CStr::from_ptr(name.as_ptr()).to_string_lossy().into_owned());
            }
            let mut memory = NvmlMemory::default();
            let code = (self.memory)(handle, &mut memory);
            if code == 0 {
                result.kind = "dedicated";
                result.total_mib = Some(memory.total as f64 / 1_048_576.0);
                result.used_mib = Some(memory.used as f64 / 1_048_576.0);
                result.free_mib = Some(memory.free as f64 / 1_048_576.0);
                result.reason = None;
            } else {
                result.reason = Some(nvml_reason(code));
            }
        }
        result
    }
}
impl Drop for Nvml {
    fn drop(&mut self) {
        unsafe {
            (self.shutdown)();
            libc::dlclose(self.library);
        }
    }
}

// Stable i915 uAPI (drm_i915_query / drm_i915_query_item). Do not query free
// memory: unprivileged drivers can return the total there instead of free bytes.
#[repr(C)]
struct I915Query {
    count: u32,
    flags: u32,
    items: u64,
}
#[repr(C)]
struct I915Item {
    id: u64,
    length: i32,
    flags: u32,
    data: u64,
}

fn query_i915(fd: libc::c_int, item: &mut I915Item) -> bool {
    let mut query = I915Query {
        count: 1,
        flags: 0,
        items: (item as *mut I915Item) as u64,
    };
    // _IOWR('d', DRM_COMMAND_BASE + DRM_I915_QUERY, drm_i915_query).
    const REQUEST: libc::c_ulong = 0xc010_6479;
    unsafe { libc::ioctl(fd, REQUEST, &mut query) >= 0 }
}

fn parse_memory_regions(bytes: &[u8], header: usize) -> Result<(bool, u64), &'static str> {
    if bytes.len() < header {
        return Err("probe-failed");
    }
    let count = u32::from_ne_bytes(bytes[..4].try_into().unwrap()) as usize;
    const REGION_SIZE: usize = 88;
    if count == 0 || count > 64 || bytes.len() < header + count * REGION_SIZE {
        return Err("probe-failed");
    }
    let mut system = false;
    let mut local = 0u64;
    for region in bytes[header..header + count * REGION_SIZE]
        .as_chunks::<REGION_SIZE>()
        .0
    {
        let class = u16::from_ne_bytes(region[..2].try_into().unwrap());
        let size = u64::from_ne_bytes(region[8..16].try_into().unwrap());
        match class {
            0 => system = true,
            1 => local = local.saturating_add(size),
            _ => {}
        }
    }
    Ok((system, local))
}
#[repr(C)]
struct XeQuery {
    extensions: u64,
    query: u32,
    size: u32,
    data: u64,
    reserved: [u64; 2],
}
fn xe_regions(fd: libc::c_int) -> Option<Vec<u8>> {
    let mut query = XeQuery {
        extensions: 0,
        query: 1,
        size: 0,
        data: 0,
        reserved: [0; 2],
    };
    // _IOWR('d', DRM_COMMAND_BASE + DRM_XE_DEVICE_QUERY, drm_xe_device_query).
    const REQUEST: libc::c_ulong = 0xc028_6440;
    unsafe {
        if libc::ioctl(fd, REQUEST, &mut query) < 0 || !(8..=65536).contains(&query.size) {
            return None;
        }
        let mut bytes = vec![0; query.size as usize];
        query.data = bytes.as_mut_ptr() as u64;
        if libc::ioctl(fd, REQUEST, &mut query) < 0 {
            return None;
        }
        Some(bytes)
    }
}
fn intel_memory(request: &Request) -> MemoryDevice {
    let mut result = MemoryDevice::unknown(request, "drm", "unsupported");
    let Some(node) = request.render_node.as_deref().filter(|p| {
        p.strip_prefix("/dev/dri/renderD")
            .is_some_and(|n| !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()))
    }) else {
        return result;
    };
    let file = match std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(node)
    {
        Ok(file) => file,
        Err(error) => {
            result.reason = Some(if error.kind() == std::io::ErrorKind::PermissionDenied {
                "permission-denied"
            } else {
                "driver-unavailable"
            });
            return result;
        }
    };
    if request.driver.as_deref() == Some("xe") {
        if let Some(bytes) = xe_regions(file.as_raw_fd()) {
            match parse_memory_regions(&bytes, 8) {
                Ok((_, total)) if total > 0 => {
                    result.kind = "dedicated";
                    result.total_mib = Some(total as f64 / 1_048_576.0);
                    result.reason = None;
                }
                Ok((true, 0)) => {
                    result.kind = "shared";
                    result.reason = None;
                }
                _ => {}
            }
        }
        return result;
    }
    let mut item = I915Item {
        id: 4,
        length: 0,
        flags: 0,
        data: 0,
    };
    {
        if !query_i915(file.as_raw_fd(), &mut item) || !(16..=65536).contains(&item.length) {
            return result;
        }
        let mut bytes = vec![0u8; item.length as usize];
        item.data = bytes.as_mut_ptr() as u64;
        if !query_i915(file.as_raw_fd(), &mut item) {
            return result;
        }
        match parse_memory_regions(&bytes, 16) {
            Ok((_, total)) if total > 0 => {
                result.kind = "dedicated";
                result.total_mib = Some(total as f64 / 1_048_576.0);
                result.reason = None;
            }
            Ok((true, 0)) => {
                result.kind = "shared";
                result.reason = None;
            }
            _ => {}
        }
    }
    result
}

/// Called exclusively by the Linux diagnostic utility process before it starts
/// any subprocesses. Its parent can then kill/reap the entire probe group.
#[napi]
pub fn linux_hardware_probe_process_group() -> bool {
    unsafe {
        libc::getpgrp() == libc::getpid()
            || libc::setpgid(0, 0) == 0 && libc::getpgrp() == libc::getpid()
    }
}

#[napi]
pub async fn linux_gpu_memory_info(requests_json: String) -> napi::Result<String> {
    let requests: Vec<Request> = serde_json::from_str(&requests_json)
        .map_err(|e| napi::Error::from_reason(e.to_string()))?;
    if requests.len() > 64 {
        return Err(napi::Error::from_reason("too many GPU devices"));
    }
    let devices = tokio::task::spawn_blocking(move || {
        let nvml = requests
            .iter()
            .any(|r| r.vendor_id == Some(0x10de))
            .then(Nvml::open);
        requests
            .iter()
            .filter_map(|request| {
                if request.vendor_id == Some(0x10de) {
                    Some(match nvml.as_ref().unwrap() {
                        Ok(session) => session.read(request),
                        Err(reason) => MemoryDevice::unknown(request, "nvml", reason),
                    })
                } else if request.vendor_id == Some(0x8086)
                    && matches!(request.driver.as_deref(), Some("i915" | "xe"))
                {
                    Some(intel_memory(request))
                } else {
                    None
                }
            })
            .collect::<Vec<_>>()
    })
    .await
    .map_err(|e| napi::Error::from_reason(e.to_string()))?;
    serde_json::to_string(&serde_json::json!({ "devices": devices, "reason": null }))
        .map_err(|e| napi::Error::from_reason(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn regions(classes: &[(u16, u64)]) -> Vec<u8> {
        let mut bytes = vec![0; 16 + classes.len() * 88];
        bytes[..4].copy_from_slice(&(classes.len() as u32).to_ne_bytes());
        for (i, (class, size)) in classes.iter().enumerate() {
            let start = 16 + i * 88;
            bytes[start..start + 2].copy_from_slice(&class.to_ne_bytes());
            bytes[start + 8..start + 16].copy_from_slice(&size.to_ne_bytes());
        }
        bytes
    }
    #[test]
    fn distinguishes_shared_ram_and_dedicated_regions_without_using_free_counter() {
        assert_eq!(
            parse_memory_regions(&regions(&[(0, 32 << 30)]), 16),
            Ok((true, 0))
        );
        assert_eq!(
            parse_memory_regions(&regions(&[(0, 32 << 30), (1, 8 << 30)]), 16),
            Ok((true, 8 << 30))
        );
        assert!(parse_memory_regions(&[0; 16], 16).is_err());
        assert!(parse_memory_regions(&regions(&[(1, 8 << 30)])[..32], 16).is_err());
    }
    #[test]
    fn xe_memory_regions_share_the_class_and_size_contract() {
        let i915 = regions(&[(0, 32 << 30), (1, 8 << 30)]);
        let xe: Vec<_> = i915[..8].iter().chain(&i915[16..]).copied().collect();
        assert_eq!(parse_memory_regions(&xe, 8), Ok((true, 8 << 30)));
    }
    #[test]
    fn nvml_errors_remain_distinguishable() {
        assert_eq!(nvml_reason(4), "permission-denied");
        assert_eq!(nvml_reason(9), "driver-unavailable");
        assert_eq!(nvml_reason(3), "unsupported");
    }
}
