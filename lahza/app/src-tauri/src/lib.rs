mod engine;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(engine::EngineState::new())
        .setup(|app| {
            engine::spawn(app.handle())?;
            engine::install_signal_handlers(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine::engine_info])
        .build(tauri::generate_context!())
        .expect("Lahza Studio ishga tushmadi")
        .run(|app, event| {
            // Cmd+Q, oxirgi oyna yopilishi, app.exit() - hammasi Exit'ga keladi.
            // Force quit/crash'da bu ishlamaydi - u holda engine'ning o'z watchdog'i (--parent-pid,
            // --watch-stdin) ishlaydi.
            if let tauri::RunEvent::Exit = event {
                engine::kill(app);
            }
        });
}
