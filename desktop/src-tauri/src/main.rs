// Prevents additional console window on Windows in release (仅 GUI 模式)
#![cfg_attr(all(not(debug_assertions), feature = "desktop"), windows_subsystem = "windows")]

mod cli;

// ---------------- 仅 CLI 构建：关闭默认特性（不启用 desktop）时使用 ----------------
#[cfg(not(feature = "desktop"))]
fn main() {
    let args: Vec<String> = std::env::args().collect();
    // 在仅 CLI 模式下，无论是否有参数都直接走 CLI 逻辑
    cli::run(&args);
}

// ---------------- GUI + CLI 构建：启用 desktop（默认）时使用 ----------------
#[cfg(feature = "desktop")]
fn main() {
    let args: Vec<String> = std::env::args().collect();
    // 有参数时走 CLI 模式，否则走 GUI
    if args.len() > 1 {
        cli::run(&args);
    } else {
        desktop_lib::run();
    }
}
