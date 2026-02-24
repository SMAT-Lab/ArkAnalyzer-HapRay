//! CLI 模式 - 无 UI 命令行执行
//!
//! 用法: ArkAnalyzer-HapRay <action> [--param value]...

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use desktop_lib::{common, execution, plugins::load_plugins_with_log};

// -----------------------------------------------------------------------------
// 类型定义
// -----------------------------------------------------------------------------

/// 解析后的 CLI 运行参数
struct CliRunRequest {
    plugin_id: String,
    action: String,
    params: HashMap<String, serde_json::Value>,
}

// -----------------------------------------------------------------------------
// 路径解析
// -----------------------------------------------------------------------------

fn plugins_dir_from_workspace() -> Option<PathBuf> {
    #[cfg(debug_assertions)]
    {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let workspace = manifest.parent()?.parent()?;
        [workspace.join("dist").join("tools"), workspace.join("tools")]
            .into_iter()
            .find(|p| p.exists())
    }
    #[cfg(not(debug_assertions))]
    None
}

/// 检查目录是否包含至少一个有效插件（有 plugin.json 的子目录）
fn plugins_dir_has_plugins(p: &Path) -> bool {
    let Ok(entries) = std::fs::read_dir(p) else {
        return false;
    };
    entries.flatten().any(|e| {
        let path = e.path();
        path.is_dir() && path.join("plugin.json").exists()
    })
}

fn plugins_dir_from_exe() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.canonicalize().unwrap_or(exe);
    eprintln!("[cli] exe: {}", exe.display());
    let parent = exe.parent()?;
    eprintln!("[cli] exe.parent: {}", parent.display());

    // 候选顺序：与 exe 同目录的 tools 优先（dist/ArkAnalyzer-HapRay.exe -> dist/tools），再考虑上级目录
    let candidates: Vec<PathBuf> = {
        let mut v = Vec::new();
        #[cfg(target_os = "macos")]
        if let Some(contents) = parent.parent() {
            v.push(contents.join("Resources").join("tools"));
        }
        #[cfg(not(target_os = "macos"))]
        {
            v.push(parent.join("tools")); // dist/xxx.exe -> dist/tools
        }
        v.extend([
            parent.join("../Resources/tools"),
            parent.join("../tools"),
            parent.join("../../dist/tools"),
            parent.join("../../../tools"), // dist/ArkAnalyzer-HapRay.app/Contents/MacOS -> dist/tools
        ]);
        #[cfg(target_os = "macos")]
        v.push(parent.join("tools"));
        v
    };

    for tools in &candidates {
        if tools.exists() && plugins_dir_has_plugins(tools) {
            return Some(tools.clone());
        }
    }

    // 若所有候选都无有效插件，返回第一个存在的（兼容空目录场景）
    for tools in &candidates {
        if tools.exists() {
            return Some(tools.clone());
        }
    }

    None
}

fn find_plugins_dir() -> Option<PathBuf> {
    plugins_dir_from_workspace().or_else(plugins_dir_from_exe)
}

fn config_file_path() -> Option<PathBuf> {
    dirs::home_dir().map(|h| h.join(".hapray-gui").join("config.json"))
}

/// 从已加载的插件中提取短参数映射 (short -> param_name)
fn short_option_mappings_from_plugins(
    plugins: &[desktop_lib::plugins::PluginMetadata],
    plugin_id: &str,
    action: &str,
) -> HashMap<String, String> {
    let mut mappings = HashMap::new();
    let Some(meta) = plugins.iter().find(|p| p.id == plugin_id) else {
        return mappings;
    };
    let Some(action_config) = meta.actions.get(action) else {
        return mappings;
    };
    for (param_name, param_def) in &action_config.parameters {
        if let Some(ref short) = param_def.short {
            mappings.insert(short.clone(), param_name.clone());
        }
    }
    mappings
}

// -----------------------------------------------------------------------------
// 参数解析
// -----------------------------------------------------------------------------

fn parse_long_arg(
    key: &str,
    args: &[String],
    i: &mut usize,
) -> (String, serde_json::Value) {
    if key.starts_with("no-") {
        let param_key = key.trim_start_matches("no-").to_string();
        (param_key, serde_json::json!(false))
    } else if *i + 1 < args.len() && !args[*i + 1].starts_with('-') {
        *i += 1;
        let value = args[*i].clone();
        (key.to_string(), serde_json::json!(value))
    } else {
        (key.to_string(), serde_json::json!(true))
    }
}

/// 常见短参数 fallback（当 plugin.json 的 short 映射缺失时使用）
fn common_short_fallback(short: &str) -> Option<&'static str> {
    match short {
        "i" => Some("input"),
        "o" => Some("output"),
        _ => None,
    }
}

fn parse_short_arg(
    short: &str,
    short_to_param: &HashMap<String, String>,
    args: &[String],
    i: &mut usize,
) -> (String, serde_json::Value) {
    let param_key = short_to_param
        .get(short)
        .cloned()
        .or_else(|| common_short_fallback(short).map(String::from))
        .unwrap_or_else(|| short.to_string());

    let value = if *i + 1 < args.len() && !args[*i + 1].starts_with('-') {
        *i += 1;
        serde_json::json!(args[*i].clone())
    } else {
        serde_json::json!(true)
    };
    (param_key, value)
}

fn parse_raw_args(
    args: &[String],
    short_to_param: &HashMap<String, String>,
) -> HashMap<String, serde_json::Value> {
    let mut params = HashMap::new();
    let mut i = 0;

    while i < args.len() {
        let arg = &args[i];

        if arg.starts_with("--") {
            let key = arg.trim_start_matches('-');
            if !key.is_empty() {
                let (k, v) = parse_long_arg(key, args, &mut i);
                params.insert(k, v);
            }
        } else if arg.starts_with('-')
            && arg.len() == 2
            && !arg.chars().nth(1).map_or(true, |c| c.is_ascii_digit())
        {
            let short = &arg[1..2];
            let (k, v) = parse_short_arg(short, short_to_param, args, &mut i);
            params.insert(k, v);
        }
        i += 1;
    }
    params
}

fn parse_cli_request(
    plugins_dir: &Path,
    raw_args: &[String],
) -> Option<CliRunRequest> {
    if raw_args.len() < 2 {
        return None;
    }
    let action = raw_args[1].clone();
    if action.starts_with('-') {
        return None;
    }

    let plugins_path = plugins_dir.to_path_buf();
    let (plugins, _log) = load_plugins_with_log(&plugins_path);
    let registry: HashMap<String, String> = plugins
        .iter()
        .flat_map(|meta| meta.actions.keys().map(move |k| (k.clone(), meta.id.clone())))
        .collect();
    let plugin_id = registry.get(&action)?.clone();
    let short_to_param = short_option_mappings_from_plugins(&plugins, &plugin_id, &action);
    let params = parse_raw_args(&raw_args[2..], &short_to_param);

    Some(CliRunRequest {
        plugin_id,
        action,
        params,
    })
}

// -----------------------------------------------------------------------------
// 插件配置
// -----------------------------------------------------------------------------

fn load_plugin_env_config(plugin_id: &str) -> Vec<(String, String)> {
    config_file_path()
        .and_then(|p| common::load_plugin_env_config(&p, plugin_id).ok())
        .unwrap_or_default()
}

// -----------------------------------------------------------------------------
// 工具执行
// -----------------------------------------------------------------------------

fn execute_tool(
    plugins_dir: &Path,
    request: &mut CliRunRequest,
) -> Result<i32, String> {
    eprintln!("[cli] plugins_dir: {}", plugins_dir.display());

    let prepared =
        execution::prepare_tool_command(plugins_dir, &request.plugin_id, &request.action, &mut request.params)?;

    eprintln!("[cli] plugin_dir (cwd): {}", prepared.cwd.display());
    eprintln!("[cli] resolved exe_path: {}", prepared.exe_path.display());
    log_command(prepared.exe_path.to_str().unwrap_or(""), &prepared.args);

    let mut cmd = Command::new(&prepared.exe_path);
    for (k, v) in load_plugin_env_config(&request.plugin_id) {
        eprintln!("[cli] env {}={}", k, v);
        cmd.env(k, v);
    }

    let status = cmd
        .args(&prepared.args)
        .current_dir(&prepared.cwd)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("启动进程失败: {}", e))?
        .wait()
        .map_err(|e| format!("等待进程失败: {}", e))?;

    Ok(status.code().unwrap_or(1))
}

fn log_command(exe: &str, args: &[String]) {
    let args_str: Vec<String> = args
        .iter()
        .map(|a| {
            if a.contains(' ') || a.contains('"') || a.is_empty() {
                format!("\"{}\"", a.replace('\\', "\\\\").replace('"', "\\\""))
            } else {
                a.clone()
            }
        })
        .collect();
    eprintln!("$ {} {}", exe, args_str.join(" "));
}

// -----------------------------------------------------------------------------
// 用户界面
// -----------------------------------------------------------------------------

const USAGE: &str = r#"用法: ArkAnalyzer-HapRay <action> [--param value]...
示例: ArkAnalyzer-HapRay analyze --input ./path"#;

fn print_usage() {
    eprintln!("{}", USAGE);
}

fn exit_with_error(message: &str) -> ! {
    eprintln!("错误: {}", message);
    print_usage();
    std::process::exit(1)
}

// -----------------------------------------------------------------------------
// 入口
// -----------------------------------------------------------------------------

/// CLI 模式入口，解析参数并执行工具，执行完毕后退出进程
pub fn run(args: &[String]) -> ! {
    let plugins_dir = match find_plugins_dir() {
        Some(d) => d,
        None => {
            eprintln!("错误: 未找到插件目录");
            eprintln!("请确保 tools 目录存在于可执行文件附近");
            print_usage();
            std::process::exit(1);
        }
    };
    eprintln!("[cli] plugins_dir: {}", plugins_dir.display());

    let request = match parse_cli_request(&plugins_dir, args) {
        Some(r) => r,
        None => {
            if args.len() > 1 && (args[1] == "-h" || args[1] == "--help") {
                print_usage();
                std::process::exit(0);
            }
            exit_with_error("无法解析命令行参数");
        }
    };

    let mut request = request;
    match execute_tool(&plugins_dir, &mut request) {
        Ok(code) => std::process::exit(code),
        Err(e) => exit_with_error(&e),
    }
}
