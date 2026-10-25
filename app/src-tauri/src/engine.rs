//! Python engine sidecar'ini boshqarish (ADR-0001, docs/01-arxitektura.md).
//!
//! * Har ishga tushishda yangi sessiya tokeni (NFR-08).
//! * Engine stdout'ga `LAHZA_READY port=NNNN` yozadi - port shundan olinadi.
//! * Engine qulasa, kamayib boruvchi tezlikda (1, 2, ... 5 s) qayta ishga tushiriladi, ko'pi bilan 5 marta.
//! * Ilova yopilganda engine o'ldiriladi.

use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const MAX_RESTARTS: u32 = 5;

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
        .args(["serve", "--port", "0"])
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
        cmd = cmd.env(
            "LAHZA_CORS_ORIGINS",
            "http://127.0.0.1:1420,http://localhost:1420",
        );
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
        let _ = child.kill();
    }
}
