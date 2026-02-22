//! 命令行参数解析 - 参考 hapray-gui/cmd.py
//! 支持: ArkAnalyzer-HapRay <action> [--param value]... 或 -x value 短选项

use crate::plugins::resolve_plugin_dir;
use serde::Serialize;
use std::collections::HashMap;
use std::path::Path;

/// CLI 运行 payload，emit 给前端执行
#[derive(Debug, Clone, Serialize)]
pub struct CliRunPayload {
    pub plugin_id: String,
    pub action: String,
    pub params: HashMap<String, serde_json::Value>,
}

/// 从插件目录构建 action -> plugin_id 映射（参考 cmd.py _build_action_mapping）
pub fn build_action_to_plugin(plugins_dir: &Path) -> HashMap<String, String> {
    let mut action_to_plugin = HashMap::new();
    let entries = match std::fs::read_dir(plugins_dir) {
        Ok(e) => e,
        Err(_) => return action_to_plugin,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let plugin_json = path.join("plugin.json");
        if !plugin_json.exists() {
            continue;
        }
        let content = match std::fs::read_to_string(&plugin_json) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let meta: serde_json::Value = match serde_json::from_str(&content) {
            Ok(m) => m,
            Err(_) => continue,
        };
        let plugin_id = meta
            .get("id")
            .and_then(|v| v.as_str())
            .map(String::from)
            .unwrap_or_else(|| path.file_name().unwrap().to_string_lossy().to_string());
        let actions = meta.get("actions").and_then(|a| a.as_object());
        if let Some(actions_obj) = actions {
            for action_key in actions_obj.keys() {
                action_to_plugin.insert(action_key.clone(), plugin_id.to_string());
            }
        }
    }
    action_to_plugin
}

/// 获取 action 的 short -> param_name 映射
fn get_short_to_param(plugins_dir: &Path, plugin_id: &str, action: &str) -> HashMap<String, String> {
    let mut short_to_param = HashMap::new();
    let plugin_dir = match resolve_plugin_dir(plugins_dir, plugin_id) {
        Some(d) => d,
        None => return short_to_param,
    };
    let plugin_json = plugin_dir.join("plugin.json");
    if !plugin_json.exists() {
        return short_to_param;
    }
    if let Ok(content) = std::fs::read_to_string(&plugin_json) {
        if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&content) {
            if let Some(actions) = meta.get("actions").and_then(|a| a.get(action)) {
                if let Some(params) = actions.get("parameters").and_then(|p| p.as_object()) {
                    for (param_name, param_def) in params {
                        if let Some(short) = param_def.get("short").and_then(|s| s.as_str()) {
                            short_to_param.insert(short.to_string(), param_name.clone());
                        }
                    }
                }
            }
        }
    }
    short_to_param
}

/// 解析 --key value 或 -x value 格式的参数
fn parse_args(
    args: &[String],
    short_to_param: &HashMap<String, String>,
) -> HashMap<String, serde_json::Value> {
    let mut params = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        if arg.starts_with("--") {
            let key = arg.trim_start_matches('-').to_string();
            if key.is_empty() {
                i += 1;
                continue;
            }
            // 检查 --no-xxx 格式（bool false）
            let (param_key, value): (String, serde_json::Value) = if key.starts_with("no-") {
                let k = key.trim_start_matches("no-").to_string();
                (k, serde_json::json!(false))
            } else if i + 1 < args.len() && !args[i + 1].starts_with('-') {
                let next = args[i + 1].clone();
                i += 1;
                (key, serde_json::json!(next))
            } else {
                (key, serde_json::json!(true))
            };
            params.insert(param_key, value);
        } else if arg.starts_with('-') && arg.len() == 2 && !arg.chars().nth(1).map_or(true, |c| c.is_ascii_digit()) {
            // -x 短选项
            let short = arg.chars().nth(1).unwrap().to_string();
            let param_key = short_to_param.get(&short).cloned().unwrap_or(short);
            let value = if i + 1 < args.len() && !args[i + 1].starts_with('-') {
                i += 1;
                serde_json::json!(args[i].clone())
            } else {
                serde_json::json!(true)
            };
            params.insert(param_key, value);
        }
        i += 1;
    }
    params
}

/// 解析命令行参数，若为 CLI 模式则返回 Some(payload)
/// 格式: ArkAnalyzer-HapRay <action> [--param value]...
pub fn parse_cli_args(
    plugins_dir: &Path,
    raw_args: &[String],
) -> Option<CliRunPayload> {
    if raw_args.len() < 2 {
        return None;
    }
    let action = raw_args[1].clone();
    if action.starts_with('-') {
        return None;
    }
    let action_to_plugin = build_action_to_plugin(plugins_dir);
    let plugin_id = action_to_plugin.get(&action)?.clone();
    let short_to_param = get_short_to_param(plugins_dir, &plugin_id, &action);
    let params = parse_args(&raw_args[2..], &short_to_param);
    Some(CliRunPayload {
        plugin_id,
        action,
        params,
    })
}
