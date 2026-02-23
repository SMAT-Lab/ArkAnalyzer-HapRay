//! 共享工具函数 - JSON 转换、配置转环境变量等

use std::path::Path;

/// 从配置文件加载插件配置并转为环境变量（GUI 与 CLI 共用）
/// 路径通常为 ~/.hapray-gui/config.json
pub fn load_plugin_env_config(path: &Path, plugin_id: &str) -> Result<Vec<(String, String)>, String> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let content = std::fs::read_to_string(path).map_err(|e| format!("读取配置失败: {}", e))?;
    let config: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("解析配置失败: {}", e))?;
    let plugins = config
        .get("plugins")
        .and_then(|p| p.as_object())
        .and_then(|p| p.get(plugin_id))
        .and_then(|e| e.get("config"))
        .and_then(|c| c.as_object());
    Ok(plugins
        .map(config_object_to_env_vars)
        .unwrap_or_default())
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
