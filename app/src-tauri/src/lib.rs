mod engine;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(engine::EngineState::new())
        .setup(|app| {
            engine::spawn(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine::engine_info])
        .build(tauri::generate_context!())
        .expect("Lahza Studio ishga tushmadi")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                engine::kill(app);
            }
        });
}
