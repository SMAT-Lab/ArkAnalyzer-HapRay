//! CLI 模式 - 无 UI 命令行执行
//!
//! 用法: ArkAnalyzer-HapRay <action> [--param value]...

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use desktop_lib::{common, execution};

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

fn plugins_dir_from_exe() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.canonicalize().unwrap_or(exe);
    eprintln!("[cli] exe: {}", exe.display());
    let parent = exe.parent()?;
    eprintln!("[cli] exe.parent: {}", parent.display());
    
    #[cfg(target_os = "macos")]
    if let Some(contents) = parent.parent() {
        let tools = contents.join("Resources").join("tools");
        if tools.exists() {
            return Some(tools);
        }
    }

    let relative_paths = [
        "../Resources/tools",
        "../tools",
        "../../dist/tools",
        "tools",
    ];

    for rel in relative_paths {
        let tools = parent.join(rel);
        if tools.exists() {
            return Some(tools);
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

// -----------------------------------------------------------------------------
// 插件元数据
// -----------------------------------------------------------------------------

fn read_plugin_json(plugin_dir: &Path) -> Option<serde_json::Value> {
    let path = plugin_dir.join("plugin.json");
    let content = std::fs::read_to_string(&path).ok()?;
    serde_json::from_str(&content).ok()
}

fn find_plugin_dir_by_id(plugins_dir: &Path, plugin_id: &str) -> Option<PathBuf> {
    let direct = plugins_dir.join(plugin_id).join("plugin.json");
    if direct.exists() {
        return Some(plugins_dir.join(plugin_id));
    }

    for entry in std::fs::read_dir(plugins_dir).ok()?.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let meta = read_plugin_json(&path)?;
        if meta.get("id").and_then(|v| v.as_str()) == Some(plugin_id) {
            return Some(path);
        }
    }
    None
}

fn build_action_registry(plugins_dir: &Path) -> HashMap<String, String> {
    let mut registry = HashMap::new();

    let entries = match std::fs::read_dir(plugins_dir) {
        Ok(e) => e,
        Err(_) => return registry,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let meta = match read_plugin_json(&path) {
            Some(m) => m,
            None => continue,
        };

        let plugin_id = meta
            .get("id")
            .and_then(|v| v.as_str())
            .map(String::from)
            .unwrap_or_else(|| path.file_name().unwrap().to_string_lossy().to_string());

        if let Some(actions) = meta.get("actions").and_then(|a| a.as_object()) {
            for action_key in actions.keys() {
                registry.insert(action_key.clone(), plugin_id.clone());
            }
        }
    }
    registry
}

fn short_option_mappings(
    plugins_dir: &Path,
    plugin_id: &str,
    action: &str,
) -> Option<HashMap<String, String>> {
    let plugin_dir = find_plugin_dir_by_id(plugins_dir, plugin_id)?;
    let meta = read_plugin_json(&plugin_dir)?;
    let params = meta
        .get("actions")
        .and_then(|a| a.get(action))
        .and_then(|ac| ac.get("parameters"))
        .and_then(|p| p.as_object())?;

    let mut mappings = HashMap::new();
    for (param_name, param_def) in params {
        if let Some(short) = param_def.get("short").and_then(|s| s.as_str()) {
            mappings.insert(short.to_string(), param_name.clone());
        }
    }
    Some(mappings)
}

fn short_option_mappings_or_empty(
    plugins_dir: &Path,
    plugin_id: &str,
    action: &str,
) -> HashMap<String, String> {
    short_option_mappings(plugins_dir, plugin_id, action).unwrap_or_default()
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

fn parse_short_arg(
    short: &str,
    short_to_param: &HashMap<String, String>,
    args: &[String],
    i: &mut usize,
) -> (String, serde_json::Value) {
    let param_key = short_to_param
        .get(short)
        .cloned()
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

    let registry = build_action_registry(plugins_dir);
    let plugin_id = registry.get(&action)?.clone();
    let short_to_param = short_option_mappings_or_empty(plugins_dir, &plugin_id, &action);
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
    let path = match config_file_path() {
        Some(p) if p.exists() => p,
        _ => return Vec::new(),
    };

    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };
    let config: serde_json::Value = match serde_json::from_str(&content) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };
    let config_obj = match config
        .get("plugins")
        .and_then(|p| p.as_object())
        .and_then(|p| p.get(plugin_id))
        .and_then(|e| e.get("config"))
        .and_then(|c| c.as_object())
    {
        Some(obj) => obj,
        None => return Vec::new(),
    };

    common::config_object_to_env_vars(config_obj)
}

// -----------------------------------------------------------------------------
// 工具执行
// -----------------------------------------------------------------------------

fn execute_tool(
    plugins_dir: &Path,
    request: &mut CliRunRequest,
) -> Result<i32, String> {
    eprintln!("[cli] plugins_dir: {}", plugins_dir.display());

    let plugin_dir = find_plugin_dir_by_id(plugins_dir, &request.plugin_id).ok_or_else(|| {
        format!(
            "插件不存在: 未找到 id={} (plugins_dir: {})",
            request.plugin_id,
            plugins_dir.display()
        )
    })?;
    eprintln!("[cli] plugin_dir: {}", plugin_dir.display());

    let meta = read_plugin_json(&plugin_dir)
        .ok_or_else(|| "读取插件配置失败".to_string())?;

    let execution = meta
        .get("execution")
        .and_then(|e| e.get("release").or_else(|| e.get("debug")))
        .ok_or("execution 配置缺失")?;

    let cmd_arr = execution
        .get("cmd")
        .and_then(|c| c.as_array())
        .ok_or("cmd 配置缺失")?;

    let executable = execution::pick_executable(cmd_arr, &plugin_dir);
    eprintln!("[cli] picked executable (raw): {}", executable);

    let script = execution.get("script").and_then(|s| s.as_str());
    let plugin_path = plugin_dir.canonicalize().unwrap_or_else(|_| plugin_dir.to_path_buf());

    let mut args: Vec<String> = Vec::new();
    if let Some(s) = script {
        args.push(s.to_string());
    }

    request.params.insert("action".to_string(), serde_json::json!(request.action.clone()));
    execution::apply_action_mapping(&meta, &request.action, &mut request.params, &mut args);

    for (key, value) in request.params.drain() {
        execution::push_param_as_args(&key, value, &mut args);
    }

    let exe_path = execution::resolve_executable(&executable, &plugin_path);
    eprintln!("[cli] resolved exe_path: {}", exe_path);

    // 将相对路径解析为基于 plugin_path 的绝对路径，避免依赖进程 cwd
    let exe_path_abs = if Path::new(&exe_path).is_absolute() {
        PathBuf::from(&exe_path)
    } else if exe_path.starts_with("./") || exe_path.starts_with("../") {
        let joined = plugin_path.join(&exe_path);
        if joined.exists() {
            joined.canonicalize().unwrap_or(joined)
        } else {
            eprintln!("[cli] 可执行文件不存在: {} (从 plugin_path 解析)", joined.display());
            return Err(format!(
                "可执行文件不存在: {}。请确保已构建 opt-detector 并放入 tools/opt-detector/ 目录",
                joined.display()
            ));
        }
    } else {
        Path::new(&exe_path)
            .canonicalize()
            .unwrap_or_else(|_| {
                let in_plugin = plugin_path.join(&exe_path);
                if in_plugin.exists() {
                    in_plugin.canonicalize().unwrap_or(in_plugin)
                } else {
                    eprintln!("[cli] 可执行文件不存在: {} 或 {}", exe_path, in_plugin.display());
                    PathBuf::from(&exe_path)
                }
            })
    };

    if !exe_path_abs.exists() {
        return Err(format!(
            "可执行文件不存在: {}。请确保已构建 opt-detector 并放入 tools/opt-detector/ 目录",
            exe_path_abs.display()
        ));
    }

    let cwd = plugin_path
        .canonicalize()
        .unwrap_or_else(|_| plugin_path.to_path_buf());

    log_command(exe_path_abs.to_str().unwrap_or(&exe_path), &args);

    let mut cmd = Command::new(&exe_path_abs);
    for (k, v) in load_plugin_env_config(&request.plugin_id) {
        cmd.env(k, v);
    }

    let status = cmd
        .args(&args)
        .current_dir(&cwd)
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
