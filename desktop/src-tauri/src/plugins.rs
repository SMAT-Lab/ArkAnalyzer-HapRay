//! 插件加载 - 读取 plugin.json 并构建菜单结构

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tauri::Manager;

// -----------------------------------------------------------------------------
// 常量
// -----------------------------------------------------------------------------

const DEFAULT_ORDER: i32 = 999;
const DEFAULT_ICON: &str = "⚙️";
const PLUGIN_JSON: &str = "plugin.json";

/// 顶层菜单配置: (显示名, 图标, 排序)
const TOP_MENUS: &[(&str, &str, i32)] = &[
    ("负载测试", "📊", 1),
    ("应用分析", "🔍", 2),
];

/// 根据 plugin_id 解析插件目录（支持目录名与 id 不一致，如 opt-detector 目录下 plugin.json 的 id 为 optimization_detector）
pub fn resolve_plugin_dir(plugins_dir: &Path, plugin_id: &str) -> Option<PathBuf> {
    let direct = plugins_dir.join(plugin_id).join(PLUGIN_JSON);
    if direct.exists() {
        return Some(plugins_dir.join(plugin_id));
    }
    let entries = std::fs::read_dir(plugins_dir).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let plugin_json = path.join(PLUGIN_JSON);
        if !plugin_json.exists() {
            continue;
        }
        let content = std::fs::read_to_string(&plugin_json).ok()?;
        let meta: serde_json::Value = serde_json::from_str(&content).ok()?;
        let json_id = meta.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let dir_name = path.file_name().map(|n| n.to_string_lossy()).unwrap_or_default();
        // 与 load_plugins_with_log 一致：JSON 的 id 为空时用目录名作为 id
        if json_id == plugin_id || (json_id.is_empty() && dir_name == plugin_id) {
            return Some(path);
        }
    }
    None
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginMetadata {
    pub id: String,
    pub name: String,
    pub description: String,
    pub version: String,
    #[serde(default)]
    pub actions: HashMap<String, ActionConfig>,
    #[serde(default)]
    pub config: ConfigSchema,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionConfig {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub menu: MenuConfig,
    #[serde(default)]
    pub parameters: IndexMap<String, ParameterDef>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MenuConfig {
    pub menu1: Option<String>,
    pub menu2: Option<String>,
    #[serde(default = "default_order")]
    pub order: i32,
    #[serde(default = "default_icon")]
    pub icon: String,
}

fn default_order() -> i32 {
    DEFAULT_ORDER
}
fn default_icon() -> String {
    DEFAULT_ICON.to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParameterDef {
    #[serde(rename = "type", default)]
    pub param_type: String,
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub required: bool,
    #[serde(default)]
    pub default: Option<serde_json::Value>,
    #[serde(default)]
    pub choices: Option<serde_json::Value>,
    #[serde(default)]
    pub multi_select: bool,
    #[serde(default)]
    pub help: String,
    #[serde(default)]
    pub short: Option<String>,
    #[serde(default)]
    pub nargs: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ConfigSchema {
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub items: IndexMap<String, ConfigItemDef>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigItemDef {
    #[serde(rename = "type", default)]
    pub item_type: String,
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub default: Option<serde_json::Value>,
    #[serde(default)]
    pub help: String,
    #[serde(default)]
    pub choices: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MenuItem {
    pub plugin_id: String,
    pub action: String,
    pub display_name: String,
    pub icon: String,
    pub order: i32,
    pub menu_category: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidebarMenu {
    pub category: String,
    pub icon: String,
    pub order: i32,
    pub items: Vec<MenuItem>,
}

/// 返回插件目录的候选路径（按优先级），用于查找与错误诊断
fn plugins_dir_candidates(app_handle: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    #[cfg(debug_assertions)]
    {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        if let Some(workspace) = manifest.parent().and_then(|p| p.parent()) {
            candidates.push(workspace.join("dist").join("tools"));
            candidates.push(workspace.join("tools"));
        }
        if let Some(desktop) = manifest.parent() {
            candidates.push(desktop.join("dist").join("tools"));
        }
    }

    if let Ok(resource_dir) = app_handle.path().resource_dir() {
        candidates.push(resource_dir.join("tools"));
        if let Some(parent) = resource_dir.parent() {
            candidates.push(parent.join("tools"));
            if let Some(gp) = parent.parent() {
                candidates.push(gp.join("tools"));
            }
        }
    }

    #[cfg(target_os = "macos")]
    if let Ok(exe) = std::env::current_exe() {
        if let Some(contents) = exe.parent().and_then(|p| p.parent()) {
            candidates.push(contents.join("Resources").join("tools"));
        }
    }

    candidates
}

/// 尝试的路径列表，用于错误诊断
pub(crate) fn get_plugins_dir_tried_paths(app_handle: &tauri::AppHandle) -> Vec<String> {
    plugins_dir_candidates(app_handle)
        .into_iter()
        .map(|p| p.display().to_string())
        .collect()
}

pub fn get_plugins_dir(app_handle: &tauri::AppHandle) -> Option<PathBuf> {
    plugins_dir_candidates(app_handle)
        .into_iter()
        .find(|p| p.exists())
    }

/// 加载插件并返回加载日志，用于诊断加载失败原因
pub fn load_plugins_with_log(plugins_dir: &PathBuf) -> (Vec<PluginMetadata>, Vec<String>) {
    let mut plugins = Vec::new();
    let mut log = Vec::new();

    log.push(format!("[INFO] 插件目录: {}", plugins_dir.display()));

    let entries = match std::fs::read_dir(plugins_dir) {
        Ok(e) => e,
        Err(e) => {
            log.push(format!("[ERROR] 读取目录失败: {}", e));
            return (plugins, log);
        }
    };

    for entry in entries.flatten() {
        let path = entry.path();
        let dir_name = path.file_name().unwrap().to_string_lossy().to_string();

        if !path.is_dir() {
            log.push(format!("[SKIP] {}: 非目录", dir_name));
            continue;
        }

        let plugin_json = path.join(PLUGIN_JSON);
        if !plugin_json.exists() {
            log.push(format!("[SKIP] {}: 缺少 plugin.json", dir_name));
            continue;
        }

        let content = match std::fs::read_to_string(&plugin_json) {
            Ok(c) => c,
            Err(e) => {
                log.push(format!("[ERROR] {}: 读取 plugin.json 失败: {}", dir_name, e));
                continue;
            }
        };

        let mut meta: PluginMetadata = match serde_json::from_str(&content) {
            Ok(m) => m,
            Err(e) => {
                log.push(format!("[ERROR] {}: 解析 plugin.json 失败: {}", dir_name, e));
                continue;
            }
        };

        if meta.id.is_empty() {
            meta.id = dir_name.clone();
        }
        let before = meta.actions.len();
        meta.actions.retain(|_, a| a.menu.menu1.is_some());
        let after = meta.actions.len();
        let config_count = meta.config.items.len();
        plugins.push(meta);
        log.push(format!(
            "[OK] {}: 已加载, actions={}->{} (有menu1), config.items={}",
            dir_name, before, after, config_count
        ));
    }

    log.push(format!("[INFO] 共加载 {} 个插件", plugins.len()));
    (plugins, log)
}

pub fn build_sidebar_menu(plugins: &[PluginMetadata]) -> Vec<SidebarMenu> {
    let top_menus: HashMap<String, (String, i32)> = TOP_MENUS
        .iter()
        .map(|(name, icon, order)| ((*name).to_string(), ((*icon).to_string(), *order)))
        .collect();

    let mut menu_actions: HashMap<String, Vec<MenuItem>> = HashMap::new();

    for plugin in plugins {
        for (action_key, action_config) in &plugin.actions {
            let Some(menu1) = &action_config.menu.menu1 else {
                continue;
            };
            if !top_menus.contains_key(menu1) {
                continue;
            }

            let display_name = action_config
                .menu
                .menu2
                .as_deref()
                .unwrap_or(&action_config.name);

            let item = MenuItem {
                plugin_id: plugin.id.clone(),
                action: action_key.clone(),
                display_name: display_name.to_string(),
                icon: action_config.menu.icon.clone(),
                order: action_config.menu.order,
                menu_category: menu1.clone(),
            };

            menu_actions
                .entry(menu1.clone())
                .or_default()
                .push(item);
        }
    }

    let mut result = Vec::new();
    for (name, (icon, order)) in top_menus {
        let mut items = menu_actions.remove(&name).unwrap_or_default();
        items.sort_by_key(|i| i.order);
        result.push(SidebarMenu {
            category: name,
            icon,
            order,
            items,
        });
    }
    result.sort_by_key(|m| m.order);
    result
}
