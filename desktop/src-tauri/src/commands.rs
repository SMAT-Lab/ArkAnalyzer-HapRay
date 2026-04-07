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
use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::sync::OnceLock;
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

/// 与 CLI `scripts/main.py` 全局参数一致：`plugin.json` 中 `tool_contract.enabled` 时注入 `--result-file` / 可选 `--machine-json`。
fn tool_contract_enabled(meta: &serde_json::Value) -> bool {
    meta.get("tool_contract")
        .and_then(|v| v.get("enabled"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
}

fn tool_contract_result_basename(meta: &serde_json::Value) -> String {
    meta.get("tool_contract")
        .and_then(|v| v.get("result_file"))
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| "hapray-tool-result.json".to_string())
}

fn tool_contract_machine_json(meta: &serde_json::Value) -> bool {
    meta.get("tool_contract")
        .and_then(|v| v.get("machine_json"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
}

/// 在 argv 中插入 `--result-file <path>`：若首参为脚本入口（`*.py` / `*.ts` 等）则插在脚本名之后，与各工具 CLI 全局参数顺序一致；否则插在开头。
fn insert_result_file_args(args: &mut Vec<String>, result_path: &str) {
    let pos = if args
        .first()
        .map(|s| {
            s.contains("main.py")
                || s.ends_with(".py")
                || s.ends_with(".ts")
                || s.ends_with(".tsx")
        })
        .unwrap_or(false)
    {
        1
    } else {
        0
    };
    args.insert(pos, result_path.to_string());
    args.insert(pos, "--result-file".to_string());
}

fn append_machine_json_arg(args: &mut Vec<String>) {
    if !args.iter().any(|a| a == "--machine-json") {
        args.push("--machine-json".to_string());
    }
}

/// 解析 `hapray-tool-result.json`（v1），优先取 `outputs.reports_path` 作为打开报告目录的依据。
#[derive(Debug)]
struct ParsedHaprayToolResult {
    success: bool,
    reports_path: Option<String>,
}

fn parse_hapray_tool_result(path: &Path) -> Option<ParsedHaprayToolResult> {
    let content = std::fs::read_to_string(path).ok()?;
    let v: serde_json::Value = serde_json::from_str(&content).ok()?;
    let exit_code = v
        .get("exit_code")
        .and_then(|x| x.as_i64())
        .or_else(|| v.get("exit_code").and_then(|x| x.as_u64()).map(|u| u as i64))
        .unwrap_or(-1);
    let success_flag = v.get("success").and_then(|x| x.as_bool());
    let success = success_flag.unwrap_or(exit_code == 0);

    let mut reports_path = v
        .get("outputs")
        .and_then(|o| o.get("reports_path"))
        .and_then(|x| x.as_str())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());

    if reports_path.is_none() {
        if let Some(o) = v.get("outputs").and_then(|x| x.as_object()) {
            for key in ["output_dir", "output"] {
                if let Some(s) = o.get(key).and_then(|x| x.as_str()) {
                    if !s.is_empty() {
                        reports_path = Some(s.to_string());
                        break;
                    }
                }
            }
            if reports_path.is_none() {
                if let Some(arr) = o.get("report_files").and_then(|x| x.as_array()) {
                    if let Some(first) = arr.first().and_then(|x| x.as_str()) {
                        let p = Path::new(first);
                        if let Some(parent) = p.parent() {
                            if !parent.as_os_str().is_empty() {
                                reports_path = Some(parent.to_string_lossy().to_string());
                            }
                        }
                    }
                }
            }
        }
    }

    Some(ParsedHaprayToolResult {
        success,
        reports_path,
    })
}

/// 保存执行记录（参考 result_processor.py）
fn save_execution_record(
    app: &tauri::AppHandle,
    plugin_id: &str,
    action: &str,
    timestamp: &str,
    success: bool,
    message: &str,
    params: &HashMap<String, serde_json::Value>,
    meta: &serde_json::Value,
    command: &str,
    output_path: Option<&str>,
    hapray_tool_result_path: Option<&str>,
    output: &str,
) {
    let results_dir = match get_results_dir(app) {
        Ok(d) => d,
        Err(_) => return,
    };
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

    let result_dir = results_dir.join(plugin_id).join(timestamp);
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
        "hapray_tool_result_path": hapray_tool_result_path,
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

    let timestamp = Utc::now().format("%Y%m%d_%H%M%S").to_string();
    let mut run_args = prepared.args.clone();
    let mut contract_file_opt: Option<PathBuf> = None;

    if tool_contract_enabled(&prepared.meta) {
        if let Ok(base) = get_results_dir(&app) {
            let contract_dir = base.join(&payload.plugin_id).join(&timestamp);
            if let Err(e) = std::fs::create_dir_all(&contract_dir) {
                eprintln!("[tool_contract] 创建契约目录失败: {}", e);
            } else {
                let basename = tool_contract_result_basename(&prepared.meta);
                let path = contract_dir.join(&basename);
                let path_str = path.to_string_lossy().to_string();
                insert_result_file_args(&mut run_args, &path_str);
                if tool_contract_machine_json(&prepared.meta) {
                    append_machine_json_arg(&mut run_args);
                }
                contract_file_opt = Some(path);
            }
        }
    }

    let exe_path_str = prepared.exe_path.to_string_lossy();
    let args_str: Vec<String> = run_args
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
        .args(&run_args)
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

    let hapray_path_str = contract_file_opt
        .as_ref()
        .map(|p| p.to_string_lossy().to_string());

    let parsed_from_contract = contract_file_opt
        .as_ref()
        .and_then(|p| parse_hapray_tool_result(p));

    let success = parsed_from_contract
        .as_ref()
        .map(|p| p.success)
        .unwrap_or_else(|| status.success());

    let message = if success {
        "执行成功".to_string()
    } else {
        "执行失败".to_string()
    };

    // 优先：hapray-tool-result.json 的 outputs.reports_path；其次日志启发式；最后表单参数。
    let output_path = parsed_from_contract
        .as_ref()
        .and_then(|p| p.reports_path.clone())
        .or_else(|| extract_output_path_from_log_first(&payload.action, &output_log, work_dir.as_path()))
        .or_else(|| extract_output_path_from_params(&payload.action, &params_for_history, work_dir.as_path()));

    save_execution_record(
        &app,
        &payload.plugin_id,
        &payload.action,
        &timestamp,
        success,
        &message,
        &payload.params,
        &prepared.meta,
        &full_cmd,
        output_path.as_deref(),
        hapray_path_str.as_deref(),
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

fn hdc_bundled_candidates() -> Vec<PathBuf> {
    let name = if cfg!(windows) { "hdc.exe" } else { "hdc" };
    let mut v = Vec::new();

    #[cfg(debug_assertions)]
    {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        if let Some(workspace) = manifest.parent().and_then(|p| p.parent()) {
            v.push(workspace.join("dist").join("tools").join("bin").join(name));
        }
        if let Some(desktop) = manifest.parent() {
            v.push(desktop.join("dist").join("tools").join("bin").join(name));
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        let exe = exe.canonicalize().unwrap_or(exe);
        if let Some(parent) = exe.parent() {
            #[cfg(target_os = "macos")]
            if let Some(contents) = parent.parent() {
                v.push(
                    contents
                        .join("Resources")
                        .join("tools")
                        .join("bin")
                        .join(name),
                );
            }
            #[cfg(not(target_os = "macos"))]
            v.push(parent.join("tools").join("bin").join(name));
            v.extend([
                parent.join("../Resources/tools/bin").join(name),
                parent.join("../../dist/tools/bin").join(name),
                parent.join("../../../tools/bin").join(name),
            ]);
            #[cfg(target_os = "macos")]
            v.push(parent.join("tools").join("bin").join(name));
        }
    }

    v
}

/// 解析 hdc 可执行文件路径。注意：**从启动台打开的 GUI 不会读取 ~/.zshrc**，在 .zshrc 里改 PATH 对 App 无效。
/// 顺序：`HAPRAY_HDC_PATH` → PATH（`which hdc`）→ 打包目录 `tools/bin/hdc` → 常见 SDK 路径 → 命令名 `hdc`。
/// 对绝对路径设置 cwd 为可执行文件所在目录，便于加载同目录下 `libusb_shared` 等动态库。
fn resolve_hdc_executable() -> PathBuf {
    let mut tried: Vec<String> = Vec::new();

    if let Ok(p) = std::env::var("HAPRAY_HDC_PATH") {
        let pb = PathBuf::from(p.trim());
        if pb.is_file() {
            return pb;
        }
        tried.push(format!(
            "HAPRAY_HDC_PATH={:?}（存在且为文件: 否）",
            p.trim()
        ));
    }

    match which::which("hdc") {
        Ok(p) => return p,
        Err(e) => tried.push(format!("which hdc: {}", e)),
    }

    for cand in hdc_bundled_candidates() {
        if cand.is_file() {
            return cand;
        }
        tried.push(format!("打包/相对路径: {:?}", cand));
    }

    let mut sdk_candidates: Vec<PathBuf> = Vec::new();
    if let Ok(home) = std::env::var("HOME") {
        sdk_candidates.push(
            Path::new(&home).join("code/command-line-tools/sdk/default/openharmony/toolchains/hdc"),
        );
    }
    #[cfg(target_os = "macos")]
    {
        // DevEco Studio 自带 OpenHarmony SDK（用户常在 .zshrc 里加此目录的 PATH，但 GUI 读不到）
        sdk_candidates.push(PathBuf::from(
            "/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc",
        ));
    }
    #[cfg(windows)]
    if let Ok(profile) = std::env::var("USERPROFILE") {
        sdk_candidates.push(
            Path::new(&profile).join("code/command-line-tools/sdk/default/openharmony/toolchains/hdc"),
        );
    }
    for cand in sdk_candidates {
        if cand.is_file() {
            return cand;
        }
        tried.push(format!("SDK 常见路径: {:?}", cand));
    }

    eprintln!(
        "[hdc] resolve: 未在固定位置找到可执行文件，将使用命令名 \"hdc\"（依赖运行时 PATH）。已检查: {}",
        tried.join(" | ")
    );
    PathBuf::from("hdc")
}

/// 与 hdc 可执行文件同目录的 PATH/cwd，便于加载 libusb 等。
fn hdc_command_with_env() -> (PathBuf, Command) {
    let hdc_path = resolve_hdc_executable();
    let mut cmd = Command::new(&hdc_path);
    #[cfg(windows)]
    {
        cmd.creation_flags(0x08000000);
    }
    if hdc_path.is_absolute() {
        if let Some(toolchains) = hdc_path.parent() {
            cmd.current_dir(toolchains);
            let path = std::env::var("PATH").unwrap_or_default();
            #[cfg(windows)]
            {
                cmd.env("PATH", format!("{};{}", toolchains.display(), path));
            }
            #[cfg(not(windows))]
            {
                cmd.env("PATH", format!("{}:{}", toolchains.display(), path));
            }
        }
    }
    (hdc_path, cmd)
}

/// 从 `bm dump -a` 输出中提取 Bundle 包名（兼容「每行一个包名」与「bundleName:/bundle name:」等键值格式）。
fn parse_bundle_names_from_bm_dump(stdout: &str) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();

    static RE_KV: OnceLock<Regex> = OnceLock::new();
    let re_kv = RE_KV.get_or_init(|| {
        Regex::new(
            r#"(?i)(?:bundle\s*name|bundleName)\s*[:：=]\s*"?([a-zA-Z][a-zA-Z0-9_.]*(?:\.[a-zA-Z0-9_]+)+)"?"#,
        )
        .expect("bundle kv regex")
    });
    for cap in re_kv.captures_iter(stdout) {
        if let Some(m) = cap.get(1) {
            let s = m.as_str();
            if seen.insert(s.to_string()) {
                out.push(s.to_string());
            }
        }
    }

    static RE_JSON: OnceLock<Regex> = OnceLock::new();
    let re_json = RE_JSON.get_or_init(|| {
        Regex::new(r#""bundleName"\s*:\s*"([^"]+)""#).expect("bundle json regex")
    });
    for cap in re_json.captures_iter(stdout) {
        if let Some(m) = cap.get(1) {
            let s = m.as_str();
            if s.contains('.') && seen.insert(s.to_string()) {
                out.push(s.to_string());
            }
        }
    }

    for raw_line in stdout.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') || line.starts_with('[') {
            continue;
        }
        if !line.contains('.') {
            continue;
        }
        if line.chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '.' || c == '_')
        {
            if seen.insert(line.to_string()) {
                out.push(line.to_string());
            }
        }
    }

    out.sort();
    out.dedup();
    out
}

fn get_installed_apps() -> Result<Vec<String>, String> {
    let (hdc_path, mut cmd) = hdc_command_with_env();
    cmd.args(["shell", "bm", "dump", "-a"]);
    let output = cmd.output().map_err(|e| {
        eprintln!(
            "[hdc] spawn 失败: path={:?}, kind={:?}, error={}",
            hdc_path,
            e.kind(),
            e
        );
        if e.kind() == std::io::ErrorKind::NotFound {
            format!(
                "hdc 未找到或无法执行（已尝试 {:?}）。可设置环境变量 HAPRAY_HDC_PATH 指向 hdc 绝对路径，或把 toolchains 目录加入系统 PATH。",
                hdc_path
            )
        } else {
            format!("执行 hdc 失败: {}", e)
        }
    })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        eprintln!(
            "[hdc] shell bm dump -a 非零退出: exit={:?}, stderr_len={}, stdout_len={}",
            output.status.code(),
            stderr.len(),
            stdout.len()
        );
        eprintln!("[hdc] stderr: {}", stderr.trim());
        if !stdout.trim().is_empty() {
            eprintln!("[hdc] stdout: {}", stdout.trim());
        }
        return Err(format!(
            "hdc shell bm dump -a 失败 (exit {:?})。stderr: {}。stdout: {}",
            output.status.code(),
            stderr.trim(),
            stdout.trim()
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let bundle_names = parse_bundle_names_from_bm_dump(&stdout);

    if bundle_names.is_empty() {
        let preview: String = stdout.chars().take(2048).collect();
        if preview.trim().is_empty() {
            eprintln!(
                "[hdc] bm dump -a stdout 为空（exit 0）。请确认 `hdc list targets` 能列出设备。"
            );
        } else {
            eprintln!(
                "[hdc] bm dump -a 解析到 0 个包名。stdout 前 2048 字符:\n{}",
                preview
            );
        }
        let mut t = hdc_command_with_env().1;
        t.args(["list", "targets"]);
        if let Ok(tout) = t.output() {
            let ts = String::from_utf8_lossy(&tout.stdout);
            let te = String::from_utf8_lossy(&tout.stderr);
            eprintln!(
                "[hdc] list targets: exit={:?} stdout={} stderr={}",
                tout.status.code(),
                ts.trim(),
                te.trim()
            );
        }
    }

    let mut apps = Vec::new();
    for line in bundle_names {
        let category = if line.starts_with("com.huawei.") {
            "system"
        } else {
            "third"
        };
        apps.push(format!("{}::{}", category, line));
    }
    apps.sort();
    apps.dedup();
    Ok(apps)
}
