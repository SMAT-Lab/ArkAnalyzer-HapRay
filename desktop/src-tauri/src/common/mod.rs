//! 共享工具函数 - JSON 转换、配置转环境变量等

use std::path::Path;

/// 从配置文件加载通用配置 + 插件特有配置，并转为环境变量（GUI 与 CLI 共用）
/// 路径通常为 ~/.hapray-gui/config.json
pub fn load_plugin_env_config(path: &Path, plugin_id: &str) -> Result<Vec<(String, String)>, String> {
    if !path.exists() {
        return Ok(Vec::new());
    }

    let content = std::fs::read_to_string(path).map_err(|e| format!("读取配置失败: {}", e))?;
    let config: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("解析配置失败: {}", e))?;

    let mut envs: Vec<(String, String)> = Vec::new();

    // 通用配置：顶层除 plugins 外的字段
    if let Some(obj) = config.as_object() {
        let mut global_obj = serde_json::Map::new();
        for (k, v) in obj {
            if k != "plugins" {
                global_obj.insert(k.clone(), v.clone());
            }
        }
        if !global_obj.is_empty() {
            envs.extend(config_object_to_env_vars(&global_obj));
        }
    }

    // 插件特有配置：config.plugins[plugin_id].config
    let plugin_config = config
        .get("plugins")
        .and_then(|p| p.as_object())
        .and_then(|p| p.get(plugin_id))
        .and_then(|e| e.get("config"))
        .and_then(|c| c.as_object());
    if let Some(obj) = plugin_config {
        envs.extend(config_object_to_env_vars(obj));
    }

    Ok(envs)
}

/// 将 serde_json::Value 转为命令行参数字符串
pub fn json_value_to_str(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Null => String::new(),
        _ => v.to_string(),
    }
}

/// 将配置值转为环境变量字符串
pub fn config_value_to_env_string(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Null => String::new(),
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        _ => value.to_string(),
    }
}

/// 将插件配置对象转为环境变量列表（键大写、- 转 _）
pub fn config_object_to_env_vars(
    config_obj: &serde_json::Map<String, serde_json::Value>,
) -> Vec<(String, String)> {
    config_obj
        .iter()
        .map(|(key, value)| {
            let env_key = key.to_uppercase().replace('-', "_");
            (env_key, config_value_to_env_string(value))
        })
        .collect()
}
