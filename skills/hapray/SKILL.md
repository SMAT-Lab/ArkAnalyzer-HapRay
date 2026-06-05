---
name: hapray
version: "1.5.5"
description: |
  Guides OpenHarmony/HarmonyOS HapRay performance analysis in six stages:
  setup, perf-collect, high-load analysis (read report/), root-cause (standalone, full), deliverable.
  Symbol recovery (update) is an OPTIONAL branch, only when explicitly requested or hotspots are stripped.
  Use when the user mentions HapRay, 鸿蒙性能, perf testing, 高负载分析, symbol recovery, or root-cause.
  触发词含：鸿蒙性能、高负载分析、空刷根因、符号恢复。
  Hard gates: no shell until path_prompt_done; then Read this SKILL plus the current stage doc before CLI.
---

# HapRay 引导式工作流

> **包结构**：`SKILL.md` + `workflow/` + `analysis/` + `root-cause/` + `report/` + [`schemas/`](schemas/hapray-tool-result.md)（CLI 契约；发布包无 `docs/` 时以 Schema 为准）。

## 六阶段流水线

> **核心变更（v1.6，阶段骨架不变，仅改语义）**：`perf` 已产出 `report/` 下全部分析器数据（`summary.json`、`more_flame_graph.json`、全部 `trace_*.json`、`redundant_thread_analysis.json`、`ui_animate.json`、`hapray_report.*`）。**阶段 3 `gen-perf-report`（`update` 符号恢复）从「必跑」降为「按需」**：未提符号恢复时**跳过阶段 3**，直接进入阶段 4 读 `report/` 做高负载分析。**阶段 5 root-cause 脱离 `update`**（独立 CLI + Agent），且**不限空刷**。

| 阶段 | 目录 / 文件 | CLI | 产出 |
|:--:|-------------|-----|------|
| **0** | 本节 §0 | — | 路径门禁 |
| **1 setup** | `workflow/setup-binary.md` / `setup-source.md` | build / 下载 | 环境就绪 |
| **2 collect** | `workflow/perf-collect.md` | `perf` / `prepare` | `reports/<ts>/<用例>/report/` 全套分析器产物 |
| **3 gen-perf-report（可选）** | `workflow/gen-perf-report.md` | **`update --so_dir`** | **仅按需符号恢复**：增强火焰图、符号级热点（未提符号恢复则**跳过**） |
| **4 analysis** | `analysis/README.md` → 子 Skill | **读 `report/` / SQL** | SO/符号/帧/线程/IPC/内存高负载热点、动静交叉、新发现 |
| **5 root-cause** | `root-cause/empty-frame.md` | **独立 `root-cause`** + Agent | `root_cause.md`（空刷）+ Agent 全面根因（不限空刷） |
| **6 deliver** | `report/analysis-deliverable.md` | — | `reports/hapray-analysis-*.md`（高负载分析报告，融合根因） |

```text
§0 → 1 setup → 2 perf-collect → [3 gen-perf-report 可选符号恢复] → 4 analysis(读 report/) → 5 root-cause(独立·全面) → 6 analysis-deliverable
```

> 默认链路跳过阶段 3：`1 → 2 → 4 → 5 → 6`。仅当需要符号级热点（或火焰图 stripped）时才插入阶段 3 `update --so_dir`，完成后回到阶段 4 补符号级分析。

## 全局规范

### 工作区落盘（`<PROJECT_ROOT>`，MUST）

**`<PROJECT_ROOT>` = 当前 IDE 工作区根目录。** 一切下载、采集、报告、用例、契约 JSON、会话日志**必须**落在其下。**禁止**写入 `~/ArkAnalyzer-HapRay/`（除非已通过脚本重定向到工作区）、`/tmp`、桌面或工作区外路径。

| 用途 | 固定路径 |
|------|----------|
| Release 下载包 | `<PROJECT_ROOT>/hapray-release/` |
| 二进制解压根 `<RUNTIME_ROOT>` | `<PROJECT_ROOT>/hapray-release/runtime/` |
| perf 报告 / 可选 update | `<PROJECT_ROOT>/reports/<timestamp>/` |
| HTML 报告（便于打开） | `<PROJECT_ROOT>/reports/<timestamp>/…/report/hapray_report.html` |
| Agent 分析交付 | `<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<topic>.md` |
| 自写用例 | `<PROJECT_ROOT>/testcases/<包名>/PerfLoad_*.py` + `.json` |
| 契约 JSON | `<PROJECT_ROOT>/hapray-tool-result.json` |
| CLI 会话日志 | `<PROJECT_ROOT>/logs/*.log` |
| UI 探测 | `<PROJECT_ROOT>/reports/_ui_probe_<包名>/` |

**阶段 1 第一步（任何 CLI 之前 MUST）**：

```bash
bash <SKILL_DIR>/scripts/ensure-workspace-layout.sh "<PROJECT_ROOT>"
```

- **macOS**：将工具默认的 `~/ArkAnalyzer-HapRay/{reports,logs,runtime,…}` **符号链接**到上表路径，使 `perf`（及可选 `update`）无需事后拷贝。  
- **Linux / Windows**：在 `<PROJECT_ROOT>` 下执行 CLI（`cd` 到工作区），相对路径 `./reports` 即落在工作区。

**二进制轨用例同步**（`prepare`/`perf` 前，若用例写在 `testcases/`）：

```bash
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"
```

**源码轨**：`<REPO_ROOT>` 可为 HapRay 克隆仓（可与 `<PROJECT_ROOT>` 不同）；采集完成后若报告仍在 `<REPO_ROOT>/perf_testing/reports/`，**MUST** `cp -R` 到 `<PROJECT_ROOT>/reports/<timestamp>/`。

### 网络：默认禁止 GitHub

无用户明确要求时：GitCode 同源；radare2 用包管理器，装不上则跳过。

---

> ## ⛔ Agent 硬门禁
>
> | 变量 | 默认 | 设为 true 的条件 |
> |------|------|------------------|
> | `path_prompt_done` | `false` | §0 分步问路径并汇总确认 |
> | `skill_read_done` | `false` | Read **本文件全文** + **当前阶段**文档 |
>
> | 状态 | 允许 | 禁止 |
> |------|------|------|
> | `path_prompt_done=false` | §0 对话 | **一切** Shell |
> | `path_prompt_done=true` 且 `skill_read_done=false` | Read 主 SKILL + 阶段文档 | **一切** Shell |
> | 两者均为 `true` | 按 §11 执行 | 臆造路径；符号恢复缺 §0 的 `--so_dir`；root-cause 缺 §0 的源码路径；**未** `ensure-workspace-layout` 就跑 CLI |
>
> 每次 Shell 前：`path_prompt_done` → `skill_read_done` → 当前阶段是否已 Read。

---

## 阶段 Read 清单（`skill_read_done` 前）

1. **必读**：本文件 `SKILL.md` 全文  
2. **按阶段追加**（至少一项）：
   - 1 setup → [setup-binary](workflow/setup-binary.md) 和/或 [setup-source](workflow/setup-source.md) + **`scripts/ensure-workspace-layout.sh`**
   - 2 collect → [perf-collect](workflow/perf-collect.md)
   - 3 gen-perf-report → [gen-perf-report](workflow/gen-perf-report.md)（仅按需符号恢复，未提则跳过）
   - 4 analysis → [analysis/README](analysis/README.md) + 触发的子 Skill（默认 [high-load](analysis/high-load-analysis.md)）
   - 5 root-cause → [root-cause/empty-frame](root-cause/empty-frame.md)
   - 6 deliver → [report/analysis-deliverable](report/analysis-deliverable.md)

---

## §0 路径门禁

### 何时触发 / 豁免

**触发**：会跑 `perf`/`prepare`/构建/下载/`hdc`/`root-cause`/（可选）`update` 等 CLI。

**豁免（ReadOnly）**：只读已有报告或解释 Skill，且**确认**零 Shell → 跳过 §0，见 §1。

### 必问模板（第 1 项）

```text
**第 1/2 项：源码路径（root-cause 全面根因主输入）**
接受含 *.ts、*.ets 的应用源码目录（root-cause 阶段据此做源码级根因定位）
→ 回复具体路径，或回复「跳过」

收到后我会继续询问第 2 项（SO 路径）。
```

### 必问模板（第 2 项）

```text
**第 2/2 项：SO 路径（仅符号恢复时需要，可跳过）**
接受含应用 *.so 的目录，例：<path>/libs/arm64/
说明：默认流程不跑符号恢复；仅当你要符号级热点、或火焰图热点为 libxxx.so+0x.. 时才需要
→ 回复具体路径，或回复「跳过」

汇总确认：
- 源码路径：<本地路径或「跳过」>
- SO 路径：<本地路径或「跳过」>

确认无误后，我将 Read 当前阶段文档，再开始执行。
```

### 用户答复判定

| 用户表述 | 记录 |
|----------|------|
| 源码路径 | `app_packages_dir_user` → 阶段 5 root-cause `--source-dir` / `--app-packages-dir` |
| 「跳过」源码 | root-cause 降级为 analyze（仅证据，无源码级行号）或仅做 perf 产物级根因 |
| SO 路径 | `so_dir_user` → 可选符号恢复 `update --so_dir` |
| 「跳过」SO | 不做符号恢复（默认）；符号级热点若为 stripped 地址则标注「建议符号恢复」 |
| 仅「继续/跑吧」未给路径 | **不算**答复，重发模板 |

**禁止**：路径未齐就 Shell；未 Read 阶段文档就 Shell；同条消息问路径又 Shell。

---

## §1 场景路由

```text
用户请求
  ├─ ReadOnly → 跳过 §0；可读 4/5/6 文档解释产物
  ├─ SIMPLE   → §0 → 4 analysis(读 report/) → 5 root-cause? → 6 deliver
  └─ Full     → §0 → 1 → 2 → [3 符号恢复?按需] → 4 analysis → 5 root-cause? → 6 deliver
```

| 场景 | 阶段 Read |
|------|-----------|
| ReadOnly | 按需 analysis / root-cause / analysis-deliverable |
| SIMPLE | analysis + root-cause? + analysis-deliverable（+ gen-perf-report 仅按需符号恢复） |
| Full | setup-* + perf-collect + analysis + root-cause? + analysis-deliverable（+ gen-perf-report 仅按需符号恢复） |

### TL;DR

| 步 | 阶段 | 动作 |
|:--:|:--:|------|
| 0 | 0 | §0 问路径 |
| 0.5 | — | Read 主 SKILL + 当前阶段 doc |
| 0.25 | — | `ensure-workspace-layout.sh <PROJECT_ROOT>` |
| 1 | 1 | 判轨 → setup-binary / setup-source |
| 2 | 2 | perf-collect（产出 `report/` 全套分析器数据） |
| 3 | 3 | **仅按需** gen-perf-report：符号恢复 `update --so_dir`（要符号级热点 / 火焰图 stripped 时）；未提则**跳过** |
| 4 | 4 | analysis：**读 `report/`** 做 high-load 分析（默认主线，不跑 update） |
| 5 | 5 | root-cause：独立 `root-cause` CLI（空刷）+ Agent 全面根因（借源码） |
| 6 | 6 | analysis-deliverable 落盘（融合空刷 + 全面根因） |

### 状态机

| 状态 | 禁止 |
|------|------|
| `PATH_PROMPT` | Shell |
| `SKILL_READ` | Shell |
| `DISCOVER` | perf（环境未就绪） |
| `EXECUTE` / `PARSE` / `ANALYZE` / `REPORT` | — |

---

## §2 路径术语与运行轨

| 术语 | 含义 |
|------|------|
| `<SKILL_DIR>` | 本 Skill 包目录（含 `SKILL.md` 的 `skills/hapray/`） |
| `<PROJECT_ROOT>` | **当前 IDE 工作区根**；所有下载与产出的唯一落盘根（见「工作区落盘」） |
| `<REPO_ROOT>` | HapRay **源码克隆**根（可与 `<PROJECT_ROOT>` 不同；仅源码轨构建用） |
| `<RUNTIME_ROOT>` | `<PROJECT_ROOT>/hapray-release/runtime/`（二进制解压后） |
| `reports_path` | 契约：`<PROJECT_ROOT>/reports/<timestamp>/` 下采集产物目录 |

**判轨**：`<PROJECT_ROOT>` 或 `<REPO_ROOT>` 含 `perf_testing/pyproject.toml` → 可选源码轨；否则 → 二进制轨（setup-binary）。**无论哪一轨**，报告与用例对用户可见路径均在 `<PROJECT_ROOT>`。**`perf` 后默认直接进入阶段 4 读 `report/` 做高负载分析；阶段 3 `gen-perf-report`（`update`）仅在需要符号恢复时按需执行。**

---

## §3 workflow 索引（阶段 1–3）

| 阶段 | 文件 | 要点 |
|:--:|------|------|
| 1a | [setup-binary.md](workflow/setup-binary.md) | GitCode 直链；§5 自检 |
| 1b | [setup-source.md](workflow/setup-source.md) | 7 步 + `scripts/validate-env.sh` |
| 2 | [perf-collect.md](workflow/perf-collect.md) | 预设→perf；禁止默认 gui-agent；**产出 `report/`** |
| 3（可选） | [gen-perf-report.md](workflow/gen-perf-report.md) | **`update --so_dir`** 符号恢复（仅按需，默认 Agent；未提则跳过） |

---

## §4 分析模式

- **Quick**：采集 + analysis（至少一个子 Skill，默认 high-load）+ 阶段 6 报告  
- **Full**：analysis 三项逐一评估 + 阶段 5 全面 root-cause（空刷 + 其余高负载问题）  

---

## §5 analysis 路由（阶段 4）

[`analysis/README.md`](analysis/README.md) 索引。`perf` 后**直接读 `report/`**（默认不跑 update），按序评估：`high-load` → `scroll-jank` → `symbol-recovery`；不满足则 `已跳过（原因）`。**high-load 为阶段 4 主线**。

| 产物 / 信号 | 子 Skill |
|-------------|----------|
| 高负载 / 未知瓶颈（默认主线） | high-load |
| `trace.db` + 滑动/掉帧 | scroll-jank |
| `libxxx.so+0x...`（需符号级） | symbol-recovery（触发可选阶段 3 `update --so_dir`） |

**阶段 5 root-cause**：见 [`root-cause/empty-frame.md`](root-cause/empty-frame.md)（独立 CLI + Agent 全面根因，不限空刷）。

---

## §6 root-cause（阶段 5，独立·全面）

权威文档：[`root-cause/empty-frame.md`](root-cause/empty-frame.md)。  
**脱离 `update`**：空刷走独立 `root-cause` CLI；其余高负载问题（SO/符号热点、高负载帧、冗余线程、IPC、内存）由 Agent 结合阶段 4 发现 + 源码逐类做源码级定位。空刷 CLI 结论作为其中一项证据融合进最终报告。

---

## §7 约束索引

| 主题 | 权威 |
|------|------|
| 路径门禁 | §0 |
| 分阶段 Read | 阶段 Read 清单 |
| setup | workflow/setup-* |
| 采集 | workflow/perf-collect |
| 可选符号恢复 | workflow/gen-perf-report |
| 高负载挖掘（阶段 4 主线） | analysis/* |
| 全面 root-cause（阶段 5，独立） | root-cause/empty-frame |
| Agent 交付 | report/analysis-deliverable |

---

## §8 执行主流程

> 前置：`path_prompt_done=true` 且 `skill_read_done=true`。

§0 → Read 阶段 doc → 1 setup → 2 collect（产出 `report/`）→ [3 仅按需符号恢复 `update --so_dir`] → 4 analysis **读 `report/` 做 high-load 分析**（`hapray-tool-result.json` 取 `reports_path`；默认不跑 update）→ 5 root-cause（独立 CLI 空刷 + Agent 全面根因，借源码）→ 6 [`analysis-deliverable`](report/analysis-deliverable.md) 落盘（**融合空刷 + 全面根因**）。

---

## §9 异常与降级

| 情况 | 动作 |
|------|------|
| 二进制下载失败 | setup-source |
| 无预设用例 | 写脚本 + prepare → perf |
| 缺 trace 等 | 子 Skill 跳过 + 补采命令 |
| 火焰图热点为 stripped 地址 | 阶段 3 按需 `update --so_dir`；否则标注「建议符号恢复」，SO/帧/线程级照常 |
| 无源码（root-cause） | root-cause 降级为 analyze（仅证据无行号）或仅做 perf 产物级根因 |
| `result-file` 损坏 | 仅证据报告 |

---

## §10 命令模板

> ⛔ 门禁未过禁止执行。

### 工作区初始化（两轨共用，最先执行）

```bash
bash <SKILL_DIR>/scripts/ensure-workspace-layout.sh "<PROJECT_ROOT>"
```

### 源码轨（1 setup → 2 collect）

```bash
cd <REPO_ROOT> && bash <SKILL_DIR>/scripts/validate-env.sh
# 用例 MUST 写在 <PROJECT_ROOT>/testcases/<包名>/
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"   # 二进制轨
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --apps <包名> --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# perf 已产出 <用例>/report/ 全套分析器数据（summary.json、more_flame_graph.json、trace_*.json…）
# macOS 已 ensure-workspace-layout 时报告已在 <PROJECT_ROOT>/reports/；
# 若 <REPO_ROOT>≠<PROJECT_ROOT> 且报告在 REPO 下：cp -R 到 <PROJECT_ROOT>/reports/
```

### 阶段 3（可选）gen-perf-report 符号恢复 —— 仅在需要符号级热点时

```bash
# 默认跳过；仅当要符号级热点或火焰图 stripped 时执行。源码轨：
uv run python -m scripts.main update \
  --report_dir <PROJECT_ROOT>/reports/<timestamp> \
  --so_dir "<§0_SO>" \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# 二进制轨：用 <RUNTIME_ROOT>/.../perf-testing update -r ... --so_dir ...
```

### 阶段 4 analysis high-load（读 `report/`，**默认不跑 update**）

```bash
# 从 hapray-tool-result.json 取 reports_path，对 report/ 与 hiperf/step*/perf.db 做分析
# 具体 SQL 与维度见 analysis/high-load-analysis.md
sqlite3 <用例>/hiperf/step5/perf.db "PRAGMA table_info(perf_sample)"
```

### 阶段 5 root-cause（独立，**脱离 update**）

```bash
# 空刷专项（独立 CLI）：--source-dir 提供 §0 源码路径以启用 with_source 行级根因
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --source-dir "<§0_源码>" \
  [--index-dir "<§0_源码>/index"]
# 仅证据（不调 LLM）：追加 --skip-llm
# 其余高负载问题的全面根因由 Agent 结合阶段 4 发现 + 源码逐类定位（见 root-cause/empty-frame.md）
```

### 二进制轨（采集）

```bash
# 下载解压见 setup-binary.md → <RUNTIME_ROOT>=<PROJECT_ROOT>/hapray-release/runtime/
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"
PERF="<RUNTIME_ROOT>/.../perf-testing"   # 或 .app 内 perf-testing，见 setup-binary §5
"$PERF" prepare --run_testcases "PerfLoad_<用例名>" --device <SN>
"$PERF" perf --run_testcases "PerfLoad_<用例名>" --round 1 --devices <SN> \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# 报告根：<PROJECT_ROOT>/reports/<timestamp>/（macOS 须先 ensure-workspace-layout）
```

Windows：`.\hapray.exe --help`。

### SIMPLE（已有 perf/trace，补生成报告）

```bash
# 仅当从原始 perf.data/htrace 重建报告时；需要符号恢复才加 --so_dir
uv run python -m scripts.main update --report_dir ./reports/<timestamp> [--so_dir "..."]
```

---

## §11 明确禁止

- 门禁未过跑 Shell；**产出写 `<PROJECT_ROOT>` 外**（含未重定向的 `~/ArkAnalyzer-HapRay`）；默认 GitHub  
- 跳过 `ensure-workspace-layout.sh` 直接 `perf`/`update`（macOS 必炸到主目录）  
- 用例只写在 Release 包 `_internal/` 或 `<REPO_ROOT>` 而不落盘 `<PROJECT_ROOT>/testcases/`  
- 无预设时默认 gui-agent / `perf --manual`  
- **未提符号恢复却默认跑 `update`**（perf 后应先读 `report/` 做高负载分析）；**把 root-cause 绑死在 `update` 上**（应走独立 `root-cause` CLI + Agent 全面根因）  
- 符号恢复确需执行时无故 `--symbol-recovery-no-llm`；伪交付 / 虚构数据  

---

## §12 参考

- [`schemas/hapray-tool-result.md`](schemas/hapray-tool-result.md) + [`hapray-tool-result-v1.json`](schemas/hapray-tool-result-v1.json)
- `workflow/` · `analysis/` · `root-cause/` · `report/`  
- 源码仓可选：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`（**发布包无 `docs/`**）
