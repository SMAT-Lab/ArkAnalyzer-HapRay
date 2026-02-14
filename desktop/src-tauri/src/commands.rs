//! Tauri 命令 - 插件加载、工具执行与配置管理

use crate::plugins::{build_sidebar_menu, get_plugins_dir, load_plugins_with_log, resolve_plugin_dir, PluginMetadata, SidebarMenu};
#[derive(Debug, Serialize)]
pub struct LoadPluginsResult {
    pub plugins: Vec<PluginMetadata>,
    pub menu: Vec<SidebarMenu>,
    pub load_log: Vec<String>,
}
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::Read;
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use tauri::Emitter;
use tauri::Manager;
fn get_config_path(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    let home = app
        .path()
        .home_dir()
        .map_err(|e| format!("获取用户目录失败: {}", e))?;
    let config_dir = home.join(".hapray-gui");
    std::fs::create_dir_all(&config_dir).map_err(|e| format!("创建配置目录失败: {}", e))?;
    Ok(config_dir.join("config.json"))
}

fn get_results_dir(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    let home = app
        .path()
        .home_dir()
        .map_err(|e| format!("获取用户目录失败: {}", e))?;
    let results_dir = home.join(".hapray-gui").join("results");
    std::fs::create_dir_all(&results_dir).map_err(|e| format!("创建结果目录失败: {}", e))?;
    Ok(results_dir)
}

/// 从 params 中提取输出路径（output、output_path、output_dir 等）
fn extract_output_path(params: &HashMap<String, serde_json::Value>, cwd: &Path) -> Option<String> {
    for key in ["output", "output_path", "output_dir", "out_dir"] {
        if let Some(v) = params.get(key) {
            if let Some(s) = v.as_str() {
                if !s.is_empty() {
                    let p = Path::new(s);
                    let abs = if p.is_absolute() {
                        p.to_path_buf()
                    } else {
                        cwd.join(p)
                    };
                    if abs.exists() {
                        return Some(abs.to_string_lossy().to_string());
                    }
                    return Some(abs.to_string_lossy().to_string());
                }
            }
        }
    }
    None
}

/// 保存执行记录（参考 result_processor.py）
fn save_execution_record(
    app: &tauri::AppHandle,
    plugin_id: &str,
    action: &str,
    success: bool,
    message: &str,
    params: &HashMap<String, serde_json::Value>,
    meta: &serde_json::Value,
    command: &str,
    output_path: Option<&str>,
    output: &str,
) {
    let results_dir = match get_results_dir(app) {
        Ok(d) => d,
        Err(_) => return,
    };

    let timestamp = Utc::now().format("%Y%m%d_%H%M%S").to_string();
    let tool_name = meta.get("name").and_then(|n| n.as_str()).unwrap_or(plugin_id);
    let action_name = meta
        .get("actions")
        .and_then(|a| a.get(action))
        .and_then(|ac| ac.get("name"))
        .and_then(|n| n.as_str());
    let menu_category = meta
        .get("actions")
        .and_then(|a| a.get(action))
        .and_then(|ac| ac.get("menu"))
        .and_then(|m| m.get("menu1"))
        .and_then(|c| c.as_str());

    let result_dir = results_dir.join(plugin_id).join(&timestamp);
    if let Err(e) = std::fs::create_dir_all(&result_dir) {
        eprintln!("创建执行记录目录失败: {}", e);
        return;
    }

    let result_data = serde_json::json!({
        "tool_name": tool_name,
        "plugin_id": plugin_id,
        "action": action,
        "action_name": action_name,
        "menu_category": menu_category,
        "timestamp": timestamp,
        "success": success,
        "message": message,
        "params": params,
        "command": command,
        "output_path": output_path,
        "output": output,
        "result_dir": result_dir.to_string_lossy().to_string(),
    });

    let result_file = result_dir.join("result.json");
    if let Err(e) = std::fs::write(
        &result_file,
        serde_json::to_string_pretty(&result_data).unwrap_or_default(),
    ) {
        eprintln!("保存执行记录失败: {}", e);
    }
}

#[tauri::command]
pub async fn read_config_command(app: tauri::AppHandle) -> Result<HashMap<String, serde_json::Value>, String> {
    let path = get_config_path(&app)?;
    if !path.exists() {
        return Ok(HashMap::new());
    }
    let content = std::fs::read_to_string(&path).map_err(|e| format!("读取配置失败: {}", e))?;
    serde_json::from_str(&content).map_err(|e| format!("解析配置失败: {}", e))
}

#[tauri::command]
pub async fn write_config_command(
    app: tauri::AppHandle,
    config: HashMap<String, serde_json::Value>,
) -> Result<(), String> {
    let path = get_config_path(&app)?;
    let content = serde_json::to_string_pretty(&config).map_err(|e| format!("序列化配置失败: {}", e))?;
    std::fs::write(&path, content).map_err(|e| format!("写入配置失败: {}", e))
}

#[tauri::command]
pub async fn load_plugins_command(app: tauri::AppHandle) -> Result<LoadPluginsResult, String> {
    let mut load_log = Vec::new();

    let plugins_dir = match get_plugins_dir(&app) {
        Some(p) => {
            load_log.push(format!("[INFO] 使用插件目录: {}", p.display()));
            p
        }
        None => {
            load_log.push("[ERROR] 插件目录不存在，已尝试: 1) 开发环境 workspace/dist/tools 2) $RESOURCE/tools 及父级".to_string());
            return Err(load_log.join("\n"));
        }
    };

    let (plugins, mut plugin_log) = load_plugins_with_log(&plugins_dir);
    load_log.append(&mut plugin_log);

    let menu = build_sidebar_menu(&plugins);

    Ok(LoadPluginsResult {
        plugins,
        menu,
        load_log,
    })
}

#[derive(Debug, Deserialize)]
pub struct ExecuteToolPayload {
    pub plugin_id: String,
    pub action: String,
    pub params: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct ExecuteToolResult {
    pub success: bool,
    pub message: String,
    pub output: String,
}

#[tauri::command]
pub async fn execute_tool_command(
    app: tauri::AppHandle,
    payload: ExecuteToolPayload,
) -> Result<ExecuteToolResult, String> {
    let plugins_dir = get_plugins_dir(&app).ok_or_else(|| "插件目录不存在".to_string())?;
    let plugin_dir = match resolve_plugin_dir(&plugins_dir, &payload.plugin_id) {
        Some(d) => d,
        None => {
            return Ok(ExecuteToolResult {
                success: false,
                message: format!(
                    "插件不存在: 未找到 id={} (plugins_dir: {})",
                    payload.plugin_id,
                    plugins_dir.display()
                ),
                output: String::new(),
            });
        }
    };
    let plugin_json_path = plugin_dir.join("plugin.json");

    let content = std::fs::read_to_string(&plugin_json_path)
        .map_err(|e| format!("读取插件配置失败: {}", e))?;
    let meta: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("解析插件配置失败: {}", e))?;

    let execution = meta
        .get("execution")
        .and_then(|e| e.get("release").or_else(|| e.get("debug")))
        .ok_or("execution 配置缺失")?;

    let cmd_arr = execution
        .get("cmd")
        .and_then(|c| c.as_array())
        .ok_or("cmd 配置缺失")?;

    // 从 cmd_arr 中选取第一个相对于 plugin.json 所在目录存在的可执行文件
    let executable = cmd_arr
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
        });

    let script = execution.get("script").and_then(|s| s.as_str());
    let plugin_path = plugin_dir.canonicalize().unwrap_or(plugin_dir);

    // 构建参数
    let mut args: Vec<String> = Vec::new();
    if let Some(s) = script {
        args.push(s.to_string());
    }

    let mut params = payload.params.clone();
    params.insert("action".to_string(), serde_json::json!(payload.action));

    // 处理 action 映射（参考 tool_executor.py）
    let action_mapping = meta
        .get("actions")
        .and_then(|a| a.get(&payload.action))
        .and_then(|ac| ac.get("action_mapping"))
        .and_then(|am| am.as_object());

    if let Some(mapping) = action_mapping {
        let mapping_type = mapping.get("type").and_then(|t| t.as_str());
        match mapping_type {
            Some("position") => args.push(payload.action.clone()),
            Some("remove") => {}
            Some("map") => {
                if let Some(cmd_arr) = mapping.get("command").and_then(|c| c.as_array()) {
                    for item in cmd_arr {
                        if let Some(s) = item.as_str() {
                            if s.starts_with('{') && s.ends_with('}') {
                                let placeholder_key = &s[1..s.len() - 1];
                                if let Some(v) = params.remove(placeholder_key) {
                                    let val = json_value_to_str(&v);
                                    if !val.is_empty() {
                                        args.push(val);
                                    }
                                }
                            } else {
                                args.push(s.to_string());
                            }
                        } else {
                            args.push(json_value_to_str(item));
                        }
                    }
                }
            }
            _ => args.push(payload.action.clone()),
        }
    } else {
        args.push(payload.action.clone());
    }

    // 参考 tool_executor.py：参数转换逻辑
    for (key, value) in params {
        if key == "action" {
            continue;
        }
        // 跳过 None 和空字符串
        if value.is_null() {
            continue;
        }
        match value {
            serde_json::Value::String(s) if s.is_empty() => continue,
            serde_json::Value::Bool(b) => {
                // 特殊处理：trace 和 perf 参数，false 时添加 --no-trace/--no-perf
                if key == "trace" {
                    if !b {
                        args.push("--no-trace".to_string());
                    }
                } else if key == "perf" {
                    if !b {
                        args.push("--no-perf".to_string());
                    }
                } else if b {
                    args.push(format!("--{}", key));
                }
            }
            serde_json::Value::Array(arr) => {
                if !arr.is_empty() {
                    args.push(format!("--{}", key));
                    for v in arr {
                        args.push(json_value_to_str(&v));
                    }
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

    // 解析可执行文件路径
    let exe_path = resolve_executable(&executable, &plugin_path);
    let cwd = plugin_path.to_str().unwrap_or(".");

    // 构建完整命令字符串并 emit 到前端
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
    let full_cmd = format!("执行命令:\n$ {} {}\n\n", exe_path, args_str.join(" "));
    let _ = app.emit("tool-command", &full_cmd);

    // 获取插件配置并作为环境变量传递（参考 tool_executor.py）
    let plugin_config = get_plugin_config(&app, &payload.plugin_id)?;
    let mut cmd_builder = Command::new(&exe_path);
    for (env_key, env_value) in plugin_config {
        cmd_builder.env(env_key, env_value);
    }

    let mut child = match cmd_builder
        .args(&args)
        .current_dir(cwd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            return Ok(ExecuteToolResult {
                success: false,
                message: format!("启动进程失败: {}", e),
                output: String::new(),
            })
        }
    };

    let stdout_handle = child.stdout.take().unwrap();
    let stderr_handle = child.stderr.take().unwrap();

    let output_collector = Arc::new(Mutex::new(String::new()));
    let out_stdout = Arc::clone(&output_collector);
    let out_stderr = Arc::clone(&output_collector);
    let app_stdout = app.clone();
    let app_stderr = app.clone();

    let t1 = std::thread::spawn(move || {
        let mut buf = [0u8; 256];
        let mut reader = stdout_handle;
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let s = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = app_stdout.emit("tool-output", &s);
                    if let Ok(mut out) = out_stdout.lock() {
                        out.push_str(&s);
                    }
                }
                Err(_) => break,
            }
        }
    });

    let t2 = std::thread::spawn(move || {
        let mut buf = [0u8; 256];
        let mut reader = stderr_handle;
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let s = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = app_stderr.emit("tool-output", &s);
                    if let Ok(mut out) = out_stderr.lock() {
                        out.push_str(&s);
                    }
                }
                Err(_) => break,
            }
        }
    });

    let status = match child.wait() {
        Ok(s) => s,
        Err(e) => {
            return Ok(ExecuteToolResult {
                success: false,
                message: format!("等待进程失败: {}", e),
                output: String::new(),
            })
        }
    };

    let _ = t1.join();
    let _ = t2.join();
    let output_log = output_collector.lock().map(|g| g.clone()).unwrap_or_default();

    let success = status.success();
    let message = if success {
        "执行成功".to_string()
    } else {
        "执行失败".to_string()
    };

    let output_path = extract_output_path(&payload.params, Path::new(cwd));

    save_execution_record(
        &app,
        &payload.plugin_id,
        &payload.action,
        success,
        &message,
        &payload.params,
        &meta,
        &full_cmd,
        output_path.as_deref(),
        &output_log,
    );

    Ok(ExecuteToolResult {
        success,
        message,
        output: String::new(),
    })
}

/// 获取插件配置并转换为环境变量格式（键大写、- 转 _，值转字符串）
fn get_plugin_config(
    app: &tauri::AppHandle,
    plugin_id: &str,
) -> Result<Vec<(String, String)>, String> {
    let path = get_config_path(app)?;
    if !path.exists() {
        return Ok(Vec::new());
    }
    let content = std::fs::read_to_string(&path).map_err(|e| format!("读取配置失败: {}", e))?;
    let config: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("解析配置失败: {}", e))?;

    let plugins = config
        .get("plugins")
        .and_then(|p| p.as_object())
        .and_then(|p| p.get(plugin_id))
        .and_then(|e| e.get("config"))
        .and_then(|c| c.as_object());

    let mut env_vars = Vec::new();
    if let Some(config_obj) = plugins {
        for (key, value) in config_obj {
            let env_key = key.to_uppercase().replace('-', "_");
            let env_value = match value {
                serde_json::Value::Bool(b) => {
                    if *b {
                        "true".to_string()
                    } else {
                        "false".to_string()
                    }
                }
                serde_json::Value::Null => String::new(),
                serde_json::Value::String(s) => s.clone(),
                serde_json::Value::Number(n) => n.to_string(),
                _ => value.to_string(),
            };
            env_vars.push((env_key, env_value));
        }
    }
    Ok(env_vars)
}

fn json_value_to_str(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Null => String::new(),
        _ => v.to_string(),
    }
}

/// 获取执行记录历史（参考 result_processor.get_result_history）
#[tauri::command]
pub async fn get_execution_history_command(
    app: tauri::AppHandle,
    tool_name: Option<String>,
) -> Result<Vec<serde_json::Value>, String> {
    let results_dir = get_results_dir(&app)?;
    let mut history = Vec::new();

    let dirs: Vec<std::path::PathBuf> = if let Some(ref name) = tool_name {
        let tool_dir = results_dir.join(name);
        if !tool_dir.exists() {
            return Ok(history);
        }
        std::fs::read_dir(&tool_dir)
            .map_err(|e| format!("读取目录失败: {}", e))?
            .flatten()
            .filter_map(|e| {
                let p = e.path();
                if p.is_dir() {
                    Some(p)
                } else {
                    None
                }
            })
            .collect()
    } else {
        let mut all = Vec::new();
        if let Ok(entries) = std::fs::read_dir(&results_dir) {
            for entry in entries.flatten() {
                let tool_dir = entry.path();
                if tool_dir.is_dir() {
                    if let Ok(sub) = std::fs::read_dir(&tool_dir) {
                        for sub_entry in sub.flatten() {
                            let p = sub_entry.path();
                            if p.is_dir() {
                                all.push(p);
                            }
                        }
                    }
                }
            }
        }
        all
    };

    let mut result_dirs: Vec<_> = dirs.into_iter().collect();
    result_dirs.sort_by(|a, b| b.cmp(a));

    for result_dir in result_dirs {
        let result_file = result_dir.join("result.json");
        if result_file.exists() {
            if let Ok(content) = std::fs::read_to_string(&result_file) {
                if let Ok(data) = serde_json::from_str::<serde_json::Value>(&content) {
                    history.push(data);
                }
            }
        }
    }

    Ok(history)
}

/// 获取单条执行记录详情
#[tauri::command]
pub async fn get_execution_record_detail_command(
    app: tauri::AppHandle,
    plugin_id: String,
    timestamp: String,
) -> Result<Option<serde_json::Value>, String> {
    let results_dir = get_results_dir(&app)?;
    let result_file = results_dir.join(&plugin_id).join(&timestamp).join("result.json");
    if !result_file.exists() {
        return Ok(None);
    }
    let content = std::fs::read_to_string(&result_file).map_err(|e| format!("读取失败: {}", e))?;
    let data = serde_json::from_str::<serde_json::Value>(&content)
        .map_err(|e| format!("解析失败: {}", e))?;
    Ok(Some(data))
}

/// 在文件管理器中打开路径（文件用默认应用打开，目录在 Finder 中打开）
#[tauri::command]
pub async fn open_path_command(_app: tauri::AppHandle, path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    if !p.exists() {
        return Err(format!("路径不存在: {}", path));
    }
    // 解析为绝对路径，避免相对路径或符号链接导致的问题
    let abs_path = match p.canonicalize() {
        Ok(c) => c,
        Err(_) => p.to_path_buf(),
    };
    let path_str = abs_path.to_string_lossy().to_string();

    let result = tauri::async_runtime::spawn_blocking(move || {
        #[cfg(target_os = "macos")]
        {
            // macOS: 使用系统 open 命令，对 .xlsx 等文件能正确关联默认应用
            std::process::Command::new("open")
                .arg(&path_str)
                .status()
                .map_err(|e| format!("打开失败: {}", e))
                .and_then(|s| {
                    if s.success() {
                        Ok(())
                    } else {
                        Err(format!("open 命令执行失败: {}", s))
                    }
                })
        }

        #[cfg(not(target_os = "macos"))]
        {
            tauri_plugin_opener::open_path(&path_str, None::<&str>).map_err(|e| format!("打开失败: {}", e))
        }
    })
    .await
    .map_err(|e| format!("打开失败: {}", e))?
    .map_err(|e| e);

    result
}

/// 获取动态 choices：支持 get_testcases、get_installed_apps
#[tauri::command]
pub async fn get_dynamic_choices_command(
    app: tauri::AppHandle,
    choices_func: String,
) -> Result<Vec<String>, String> {
    match choices_func.as_str() {
        "get_testcases" => get_testcases(&app),
        "get_installed_apps" => get_installed_apps(),
        _ => Err(format!("未知的动态选项函数: {}", choices_func)),
    }
}

fn get_testcases(app: &tauri::AppHandle) -> Result<Vec<String>, String> {
    let plugins_dir = get_plugins_dir(app).ok_or_else(|| "插件目录不存在".to_string())?;
    let testcases_dir = plugins_dir
        .join("perf-testing")
        .join("_internal")
        .join("hapray")
        .join("testcases");

    if !testcases_dir.exists() {
        return Ok(vec![]);
    }

    let mut testcases = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&testcases_dir) {
        for entry in entries.flatten() {
            let app_dir = entry.path();
            if !app_dir.is_dir() || app_dir.file_name().and_then(|n| n.to_str()).unwrap_or("").starts_with('_') {
                continue;
            }
            if let Ok(py_files) = std::fs::read_dir(&app_dir) {
                for py_entry in py_files.flatten() {
                    let py_path = py_entry.path();
                    if py_path.extension().map_or(false, |e| e == "py") {
                        if let Some(stem) = py_path.file_stem() {
                            let name = stem.to_string_lossy();
                            if name != "__init__" {
                                testcases.push(name.to_string());
                            }
                        }
                    }
                }
            }
        }
    }
    testcases.sort();
    Ok(testcases)
}

fn get_installed_apps() -> Result<Vec<String>, String> {
    let output = std::process::Command::new("hdc")
        .args(["shell", "bm", "dump", "-a"])
        .output()
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                "hdc 命令未找到，请确保已安装 HDC 工具并配置到 PATH".to_string()
            } else {
                format!("执行 hdc 失败: {}", e)
            }
        })?;

    let mut apps = Vec::new();
    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        for raw_line in stdout.lines() {
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') || line.starts_with('[') {
                continue;
            }
            if line.contains('.') && !line.starts_with("com.huawei.") && !line.starts_with("com.ohos.") {
                apps.push(line.to_string());
            }
        }
    }
    apps.sort();
    apps.dedup();
    Ok(apps)
}

fn resolve_executable(cmd: &str, plugin_path: &Path) -> String {
    let cmd_lower = cmd.to_lowercase();
    if cmd_lower.contains("python") {
        return "python".to_string();
    }
    if cmd_lower.contains("node") {
        return "node".to_string();
    }

    // 相对路径
    if cmd.starts_with("./") || cmd.starts_with("../") {
        let joined = plugin_path.join(cmd);
        if joined.exists() {
            return joined.to_string_lossy().to_string();
        }
    }

    // 插件目录下查找
    let name = cmd.trim_start_matches("./");
    let in_plugin = plugin_path.join(name);
    if in_plugin.exists() {
        return in_plugin.to_string_lossy().to_string();
    }

    cmd.to_string()
}
