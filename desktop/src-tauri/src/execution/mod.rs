//! 工具执行 - 命令构建、可执行文件解析、参数转换（CLI 与 GUI 共用）

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::common;
use crate::plugins;

/// 当前平台是否应跳过 .exe 条目（macOS/Linux 无法执行 Windows .exe）
fn should_skip_exe() -> bool {
    !cfg!(target_os = "windows")
}

/// 解析可执行文件路径（python/node/相对路径/插件内路径）
pub fn resolve_executable(cmd: &str, plugin_path: &Path) -> String {
    let cmd_lower = cmd.to_lowercase();
    if cmd_lower.contains("python") {
        return "python".to_string();
    }
    if cmd_lower.contains("node") {
        return "node".to_string();
    }
    if cmd.starts_with("./") || cmd.starts_with("../") {
        let joined = plugin_path.join(cmd);
        if joined.exists() {
            return joined.to_string_lossy().to_string();
        }
    }
    let name = cmd.trim_start_matches("./");
    let in_plugin = plugin_path.join(name);
    if in_plugin.exists() {
        return in_plugin.to_string_lossy().to_string();
    }
    cmd.to_string()
}

/// 从 cmd 数组选取第一个存在的可执行文件（平台感知：macOS/Linux 跳过 .exe）
pub fn pick_executable(
    cmd_arr: &[serde_json::Value],
    plugin_dir: &Path,
) -> String {
    let skip_exe = should_skip_exe();
    let chosen = cmd_arr
        .iter()
        .filter_map(|v| v.as_str())
        .find_map(|cmd_str| {
            if skip_exe && cmd_str.ends_with(".exe") {
                return None;
            }
            let path = plugin_dir.join(cmd_str);
            if path.exists() {
                Some(path.to_string_lossy().to_string())
            } else {
                None
            }
        });
    chosen.unwrap_or_else(|| {
        cmd_arr
            .iter()
            .filter_map(|v| v.as_str())
            .find(|s| !(skip_exe && s.ends_with(".exe")))
            .unwrap_or("")
            .to_string()
    })
}

/// 应用 action_mapping 将参数转为命令参数
pub fn apply_action_mapping(
    meta: &serde_json::Value,
    action: &str,
    params: &mut HashMap<String, serde_json::Value>,
    args: &mut Vec<String>,
) {
    let mapping = meta
        .get("actions")
        .and_then(|a| a.get(action))
        .and_then(|ac| ac.get("action_mapping"))
        .and_then(|am| am.as_object());

    let mapping_type = mapping.and_then(|m| m.get("type").and_then(|t| t.as_str()));

    match mapping_type {
        Some("position") => args.push(action.to_string()),
        Some("remove") => {}
        Some("map") => {
            if let Some(m) = mapping {
                if let Some(cmd_arr) = m.get("command").and_then(|c| c.as_array()) {
                    for item in cmd_arr {
                        if let Some(s) = item.as_str() {
                            if s.starts_with('{') && s.ends_with('}') {
                                let key = &s[1..s.len() - 1];
                                if let Some(v) = params.remove(key) {
                                    let val = common::json_value_to_str(&v);
                                    if !val.is_empty() {
                                        args.push(val);
                                    }
                                }
                            } else {
                                args.push(s.to_string());
                            }
                        } else {
                            args.push(common::json_value_to_str(item));
                        }
                    }
                }
            }
        }
        _ => args.push(action.to_string()),
    }
}

/// 将单个参数追加到 args
pub fn push_param_as_args(
    key: &str,
    value: serde_json::Value,
    args: &mut Vec<String>,
) {
    if key == "action" {
        return;
    }
    if value.is_null() {
        return;
    }

    match value {
        serde_json::Value::String(s) if s.is_empty() => {}
        serde_json::Value::Bool(b) => {
            match key {
                "trace" if !b => args.push("--no-trace".to_string()),
                "perf" if !b => args.push("--no-perf".to_string()),
                _ if b => args.push(format!("--{}", key)),
                _ => {}
            }
        }
        serde_json::Value::Array(arr) if !arr.is_empty() => {
            args.push(format!("--{}", key));
            for v in arr {
                args.push(common::json_value_to_str(&v));
            }
        }
        serde_json::Value::String(s) => {
            args.push(format!("--{}", key));
            args.push(s);
        }
        serde_json::Value::Number(n) => {
            args.push(format!("--{}", key));
            args.push(n.to_string());
        }
        _ => {}
    }
}

/// 准备执行工具命令（CLI 与 GUI 共用）
#[derive(Debug)]
pub struct PreparedToolCommand {
    pub exe_path: PathBuf,
    pub args: Vec<String>,
    pub cwd: PathBuf,
    pub meta: serde_json::Value,
}

/// 解析插件目录、读取配置并构建可执行路径与参数（CLI 与 GUI 共用）
pub fn prepare_tool_command(
    plugins_dir: &Path,
    plugin_id: &str,
    action: &str,
    params: &mut HashMap<String, serde_json::Value>,
) -> Result<PreparedToolCommand, String> {
    let plugin_dir = plugins::resolve_plugin_dir(plugins_dir, plugin_id).ok_or_else(|| {
        format!(
            "插件不存在: 未找到 id={} (plugins_dir: {})",
            plugin_id,
            plugins_dir.display()
        )
    })?;

    let plugin_json_path = plugin_dir.join("plugin.json");
    let content = std::fs::read_to_string(&plugin_json_path)
        .map_err(|e| format!("读取插件配置失败: {}", e))?;
    let meta: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("解析插件配置失败: {}", e))?;

    let execution = meta
        .get("execution")
        .and_then(|e| e.get("release").or_else(|| e.get("debug")))
        .ok_or("execution 配置缺失")?;

    let cmd_arr = execution
        .get("cmd")
        .and_then(|c| c.as_array())
        .ok_or("cmd 配置缺失")?;

    let executable = pick_executable(cmd_arr, &plugin_dir);
    let script = execution.get("script").and_then(|s| s.as_str());
    let plugin_path = plugin_dir
        .canonicalize()
        .unwrap_or_else(|_| plugin_dir.to_path_buf());

    let mut args: Vec<String> = Vec::new();
    if let Some(s) = script {
        args.push(s.to_string());
    }

    params.insert("action".to_string(), serde_json::json!(action));
    apply_action_mapping(&meta, action, params, &mut args);

    for (key, value) in params.drain() {
        push_param_as_args(&key, value, &mut args);
    }

    let exe_path = resolve_executable(&executable, &plugin_path);

    let exe_path_abs = if Path::new(&exe_path).is_absolute() {
        PathBuf::from(&exe_path)
    } else if exe_path.starts_with("./") || exe_path.starts_with("../") {
        let joined = plugin_path.join(&exe_path);
        if joined.exists() {
            joined.canonicalize().unwrap_or(joined)
        } else {
            return Err(format!(
                "可执行文件不存在: {}。请确保已构建并放入插件目录",
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
                    PathBuf::from(&exe_path)
                }
            })
    };

    if !exe_path_abs.exists() {
        return Err(format!(
            "可执行文件不存在: {}。请确保已构建并放入插件目录",
            exe_path_abs.display()
        ));
    }

    let cwd = plugin_path
        .canonicalize()
        .unwrap_or_else(|_| plugin_path.to_path_buf());

    Ok(PreparedToolCommand {
        exe_path: exe_path_abs,
        args,
        cwd,
        meta,
    })
}
