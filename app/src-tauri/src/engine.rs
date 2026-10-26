//! Python engine sidecar'ini boshqarish (ADR-0001, docs/01-arxitektura.md).
//!
//! * Har ishga tushishda yangi sessiya tokeni (NFR-08).
//! * Engine stdout'ga `LAHZA_READY port=NNNN` yozadi - port shundan olinadi.
//! * Engine qulasa, kamayib boruvchi tezlikda (1, 2, ... 5 s) qayta ishga tushiriladi, ko'pi bilan 5 marta.
//! * Ilova yopilganda engine to'xtatiladi: avval SIGTERM butun jarayon guruhiga (PyInstaller onefile
//!   bootloader + Python bolasi + ffmpeg/llama-server), ~2.5 s kutish, keyin SIGKILL (`kill`).
//! * Chuqur himoya: engine `--parent-pid <pid> --watch-stdin` bilan ishga tushadi - ilova force quit/
//!   crash bo'lsa (Rust kodi ishlamaydi) engine o'zi chiqadi (engine/src/lahza_engine/core/lifecycle.py).
//! * Engine `--discovery` bilan: `<data_dir>/engine.json` - Adobe plaginlari va mustaqil servis uni
//!   ko'radi (servis ochiq desktop'ni ko'rib ikkinchi engine ko'tarmaydi; `sidecar_args`).
//! * SIGTERM/SIGINT/SIGHUP ilovaga kelsa ham engine to'xtatilib, ilova toza chiqadi (`install_signal_handlers`).

use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const MAX_RESTARTS: u32 = 5;
/// Yumshoq to'xtash (SIGTERM) uchun kutish; so'ng SIGKILL.
const GRACEFUL_STOP: Duration = Duration::from_millis(2500);

#[derive(Clone, Serialize)]
pub struct EngineInfo {
    pub port: u16,
    pub token: String,
}

pub struct EngineState {
    token: String,
    info: Mutex<Option<EngineInfo>>,
    child: Mutex<Option<CommandChild>>,
    restarts: Mutex<u32>,
}

impl EngineState {
    pub fn new() -> Self {
        let token = format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        );
        Self {
            token,
            info: Mutex::new(None),
            child: Mutex::new(None),
            restarts: Mutex::new(0),
        }
    }
}

/// Vite dev server origin'lari (faqat debug build).
const DEV_CORS_ORIGINS: &str = "http://127.0.0.1:1420,http://localhost:1420";

/// Sidecar argumentlari. `--discovery`: engine `<data_dir>/engine.json` yozadi (qat'iy portlar
/// 47600-47602) - Adobe plaginlari Studio engine'ini topadi, `install-service` servisi esa uni ko'rib
/// ikkinchi nusxa ko'tarmaydi (docs/12-adobe-plaginlar.md 3.2/3.3). Portlar band yoki boshqa tirik
/// engine bor bo'lsa, engine o'zi discovery'siz tasodifiy portga o'tadi (`cli.py` `cmd_serve`).
fn sidecar_args(parent_pid: u32) -> Vec<String> {
    [
        "serve",
        "--port",
        "0",
        "--discovery",
        "--watch-stdin",
        "--parent-pid",
    ]
    .iter()
    .map(|s| s.to_string())
    .chain([parent_pid.to_string()])
    .collect()
}

#[tauri::command]
pub fn engine_info(state: tauri::State<'_, EngineState>) -> Result<EngineInfo, String> {
    state
        .info
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .ok_or_else(|| "starting".to_string())
}

pub fn spawn(app: &AppHandle) -> Result<(), String> {
    let state = app.state::<EngineState>();
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;

    let mut cmd = app
        .shell()
        .sidecar("lahza-engine")
        .map_err(|e| e.to_string())?
        .args(sidecar_args(std::process::id()))
        // Bootloader, Python bolasi va ularning bolalari bitta guruhda - birga to'xtatiladi
        // (Windows: Job Object).
        .set_process_group(true)
        .env("LAHZA_TOKEN", &state.token)
        .env("LAHZA_BIN_DIR", resources.join("bin"))
        .env(
            "LAHZA_CATALOG",
            resources.join("catalog").join("catalog.json"),
        );
    cmd = cmd
        .env("LAHZA_CATALOG_PUBKEY", env!("LAHZA_BUNDLED_CATALOG_PUBKEY"))
        .env("LAHZA_DEV", "0");
    if cfg!(debug_assertions) {
        cmd = cmd.env("LAHZA_CORS_ORIGINS", DEV_CORS_ORIGINS);
    }

    let (mut rx, child) = cmd.spawn().map_err(|e| e.to_string())?;
    *state.child.lock().map_err(|e| e.to_string())? = Some(child);

    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    if let Some(port) = text
                        .trim()
                        .strip_prefix("LAHZA_READY port=")
                        .and_then(|p| p.parse::<u16>().ok())
                    {
                        let st = handle.state::<EngineState>();
                        let info = EngineInfo {
                            port,
                            token: st.token.clone(),
                        };
                        if let Ok(mut slot) = st.info.lock() {
                            *slot = Some(info);
                        }
                        let _ = handle.emit("engine://ready", port);
                    }
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[engine] {}", String::from_utf8_lossy(&line).trim_end());
                }
                CommandEvent::Terminated(payload) => {
                    let st = handle.state::<EngineState>();
                    if let Ok(mut slot) = st.info.lock() {
                        *slot = None;
                    }
                    let _ = handle.emit("engine://exited", payload.code);
                    let attempt = st
                        .restarts
                        .lock()
                        .map(|mut r| {
                            *r += 1;
                            *r
                        })
                        .unwrap_or(MAX_RESTARTS + 1);
                    if attempt <= MAX_RESTARTS {
                        tokio::time::sleep(Duration::from_secs(attempt as u64)).await;
                        if let Err(e) = spawn(&handle) {
                            eprintln!("[engine] qayta ishga tushmadi: {e}");
                        }
                    }
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

pub fn kill(app: &AppHandle) {
    let state = app.state::<EngineState>();
    // Qayta ishga tushirishni to'xtatish.
    if let Ok(mut r) = state.restarts.lock() {
        *r = MAX_RESTARTS + 1;
    }
    let child = state.child.lock().ok().and_then(|mut c| c.take());
    if let Some(child) = child {
        stop_child(child, GRACEFUL_STOP);
    }
}

/// Avval SIGTERM (guruhga), `grace` ichida chiqmasa - SIGKILL (guruhga) va kutish.
fn stop_child(child: CommandChild, grace: Duration) {
    #[cfg(unix)]
    {
        // set_process_group(true): pgid == bootloader pid.
        let pgid = child.pid() as libc::pid_t;
        if pgid > 1 && unsafe { libc::killpg(pgid, libc::SIGTERM) } == 0 {
            let deadline = Instant::now() + grace;
            while Instant::now() < deadline {
                // ESRCH: guruhda hech kim qolmadi.
                if unsafe { libc::killpg(pgid, 0) } != 0 {
                    break;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
        }
    }
    #[cfg(not(unix))]
    let _ = (grace, Instant::now());
    // Guruhga SIGKILL (Windows: Job Object terminate) + bootloader'ni yig'ish.
    if let Err(e) = child.kill() {
        eprintln!("[engine] to'xtatishda xato: {e}");
    }
}

/// Ilovaga kelgan SIGTERM/SIGINT/SIGHUP: engine'ni to'xtatib, ilovani toza yopish.
/// Signal handler faqat self-pipe'ga bayt yozadi (async-signal-safe); ish alohida oqimda.
#[cfg(unix)]
pub fn install_signal_handlers(app: &AppHandle) {
    use std::sync::atomic::{AtomicI32, Ordering};
    static WRITE_FD: AtomicI32 = AtomicI32::new(-1);

    extern "C" fn on_signal(_sig: libc::c_int) {
        let fd = WRITE_FD.load(Ordering::Relaxed);
        if fd >= 0 {
            let b = [1u8];
            unsafe {
                libc::write(fd, b.as_ptr() as *const libc::c_void, 1);
            }
        }
    }

    let mut fds = [0 as libc::c_int; 2];
    if unsafe { libc::pipe(fds.as_mut_ptr()) } != 0 {
        return;
    }
    for fd in fds {
        unsafe { libc::fcntl(fd, libc::F_SETFD, libc::FD_CLOEXEC) };
    }
    WRITE_FD.store(fds[1], Ordering::Relaxed);
    for sig in [libc::SIGTERM, libc::SIGINT, libc::SIGHUP] {
        unsafe {
            let mut sa: libc::sigaction = std::mem::zeroed();
            sa.sa_sigaction = on_signal as *const () as usize;
            // Ikkinchi signal - odatiy xatti-harakat (majburiy chiqish).
            sa.sa_flags = libc::SA_RESETHAND;
            libc::sigemptyset(&mut sa.sa_mask);
            libc::sigaction(sig, &sa, std::ptr::null_mut());
        }
    }
    let handle = app.clone();
    let read_fd = fds[0];
    std::thread::spawn(move || {
        let mut b = [0u8; 1];
        loop {
            let n = unsafe { libc::read(read_fd, b.as_mut_ptr() as *mut libc::c_void, 1) };
            if n == 1 {
                break;
            }
            if n == 0 || std::io::Error::last_os_error().kind() != std::io::ErrorKind::Interrupted {
                return;
            }
        }
        kill(&handle);
        handle.exit(0);
    });
}

#[cfg(not(unix))]
pub fn install_signal_handlers(_app: &AppHandle) {}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[test]
    fn sidecar_args_enable_discovery() {
        assert_eq!(
            sidecar_args(4321),
            [
                "serve",
                "--port",
                "0",
                "--discovery",
                "--watch-stdin",
                "--parent-pid",
                "4321"
            ]
        );
        // Token argumentda emas (`ps` da ko'rinmasin) - faqat LAHZA_TOKEN muhitida.
        assert!(!sidecar_args(1).iter().any(|a| a == "--token"));
    }

    #[test]
    fn dev_cors_origins_are_vite() {
        assert_eq!(
            DEV_CORS_ORIGINS.split(',').collect::<Vec<_>>(),
            ["http://127.0.0.1:1420", "http://localhost:1420"]
        );
    }

    #[test]
    fn graceful_stop_budget_is_short() {
        assert!(GRACEFUL_STOP >= Duration::from_secs(2) && GRACEFUL_STOP <= Duration::from_secs(3));
    }
}
