# 全面根因分析（阶段 5，独立 · 脱离 update）

适用场景：阶段4 high-load 完成后，对**所有**已挖出的高负载问题做**源码级根因定位**——**不限空刷**。本阶段**脱离 `update`**：空刷走**独立 `root-cause` CLI**（`run_empty_frame_analysis`，实现于 `perf_testing/hapray/analyze/llm_root_cause/`）；其余高负载问题（SO/符号热点、高负载帧、冗余线程、IPC、内存等）由 **Agent** 结合阶段4发现 + 源码逐类定位。两者融合进阶段6报告。

> **阶段3 符号恢复**：SO 路径与符号级热点见 [`../workflow/gen-perf-report.md`](../workflow/gen-perf-report.md)（可选）。**本阶段为全面 root-cause 权威来源**。

> **Agent 必读**：若空刷 CLI 产出 `root_cause_agent_task.json` 且报告含 "Pending Agent Inference"，当前对话 Agent **必须**读取任务 JSON、按 `expected_schema_json` 写 `root_cause_agent_result.json`，再重跑 `root-cause`，禁止只读 tasks 就结束。

---

## 〇、两条腿：空刷 CLI + Agent 全面根因

| 腿 | 覆盖 | 驱动 | 产出 |
|----|------|------|------|
| **A 空刷专项** | empty frame（空刷帧） | 独立 `root-cause` CLI（默认 Agent 编排） | `root_cause.md` / `root_cause_evidence.md` |
| **B 全面根因** | SO/符号热点、高负载帧、冗余线程、IPC、内存、组件复用等**非空刷**问题 | **当前 Agent**（读阶段4发现 + 源码 + perf 产物） | 直接写入阶段6报告的「根因分析」章节 |

**A 与 B 合并**：A 的 Top Suspects 作为空刷类根因；B 覆盖其余高负载维度。二者按 P0/P1/P2/P3 统一排序，融合进 [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md) 第三章三段式（HapRay 证据 + 源码根因 + 修复建议）。

### 〇.0 独立 CLI 用法（A 空刷专项，脱离 update）

```bash
cd perf_testing
# with_source（推荐，需 §0 源码路径）：LLM/Agent 读源码给行级修复
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --source-dir "<§0_源码>" \
  [--index-dir "<§0_源码>/index"]

# 仅证据（不调 LLM）：root_cause.md == root_cause_evidence.md
uv run python -m scripts.main root-cause --report-dir <用例>/report --skip-llm
```

- `--report-dir` **须指向含 `trace_emptyFrame.json` 的目录**（一般为 `<用例>/report`）。
- 默认 **Agent 编排**（导出 `root_cause_agent_task.json` → Agent 写 `root_cause_agent_result.json` → 重跑）。本地直连 API 需 `HAPRAY_ROOT_CAUSE_EXECUTION=api` + `LLM_*`（兼容路径，非默认）。
- **无需 `update`**：本命令独立运行，仅消费 perf 已产出的 `report/`。

### 〇.0.1 B 全面根因：Agent 逐类定位（不限空刷）

对阶段4 high-load 输出的每一类热点，Agent 借 §0 源码做源码级定位，作为独立根因条目：

| 高负载维度（来自阶段4） | 根因定位方式 |
|------------------------|--------------|
| SO / 符号级热点（`perf_sample` Top） | 热点符号 → 源码函数/调用链；第三方库则定位调用点与频次 |
| 高负载帧（`frame_slice` / `trace_frames`） | 帧时间窗内的触发组件/回调 → 源码 `build()` / 生命周期 |
| 冗余线程（`redundant_thread_analysis.json`） | 线程名 → 源码线程池/Worker 创建点 |
| IPC Binder（`trace_ipc_binder.json`） | 高频事务调用方 → 源码 IPC 调用点 |
| 内存（`memory_report.xlsx`） | 超额分配 → 源码分配热点 |
| 组件复用（`trace_componentReuse.json`） | 低复用率组件 → 源码 LazyForEach/复用配置 |

**禁止**：无源码依据的臆造行号；把阶段4未挖出的问题硬写成根因；只复述空刷 CLI 而不覆盖其余维度。

---

## 一、与 `update` 集成（旧路径，可选）

> 以下为 `update` **集成调用** root-cause 的旧行为，**非默认**。默认走 §〇.0 独立 CLI。若用户已在跑符号恢复 `update` 且同时要空刷根因，可启用本路径（`update` 内部调用 `run_root_cause_for_case`）。

`perf` → **`update`** 时（`update_action.py` + `root_cause_integration.py`），存在 `trace_emptyFrame.json` 时**默认**尝试 root-cause。

**门禁**：路径索取与主 Skill [`../SKILL.md`](../SKILL.md) **§0 必问模板** 相同（源码路径 → SO 路径 → 汇总确认）；禁止未询问就跑 CLI。勿在本子 Skill 内单独问 root-cause 而跳过 SO。

### 〇.1 输入路径（`--app-packages-dir`）

**自动识别**（`input_kind`）：

| 识别结果 | 目录特征 | 行为 |
|----------|----------|------|
| **源码** (`source`) | 含 `*.ts`/`*.ets`、`symbol_index.jsonl`，或 `src/main/ets`、`source-analysis/` | **with_source**；使用用户源码树 |
| **无可用源码** | 未提供、路径无效，或目录不具备可分析源码树 | **跳过** root-cause，或 **analyze**（仅报告证据、无行级代码）；提示用户补 §0 源码路径后重跑 |

**优先级**：

1. **用户路径**：`--app-packages-dir` 或 `HAPRAY_APP_PACKAGES_DIR` → 按上表识别  
2. **报告内已有**：`.app_packages/<包名>/source-analysis/`（须为用户事先准备的源码/索引）

索引：用户源码树下 `index/` 或 `.app_packages/<包名>/source-analysis/index/`；有有效 `symbol_index.jsonl` 时自动 **with_source**。

**开关**：

| 意图 | 参数 / 环境变量 |
|------|-----------------|
| 跳过 root-cause | `update --no-root-cause` 或 `HAPRAY_UPDATE_NO_ROOT_CAUSE=1` |
| 仅证据、不推断 | `update --root-cause-skip-llm`（等同 `root-cause --skip-llm`） |
| 无有效输入 | 自动跳过（等价 `--no-root-cause`，无需手改） |

### 〇.2 集成流水线

| 阶段 | 行为 |
|------|------|
| 输入准备 | 用户 §0 本地 `--app-packages-dir`；无有效源码则见 〇.1 |
| 符号恢复 | 需用户 §0 本地 `--so_dir`；无 SO 则跳过（与 root-cause 独立，见阶段 3 文档） |
| root-cause | 有源码树 → **with_source**；无源码 → **跳过** 或 **analyze**；读 `<用例>/report/`；默认 **Agent** |
| 总报告 | `hapray_report.json` → `more.root_cause`；`hapray_report.html` 嵌入根因面板 |

**update 示例**：

```bash
uv run python -m scripts.main update \
  --report_dir ./reports/<timestamp> \
  --so_dir "D:/local/libs/arm64" \
  --app-packages-dir "D:/local/app_source"
```

### 〇.3 验收与 Agent 闭环

| 检查项 | 通过条件 |
|--------|----------|
| `root_cause.md` | 存在，且非 “Pending Agent Inference” 占位 |
| 输入材料（with_source） | 用户源码路径或 `.app_packages/<包名>/source-analysis/index/symbol_index.jsonl` |
| 总报告 | `hapray_report.html` 含 `hapray-root-cause-panel` 或 JSON 含 `more.root_cause` |
| Agent 任务 | 若存在 `root_cause_agent_task.json` → 写 `root_cause_agent_result.json` → 重跑独立 `root-cause`（或集成 `update`） |
| 阶段 6 交付 | `root_cause.md` 验收通过后，Agent **MUST Read** 并将空刷 Top Suspects **融合**进 [`report/analysis-deliverable.md`](../report/analysis-deliverable.md) 第三章（与 B 全面根因统一排序，非机械全文复制） |

---

## 一、端到端流程

```
用户 §0 源码路径（*.ts / index/，由用户事先准备）
    │
    ▼
[可选] build-index（仅当已有 *.ts 树且尚无 index/）
    │
    ╔══════════════════════════════════════════════════════════════╗
    ║          每次分析（在线流程，hapray root-cause 驱动）        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  HapRay 报告目录（含 trace_emptyFrame.json 等）              ║
    ║    │                                                         ║
    ║    ▼  [步骤 1]  ContextBuilder                               ║
    ║    ▼  [步骤 2]  EmptyFrameEvidenceExtractor（纯事实）         ║
    ║    ▼  [步骤 3]  CodeIndexLookup（可选，需 --index-dir）      ║
    ║    ▼  [步骤 4]  代码片段 + 调用链（with_source，需源码目录）   ║
    ║    ▼  [步骤 5]  LLM / Agent 分析 → root_cause.md            ║
    ╚══════════════════════════════════════════════════════════════╝
```

---

## 二、核心模块

| 模块 | 文件 | 职责 | 主要输入 | 主要输出 |
|------|------|------|----------|----------|
| **入口** | `root_cause_action.py` | 串联全流程 | `--report-dir`、`--index-dir` | 触发各子模块 |
| **空刷证据提取** | `empty_frame_evidence.py` | 原始事实，不含推断 | `trace_emptyFrame.json`、`perf.db` 等 | /proc 命中 + 唤醒链 + UI 快照 |
| **代码索引关联** | `code_index_lookup.py` | 匹配嫌疑代码位置 | `symbol_index.jsonl` | `source_candidates`（行号元数据） |
| **代码片段提取** | `code_snippet_extractor.py` | 从用户源码 `.ts` 读行范围 | 源码目录、`source_candidates` | 代码片段 |
| **调用链追溯** | `callgraph_traverser.py` | 读 `.callgraph.json` | 用户源码目录 | 触发链路文本 |
| **索引构建** | `index_builder.py` | 扫描用户 `*.ts` 建索引 | 用户 §0 源码目录 | `symbol_index.jsonl` 等 |

---

## 三、LLM 分析模式

### analyze 模式（默认）

**适用：** 仅有 HapRay 报告，或 §0 **未提供**可用源码树。

**工作方式：** 规则引擎提取证据 → LLM 推断根因类别与修复方向（无行级代码引用）。

### with_source 模式（增强）

**适用：** §0 已提供含 `*.ts`/`*.ets` 的**源码路径**（及可选 `index/`）。

**工作方式：** 在 analyze 基础上读取嫌疑函数**源码片段**与调用链 → 行级修复建议。

**自动选择：** 检测到有效用户源码树 → **with_source**；否则 **跳过** 或 **analyze**。

---

## 四、关键数据流（三路证据汇聚）

```
trace_emptyFrame.json / element_tree / perf.db
    → EmptyFrameEvidenceExtractor（纯事实）
    → [with_source] CodeIndexLookup + 源码片段 + callgraph
    → LLM / Agent → root_cause.md
```

---

## 五、运行方式

### 前置：用户源码路径（§0）

1. 会话开头按主 Skill §0 索取 **源码路径**（与 SO 路径分步确认；均为**本地路径**，不从设备拉取）。  
2. 目录须含可分析 **ArkTS/ETS**（`*.ts`/`*.ets`）或已有 `symbol_index.jsonl` / `index/`。  
3. 无有效源码时 **跳过** root-cause 或 **analyze**，并建议用户补 §0 路径后重跑。

**可选**（用户已提供 `*.ts` 树且尚无 `index/`）：

```bash
cd perf_testing
python scripts/main.py build-index --input <用户§0_源码目录>
```

### Agent 编排 / LLM

默认 **Agent** 编排（`root_cause_agent_task.json` → Agent 写 `root_cause_agent_result.json` → 重跑）。本地 API 需 `HAPRAY_ROOT_CAUSE_EXECUTION=api` 及 `LLM_*` 环境变量（兼容路径，非默认）。

### 每次分析（`hapray root-cause` 或 update 已集成）

**`--report-dir` 须指向含 `trace_emptyFrame.json` 的目录**（一般为 `<用例>/report`）。

```bash
cd perf_testing

uv run python -m scripts.main update \
  --report_dir <report_dir> \
  --so_dir <本地_so目录> \
  --app-packages-dir <用户§0_源码目录>

# 仅证据
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --skip-llm

# with_source（须 §0 源码路径）
python scripts/main.py root-cause \
  --report-dir <用例>/report \
  --index-dir <源码目录或_report内source-analysis>/index \
  --source-dir <用户§0_源码目录>
```

**参数说明（节选）**：

| 参数 | 说明 |
|------|------|
| `--report-dir` | 含 `trace_emptyFrame.json` 的报告目录 |
| `--app-packages-dir` | update 集成时传入 §0 **源码路径** |
| `--index-dir` | 用户源码索引目录（`symbol_index.jsonl`） |
| `--source-dir` | §0 **用户源码目录** |
| `--skip-llm` | 仅规则引擎证据 |

### 输出

| 文件 | 说明 |
|------|------|
| `root_cause.md` | 主报告 |
| `root_cause_evidence.md` | 规则引擎证据（调试） |

---

## 六、输出报告结构

```markdown
# Root Cause Analysis Report
## Executive Summary
## Top Suspects
- **位置**: `文件名:行号`
- **修复建议**: （with_source 时引用用户源码片段）
## Caveats
```

---

## 七、核心输出文档

| 文档 | 位置 | 说明 |
|------|------|------|
| `root_cause.md` | `<report_dir>/` | 根因分析报告 |
| `root_cause_evidence.md` | `<report_dir>/` | 原始证据 |
| `symbol_index.jsonl` | `<index_dir>/` | 符号索引（来自用户源码树） |
| `*.callgraph.json` | 用户源码目录 | 调用图（若用户已提供） |
