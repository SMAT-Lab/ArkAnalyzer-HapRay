//! Tauri 命令 - 插件加载、工具执行与配置管理

use crate::common;
use crate::execution;
use crate::plugins::{build_sidebar_menu, get_plugins_dir, load_plugins_with_log, PluginMetadata, SidebarMenu};

#[derive(Debug, Serialize)]
pub struct LoadPluginsResult {
    pub plugins: Vec<PluginMetadata>,
    pub menu: Vec<SidebarMenu>,
    pub load_log: Vec<String>,
}
use chrono::Utc;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
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
    // 将执行记录统一保存在用户目录下 ~/.hapray-gui/results，保持与原有行为一致
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

fn extract_output_path_from_params(action: &str, params: &HashMap<String, serde_json::Value>, cwd: &Path) -> Option<String> {
    let _ = action; // 保留 action 参数，便于未来按 action 扩展，但此处不做路径映射
    extract_output_path(params, cwd)
}

/// 从执行日志中尝试解析产物输出目录（params 未提供时的兜底）。
/// 匹配常见关键词后的路径（中英文），并校验为已存在的目录。
fn extract_output_path_from_log(log: &str, cwd: &Path) -> Option<String> {
    if log.is_empty() {
        return None;
    }
    // 按行或常见分隔看，避免单行过长时漏掉靠后的路径
    let normalized = log.replace("\r\n", "\n").replace('\r', "\n");
    let haystack = normalized.as_str();

    // 关键词 + 冒号/等号后的路径；捕获组为非空、不含换行的串（路径可能含空格）
    let patterns = [
        (r"(?i)输出目录\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)输出路径\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)结果\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)output\s+(?:directory|path|dir)\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)reports?\s+(?:will\s+be\s+saved\s+to|path)\s*[:：]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)reports?\s*(?:path)?\s*[:：]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)reports?\s+will\s+be\s+saved\s+to\s*[:：]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)reports?\s+path\s*[:：]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)saved\s+to\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"(?i)written\s+to\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"保存到\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
        (r"报告\s*[：:=]\s*([^\s\n\r][^\n\r]*)", 1),
    ];

    let mut candidates: Vec<String> = Vec::new();
    for (pat, group) in patterns {
        if let Ok(re) = Regex::new(pat) {
            for cap in re.captures_iter(haystack) {
                if let Some(m) = cap.get(group) {
                    let s = m.as_str().trim().trim_matches(|c| c == '"' || c == '\'' || c == ',' || c == '.');
                    let looks_like_path = s.contains('/')
                        || s.contains('\\')
                        || (s.as_bytes().len() >= 2
                            && s.as_bytes()[0].is_ascii_alphabetic()
                            && s.as_bytes().get(1) == Some(&b':'));
                    if !s.is_empty() && looks_like_path {
                        candidates.push(s.to_string());
                    }
                }
            }
        }
    }

    for raw in candidates {
        let trimmed = raw.trim();
        let path = Path::new(trimmed);
        let abs = if path.is_absolute() {
            path.to_path_buf()
        } else {
            cwd.join(path)
        };
        if abs.exists() {
            if abs.is_dir() {
                return Some(abs.to_string_lossy().to_string());
            }
            // 日志里常见的是报告/文件路径，其父目录即输出目录
            if abs.is_file() {
                if let Some(parent) = abs.parent() {
                    if parent.exists() && parent.is_dir() {
                        return Some(parent.to_string_lossy().to_string());
                    }
                }
            }
        }
    }
    None
}

fn extract_output_path_from_log_first(action: &str, log: &str, cwd: &Path) -> Option<String> {
    let _ = action;
    extract_output_path_from_log(log, cwd)
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
            let tried = crate::plugins::get_plugins_dir_tried_paths(&app);
            load_log.push(format!(
                "[ERROR] 插件目录不存在，已尝试:\n{}",
                tried
                    .iter()
                    .enumerate()
                    .map(|(i, p)| format!("  {}) {}", i + 1, p))
                    .collect::<Vec<_>>()
                    .join("\n")
            ));
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

/// 解析子进程工作目录：若传入的 cwd 非空且为有效目录则使用，否则使用当前目录。
fn resolve_work_dir(cwd_override: Option<&str>) -> PathBuf {
    if let Some(s) = cwd_override {
        let s = s.trim();
        if !s.is_empty() {
            let p = PathBuf::from(s);
            if p.is_dir() {
                return p.canonicalize().unwrap_or(p);
            }
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

#[derive(Debug, Deserialize)]
pub struct ExecuteToolPayload {
    pub plugin_id: String,
    pub action: String,
    pub params: HashMap<String, serde_json::Value>,
    /// 可选。子进程的工作目录；不传或无效则使用当前目录。
    pub cwd: Option<String>,
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
    let mut params = payload.params.clone();
    // prepare_tool_command 内部会对 params 做 drain() 以构建命令行参数；
    // 因此这里保留一份未被清空的副本，用于输出目录历史记录的兜底解析。
    let params_for_history = params.clone();
    let prepared = match execution::prepare_tool_command(
        &plugins_dir,
        &payload.plugin_id,
        &payload.action,
        &mut params,
    ) {
        Ok(p) => p,
        Err(e) => {
            return Ok(ExecuteToolResult {
                success: false,
                message: e,
                output: String::new(),
            });
        }
    };

    let exe_path_str = prepared.exe_path.to_string_lossy();
    let args_str: Vec<String> = prepared
        .args
        .iter()
        .map(|a| {
            if a.contains(' ') || a.contains('"') || a.is_empty() {
                format!("\"{}\"", a.replace('\\', "\\\\").replace('"', "\\\""))
            } else {
                a.clone()
            }
        })
        .collect();
    let full_cmd = format!("执行命令:\n$ {} {}\n\n", exe_path_str, args_str.join(" "));
    let tool_key = format!("{}-{}", payload.plugin_id, payload.action);
    #[derive(Clone, Serialize)]
    struct ToolCommandPayload {
        tool_key: String,
        command: String,
    }
    let _ = app.emit(
        "tool-command",
        ToolCommandPayload {
            tool_key: tool_key.clone(),
            command: full_cmd.clone(),
        },
    );

    let plugin_config = get_plugin_config(&app, &payload.plugin_id)?;
    let work_dir: PathBuf = resolve_work_dir(payload.cwd.as_deref());
    let mut cmd_builder = Command::new(&prepared.exe_path);
    for (env_key, env_value) in plugin_config {
        cmd_builder.env(env_key, env_value);
    }
    #[cfg(windows)]
    cmd_builder.creation_flags(0x08000000); // CREATE_NO_WINDOW，避免点击菜单时闪出命令行窗口

    let mut child = match cmd_builder
        .args(&prepared.args)
        .current_dir(&work_dir)
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
    let tool_key_stdout = tool_key.clone();
    let tool_key_stderr = tool_key.clone();

    #[derive(Clone, Serialize)]
    struct ToolOutputPayload {
        tool_key: String,
        chunk: String,
    }

    let t1 = std::thread::spawn(move || {
        let mut buf = [0u8; 256];
        let mut reader = stdout_handle;
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let s = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = app_stdout.emit(
                        "tool-output",
                        ToolOutputPayload {
                            tool_key: tool_key_stdout.clone(),
                            chunk: s.clone(),
                        },
                    );
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
                    let _ = app_stderr.emit(
                        "tool-output",
                        ToolOutputPayload {
                            tool_key: tool_key_stderr.clone(),
                            chunk: s.clone(),
                        },
                    );
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

    // 以日志输出为准（工具在 macOS 下会自行重定向到用户目录并打印最终路径）
    // 仅当日志无法解析到路径时，才回退到 params 推导路径。
    let output_path = extract_output_path_from_log_first(&payload.action, &output_log, work_dir.as_path())
        .or_else(|| extract_output_path_from_params(&payload.action, &params_for_history, work_dir.as_path()));

    save_execution_record(
        &app,
        &payload.plugin_id,
        &payload.action,
        success,
        &message,
        &payload.params,
        &prepared.meta,
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
    common::load_plugin_env_config(&path, plugin_id)
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

/// 列举 `perf-testing/testcases` 下与 Python 一致的用例名（.py / .yaml 文件名 stem），由构建脚本从 hapray/testcases 复制而来。
fn get_testcases(app: &tauri::AppHandle) -> Result<Vec<String>, String> {
    let plugins_dir = get_plugins_dir(app).ok_or_else(|| "插件目录不存在".to_string())?;
    let testcases_dir = plugins_dir.join("perf-testing").join("testcases");

    if !testcases_dir.is_dir() {
        return Ok(vec![]);
    }

    let mut names = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&testcases_dir) {
        for entry in entries.flatten() {
            let app_dir = entry.path();
            if !app_dir.is_dir() {
                continue;
            }
            if let Ok(files) = std::fs::read_dir(&app_dir) {
                for f in files.flatten() {
                    let p = f.path();
                    let Some(ext) = p.extension().and_then(|e| e.to_str()) else {
                        continue;
                    };
                    if ext != "py" && ext != "yaml" {
                        continue;
                    }
                    if let Some(stem) = p.file_stem().and_then(|s| s.to_str()) {
                        if stem != "__init__" {
                            names.push(stem.to_string());
                        }
                    }
                }
            }
        }
    }

    names.sort();
    names.dedup();
    Ok(names)
}

fn get_installed_apps() -> Result<Vec<String>, String> {
    let mut cmd = std::process::Command::new("hdc");
    #[cfg(windows)]
    {
        // CREATE_NO_WINDOW，避免加载应用包名（调用 hdc）时闪出命令行窗口
        cmd.creation_flags(0x08000000);
    }
    let output = cmd
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
            // 依据包名前缀进行分类：
            // - com.huawei.* 视为系统 App
            // - 其它视为三方 App
            if line.contains('.') {
                let category = if line.starts_with("com.huawei.") {
                    "system"
                } else {
                    "third"
                };
                apps.push(format!("{}::{}", category, line));
            }
        }
    }
    apps.sort();
    apps.dedup();
    Ok(apps)
}
