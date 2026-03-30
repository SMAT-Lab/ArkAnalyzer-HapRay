# `hapray-tool-result.json` 字段说明（tool-result v1）

**规范来源**：克隆仓库内 JSON Schema — [`docs/schemas/hapray-tool-result-v1.json`](../../docs/schemas/hapray-tool-result-v1.json)（本文件位于 `skills/hapray/`，上两级为仓库根）。

若仅复制 `~/.cursor/skills/hapray/` 而无整仓，请以 **线上/本机克隆的 ArkAnalyzer-HapRay** 中的同名 Schema 为准；完整契约与分工具说明见 [`docs/工具契约式输入输出方案.md`](../../docs/工具契约式输入输出方案.md)。

---

## 顶层字段（与 Schema 一致）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | 固定 **`"1.0"`** |
| `tool_id` | string | 是 | **`perf_testing`** \| **`optimization_detector`** \| **`static_analyzer`** \| **`symbol_recovery`** |
| `tool_version` | string | 否 | 工具版本号 |
| `action` | string | 否 | 子命令或动作名（如 `perf`、`static`、`hap`、`gui-agent`） |
| `success` | boolean \| null | 是 | 是否成功；`false` 失败；`null` 表示未归约为布尔（如部分历史行为） |
| `exit_code` | integer | 是 | 与进程退出码一致，`0` 通常表示成功 |
| `outputs` | object | 是 | 扩展字段，见下节 |
| `error` | string \| null | 是 | 失败时短信息；成功时多为 `null` |

Schema 允许 **`additionalProperties`**，实际载荷可能含扩展字段；Agent 解析时应 **以 Schema + 各工具文档** 为准。

---

## `outputs` 常用键（契约层）

| 键 | 说明 |
|----|------|
| **`hapray_tool_result_path`** | 本契约 JSON 文件的绝对路径（写入前即写入 `outputs`） |
| **`hapray_tool_result_sink`** | 若为 **`"stdout"`**，表示契约通过 **stdout 一行 JSON** 输出（`--machine-json` 兜底） |
| **`reports_path`** | （常见）业务报告根目录或主产物路径；`perf_testing` 等会写入 |
| **`report_files`** / **`reports_by_format`** 等 | **optimization_detector** 等对 `-o`/`-f` 多格式产物的索引，见 `docs/工具契约式输入输出方案.md` 分工具章节 |
| **`gui_agent`** 等 | **gui-agent** 成功时可能由 `enrich_gui_agent_contract_outputs` 合并的轻量摘要字段 |

**落盘优先级**（系统级）：优先 **`--result-file <path>`**；否则按各工具约定在输出目录旁写入 **`hapray-tool-result.json`**；无法再写盘时用 **`--machine-json`** 走 stdout。详见契约文档 §3。

---

## Agent 使用建议

1. 调用 CLI 时附加 **`--result-file /绝对路径/hapray-tool-result.json`**（或与业务输出同目录的可写路径）。  
2. 执行成功后 **读取该 JSON**，优先取 **`outputs.reports_path`**（若存在）定位 HTML/目录；再结合业务报告。  
3. 失败时检查 **`success`**、**`exit_code`**、**`error`**，勿仅解析人类可读日志。

---

## 与主 Skill 的关系

主文件 [`SKILL.md`](SKILL.md) §5「执行与机器可读结果」指向本说明与仓库 **`docs/`**；字段细节以 **Schema + `docs/工具契约式输入输出方案.md`** 为单一技术来源，本文作 Skill 内 **速查**。
