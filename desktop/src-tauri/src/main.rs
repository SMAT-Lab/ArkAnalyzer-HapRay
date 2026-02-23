// Prevents additional console window on Windows in release (仅 GUI 模式)
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod cli;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    // 有参数时走 CLI 模式，否则走 GUI
    if args.len() > 1 {
        cli::run(&args);
    } else {
        desktop_lib::run();
    }
}
