# 全面根因分析（阶段 5，独立 · 多信号综合）

适用场景：阶段4 high-load 完成后，对**所有**已挖出的高负载问题做**根因定位**——涵盖空刷、CPU 热点、帧负载、线程、IPC、SO 负载、内存、组件复用等**全部信号**。本阶段**脱离 `update`**：走独立 `root-cause` CLI（默认 `--checker comprehensive`，多信号综合）；CLI 覆盖不到的源码级深挖由 Agent 补充。两者融合进阶段6报告。

> **阶段3 符号恢复**：SO 路径与符号级热点见 [`../workflow/gen-perf-report.md`](../workflow/gen-perf-report.md)（可选）。**本阶段为全面 root-cause 权威来源**。

> **Agent 必读**：若 CLI 产出 `root_cause_agent_task.json` 且报告含 "Pending Agent Inference"，当前对话 Agent **必须**读取任务 JSON、按 `expected_schema_json` 写 `root_cause_agent_result.json`，再重跑 `root-cause`，禁止只读 tasks 就结束。

---

## 〇、整体架构：CLI 自动分析 + Agent 补充深挖

本阶段由两个组件协同完成：

| 组件 | 覆盖 | 驱动 | 产出 |
|------|------|------|------|
| **CLI 自动分析** | 全部可用信号（空刷、CPU 热点、帧负载、冗余线程、IPC、SO 负载、内存、组件复用、帧率/UI/故障树等） | 独立 `root-cause` CLI（`run_comprehensive_analysis`，实现于 `perf_testing/hapray/analyze/llm_root_cause/`） | `root_cause.md` / `root_cause_evidence.md` |
| **Agent 补充深挖** | CLI 未覆盖的源码级细节；阶段4发现中需源码人工追查的问题 | **当前 Agent**（读阶段4发现 + 源码 + perf 产物） | 直接写入阶段6报告的「根因分析」章节 |

**合并规则**：CLI 的 `root_cause.md` 作为基线根因报告；Agent 对其中**未达源码级定位**的条目做补充深挖（读 .ets 源码、追查调用链、定位具体行号），补充内容融合进 [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md) 第三章三段式（HapRay 证据 + 源码根因 + 修复建议）。二者按 P0/P1/P2/P3 统一排序。

### 〇.1 CLI 自动分析（默认，覆盖全部信号）

```bash
cd perf_testing
# with_source（推荐，需 §0 源码路径）：LLM/Agent 读源码给行级修复
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --source-dir "<§0_源码>" \
  [--index-dir "<§0_源码>/index"]

# 仅证据（不调 LLM）：root_cause.md 为结构化摘要 + Pending Agent Inference 占位符
uv run python -m scripts.main root-cause --report-dir <用例>/report --skip-llm

# 精选信号类别
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --categories cpu-hotspot,empty-frame,thread

# 旧版仅空刷模式（不推荐，仅做兼容）
uv run python -m scripts.main root-cause --report-dir <用例>/report --checker empty-frame --skip-llm
```

- `--report-dir` **须指向含 `trace_*.json` / `perf.db` 等分析器产物的目录**（一般为 `<用例>/report`）。
- 默认 **Agent 编排**（导出 `root_cause_agent_task.json` → Agent 写 `root_cause_agent_result.json` → 重跑）。本地直连 API 需 `HAPRAY_ROOT_CAUSE_EXECUTION=api` + `LLM_*`（兼容路径，非默认）。
- **无需 `update`**：本命令独立运行，仅消费 perf 已产出的 `report/`。
- **`--checker comprehensive`**（默认）覆盖全部信号；`--checker empty-frame` 为旧版仅空刷模式。

#### 〇.1.1 CLI 信号覆盖

CLI 的 `run_comprehensive_analysis` 按以下信号类别自动提取证据并推理：

| 信号类别 | 产物来源 | 类型 | 说明 |
|----------|---------|------|------|
| `empty-frame` | `trace_emptyFrame.json` | suspect | 空刷帧证据（可选，缺失时跳过） |
| `cpu-hotspot` | `hiperf/step*/perf.db` | suspect | CPU 高负载热点，含 ArkTS 源码:行 |
| `frame-load` | `trace_frameLoads.json` | suspect | 高负载帧 |
| `component-reuse` | `trace_componentReuse.json` | suspect | 低复用率组件 |
| `thread` | `redundant_thread_analysis.json` | suspect | 冗余线程 |
| `ipc` | `trace_ipc_binder.json` | suspect | 高频 IPC/Binder 事务 |
| `so-load` | `so_file_load.json` | suspect | SO 文件负载分布 |
| `memory` | `hapray_report.db: memory_records` | suspect | 内存超额分配（未开 `--memory` 时不可用） |
| `frame-stats` | `trace_frames.json` 等 | observation | 帧率/RS跳帧/Vsync异常 |
| `ui-animate` | `ui_animate.json` | observation | 离树节点/超大图/动画 |
| `fault-hilog` | `trace_fault_tree.json` 等 | observation | 故障树 + hilog 命中 |

可用 `--categories` 筛选子集，如 `--categories cpu-hotspot,empty-frame,thread`。

### 〇.2 Agent 补充深挖（CLI 之后的源码级增强）

CLI 自动分析受限于 LLM prompt 窗口和证据提取粒度，对以下场景**无法自动完成源码级定位**，需 Agent 手动补充：

| 场景 | Agent 补充方式 |
|------|---------------|
| CLI 热点条目仅有符号名/组件名，无具体源码行 | 读 §0 源码，定位 `build()` / 生命周期 / 回调的具体行号 |
| 阶段4 high-load 发现的 SO/符号热点需调用链追查 | 读 `perf_callchain` + 源码，追查调用链至业务入口 |
| 冗余线程的线程池/Worker 创建点 | 源码中搜索线程创建代码 |
| IPC 高频事务的调用点 | 源码中搜索 IPC 调用 |
| 内存超额分配的分配热点 | 源码中搜索大对象/缓存分配 |
| 组件复用率低的 LazyForEach/复用配置 | 源码中搜索组件定义与复用配置 |

**禁止**：无源码依据的臆造行号；把阶段4未挖出的问题硬写成根因；只复述 CLI 报告而不覆盖其余维度。

**Agent 补充流程**：

1. Read `root_cause.md`（磁盘上的正式报告，禁止凭记忆缩写）
2. 对其中**未达源码级定位**（无 `文件:行号` 引用）的 suspect 条目，逐条到 §0 源码中追查
3. 对阶段4 high-load 挖出但 CLI 未覆盖的线索（如动静交叉发现），补充源码级定位
4. 补充结果直接写入阶段6交付报告的第三章，与 CLI 结论统一排序

---

## 一、与 `update` 集成（旧路径，可选）

> 以下为 `update` **集成调用** root-cause 的旧行为，**非默认**。默认走 §〇.1 独立 CLI。若用户已在跑符号恢复 `update` 且同时要根因分析，可启用本路径（`update` 内部调用 `run_root_cause_for_case`，已改为 `run_comprehensive_analysis`）。

`perf` → **`update`** 时（`update_action.py` + `root_cause_integration.py`），**默认**尝试 root-cause（多信号综合，不再仅空刷）。

**门禁**：路径索取与主 Skill [`../SKILL.md`](../SKILL.md) **§0 必问模板** 相同（源码路径 → SO 路径 → 汇总确认）；禁止未询问就跑 CLI。勿在本子 Skill 内单独问 root-cause 而跳过 SO。

### 一.1 输入路径（`--app-packages-dir`）

**自动识别**（`input_kind`）：

| 识别结果 | 目录特征 | 行为 |
|----------|----------|------|
| **源码** (`source`) | 含 `*.ts`/`*.ets`、`symbol_index.jsonl`，或 `src/main/ets`、`source-analysis/` | **with_source**；使用用户源码树 |
| **无可用源码** | 未提供、路径无效，或目录不具备可分析源码树 | **跳过** root-cause，或 **analyze**（仅报告证据、无行级代码）；提示用户补 §0 源码路径后重跑 |

**优先级**：

1. **用户 §0 源码路径**：`--app-packages-dir` 或 `HAPRAY_APP_PACKAGES_DIR` → 按上表识别
2. **报告内已有**：`.app_packages/<包名>/source-analysis/`（须为用户事先准备的源码/索引）

索引：用户源码树下 `index/` 或 `.app_packages/<包名>/source-analysis/index/`；有有效 `symbol_index.jsonl` 时自动 **with_source**。

**开关**：

| 意图 | 参数 / 环境变量 |
|------|-----------------|
| 跳过 root-cause | `update --no-root-cause` 或 `HAPRAY_UPDATE_NO_ROOT_CAUSE=1` |
| 仅证据、不推断 | `update --root-cause-skip-llm`（等同 `root-cause --skip-llm`） |
| 无有效输入 | 自动跳过（等价 `--no-root-cause`，无需手改） |

### 一.2 集成流水线

| 阶段 | 行为 |
|------|------|
| 输入准备 | 用户 §0 本地 `--app-packages-dir`；无有效源码则见 一.1 |
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

### 一.3 验收与 Agent 闭环

| 检查项 | 通过条件 |
|--------|----------|
| `root_cause.md` | 存在，且非 "Pending Agent Inference" 占位 |
| `root_cause_agent_task.json` | 若存在 → Agent **必须**处理，见 §〇 开头警告 |
| 输入材料（with_source） | 用户源码路径或 `.app_packages/<包名>/source-analysis/index/symbol_index.jsonl` |
| 总报告 | `hapray_report.html` 含 `hapray-root-cause-panel` 或 JSON 含 `more.root_cause` |
| 阶段 6 交付 | `root_cause.md` 验收通过后，Agent **MUST Read** 并将全部 suspect **融合**进 [`report/analysis-deliverable.md`](../report/analysis-deliverable.md) 第三章（与 Agent 补充深挖统一排序，非机械全文复制） |

---

## 二、端到端流程

```
用户 §0 源码路径（*.ts / index/，由用户事先准备）
    │
    ▼
[可选] build-index（仅当已有 *.ts 树且尚无 index/）
    │
    ╔══════════════════════════════════════════════════════════════╗
    ║          CLI 自动分析（root-cause，多信号综合）              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  HapRay 报告目录（含 trace_*.json / perf.db 等全部产物）     ║
    ║    │                                                         ║
    ║    ▼  [步骤 1]  ContextBuilder（性能上下文摘要）              ║
    ║    ▼  [步骤 2]  多信号 EvidenceExtractor（suspect+observation）║
    ║    ▼  [步骤 3]  CodeIndexLookup（可选，需 --index-dir）      ║
    ║    ▼  [步骤 4]  代码片段 + 调用链（with_source，需源码目录）   ║
    ║    ▼  [步骤 5]  LLM / Agent 分析 → root_cause.md            ║
    ╚══════════════════════════════════════════════════════════════╝
    │
    ▼
Agent 补充深挖（对 CLI 未达源码级的条目，读 §0 源码追查）
    │
    ▼
阶段6 交付（融合 CLI 报告 + Agent 补充）
```

---

## 三、核心模块

| 模块 | 文件 | 职责 | 主要输入 | 主要输出 |
|------|------|------|----------|----------|
| **入口** | `root_cause_action.py` | 串联全流程 | `--report-dir`、`--index-dir`、`--checker` | 触发各子模块 |
| **性能上下文** | `context_builder.py` | 压缩 JSON 为 LLM 上下文 | `summary.json` 等 | `AnalysisContext` |
| **空刷证据提取** | `empty_frame_evidence.py` | 空刷帧原始事实 | `trace_emptyFrame.json`、`perf.db` 等 | /proc 命中 + 唤醒链 + UI 快照 |
| **多信号提取** | `signal_extractors.py` | 各信号自动证据提取 | `trace_*.json`、`perf.db`、`so_file_load.json` 等 | 按 category 分段的 suspect/observation |
| **代码索引关联** | `code_index_lookup.py` | 匹配嫌疑代码位置 | `symbol_index.jsonl` | `source_candidates`（行号元数据） |
| **代码片段提取** | `code_snippet_extractor.py` | 从用户源码 `.ts` 读行范围 | 源码目录、`source_candidates` | 代码片段 |
| **调用链追溯** | `callgraph_traverser.py` | 读 `.callgraph.json` | 用户源码目录 | 触发链路文本 |
| **索引构建** | `index_builder.py` | 扫描用户 `*.ts` 建索引 | 用户 §0 源码目录 | `symbol_index.jsonl` 等 |

---

## 四、LLM 分析模式

### analyze 模式（默认）

**适用：** 仅有 HapRay 报告，或 §0 **未提供**可用源码树。

**工作方式：** 规则引擎提取证据 → LLM 推断根因类别与修复方向（无行级代码引用）。

### with_source 模式（增强）

**适用：** §0 已提供含 `*.ts`/`*.ets` 的**源码路径**（及可选 `index/`）。

**工作方式：** 在 analyze 基础上读取嫌疑函数**源码片段**与调用链 → 行级修复建议。

**自动选择：** 检测到有效用户源码树 → **with_source**；否则 **跳过** 或 **analyze**。

---

## 五、关键数据流

```
trace_*.json / perf.db / so_file_load.json / ...
    → 多信号 EvidenceExtractor（suspect + observation）
    → [with_source] CodeIndexLookup + 源码片段 + callgraph
    → LLM / Agent → root_cause.md
    → Agent 补充深挖 → 阶段6 交付报告
```

---

## 六、运行方式

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

### 每次分析（`hapray root-cause`）

**`--report-dir` 须指向含 `trace_*.json` / `perf.db` 等产物的目录**（一般为 `<用例>/report`）。

```bash
cd perf_testing

# 多信号综合分析（推荐，默认）
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --source-dir <用户§0_源码目录> \
  --index-dir <源码目录>/index

# 仅证据（不调 LLM）
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --skip-llm

# 精选信号类别
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --categories cpu-hotspot,empty-frame,thread

# 旧版仅空刷模式（不推荐）
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --checker empty-frame \
  --skip-llm

# update 集成
uv run python -m scripts.main update \
  --report_dir <report_dir> \
  --so_dir <本地_so目录> \
  --app-packages-dir <用户§0_源码目录>
```

**参数说明（节选）**：

| 参数 | 说明 |
|------|------|
| `--report-dir` | 含 `trace_*.json` / `perf.db` 等产物的报告目录 |
| `--checker` | `comprehensive`（默认，多信号综合）或 `empty-frame`（旧版仅空刷） |
| `--categories` | comprehensive 模式下精选信号类别（逗号分隔），不填则全部可用信号 |
| `--app-packages-dir` | update 集成时传入 §0 **源码路径** |
| `--index-dir` | 用户源码索引目录（`symbol_index.jsonl`） |
| `--source-dir` | §0 **用户源码目录** |
| `--skip-llm` | 仅规则引擎证据；root_cause.md 为结构化摘要 + Pending Agent Inference 占位符 |

### 输出

| 文件 | 说明 |
|------|------|
| `root_cause.md` | 主报告（含全部信号 suspect + observation 推断） |
| `root_cause_evidence.md` | 规则引擎证据（调试） |
| `root_cause_agent_task.json` | Agent 任务（仅 Agent 编排模式，Pending 时产出） |
| `root_cause_agent_result.json` | Agent 结果（需 Agent 写入后重跑 CLI 方可生效） |

---

## 七、输出报告结构

```markdown
# Root Cause Analysis Report
## Executive Summary
## Top Suspects
- **位置**: `文件名:行号`
- **信号类别**: cpu-hotspot / empty-frame / thread / ...
- **修复建议**: （with_source 时引用用户源码片段）
## Caveats
```

---

## 八、核心输出文档

| 文档 | 位置 | 说明 |
|------|------|------|
| `root_cause.md` | `<report_dir>/` | 根因分析报告（多信号综合） |
| `root_cause_evidence.md` | `<report_dir>/` | 原始证据 |
| `root_cause_agent_task.json` | `<report_dir>/` | Agent 任务（Agent 编排模式，Pending 时产出） |
| `root_cause_agent_result.json` | `<report_dir>/` | Agent 结果 |
| `symbol_index.jsonl` | `<index_dir>/` | 符号索引（来自用户源码树） |
| `*.callgraph.json` | 用户源码目录 | 调用图（若用户已提供） |

---

## 九、与阶段4的分工

| 维度 | 阶段4 analysis | 阶段5 root-cause |
|------|---------------|------------------|
| 目标 | 发现线索与假设 | 确认根因 + 源码级定位 |
| 手段 | Agent 手动 SQL 查询 + 数据探索 | CLI 自动多信号提取 + LLM/Agent 推断 |
| 产出 | 高负载热点表 + 新发现 | `root_cause.md` + Agent 源码级补充 |
| 关系 | 阶段5 CLI **独立提取**信号，不依赖阶段4产出 | Agent 可**引用**阶段4发现做源码追查，避免重复 |

**关键**：CLI 的 `signal_extractors` 会独立读取 `report/` 下的原始产物（与阶段4读同一数据源），Agent 不需要将阶段4的 SQL 结果传给 CLI。但 Agent 在做补充深挖时，**应优先引用阶段4已挖出的线索**，而非从零重做。
