mod commands;
mod plugins;

use tauri::WebviewWindowBuilder;
#[cfg(windows)]
use tauri_plugin_decorum::WebviewWindowExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_decorum::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            commands::load_plugins_command,
            commands::execute_tool_command,
            commands::read_config_command,
            commands::write_config_command,
            commands::get_execution_history_command,
            commands::get_execution_record_detail_command,
            commands::open_path_command,
            commands::get_dynamic_choices_command,
        ])
        .setup(|app| {
            let config = app
                .config()
                .app
                .windows
                .iter()
                .find(|w| w.label == "main")
                .expect("main window config missing");

            let window_builder = WebviewWindowBuilder::from_config(app, config)
                .expect("Failed to create window builder from config");

            #[cfg(target_os = "macos")]
            let window_builder = window_builder
                .title_bar_style(tauri::TitleBarStyle::Overlay)
                .hidden_title(true);

            #[cfg(windows)]
            let window_builder = window_builder.decorations(false);

            #[allow(unused_variables)]
            let window = window_builder.build().expect("Failed to create window");

            #[cfg(windows)]
            let _ = window.create_overlay_titlebar();

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|_app, _event| {});
}

