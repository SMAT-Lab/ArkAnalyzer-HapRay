---
name: hapray
version: "1.5.9"
  description: |
  Guides OpenHarmony/HarmonyOS HapRay performance analysis in six stages:
  setup, perf-collect, high-load analysis (read report/), root-cause (standalone, full), deliverable.
  Memory analysis is a parallel track when --memory is enabled (memory-collect → memory-analysis → memory-deliverable).
  Symbol recovery (update) is triggered when user explicitly requests it or when hotspots are stripped; skipped otherwise.
  PR-Impact is a dual-round comparison workflow when user provides a PR/git identifier + test scenario (build→collect→analyze before, apply changes, build→collect→analyze after, compare).
  Use when the user mentions HapRay, 鸿蒙性能, perf testing, 高负载分析, 内存分析, symbol recovery, root-cause, PR影响, 改动对比, or 性能对比.
  触发词含：鸿蒙性能、高负载分析、内存分析、内存泄漏、memory leak、空刷根因、符号恢复、PR影响、改动对比、性能对比.
  Hard gates: no shell until path_prompt_done; then Read this SKILL plus the current stage doc before CLI.
---

# HapRay 引导式工作流

> **包结构**：`SKILL.md` + `workflow/` + `analysis/` + `root-cause/` + `report/` + [`schemas/`](schemas/hapray-tool-result.md)（CLI 契约；发布包无 `docs/` 时以 Schema 为准）。
>
> **双主线**：high-load（CPU 指令数，默认主线）+ memory（Native 内存，`--memory` 采集时主线）。两者数据源独立、可联合采集（`perf --memory`）后分别分析。

## 自动升级（每次加载 MUST，唯一的 §0 前 Shell 豁免）

在询问 §0 路径、执行任何 HapRay 命令或读取阶段文档前，先执行一次：

```bash
python <SKILL_DIR>/scripts/update_skill.py --skill-dir <SKILL_DIR>
```

- 输出 `status=updated`：当前 Skill 已原子升级，**MUST 重新读取新版 `SKILL.md`**，再按新版规则继续。
- 输出 `status=current`：已是最新稳定版本，继续当前流程。
- 输出 `status=failed`：网络、远端或文件校验失败；更新器保留/回滚当前版本，记录警告后继续，不阻塞离线使用。
- 输出 `status=disabled`：用户通过 `HAPRAY_SKILL_AUTO_UPDATE=0` 明确关闭自动升级，继续当前流程。
- 输出 `status=source_checkout`：当前路径是 ArkAnalyzer-HapRay 源码工作树；为避免覆盖开发改动，不执行目录替换，应通过 Git 更新源码。
- 只允许此更新命令在 `path_prompt_done=false` 时执行；它不得运行 HapRay、访问项目数据或写入 `<PROJECT_ROOT>`。

更新器仅接受 GitCode 仓库的稳定语义版本 tag，逐文件校验 Git blob SHA，并在 Skill 同级目录完成暂存、校验、原子替换和失败回滚。可用 `--check-only` 只检查，不安装。

## 六阶段流水线

> **核心变更（v1.6，阶段骨架不变，仅改语义）**：`perf` 已产出 `report/` 下全部分析器数据（`summary.json`、`more_flame_graph.json`、全部 `trace_*.json`、`redundant_thread_analysis.json`、`ui_animate.json`、`hapray_report.*`）。**阶段 3 `gen-perf-report`（`update` 符号恢复）从「必跑」降为「按需」**：用户明确要求符号恢复、或需要符号级热点/火焰图 stripped 时执行，否则**跳过阶段 3**，直接进入阶段 4 读 `report/` 做高负载分析。**阶段 5 root-cause 脱离 `update`**（独立 CLI，默认 `--checker comprehensive` 多信号综合 + Agent 补充深挖）。

| 阶段 | 目录 / 文件 | CLI | 产出 |
|:--:|-------------|-----|------|
| **0** | 本节 §0 | — | 路径门禁 |
| **0.5 build（可选）** | `workflow/build.md` | **`build`** | debug HAP + `.so` 符号文件（自动填充 §0 `so_dir`） |
| **1 setup** | `workflow/setup-binary.md` / `setup-source.md` | build / 下载 | 环境就绪 |
| **2 collect** | `workflow/perf-collect.md` | `perf` / `prepare` | `reports/<ts>/<用例>/report/` 全套分析器产物 |
| **3 gen-perf-report（可选）** | `workflow/gen-perf-report.md` | **`update --so_dir`** | **符号恢复**：用户明确要求，或需要符号级热点/火焰图 stripped 时执行；否则**跳过** |
| **4 analysis** | `analysis/README.md` → 子 Skill | **读 `report/` / SQL** | SO/符号/帧/线程/IPC/内存高负载热点、动静交叉、新发现；`--memory` 时并列做内存分析 |
| **5 root-cause** | `root-cause/comprehensive.md` | **独立 `root-cause`** + Agent 补充深挖 | `root_cause.md`（多信号综合）+ Agent 源码级补充 |
| **6 deliver** | `report/analysis-deliverable.md` 或 `report/memory-deliverable.md` | — | `reports/hapray-analysis-*-load-*.md`（高负载）或 `*-memory-*.md`（内存专题），融合根因 |

```text
§0 → [0.5 build 可选·从源码构建debug HAP] → 1 setup → 2 perf-collect → [3 gen-perf-report 可选符号恢复] → 4 analysis(读 report/) → 5 root-cause(独立·多信号综合) → 6 analysis-deliverable
```

> 默认链路跳过阶段 0.5 和 3：`1 → 2 → 4 → 5 → 6`。仅当用户有 HarmonyOS 源码工程、需从源码构建 debug 包时插入阶段 0.5 `build`（产出 HAP + `.so`，自动填充 §0 `so_dir`）；仅当需要符号级热点（或火焰图 stripped）时才插入阶段 3 `update --so_dir`。
>
> **PR-Impact 变体**：用户提供 PR/Git 标识 + 测试场景时，走 [`workflow/pr-impact-analysis.md`](workflow/pr-impact-analysis.md) 双轮对比：`§0(+Git标识+场景) → A.Git状态管理 → B.改动前轮(build→collect→analyze→root-cause→pre报告) → C.应用PR改动 → D.改动后轮(复用脚本→build→collect→analyze→root-cause→post报告) → E.对比报告 → F.恢复Git状态`。两轮各自完整走 `0.5 build → 2 → [3?] → 4 → 5 → 6`，最终追加 comparison 报告。

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
> | `path_prompt_done=false` | 自动升级命令、§0 对话 | 除 `scripts/update_skill.py` 外的**一切** Shell |
> | `path_prompt_done=true` 且 `skill_read_done=false` | Read 主 SKILL + 阶段文档 | **一切** Shell |
> | 两者均为 `true` | 按 §11 执行 | 臆造路径；符号恢复缺 §0 的 `--so_dir`；root-cause 缺 §0 的源码路径；**未** `ensure-workspace-layout` 就跑 CLI |
>
> 每次 Shell 前：`path_prompt_done` → `skill_read_done` → 当前阶段是否已 Read。

---

## 阶段 Read 清单（`skill_read_done` 前）

1. **必读**：本文件 `SKILL.md` 全文  
2. **按阶段追加**（至少一项）：
   - **PR-Impact** → [pr-impact-analysis](workflow/pr-impact-analysis.md)（PR/commit 改动前后对比；需额外追加 build + perf-collect + analysis + root-cause + analysis-deliverable）
   - 0.5 build → [build](workflow/build.md)（从源码构建 debug HAP 时）
   - 1 setup → [setup-binary](workflow/setup-binary.md) 和/或 [setup-source](workflow/setup-source.md) + **`scripts/ensure-workspace-layout.sh`**
   - 2 collect → [perf-collect](workflow/perf-collect.md)（+ [memory-collect](workflow/memory-collect.md) 当 `--memory` 时）
   - 3 gen-perf-report → [gen-perf-report](workflow/gen-perf-report.md)（仅按需符号恢复，未提则跳过）
   - 4 analysis → [analysis/README](analysis/README.md) + 触发的子 Skill（默认 [high-load](analysis/high-load-analysis.md)；`--memory` 时追加 [memory](analysis/memory-analysis.md)）
   - 5 root-cause → [root-cause/comprehensive](root-cause/comprehensive.md)
   - 6 deliver → [report/analysis-deliverable](report/analysis-deliverable.md)（高负载）或 [report/memory-deliverable](report/memory-deliverable.md)（内存专题）

---

## §0 路径门禁

### 何时触发 / 豁免

**触发**：会跑 `perf`/`prepare`/构建/下载/`hdc`/`root-cause`/（可选）`update` 等 CLI。

**豁免（ReadOnly）**：只读已有报告或解释 Skill，且**确认**零 Shell → 跳过 §0，见 §1。

> **PR-Impact 额外输入**：当场景为 PR-Impact（用户提供 PR/Git 标识 + 测试场景，要求改动前后对比）时，§0 标准两项路径问完后，**追加**两项额外输入（Git 标识 + 测试场景），详见 [`workflow/pr-impact-analysis.md`](workflow/pr-impact-analysis.md)「额外输入」节。

### 必问模板（第 1 项）

```text
**第 1/2 项：源码路径（root-cause 全面根因主输入）**
接受含 *.ts、*.ets 的应用源码目录（root-cause 阶段据此做源码级根因定位）
→ 回复具体路径，或回复「跳过」

收到后我会继续询问第 2 项（SO 路径）。
```

### 必问模板（第 2 项）

```text
**第 2/2 项：SO 路径（符号恢复时用，可跳过/从设备拉取）**
接受含应用 *.so 的目录，例：<path>/libs/arm64/
说明：
- 若用户明确要求符号恢复，必须执行
- 提供路径则直接使用；跳过则尝试从设备拉取
- 拉取失败则标注「符号恢复失败，从设备拉取so文件失败，需要提供so路径才能进行符号恢复」
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
| SO 路径 | `so_dir_user` → 符号恢复 `update --so_dir` |
| 「跳过」SO | 用户明确要求符号恢复时：尝试从设备拉取；拉取失败则标注「符号恢复失败，从设备拉取so文件失败，需要提供so路径才能进行符号恢复」。未要求时：跳过符号恢复 |
| 仅「继续/跑吧」未给路径 | **不算**答复，重发模板 |

**禁止**：路径未齐就 Shell；未 Read 阶段文档就 Shell；同条消息问路径又 Shell。

---

## §1 场景路由

```text
用户请求
  ├─ ReadOnly → 跳过 §0；可读 4/5/6 文档解释产物
  ├─ PR-Impact → §0(+额外输入: Git标识+测试场景) → pr-impact-analysis 工作流（两轮 build→collect→analyze→root-cause→deliver + 对比报告）
  ├─ 有源码工程需构建 debug → §0 → 0.5 build → 1 setup → 2 perf-collect → [3 符号恢复?按需] → 4 analysis → 5 root-cause? → 6 deliver
  ├─ SIMPLE   → §0 → 4 analysis(读 report/) → 5 root-cause? → 6 deliver
  ├─ Memory   → §0 → 1 → 2(perf --memory) → [3 符号恢复?按需] → 4 analysis(memory + 可选 high-load) → 5 root-cause? → 6 memory-deliverable
  └─ Full     → §0 → 1 → 2 → [3 符号恢复?按需] → 4 analysis → 5 root-cause? → 6 deliver
```

| 场景 | 阶段 Read |
|------|-----------|
| ReadOnly | 按需 analysis / root-cause / analysis-deliverable / memory-deliverable |
| PR-Impact | **pr-impact-analysis** + build + setup-* + perf-collect + analysis + root-cause + analysis-deliverable（两轮完整流水线 + 对比报告；+ gen-perf-report 仅按需符号恢复，两轮策略须一致） |
| 有源码构建 | build + setup-* + perf-collect + analysis + root-cause? + analysis-deliverable（+ gen-perf-report 仅按需符号恢复） |
| SIMPLE | analysis + root-cause? + analysis-deliverable（+ gen-perf-report 仅按需符号恢复） |
| Memory | memory-collect + memory-analysis + root-cause? + memory-deliverable（+ high-load 联合采集时） |
| Full | setup-* + perf-collect + analysis + root-cause? + analysis-deliverable（+ gen-perf-report 仅按需符号恢复） |

### TL;DR

| 步 | 阶段 | 动作 |
|:--:|:--:|------|
| 0 | 0 | §0 问路径 |
| 0.5 | — | Read 主 SKILL + 当前阶段 doc |
| 0.25 | — | `ensure-workspace-layout.sh <PROJECT_ROOT>` |
| 0.75 | 0.5 | **（可选）有源码时** `build --project-dir <源码> --build-mode debug` → 产出 HAP + `.so`（自动填充 §0 `so_dir`） |
| 1 | 1 | 判轨 → setup-binary / setup-source |
| 2 | 2 | perf-collect（产出 `report/` 全套分析器数据）；`--memory` 时附加内存采集（见 [memory-collect](workflow/memory-collect.md)） |
| 3 | 3 | **仅按需** gen-perf-report：符号恢复 `update --so_dir`（要符号级热点 / 火焰图 stripped 时）；未提则**跳过** |
| 4 | 4 | analysis：**读 `report/`** 做 high-load 分析（默认主线，不跑 update）；`--memory` 时并列做 [memory](analysis/memory-analysis.md) 分析 |
| 5 | 5 | root-cause：独立 `root-cause` CLI（多信号综合）+ Agent 补充深挖（借源码） |
| 6 | 6 | analysis-deliverable 落盘（融合 CLI 根因 + Agent 补充）；内存专题时用 [memory-deliverable](report/memory-deliverable.md) |

### TL;DR（PR-Impact 双轮对比）

| 步 | 阶段 | 动作 |
|:--:|:--:|------|
| 0 | 0 | §0 问路径 + **额外问 Git 标识 + 测试场景** |
| 0.5 | — | Read 主 SKILL + [pr-impact-analysis](workflow/pr-impact-analysis.md) + build + perf-collect + analysis + root-cause + deliverable |
| A | — | **Git 状态管理**：保存原始分支/commit/stash → checkout base（改动前） |
| B1-B7 | Pre | **改动前轮**：build → 编写 PerfLoad_*+prepare → perf → [符号恢复?] → analysis → root-cause → **pre 报告** |
| C | — | **应用 PR 改动**：cherry-pick / merge / apply patch |
| D1-D7 | Post | **改动后轮**：build → **复用脚本**+prepare → perf → [符号恢复?(策略一致)] → analysis → root-cause → **post 报告** |
| E | 6 | **对比报告**（comparison，逐指标对比 + 逐项评估 + 综合结论：优化/劣化/无明显影响/混合） |
| F | — | **恢复 Git 原始状态**（必须执行） |

### 状态机

| 状态 | 禁止 |
|------|------|
| `PATH_PROMPT` | Shell |
| `SKILL_READ` | Shell |
| `DISCOVER` | perf（环境未就绪） |
| `SCRIPT_AUTHORING` | 一次性写完全部步骤；写下一步操作前未验证上一步 |
| `EXECUTE` / `PARSE` / `ANALYZE` / `REPORT` | — |

### 脚本编写门禁（阶段 2 自写用例时强制）

自写 `PerfLoad_*` 时，引入 `step_verified` 门禁变量，**结构性强制逐步验证**：

| 变量 | 默认 | 设为 true 的条件 |
|------|------|------------------|
| `step_verified[N]` | `false` | 第 N 步操作已在设备上执行，且 Agent 输出了**验证证据**（Inspector dump / 截图 / 真机观察结论） |

| 状态 | 允许 | 禁止 |
|------|------|------|
| `step_verified[N]=false` | 在设备上执行第 N 步操作并采集验证证据 | 写第 N+1 步操作；落盘含第 N+1 步的脚本文件 |
| `step_verified[N]=true` | 写第 N+1 步操作代码 | — |

**执行规则**：
1. 每写一步 UI 操作，**必须先在设备上执行该操作**（`hdc shell` / `uitest dumpLayout` / 截图等），采集验证证据
2. Agent 在对话中输出验证结论（如「截图确认全屏播放器已打开，封面图和控制按钮可见」），此时 `step_verified[N]` 设为 `true`
3. 只有 `step_verified[N]=true` 后，才能写第 N+1 步操作代码
4. 若验证失败（操作未生效），必须**立即修正**该步参数并重新验证，禁止跳过
5. 所有步骤验证通过后，才能落盘完整脚本文件并执行 `prepare`
6. `prepare` 是最终完整性验证，**不是**首次验证操作是否生效的环节

**⚠️ 禁止**：一次性写完全部步骤后再验证；凭源码猜测坐标/手势参数不经设备验证就落盘脚本

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
| **PR-Impact** | [pr-impact-analysis.md](workflow/pr-impact-analysis.md) | **PR/commit 改动前后对比**：两轮 build→collect→analyze→root-cause→deliver + 对比报告；Git 状态管理 + 用例脚本复用 |
| 0.5 | [build.md](workflow/build.md) | **`build`**：deveco-cli 构建 debug HAP + .so 抽取；自动填充 §0 `so_dir` |
| 1a | [setup-binary.md](workflow/setup-binary.md) | GitCode 直链；§5 自检 |
| 1b | [setup-source.md](workflow/setup-source.md) | 7 步 + `scripts/validate-env.sh` |
| 2 | [perf-collect.md](workflow/perf-collect.md) | 预设→perf；禁止默认 gui-agent；**产出 `report/`** |
| 2m | [memory-collect.md](workflow/memory-collect.md) | **`--memory` 内存采集路由**：联合/纯内存/堆快照模式；`--memory` 采集时追加 Read |
| 3（可选） | [gen-perf-report.md](workflow/gen-perf-report.md) | **`update --so_dir`** 符号恢复（仅按需，默认 Agent；未提则跳过） |
| 3b（可选） | [symbol-recovery-standalone.md](workflow/symbol-recovery-standalone.md) | **三参数轻量**：仅 `perf.data` + SO + HTML；无源码/无 report 树；dist `symbol-recovery.exe` + Agent |

---

## §4 分析模式

- **Quick**：采集 + analysis（至少一个子 Skill，默认 high-load）+ 阶段 6 报告  
- **Full**：analysis 三项逐一评估 + 阶段 5 多信号综合 root-cause（CLI + Agent 补充深挖）  
- **PR-Impact**：双轮对比（改动前 + 改动后），各轮完整走 Full 流程，追加 comparison 报告（见 [`workflow/pr-impact-analysis.md`](workflow/pr-impact-analysis.md)）
- **Memory**：`--memory` 采集后 + analysis（memory 主线 + 可选 high-load）+ 阶段 6 内存专题报告（见 [`report/memory-deliverable.md`](report/memory-deliverable.md)）

---

## §5 analysis 路由（阶段 4）

[`analysis/README.md`](analysis/README.md) 索引。`perf` 后**直接读 `report/`**（默认不跑 update），按序评估：`high-load` → `memory`（`--memory` 采集时）→ `scroll-jank` → `symbol-recovery`；不满足则 `已跳过（原因）`。**high-load 为阶段 4 主线；`--memory` 采集时 memory 为并列主线**。

| 产物 / 信号 | 子 Skill |
|-------------|----------|
| 高负载 / 未知瓶颈（默认主线） | high-load |
| `--memory` 采集 / 内存泄漏 / 未释放 / meminfo | memory（[`analysis/memory-analysis.md`](analysis/memory-analysis.md)） |
| `trace.db` + 滑动/掉帧 | scroll-jank |
| `libxxx.so+0x...`（需符号级） | symbol-recovery（触发可选阶段 3 `update --so_dir`） |

**阶段 5 root-cause**：见 [`root-cause/comprehensive.md`](root-cause/comprehensive.md)（独立 CLI 多信号综合 + Agent 补充深挖）。

---

## §6 root-cause（阶段 5，独立·多信号综合）

权威文档：[`root-cause/comprehensive.md`](root-cause/comprehensive.md)。  
**脱离 `update`**：走独立 `root-cause` CLI（默认 `--checker comprehensive`，覆盖空刷/CPU热点/帧负载/线程/IPC/SO/内存/组件复用等全部信号）；CLI 覆盖不到的源码级深挖由 Agent 结合阶段 4 发现 + 源码逐类补充定位。CLI 结论与 Agent 补充融合进最终报告。

---

## §7 约束索引

| 主题 | 权威 |
|------|------|
| 路径门禁 | §0 |
| 分阶段 Read | 阶段 Read 清单 |
| **PR 改动前后对比** | **workflow/pr-impact-analysis** |
| 构建 debug HAP（可选阶段 0.5） | workflow/build |
| setup | workflow/setup-* |
| 采集 | workflow/perf-collect |
| 内存采集（`--memory`） | workflow/memory-collect |
| 可选符号恢复 | workflow/gen-perf-report |
| 高负载挖掘（阶段 4 主线） | analysis/* |
| 内存分析（阶段 4 并列主线） | analysis/memory-analysis |
| 多信号综合 root-cause（阶段 5，独立） | root-cause/comprehensive |
| Agent 交付（高负载） | report/analysis-deliverable |
| Agent 交付（内存专题） | report/memory-deliverable |

---

## §8 执行主流程

> 前置：`path_prompt_done=true` 且 `skill_read_done=true`。

§0 → Read 阶段 doc → 1 setup → 2 collect（产出 `report/`）→ [3 仅按需符号恢复 `update --so_dir`] → 4 analysis **读 `report/` 做 high-load 分析**（`hapray-tool-result.json` 取 `reports_path`；默认不跑 update）→ 5 root-cause（独立 CLI 多信号综合 + Agent 补充深挖，借源码）→ 6 [`analysis-deliverable`](report/analysis-deliverable.md) 落盘（**融合 CLI 根因 + Agent 补充**）。

> **内存并行流程**：当 `perf --memory` 采集时，阶段 4 并列执行 [`analysis/memory-analysis.md`](analysis/memory-analysis.md)（读 `hapray_report.db:memory_*`），阶段 6 产出 [`report/memory-deliverable.md`](report/memory-deliverable.md)（`hapray-analysis-*-memory-*.md`）。内存流程与 high-load 共享 §0/1/2/5，仅在阶段 4 和 6 分叉为独立主线。纯内存模式（`--no-trace --no-perf --memory`）时 high-load 不可用，仅走内存主线。

> **PR-Impact 双轮对比流程**：当用户提供 PR/Git 标识 + 测试场景时，走 [`workflow/pr-impact-analysis.md`](workflow/pr-impact-analysis.md) 双轮流水线：① Git 状态保存 → ② 改动前轮（build→collect→analyze→root-cause→pre 报告）→ ③ 应用 PR 改动 → ④ 改动后轮（build→collect→analyze→root-cause→post 报告）→ ⑤ 对比报告（comparison）→ ⑥ 恢复 Git 状态。两轮**必须复用同一 `PerfLoad_*` 脚本**、同一设备、相同采集参数。产出 3 份报告（pre + post + comparison，见 [`report/analysis-deliverable.md`](report/analysis-deliverable.md)）。

---

## §9 异常与降级

| 情况 | 动作 |
|------|------|
| 二进制下载失败 | setup-source |
| 无预设用例 | 写脚本 + prepare → perf |
| 缺 trace 等 | 子 Skill 跳过 + 补采命令 |
| 火焰图热点为 stripped 地址 | 阶段 3 按需 `update --so_dir`；否则标注「建议符号恢复」，SO/帧/线程级照常 |
| 无源码（root-cause） | root-cause 降级为 analyze（仅证据无行号）或仅做 perf 产物级根因；空刷等可选信号缺失时 CLI 自动跳过该信号 |
| `result-file` 损坏 | 仅证据报告 |
| `--memory` 采集但 `memory_records` 为空 | 标注「内存采集失败（nativehook 未运行）」；检查 hiprofiler_cmd 日志；GC 分析仍可用（若有 perf.db + trace.db） |
| 纯内存模式（`--no-trace --no-perf`） | high-load 跳过（无 `perf_sample`）；GC 分析跳过（无 `perf.db` + `trace.db`）；仅做 memory 主线分析 |
| 内存 callchain 符号为 `[unknown]` | 标注「需 symbol-recovery」；按需触发阶段 3 `update --so_dir` 后重分析 |
| **PR-Impact：cherry-pick/merge 冲突** | **STOP**，提示用户解决冲突后继续；不跳过冲突强行构建 |
| **PR-Impact：Post 轮 `PerfLoad_*` 失效（UI 改动）** | 标注「PR 改动导致 UI 变化，前后不可严格对比」；降级为两份独立分析（非严格对比） |
| **PR-Impact：Post 轮构建失败** | 检查是否 PR 引入编译错误；标注「Post 轮构建失败，对比报告仅基于 Pre 数据」 |
| **PR-Impact：Git 状态恢复失败** | 输出 `original_branch`/`original_commit`，指导用户手动 `git checkout` 恢复 |

---

## §10 命令模板

> ⛔ 门禁未过禁止执行。

### 工作区初始化（两轨共用，最先执行）

```bash
bash <SKILL_DIR>/scripts/ensure-workspace-layout.sh "<PROJECT_ROOT>"
```

### 阶段 0.5（可选）build —— 从源码构建 debug HAP

```bash
# 仅当用户有 HarmonyOS 源码工程时执行；产出 HAP + .so（自动填充 §0 so_dir）
# 源码轨：
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" \
  --build-mode debug \
  --product default \
  [--modules entry] \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# 二进制轨：用 <RUNTIME_ROOT>/.../perf-testing build ...
# 读取 hapray-tool-result.json outputs.so_dir 作为 §0 so_dir
```

### 源码轨（1 setup → 2 collect）

```bash
cd <REPO_ROOT> && bash <SKILL_DIR>/scripts/validate-env.sh
# 用例 MUST 写在 <PROJECT_ROOT>/testcases/<包名>/
bash <SKILL_DIR>/scripts/sync-testcases-to-runtime.sh "<包名>" "<PROJECT_ROOT>"   # 二进制轨
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --round 1 \
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

> **⚠️ 关键警告**：`update --so_dir` 会**自动触发完整符号恢复流程**（导出→推断→导入→生成增强火焰图），耗时5-15分钟。
> - **执行一次即可**，使用 `AwaitShell` 等待完成
> - **禁止**在 `update` 执行期间或完成后，手动再次执行 `symbol-recovery.exe`
> - 产物验收：`hiperf_report_with_inferred_symbols.html` 存在即表示完成

### 阶段 4 analysis high-load（读 `report/`，**默认不跑 update**）

```bash
# 从 hapray-tool-result.json 取 reports_path，对 report/ 与 hiperf/step*/perf.db 做分析
# 具体 SQL 与维度见 analysis/high-load-analysis.md
sqlite3 <用例>/hiperf/step5/perf.db "PRAGMA table_info(perf_sample)"
```

### 阶段 4 analysis memory（`--memory` 采集时，与 high-load 并列）

```bash
# 检查内存数据是否可用
sqlite3 <用例>/report/hapray_report.db "SELECT COUNT(*) FROM memory_records"
# 具体 SQL 与维度见 analysis/memory-analysis.md
```

### 阶段 6 deliver（内存专题，`--memory` 采集时）

```bash
# 交付报告模板见 report/memory-deliverable.md
# 命名：hapray-analysis-<YYYYMMDD>-<app>-memory-<suffix>.md
```

### 阶段 5 root-cause（独立，**脱离 update**，多信号综合）

```bash
# 多信号综合分析（默认 --checker comprehensive）：--source-dir 提供 §0 源码路径以启用 with_source 行级根因
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --source-dir "<§0_源码>" \
  [--index-dir "<§0_源码>/index"]

# ⚠️ 禁止默认使用 --skip-llm！会使 root_cause.md 全部 Pending，阻塞阶段 6。
# --skip-llm 仅当用户明确要求"仅提取证据"时使用，且使用后必须完成 Agent 闭环（见 comprehensive.md §〇.3）。
# 默认 Agent 编排模式不需要 LLM API key——CLI 导出任务 JSON，由当前 Agent 完成推断后重跑 CLI。

# 精选信号类别：追加 --categories cpu-hotspot,empty-frame,thread
# CLI 覆盖不到的源码级深挖由 Agent 补充（见 root-cause/comprehensive.md §〇.2）
```

> **Agent 闭环（MUST）**：首次运行后 `root_cause.md` 含 `Pending Agent Inference` 时，**禁止直接写阶段 6 报告**。必须按 [`comprehensive.md`](root-cause/comprehensive.md) §〇.3 完成：
> 1. Read `root_cause_agent_task.json` + `root_cause_evidence.md`
> 2. Agent 按 `expected_schema_json` 写 `root_cause_agent_result.json`
> 3. 重跑 `root-cause` CLI → 产出正式 `root_cause.md`（无 Pending）
> 4. 验收通过后才能进入阶段 6

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

### PR-Impact（PR/commit 改动前后对比，详见 [workflow/pr-impact-analysis.md](workflow/pr-impact-analysis.md)）

```bash
# === 阶段 A：Git 状态管理（在 <HarmonyOS源码工程根> 下） ===
cd "<HarmonyOS源码工程根>"
git rev-parse --abbrev-ref HEAD    # 保存 original_branch
git rev-parse HEAD                 # 保存 original_commit
git status --short                 # 保存 original_status
git stash push -m "hapray-pr-impact-temp"  # 若有未提交改动
# checkout 到 base（改动前）版本
git checkout <base_commit>         # commit 类型：目标提交的父提交；branch 类型：当前 HEAD 即 base

# === 阶段 B：改动前轮（Pre Round） ===
cd <REPO_ROOT>/perf_testing
# B1. 构建 debug HAP + 安装（base 代码）
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" --build-mode debug \
  --product default --install --uninstall \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# B2. 编写 PerfLoad_* + prepare 验证（仅首次，按 perf-collect.md 流程）
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
# B3. perf 采集 → report/（pre_timestamp）
uv run python -m scripts.main perf --run_testcases "PerfLoad_<用例名>" --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# B4. [可选] 符号恢复（两轮策略须一致）
uv run python -m scripts.main update --report_dir <PROJECT_ROOT>/reports/<pre_timestamp> \
  --so_dir "<§0_SO>" --result-file <PROJECT_ROOT>/hapray-tool-result.json
# B5-B6. analysis + root-cause（按标准阶段 4/5 流程）
# B7. 交付 pre 报告 → reports/hapray-analysis-<YYYYMMDD>-<app>-load-pre.md

# === 阶段 C：应用 PR 改动 ===
cd "<HarmonyOS源码工程根>"
git cherry-pick <commit_hash>      # commit 类型
# 或：git merge <branch_name>      # branch 类型
# 或：git apply <patch_file>       # patch 类型
git log --oneline -3               # 验证改动已生效

# === 阶段 D：改动后轮（Post Round，复用同一 PerfLoad_* 脚本） ===
cd <REPO_ROOT>/perf_testing
# D1. 构建 debug HAP + 安装（PR 改动后代码）
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" --build-mode debug \
  --product default --install --uninstall \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# D2. 复用脚本（禁止重写），prepare 确认可行
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
# D3. perf 采集 → report/（post_timestamp，禁止覆盖 pre 目录）
uv run python -m scripts.main perf --run_testcases "PerfLoad_<用例名>" --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
# D4-D6. [可选]符号恢复(策略一致) + analysis + root-cause
# D7. 交付 post 报告 → reports/hapray-analysis-<YYYYMMDD>-<app>-load-post.md

# === 阶段 E：对比报告 → reports/hapray-analysis-<YYYYMMDD>-<app>-load-comparison.md ===

# === 阶段 F：恢复 Git 原始状态（必须执行） ===
cd "<HarmonyOS源码工程根>"
git checkout <original_branch>
git stash pop    # 若阶段 A 执行了 stash
git rev-parse HEAD    # 验证恢复到 original_commit
```

---

## §11 明确禁止

- 门禁未过跑 Shell；**产出写 `<PROJECT_ROOT>` 外**（含未重定向的 `~/ArkAnalyzer-HapRay`）；默认 GitHub  
- 跳过 `ensure-workspace-layout.sh` 直接 `perf`/`update`（macOS 必炸到主目录）  
- 用例只写在 Release 包 `_internal/` 或 `<REPO_ROOT>` 而不落盘 `<PROJECT_ROOT>/testcases/`  
- 无预设时默认 gui-agent / `perf --manual`  
- **未提符号恢复却默认跑 `update`**（perf 后应先读 `report/` 做高负载分析）；**把 root-cause 绑死在 `update` 上**（应走独立 `root-cause` CLI（默认 `--checker comprehensive`）+ Agent 补充深挖）  
- **符号恢复重复执行**：`update --so_dir` 已自动触发完整符号恢复，**禁止**再手动执行 `symbol-recovery.exe`（使用 `AwaitShell` 等待完成即可）  
- 符号恢复确需执行时无故 `--symbol-recovery-no-llm`；伪交付 / 虚构数据  
- **`perf` 已成功产出 `report/summary.json` 后重复执行 `perf`**（须先检查已有报告是否存在，存在则直接进阶段4，禁止重跑）
- **脚本步骤不验证操作是否生效（`step_verified` 门禁违反）**：关键 UI 操作（展开播放器、切换页面、弹出面板等）发完指令就继续，不验证目标界面是否真正出现；**必须遵循 `step_verified` 门禁**（见状态机），写一步 → 设备上执行一步 → 输出验证证据 → `step_verified[N]=true` → 才能写下一步；**⛔ 一次性写完全部步骤后再验证，等价于 `path_prompt_done=false` 时执行 Shell**；未生效则立即修正，禁止带缺陷脚本进入 `prepare`
- **PR-Impact 违规**：① 两轮使用不同的 `PerfLoad_*` 脚本（破坏对比基线）；② 两轮符号恢复策略不一致；③ Post 轮覆盖 Pre 轮报告目录；④ 遗忘 Git 状态恢复（阶段 F）；⑤ 未保存原始 Git 状态就 `git checkout`/`git reset`；⑥ Post 轮重写用例脚本（非 UI 失效原因）
- **长命令返回后停顿**：`devecocli build` / `perf` / `prepare` / `root-cause` 等长耗时命令成功返回后，**必须立即**在同一轮回复中发出下一步命令（build→install→UI探测 / prepare→perf / perf→analysis）；**禁止**在命令返回后结束当前回复或等待用户催促；仅当命令**失败**时才允许停下报告错误

---

## §12 参考

- [`schemas/hapray-tool-result.md`](schemas/hapray-tool-result.md) + [`hapray-tool-result-v1.json`](schemas/hapray-tool-result-v1.json)
- `workflow/` · `analysis/` · `root-cause/` · `report/`  
- 源码仓可选：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`（**发布包无 `docs/`**）
