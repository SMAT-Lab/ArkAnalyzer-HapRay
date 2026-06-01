---
name: hapray
version: "1.5.5"
description: |
  Guides OpenHarmony/HarmonyOS HapRay performance analysis in six stages:
  setup, perf-collect, gen-perf-report (update), analysis, root-cause, LLM deliverable.
  Use when the user mentions HapRay, 鸿蒙性能, perf testing, symbol recovery, or empty-frame root-cause.
  触发词含：鸿蒙性能、空刷根因、符号恢复。
  Hard gates: no shell until path_prompt_done; then Read this SKILL plus the current stage doc before CLI.
---

# HapRay 引导式工作流

> **包结构**：`SKILL.md` + `workflow/` + `analysis/` + `root-cause/` + `report/` + [`schemas/`](schemas/hapray-tool-result.md)（CLI 契约；发布包无 `docs/` 时以 Schema 为准）。

## 六阶段流水线

| 阶段 | 目录 / 文件 | CLI | 产出 |
|:--:|-------------|-----|------|
| **0** | 本节 §0 | — | 路径门禁 |
| **1 setup** | `workflow/setup-binary.md` / `setup-source.md` | build / 下载 | 环境就绪 |
| **2 collect** | `workflow/perf-collect.md` | `perf` / `prepare` | `reports/<ts>/` raw 数据 |
| **3 gen-perf-report** | `workflow/gen-perf-report.md` | **`update`** | `hapray_report.html`、增强火焰图 |
| **4 analysis** | `analysis/README.md` → 子 Skill | 读 trace/SQL | 线索、新发现 |
| **5 root-cause** | `root-cause/empty-frame.md` | `update` 集成 / `root-cause` | `root_cause.md`（空刷） |
| **6 deliver** | `report/analysis-deliverable.md` | — | `reports/hapray-analysis-*.md`（**须内嵌** `root_cause.md` 全文，若有空刷） |

```text
§0 → 1 setup → 2 perf-collect → 3 gen-perf-report → 4 analysis → 5 root-cause? → 6 analysis-deliverable
```

## 全局规范

### 工作区落盘（`<PROJECT_ROOT>`，MUST）

**`<PROJECT_ROOT>` = 当前 IDE 工作区根目录。** 一切下载、采集、报告、用例、契约 JSON、会话日志**必须**落在其下。**禁止**写入 `~/ArkAnalyzer-HapRay/`（除非已通过脚本重定向到工作区）、`/tmp`、桌面或工作区外路径。

| 用途 | 固定路径 |
|------|----------|
| Release 下载包 | `<PROJECT_ROOT>/hapray-release/` |
| 二进制解压根 `<RUNTIME_ROOT>` | `<PROJECT_ROOT>/hapray-release/runtime/` |
| perf/update 报告 | `<PROJECT_ROOT>/reports/<timestamp>/` |
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

- **macOS**：将工具默认的 `~/ArkAnalyzer-HapRay/{reports,logs,runtime,…}` **符号链接**到上表路径，使 `perf`/`update` 无需事后拷贝。  
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
> | 两者均为 `true` | 按 §11 执行 | 臆造路径；update 缺 §0 的 `--so_dir`；**未** `ensure-workspace-layout` 就跑 CLI |
>
> 每次 Shell 前：`path_prompt_done` → `skill_read_done` → 当前阶段是否已 Read。

---

## 阶段 Read 清单（`skill_read_done` 前）

1. **必读**：本文件 `SKILL.md` 全文  
2. **按阶段追加**（至少一项）：
   - 1 setup → [setup-binary](workflow/setup-binary.md) 和/或 [setup-source](workflow/setup-source.md) + **`scripts/ensure-workspace-layout.sh`**
   - 2 collect → [perf-collect](workflow/perf-collect.md)
   - 3 gen-perf-report → [gen-perf-report](workflow/gen-perf-report.md)
   - 4 analysis → [analysis/README](analysis/README.md) + 触发的子 Skill
   - 5 root-cause → [root-cause/empty-frame](root-cause/empty-frame.md)
   - 6 deliver → [report/analysis-deliverable](report/analysis-deliverable.md)

---

## §0 路径门禁

### 何时触发 / 豁免

**触发**：会跑 `perf`/`update`/`prepare`/构建/下载/`hdc`/`root-cause` 等 CLI。

**豁免（ReadOnly）**：只读已有报告或解释 Skill，且**确认**零 Shell → 跳过 §0，见 §1。

### 必问模板（第 1 项）

```text
**第 1/2 项：源码路径（用于负载根因分析）**
接受含 *.ts、*.ets 的应用源码目录
→ 回复具体路径，或回复「跳过」

收到后我会继续询问第 2 项（SO 路径）。
```

### 必问模板（第 2 项）

```text
**第 2/2 项：SO 路径（用于二进制优化分析）**
接受含应用 *.so 的目录，例：<path>/libs/arm64/
→ 回复具体路径，或回复「跳过」

汇总确认：
- 源码路径：<本地路径或「跳过」>
- SO 路径：<本地路径或「跳过」>

确认无误后，我将 Read 当前阶段文档，再开始执行。
```

### 用户答复判定

| 用户表述 | 记录 |
|----------|------|
| 源码路径 | `app_packages_dir_user` → 阶段 5 `--app-packages-dir` |
| 「跳过」源码 | `--no-root-cause` 意向 |
| SO 路径 | `so_dir_user` → 阶段 3 `--so_dir` |
| 「跳过」SO | 不填 SO |
| 仅「继续/跑吧」未给路径 | **不算**答复，重发模板 |

**禁止**：路径未齐就 Shell；未 Read 阶段文档就 Shell；同条消息问路径又 Shell。

---

## §1 场景路由

```text
用户请求
  ├─ ReadOnly → 跳过 §0；可读 4/5/6 文档解释产物
  ├─ SIMPLE   → §0 → 3 gen-perf-report → 4 → 5? → 6
  └─ Full     → §0 → 1 → 2 → 3 → 4 → 5? → 6
```

| 场景 | 阶段 Read |
|------|-----------|
| ReadOnly | 按需 analysis / root-cause / analysis-deliverable |
| SIMPLE | gen-perf-report + analysis + root-cause? + analysis-deliverable |
| Full | setup-* + perf-collect + gen-perf-report + analysis + root-cause? + analysis-deliverable |

### TL;DR

| 步 | 阶段 | 动作 |
|:--:|:--:|------|
| 0 | 0 | §0 问路径 |
| 0.5 | — | Read 主 SKILL + 当前阶段 doc |
| 0.25 | — | `ensure-workspace-layout.sh <PROJECT_ROOT>` |
| 1 | 1 | 判轨 → setup-binary / setup-source |
| 2 | 2 | perf-collect |
| 3 | 3 | **update**（gen-perf-report） |
| 4 | 4 | analysis 子 Skill 逐一评估 |
| 5 | 5 | 有空刷 → empty-frame root-cause |
| 6 | 6 | analysis-deliverable 落盘；**Read `root_cause.md` 并全文内嵌**（有空刷时） |

### 状态机

| 状态 | 禁止 |
|------|------|
| `PATH_PROMPT` | Shell |
| `SKILL_READ` | Shell |
| `DISCOVER` | perf/update（环境未就绪） |
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

**判轨**：`<PROJECT_ROOT>` 或 `<REPO_ROOT>` 含 `perf_testing/pyproject.toml` → 可选源码轨；否则 → 二进制轨（setup-binary）。**无论哪一轨**，报告与用例对用户可见路径均在 `<PROJECT_ROOT>`。`perf` 后**必须**阶段 3 `update`。

---

## §3 workflow 索引（阶段 1–3）

| 阶段 | 文件 | 要点 |
|:--:|------|------|
| 1a | [setup-binary.md](workflow/setup-binary.md) | GitCode 直链；§5 自检 |
| 1b | [setup-source.md](workflow/setup-source.md) | 7 步 + `scripts/validate-env.sh` |
| 2 | [perf-collect.md](workflow/perf-collect.md) | 预设→perf；禁止默认 gui-agent |
| 3 | [gen-perf-report.md](workflow/gen-perf-report.md) | **`update`** + 符号恢复 Agent 默认 |

---

## §4 分析模式

- **Quick**：采集 + 至少一个 analysis 子 Skill + 阶段 6 报告  
- **Full**：analysis 三项逐一评估；有空刷则阶段 5  

---

## §5 analysis 路由（阶段 4）

[`analysis/README.md`](analysis/README.md) 索引。`PARSE` 后按序评估：`scroll-jank` → `high-load` → `symbol-recovery`；不满足则 `已跳过（原因）`。

| 产物 / 信号 | 子 Skill |
|-------------|----------|
| `trace.db` + 滑动/掉帧 | scroll-jank |
| 高负载 / 未知瓶颈 | high-load |
| `libxxx.so+0x...` | symbol-recovery |

**阶段 5 不在 analysis/**：见 [`root-cause/empty-frame.md`](root-cause/empty-frame.md)（`trace_emptyFrame.json` / 空刷）。

---

## §6 root-cause（阶段 5）

权威文档：[`root-cause/empty-frame.md`](root-cause/empty-frame.md)。  
analysis 提供线索；空刷**正式根因**（`root_cause.md`、Agent 闭环）仅走本阶段。

---

## §7 约束索引

| 主题 | 权威 |
|------|------|
| 路径门禁 | §0 |
| 分阶段 Read | 阶段 Read 清单 |
| setup | workflow/setup-* |
| 采集 | workflow/perf-collect |
| 工具报告 | workflow/gen-perf-report |
| 线索挖掘 | analysis/* |
| 空刷根因 | root-cause/empty-frame |
| Agent 交付 | report/analysis-deliverable |

---

## §8 执行主流程

> 前置：`path_prompt_done=true` 且 `skill_read_done=true`。

§0 → Read 阶段 doc → 1 setup → 2 collect → 3 **update** → 读 `hapray-tool-result.json` → 4 analysis → 5 root-cause（若有空刷）→ **验收 `root_cause.md` 非 Pending** → 6 [`analysis-deliverable`](report/analysis-deliverable.md) 落盘（**内嵌根因全文**）。

---

## §9 异常与降级

| 情况 | 动作 |
|------|------|
| 二进制下载失败 | setup-source |
| 无预设用例 | 写脚本 + prepare → perf |
| 缺 trace 等 | 子 Skill 跳过 + 补采命令 |
| `result-file` 损坏 | 仅证据报告 |

---

## §10 命令模板

> ⛔ 门禁未过禁止执行。

### 工作区初始化（两轨共用，最先执行）

```bash
bash <SKILL_DIR>/scripts/ensure-workspace-layout.sh "<PROJECT_ROOT>"
```

### 源码轨（1→2→3）

```bash
```bash
cd <REPO_ROOT> && bash <SKILL_DIR>/scripts/validate-env.sh
# 用例 MUST 写在 <PROJECT_ROOT>/testcases/<包名>/
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"   # 二进制轨
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --apps <包名> --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
uv run python -m scripts.main update \
  --report_dir <PROJECT_ROOT>/reports/<timestamp> \
  --so_dir "<§0_SO>"
# macOS 已 ensure-workspace-layout 时，perf 报告已在 <PROJECT_ROOT>/reports/
# 若 <REPO_ROOT>≠<PROJECT_ROOT> 且报告在 REPO 下：cp -R 到 <PROJECT_ROOT>/reports/
```

### 二进制轨

```bash
# 下载解压见 setup-binary.md → <RUNTIME_ROOT>=<PROJECT_ROOT>/hapray-release/runtime/
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"
PERF="<RUNTIME_ROOT>/.../perf-testing"   # 或 .app 内 perf-testing，见 setup-binary §5
"$PERF" prepare --run_testcases "PerfLoad_<用例名>" --device <SN>
"$PERF" perf --run_testcases "PerfLoad_<用例名>" --round 1 --devices <SN> \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
"$PERF" update -r <PROJECT_ROOT>/reports/<timestamp> --so_dir "<§0_SO>" \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# 报告根：<PROJECT_ROOT>/reports/<timestamp>/（macOS 须先 ensure-workspace-layout）
```

Windows：`.\hapray.exe --help`。

### SIMPLE

```bash
uv run python -m scripts.main update --report_dir ./reports/<timestamp> --so_dir "..."
```

---

## §11 明确禁止

- 门禁未过跑 Shell；**产出写 `<PROJECT_ROOT>` 外**（含未重定向的 `~/ArkAnalyzer-HapRay`）；默认 GitHub  
- 跳过 `ensure-workspace-layout.sh` 直接 `perf`/`update`（macOS 必炸到主目录）  
- 用例只写在 Release 包 `_internal/` 或 `<REPO_ROOT>` 而不落盘 `<PROJECT_ROOT>/testcases/`  
- 无预设时默认 gui-agent / `perf --manual`  
- 无故 `--symbol-recovery-no-llm`；伪交付 / 虚构数据  

---

## §12 参考

- [`schemas/hapray-tool-result.md`](schemas/hapray-tool-result.md) + [`hapray-tool-result-v1.json`](schemas/hapray-tool-result-v1.json)
- `workflow/` · `analysis/` · `root-cause/` · `report/`  
- 源码仓可选：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`（**发布包无 `docs/`**）
