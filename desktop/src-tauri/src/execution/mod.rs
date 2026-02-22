//! 工具执行 - 命令构建、可执行文件解析、参数转换

use std::collections::HashMap;
use std::path::Path;

use crate::common;

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

/// 从 cmd 数组选取第一个存在的可执行文件
pub fn pick_executable(
    cmd_arr: &[serde_json::Value],
    plugin_dir: &Path,
) -> String {
    cmd_arr
        .iter()
        .filter_map(|v| v.as_str())
        .find_map(|cmd_str| {
            let path = plugin_dir.join(cmd_str);
            if path.exists() {
                Some(path.to_string_lossy().to_string())
            } else {
                None
            }
        })
        .unwrap_or_else(|| {
            cmd_arr
                .first()
                .and_then(|v| v.as_str())
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
