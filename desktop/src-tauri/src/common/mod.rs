//! 共享工具函数 - JSON 转换、配置转环境变量等

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
