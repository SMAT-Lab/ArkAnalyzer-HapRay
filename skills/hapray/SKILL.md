---
name: hapray
version: "1.5.4"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
description: |
  【硬门禁·最先执行】path_prompt_done=false 时：禁止任何 Shell/终端命令（含 npm/uv/curl/hdc/perf/update/prepare/build）。唯一允许：在对话中发出 §0 必问模板并结束本轮，等用户下一条回复。用户已给路径或跳过/设备拉取后设 path_prompt_done=true 方可继续。
  产出落盘当前工作区<PROJECT_ROOT>；无特殊说明禁止GitHub。HapRay：§0路径门禁→构建→perf→update。详见 SKILL.md。
metadata:
  short-description: >-
    BLOCK: path_prompt_done=false → no terminal commands at all; only post §0 path question and wait. Then hapray workflow.
  zh-Hans: >-
    硬门禁：未 path_prompt_done 前禁止一切终端命令，只能对话发问 §0 并等待。之后才是构建/perf/update。
  skill-paths:
    main: SKILL.md
    tool_result: hapray-tool-result.md
    analysis_index: analysis/README.md
  tags:
    - hapray
    - arkanalyzer-hapray
    - openharmony
    - harmonyos
    - performance
    - trace
    - perf-testing
    - gui-agent
    - hapray-tool-result
    - hapray-sa-cmd
    - static-analyzer
    - source-repo-setup
    - clone-first-build
    - symbol-recovery-llm-fallback-agent
    - llm-failure-must-agent-mode
    - root-cause-agent-mode
    - update-integrated-root-cause
    - app-packages-hap-download
    - must-ask-user-so-and-root-cause-paths-first
    - block-cli-until-paths-confirmed
---

# HapRay 引导式工作流

## 全局规范（默认生效，优先于路径臆造）

### 0) 完整阅读 Skill：执行前必须通读全文，禁止偷工减料

**任何 Agent 在执行本 Skill 中的任何内容之前，必须完整通读整个 SKILL.md 文档全文**，包括但不限于：
- 文首 YAML `description` 中的硬门禁声明
- 全部章节（§0–§16）及子章节
- 所有命令模板、禁止项、失败速查表

**禁止行为**：
- ❌ 仅阅读 TL;DR 或 §1 摘要后直接执行命令
- ❌ 跳过 §0 硬门禁、§4 源码构建清单、§6 符号恢复细节等「看起来不相关」的章节
- ❌ 凭记忆或片段印象臆造路径、参数、命令顺序
- ❌ 将「曾经读过」视为「本次已读」——每次会话重新完整阅读

**执行前自检**：
```text
[自检] 是否已完整阅读 §0–§16 全文？→ 否则 STOP，先 Read 完整文档
[自检] 是否理解当前任务涉及的所有章节？→ 否则重新阅读对应 §
```

---

### 1) 产出文件落盘：当前工作区，禁止乱放

**`<PROJECT_ROOT>`** = 用户当前在 Cursor/IDE **已打开的工作区根目录**（本仓库即 ArkAnalyzer-HapRay 根，或用户打开的外层项目根）。本会话 Skill 生成的**一切**文件须尽量落在该目录树下，**禁止**随意写到无关路径。

| 类型 | 默认目录（均在 `<PROJECT_ROOT>` 下） |
|------|--------------------------------------|
| HapRay 采集产物（`perf` / `gui-agent`） | `perf_testing/reports/<timestamp>/`（源码轨 `-o` 相对此树）；或用户明确指定的子目录 |
| 独立分析报告 | `reports/hapray-analysis-<YYYYMMDD>-<topic>.md` |
| Agent 自写 `PerfLoad_*.py` | `perf_testing/hapray/testcases/<包名>/`（源码轨） |
| UI 探测 / 临时 Inspector | `perf_testing/reports/_ui_probe_<包名>/` 等**工作区内**临时目录 |
| 二进制下载 zip/dmg | 工作区内如 `downloads/` 或 `.cache/hapray-release/`，解压目标记为 `<RUNTIME_ROOT>`（仍在工作区或用户指定盘符下） |

**禁止（除非用户明确要求）**：`/tmp`、`%TEMP%`、用户桌面、与当前工作区无关的盘符路径、仓库外的随意 `C:\Users\...\` 散落；把报告只写在 Agent 内部而用户工作区找不到。

执行前在轨迹中写明：`project_root=<绝对路径>`、主要产出路径列表。

### 2) 网络与托管：默认禁止 GitHub

当前环境 **GitHub 常不可用**（`github.com` 不通或极慢）。**无用户特殊说明时**：

| 禁止 | 改用 |
|------|------|
| `git clone https://github.com/...` | **`git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git`**（§3.2 源码回退） |
| 从 GitHub Releases 下载二进制/工具 | **GitCode** `releases/download/...` 直链（§3）、`winget` / `choco` / `brew` |
| `raw.githubusercontent.com`、GitHub API、Issues/PR 链接当下载源 | GitCode 同源文档或用户本地已有文件 |
| 为 radare2/r2pm 等**默认**去 GitHub 拉取 | 包管理器安装；装不上则**跳过**（§4 第 5 步建议项），**勿死等** GitHub |

**仅当用户在同一会话中明确要求**「从 GitHub 拉 / 用某 github 链接」时，方可访问 GitHub，并须在轨迹注明 `github_explicit=true`。

---

> ## ⛔ Agent 硬门禁（优先于本文其余一切，含 TL;DR / §11 / 命令模板）
>
> **会话变量**：`path_prompt_done` — 默认 **`false`**，仅当 §0 已满足「用户已答复」判定（见下）后设为 **`true`**。
>
> | `path_prompt_done` | 允许 | 禁止 |
> |--------------------|------|------|
> | **`false`** | ① 向用户**在对话中**发出 §0「必问模板」全文；② 回答与路径无关的澄清问题 | **一切** `Shell`/`run_terminal_cmd`/`uv`/`npm`/`curl`/`hdc`/`git`/`python -m scripts.main`/`hapray`/`perf-testing`；含「先构建环境」「先查设备」「先下载二进制」 |
> | **`true`** | 按 §1 起后续流程 | 仍禁止臆造路径；update 须带 §0 记录的 `--so_dir` / `--app-packages-dir` |
>
> **常见失效原因（必须避免）**：用户说「跑 perf / 分析性能」→ Agent 直接去 `npm run build`、`prepare`、`perf`；或把必问模板只写进报告、用户看不到。**正确做法**：第一条实质性回复 = **仅**必问模板（或确认用户同条消息已给路径），**本轮不得**附带任何终端命令；等用户**下一条**回复后再 `path_prompt_done=true` 并执行 CLI。
>
> **每次拟执行终端命令前**（即使用户已说「继续」），先自检：
>
> ```text
> [§0] path_prompt_done == true ?  → 否则 STOP，先发必问模板，不执行本命令
> [§0] 本命令是否 hapray/perf/update/prepare/root-cause/hdc 采集链 ?  → 是且 path_prompt_done==false 则禁止
> ```
>
> 细则全文：**§0**。

目标：让 Agent 以更短路径完成 **按直链获取二进制发布包（失败回退源码）→ 采集/执行 → 解析产物 → 子 Skill 深入分析 → 独立报告落盘**，并具备可恢复、可审计、可机读的执行闭环。

## 文档地图（阅读顺序）

| 章节 | 内容 | 何时必读 |
|------|------|----------|
| **全局规范** | 完整阅读 Skill（§0）、产出落盘 `<PROJECT_ROOT>`；默认禁止 GitHub | **每次**会话开始，**执行任何命令前** |
| **§0** | 双路径阻塞门禁（SO + root-cause 输入） | 会话内**第一次**跑任何 HapRay CLI 之前 |
| **§1** | TL;DR + 执行状态机 | 总览与阶段检查点 |
| **§2** | 路径术语 + 源码轨/二进制轨分叉 | 判定 `<REPO_ROOT>` / `<RUNTIME_ROOT>` |
| **§3** | 识别系统 → 拼唯一直链 → `curl` 下载（不查发布页） | 获取运行环境 |
| **§4** | 源码工作区硬门禁（7 步构建） | **仅**源码轨，先于 perf/update |
| **§5** | 二进制发布包模式 | **仅**二进制轨 |
| **§6** | update、双路径参数、符号恢复、root-cause | perf/gui-agent **之后**必须 update |
| **§7** | 真机采集路由（perf / prepare / gui-agent） | 需设备采集 perf+trace |
| **§8** | Quick / Full 分析模式 | 分析深度选择 |
| **§9** | 子 Skill 路由 | 专题分析 |
| **§10** | MUST / SHOULD / MAY + 门禁索引 | 约束汇总（细则见各 §） |
| **§11** | 统一执行主流程 | 端到端步骤清单 |
| **§12–§16** | 异常降级、输出结构、命令模板、禁止项、参考 | 收尾与模板 |

> **去重原则**：同一规则只在**一处**写全；其余章节用「见 §X」引用，避免 TL;DR、门禁、主流程三处重复粘贴。

---

## §0 会话开头阻塞门禁：双路径确认（最高优先级，默认 MUST）

> **为何经常「拦不住」**：① 模型把 §0 当成「update 前再问」而先跑 `perf`/`prepare`/构建；② 同一条回复里既发问又 `Shell`；③ 用户说「继续/跑吧」但未给路径仍执行；④ `path_prompt_done` 未显式维护，默认当已完成。**本节 + 文首硬门禁表**要求：`path_prompt_done=false` 时**零终端命令**，先对话、后 CLI。

### 何时触发（满足任一即触发）

- 用户要跑 **`perf`**、**`update`**、**`perf`→`update` 全流程**、**`gui-agent`**（且后续会做 update）、**`root-cause`**、**`prepare`**、**`static`**，或分析已有报告且需要 **符号恢复 / 空刷根-cause**；
- 用户说「分析性能」「跑一遍 hapray」「生成报告」「帮我测一下」等，且按本 Skill 会进入上述命令；
- **只要**你计划在本会话内调用 HapRay 相关 CLI 或为其做环境构建（`npm run build`、`uv sync`、`curl` 下二进制、`hdc` 采数），**即视为触发**，与是否已读 §4/§7 无关。

**未触发（可不跑 §0 发问）**：用户明确「只读某份已有 `hapray_report.html` / 只解释 Skill 条文」且**确认**本会话不执行任何终端命令、不做 update/符号恢复/root-cause。

### Agent 必须执行（不可省略）

1. **设 `path_prompt_done=false`**（会话开始默认；若不确定则视为 false）。
2. **STOP 一切终端**：在步骤 4 完成前，**禁止** Shell（含后台）。**特别禁止**以「先构建/先下载/先查 hdc」为由绕过 §0。
3. **仅一轮对话输出**：在**面向用户的回复**中发出下方「必问模板」**全文**（可改 `<包名>`，须保留两项路径 + 跳过/设备拉取）。**禁止**与模板同条消息内执行任何工具调用。
4. **等待用户下一条用户消息**（不是助手自己的「我继续」）：收到路径 / 跳过 / 设备拉取后 → 设 `path_prompt_done=true`，记录 `so_dir_user`、`app_packages_dir_user`。
5. **之后**方可执行 §1 及以后步骤（构建、perf、update 等）。

### 视为「用户已答复」（满足其一即可 `path_prompt_done=true`）

| 用户表述 | Agent 记录 |
|----------|------------|
| 给出 **SO 目录** 绝对/相对路径 | `so_dir_user=<路径>`，update 时加 `--so_dir` |
| 给出 **root-cause 输入** 路径（源码树或 HAP 目录） | `app_packages_dir_user=<路径>`，update 时加 `--app-packages-dir` |
| 「跳过 SO」「不要符号恢复」 | 不填 SO；update 可加 `--symbol-recovery-no-llm`（须用户明确） |
| 「跳过 root-cause」「不要根因」 | `--no-root-cause` |
| 「都从手机拉」「设备拉取」 | 两路径留空，允许后续 hdc 兜底 |
| 消息中已含 `--so_dir` / `--app-packages-dir` 或 `HAPRAY_SO_DIR` / `HAPRAY_APP_PACKAGES_DIR` | 同条消息可 `path_prompt_done=true`；**仍建议**复述路径并确认；**同条消息仍禁止**附带 Shell |
| 用户仅说「继续」「跑吧」「开始」但**从未**给路径或跳过/拉取 | **不算**答复；**保持** `path_prompt_done=false`，**再次**发必问模板 |

### 必问模板（须在对话中发给用户，禁止只写进报告）

```text
在开始跑 HapRay（perf / update / 符号恢复 / 空刷根因）之前，需要先确认两个本地目录（从手机拉取 SO/HAP 经常失败，建议提前备好）：

1) SO 目录（符号恢复用，目录内应有 *.so）
   例：D:/artifacts/<应用名>/libs/arm64
   → 回复路径，或回复「跳过 SO」

2) root-cause 输入目录（工具会自动识别，二选一即可）
   · 反编译/源码树（推荐）：含 *.ts 或 decompiled/index/
   · 仅 HAP 包：含 *.hap 的文件夹
   例：D:/artifacts/<应用名>/decompiled/ 或 D:/artifacts/<应用名>/hap/
   → 回复路径，或回复「跳过 root-cause」

也可回复「全部从设备拉取」尝试 hdc（可能失败则自动跳过对应步骤）。

请直接回复上述路径（可只给其中一项）。收到后我再开始执行命令。
```

### 禁止行为（§0 违反 = 流程失败，须中止并道歉）

- ❌ `path_prompt_done=false` 时执行**任何** Shell（含 `npm install`、`uv sync`、`curl` 下载、`hdc`、`prepare`、`perf`、`update`）
- ❌ 同一条 assistant 回复里：既发必问模板又执行工具
- ❌ 未在**用户可见对话**中发必问模板就跑 CLI
- ❌ 用户**下一条**消息之前臆造路径、默认设备拉取并开跑
- ❌ 用户只说「继续」但未给路径 → 仍执行后续任务
- ❌ 已完成 `perf` 才发现没问路径 → **不得**悄悄 `update`；须补问路径或向用户说明 SO/root-cause 可能缺失

### 已违规时的补救（MUST）

若本会话已在 `path_prompt_done=false` 时跑过 HapRay 相关命令：

1. **立即停止**后续 CLI；向用户说明 §0 未执行。  
2. **补发**必问模板并等待回复；`path_prompt_done=true` 后再继续（含补跑 `update`）。  
3. 不得基于不完整符号恢复/root-cause 伪称「分析已完成」。

### 受 §0 约束的命令形态（命中任一则须 `path_prompt_done=true`）

`python -m scripts.main`、`hapray`、`perf-testing`、`scripts/main.py perf|update|prepare|root-cause|gui-agent|static`、`uv run`（在 `perf_testing` 下）、`npm run build`（为 HapRay 跑 perf/update 做准备）、`hdc`（为采集/拉 SO/HAP）、仓库内 `curl` 下 HapRay 二进制（§3）。

---

## §1 执行总览（TL;DR + 状态机）

### TL;DR（30 秒）

| 步 | 动作 | 详见 |
|:--:|------|------|
| 0 | **§0** 双路径必问并**等待用户下一条回复**；此前禁止任何 CLI | §0 |
| 1 | 二选一运行轨：源码轨 → §4 七步门禁；二进制轨 → §5 最小自检 | §2、§4、§5 |
| 2 | 无现成环境时：§3 识别系统后拼直链 `curl` 下载，失败则 §4 源码回退 | §3 |
| 3 | 真机采集：预设 `perf` → 无则写脚本 + **`prepare` 通过** → `perf`；仅用户明确要求才 `gui-agent` | §7 |
| 4 | 采集后**必须** `update`（§6：符号恢复默认 Agent + 默认 root-cause） | §6 |
| 5 | 解析 `hapray-tool-result.json` → 子 Skill（§9）→ 独立报告落盘 | §9、§13 |

**不可省略的硬规则**（细则见 §6、§7、§10）：**`path_prompt_done=true` 前零 Shell**；`perf` 后必 `update`；禁止无故 `--symbol-recovery-no-llm`；用户已给 SO/HAP 路径则 update **禁止 hdc 拉取**；无预设脚本时禁止默认 `gui-agent` / `perf --manual`。

### 执行状态机与检查点（可恢复）

每个阶段输出：`状态(成功/失败/降级)`、`path_prompt_done`、`证据`、`下一动作`。

| 状态 | 含义 | 进入条件 | **禁止**（未满足进入条件时） |
|------|------|----------|------------------------------|
| `PATH_PROMPT` | §0：对话发模板，**等待用户下一条** | 会话开始或 `path_prompt_done=false` | **一切** Shell；`DISCOVER`/`EXECUTE`/构建/下载/采集 |
| `DISCOVER` | 路径判定、§4/§5 自检、`hdc` 检查 | **`path_prompt_done=true`** | `perf`/`update`/`prepare` |
| `EXECUTE` | `prepare`/`perf`/`gui-agent`/`update` 等 | `DISCOVER` 通过 | — |
| `PARSE` | 读 `hapray-tool-result.json` | `EXECUTE` 完成 | — |
| `ANALYZE` | 子 Skill | `PARSE` 完成 | — |
| `REPORT` | 独立 `.md` | — | — |

**状态机铁律**：`PATH_PROMPT` 未完成时，不得以「用户急 / 先跑起来 / 环境要先装」为由进入 `DISCOVER` 或 `EXECUTE`。

---

## §7 真机采集路由（预设脚本优先，MUST）

> **范围**：真机场景下需要「跑脚本/UI 操作并采 perf+trace」时（`perf` 全流程等）。**SIMPLE 模式**（已有 `perf.data` + `trace.htrace`）直接 `update`，不适用本节。  
> **阅读顺序**：环境门禁见 **§2–§6**；本章内小节编号（如 §7 内「1.5 UI 映射」）仅在本章有效。

### 决策顺序（严格执行，禁止跳步）

| 优先级 | 条件 | 执行动作 | 记录字段 |
|:------:|------|----------|----------|
| **1** | `testcases/<包名>/` 下存在 `PerfLoad_*.py` 或 `PerfLoad_*.yaml`（或 `--run_testcases` 能匹配） | `perf --run_testcases "<用例名>" --apps <包名> …` | `collection_mode=predefined` |
| **2** | 上一步**无**匹配用例，且用户**未**明确要求 `gui-agent` / 「AI 探索」 | **按本应用编写** `PerfLoad_*` → **`prepare` 完整试跑**（须通过）→ `perf --run_testcases`（见下节） | `collection_mode=agent-authored` |
| **3** | 用户**明确**要求 `gui-agent` / 「AI 探索 UI」/ 「无脚本让模型点手机」 | `gui-agent --apps <包名> [--scenes "…"] …`（需 `GLM_API_KEY`） | `collection_mode=gui-agent` |
| **禁止默认** | 无预设用例、用户未要求 gui-agent | ❌ **不得**默认 `gui-agent`；❌ **不得** `perf --manual` / `PerfLoad_Manual`（仅 `sleep(30)`） | — |

**包名**须通过 `hdc shell bm dump -a` 等设备查询确认，禁止臆造。

### 发现预设用例（进入 `perf` 前 MUST）

1. **源码轨**：`<REPO_ROOT>/perf_testing/hapray/testcases/<包名>/`  
   **二进制轨**：`<RUNTIME_ROOT>/testcases/<包名>/`（若存在；否则同源码路径或用户给出的外部 `testcases/`）。  
2. 收集 `PerfLoad_*`（`.py` / `.yaml`），在执行轨迹写明：`predefined_cases=[...]`。  
3. 多个用例：用户指定 > 默认选与场景最相关的一条（须说明理由）。  
4. `--run_testcases` 在磁盘上匹配失败 → 视为「无预设用例」→ 走优先级 **2**（写脚本），**不是** gui-agent。

> **预设用例惯例**：`setup()` 已清场；`process()` 首步 `start_app()` 再进业务；文案一般**不写**「冷启动专测」；采集中避免 `swipe_to_home` 等退应用操作；`teardown()` 负责退出。

### 无预设用例时：Agent 按目标应用编写 `PerfLoad_*`（优先级 2，默认路径）

**禁止**因「没有现成脚本」就直接 `gui-agent`。

#### 核心原则（MUST）

| 原则 | 说明 |
|------|------|
| **禁止照搬他案用例** | 不得把其他 `testcases/<其他包名>/` 里的包名、坐标、Tab 文案、页面顺序、Ability 名原样套到当前应用。那些文件**仅**可参考 `PerfTestCase` 的**类结构**与 `execute_performance_step` 用法，**不是**可复制的业务步骤。 |
| **必须结合本应用** | 若 §0 提供且目录含**应用源码**：步骤须来自**源码分析** + 用户场景；否则来自包名、用户场景、本机 UI（截图/控件树/hdc），及 `wm size` 等。 |
| **长等待保持亮屏** | 步骤间隔/ `sleep` / `wait` 过长须 `wake_up_display()` 或分段唤醒；**息屏、黑屏挂机跑完**视为无效（`prepare` 不得判通过）。 |
| **步骤宜精** | 覆盖用户关心的**一条主路径**即可，避免无依据的多 Tab、十几次子点击或「全功能遍历」；步数由**本应用真实交互**决定，不机械套用其他 app 的步数。 |
| **UI 映射探测** | **编写脚本前**须检查 Inspector 组件 `id` 映射；若可点击节点 **ID 全空** → 必须用**纯坐标**操作（见 §1.5），**禁止**依赖 `touch_by_id` / 无依据的 `touch_by_text`。 |
| **步骤注释可读** | 脚本内**多写中文注释**：说明每步在做什么、点哪个控件、坐标/文案依据；**禁止**无注释的裸坐标或裸 `sleep`。 |
| **`prepare` 硬门禁** | 编写后必须用 **`prepare` 完整跑通**用例；逐步操作须成功、运行流畅，**禁止**未通过就 `perf`。 |
| **应用启停（与框架一致）** | `PerfTestCase.setup()` 已 `stop_app()` + 回桌面；`process()` **开头须 `start_app()`**（打开目标 app 再进入业务步骤）；`teardown()` 已 `stop_app()`，用例结束**会退出应用**。自写脚本**勿重复**在 `setup`/`teardown` 里改退出逻辑。 |
| **勿写「冷启动」专测** | **禁止**把用例做成冷启动**专项**（如 `reboot_device()`、步骤名/描述写「冷启动场景」、仅 `start_app`+回桌面采一条冷启 trace），除非用户**明确要求**冷启动压测。这与「首步 `start_app` 打开应用」**不是一回事**。 |
| **采集中勿中途退应用（自写）** | 在 `execute_performance_step` **执行期间**须保持目标 app 前台：禁止 `stop_app()`、Home/`swipe_to_home`、`swipe_to_back`（若会退出应用）、切其他包；仅应用内 Tab/页面/控件导航。 |

#### 脚本生命周期（预设与自写共用，见 `perf_testcase.py`）

| 阶段 | 框架行为 | Agent 编写要求 |
|------|----------|----------------|
| `setup()` | `stop_app()` → 亮屏 → `swipe_to_home()` | 一般**不要**覆盖；用例从「未打开目标 app」开始 |
| `process()` 开头 | — | **须** `start_app(...)`（或等价打开本应用 Ability），再写业务步骤 |
| `execute_performance_step` 内 | 采集 perf+trace | **保持应用内**操作，勿中途退应用（见上表） |
| `teardown()` | `stop_app()` + 生成报告 | **须**保留；用例跑完**必须**退出应用，自写脚本**禁止**在末步再 `stop_app` 代替 teardown |

#### 流程

```text
确认包名与场景 → [有应用源码? 分析源码定步骤 : 收集 UI 依据]
  → UI 坐标映射探测（§1.5）→ 编写 PerfLoad_*（process 首步 start_app → 应用内步骤 → 依赖 teardown 退出）
  → prepare 完整试跑（失败则改脚本再 prepare）→ 通过 → perf → update
```

#### 1) 编写前路由：源码优先 vs 无源码（MUST）

§0 已确认的 **root-cause 输入目录**（`app_packages_dir_user` / `--app-packages-dir` / `HAPRAY_APP_PACKAGES_DIR`）按下列规则分支；**未提供或用户跳过**则走 **B 无源码**。

| 分支 | 判定（满足其一即视为「有应用源码」） | 编写依据 |
|------|--------------------------------------|----------|
| **A 有源码** | 目录下存在可分析的**应用源码/反编译树**：含足够 `*.ts` / `*.ets`、`decompiled/` + `index/`、`src/main/ets/`、`decompiled/index/symbol_index.jsonl` 等（与 `detect_root_cause_input_kind` → `source` 一致，见 `perf_testing/hapray/core/common/device_app_packages.py`） | **必须先阅读、分析该目录源码**，再编写用例；步骤、页面名、按钮文案、Ability 名须能从源码中找到依据 |
| **B 无源码** | 用户跳过 root-cause 路径；或目录仅 `*.hap`、或无上述源码特征 | 沿用下文 **「无源码时的 UI 依据」**，禁止假装读过源码 |

**A 有源码 — Agent 必须做的分析（再写脚本）**

1. 定位源码根：优先 `decompiled/`、`src/main/ets/`，或用户给定树中 `.ts` 最集中的目录。  
2. 结合用户场景，在源码中查找：**入口 Ability**、路由/页面（`@Entry`、`router`、`pages`）、目标页的 **按钮/Tab 文案**（`Text('…')`、`Resource`、常量字符串）、关键交互（播放、列表、跳转）。  
3. 完成 **§1.5 UI 映射探测** 后，将步骤映射为脚本操作：有稳定 `id`/文案时用 `touch_by_id` / `touch_by_text`；**ID 全空**时仅用 **坐标**（`touch_by_coordinates` + `source_screen_*`），**禁止**臆造 id 或盲用文案。  
4. 轨迹记录：`script_authored_from=source`、`source_paths=[...]`、`ui_mapping_mode=`、`app_specific_rationale=`。

**B 无源码 — 编写前（MUST）**

1. **包名**：`hdc list targets`；`hdc shell bm dump -n <包名>` 确认 `app_package`。  
2. **场景**：向用户确认要压测的**一条**主路径。  
3. **本应用 UI 依据**（至少其一，否则勿编造大量坐标）：用户说明、设备截图、UI 树/无障碍、hdc 真机观察。  
4. **入口 Ability**：用 `bm dump` / 源码核对 `start_app(page_name=...)` 的 Ability；`prepare`/`perf` 会走完整 `setup`→`process`，**无需**人工先把 app 停在前台。  
5. 完成 **§1.5 UI 映射探测**（无源码时**强制**；探测时可 `start_app` 后 dump 各屏 Inspector）。  
6. 轨迹记录：`script_authored_from=ui-only`、`ui_mapping_mode=`。

#### 1.5) UI 坐标映射探测（编写脚本前 MUST）

> **目的**：Hypium 的 `find_component(BY.id/BY.text)` 依赖 Inspector 里**可映射**的组件属性。若 **所有（或目标路径上全部）可点击节点的 `attributes.id` 为空**，则 id/文案映射**不可靠**，脚本须改为**纯坐标**点击（`UIEventWrapper.touch_by_coordinates` + `CoordinateAdapter`，见 `ui_event_wrapper.py` / `coordinate_adapter.py`）。**禁止**在映射失败时仍写 `touch_by_id` / 猜测 `touch_by_text` 并指望 `prepare` 碰运气。

**何时做**：在落盘 `PerfLoad_*.py` **之前**，对**待测主路径上的每一屏**（至少：首页、关键 Tab/入口、压测核心页）各探测一次。

**采集 Inspector（真机前台须为目标 app 对应页面）**：

```bash
# 1) 启动并手动导航到待测页（或后续脚本首屏）
# 2) dump Inspector + 截图（源码轨示例）
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main ui \
  -o ./reports/_ui_probe_<包名> \
  [--device <设备序列号>]
```

在输出目录下查找 `ui/step*/inspector*.json`（或 `inspector_page_*.json`，以 `capture_ui.py` 落盘为准）。**同时**记录采集坐标时的屏幕分辨率（供 `source_screen_width` / `source_screen_height`）：

```bash
hdc shell hidumper -s RenderService -a screen
# 解析 render size / render resolution= WxH
```

**解析与判定**（结构同 `haptest/state_manager.py` 中 Inspector：`attributes.id`、`text`、`clickable`、`bounds`）：

1. 递归遍历 JSON，统计 **`clickable=='true'`** 且 `bounds` 有效的节点。  
2. 记 `clickable_total`、`id_non_empty`（`id` 非空字符串）、`text_non_empty`。  
3. **判定**（写入轨迹 `ui_mapping_mode`）：

| 条件 | `ui_mapping_mode` | 脚本操作要求 |
|------|-------------------|--------------|
| `clickable_total > 0` 且 `id_non_empty == 0` | **`coordinate-only`** | **必须**用 `touch_by_coordinates(x, y)`；坐标来自该屏 Inspector `bounds` **中心点**或同分辨率截图标注；**禁止**主路径使用 `touch_by_id`；**禁止**无探测依据的 `touch_by_text` |
| `id_non_empty > 0` 且目标控件有稳定 `id` | `id`（可辅以 `text`） | 可用 `touch_by_id`；文案仍须在 Inspector/源码中可核对 |
| 有稳定可见 `text`、无 `id` | `text` | 可用 `touch_by_text`；**须在 `prepare` 日志中确认无** `touch_by_text not found` |
| Inspector 拉取失败或 `clickable_total == 0` | — | **STOP**：先解决 dump/前台 app，**禁止**编造坐标写脚本 |

**`coordinate-only` 脚本要求（MUST）**：

1. 在 `setup()`（或首次点击前）设置 **`self.source_screen_width` / `self.source_screen_height`** 为**采集该组坐标时**的屏幕宽高（与 hidumper 一致），否则 `convert_coordinate` 无法跨分辨率适配。  
2. 每个点击使用 **`touch_by_coordinates`**，坐标与探测时**同一分辨率**下从 `bounds` 解析的中心点一一对应。  
3. 滑动可继续用 `swipes_*` / `driver.swipe`；长等待仍须 §2 亮屏保活。  
4. 轨迹：`ui_probe_paths=[...]`、`clickable_total=`、`id_non_empty=`、`ui_mapping_mode=coordinate-only`。

示例（从 bounds 取中心并点击）：

```python
import re

def _bounds_center(bounds_str: str) -> tuple[int, int]:
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not m:
        raise ValueError(f'bad bounds: {bounds_str}')
    l, t, r, b = map(int, m.groups())
    return (l + r) // 2, (t + b) // 2

def setup(self):
    super().setup()
    self.source_screen_width = 1216   # 替换为探测时记录的值
    self.source_screen_height = 2688

def _tap_bounds_center(self, bounds_str: str, wait_seconds: float = 2):
    x, y = self._bounds_center(bounds_str)
    self.touch_by_coordinates(x, y, wait_seconds)
```

#### 2) 编写与落盘

- 路径：`perf_testing/hapray/testcases/<包名>/PerfLoad_<应用简称>_<四位编号>.py`  
- 继承 `hapray.core.perf_testcase.PerfTestCase`；实现 `app_package` / `app_name`；`process()` 内用 `execute_performance_step('<本应用场景描述>', <秒数>, step_fn)`。  
- **脚本边界（MUST，无预设自写用例）**：  
  - **`process()` 开头须 `start_app()`**：`setup()` 已杀进程并回桌面，首步负责打开目标 app（与预设用例一致）。  
  - **采集中勿中途退应用**：`execute_performance_step` 内禁止 `stop_app`、Home/`swipe_to_home`、会退出应用的 `swipe_to_back`、切其他包。  
  - **结束由 `teardown()` 退出**：勿在业务末步再写 `stop_app`；框架会在用例结束时退出应用。  
  - **勿做冷启动专测**：除非用户明确要求，禁止 `reboot_device`、步骤名「冷启动」、仅采冷启一条路径。  
- 控件操作：**先按 §1.5 的 `ui_mapping_mode` 选型**——`coordinate-only` → 仅 `touch_by_coordinates`（+ `source_screen_*`）；`id`/`text` 模式才用 `touch_by_id` / `touch_by_text`；有源码时文案/路由仍须与源码或 Inspector 一致。  
- **长等待须保持亮屏（MUST）**：perf 采集期间息屏会导致 trace/操作无效。脚本中凡 **单次 `time.sleep` / `driver.wait` ≥ 5 秒**，或 `execute_performance_step` 内连续等待较长时，须避免长时间黑屏：
  - 等待前调用：`self.driver.wake_up_display()`
  - 等待 **≥ 15 秒** 时：拆成多段 sleep（建议每 **≤ 10 秒** 一段），**每段前** `self.driver.wake_up_display()`，或封装为本用例内的 `_wait_keep_screen_on(seconds)`（内部循环 wake + sleep）
  - **禁止** 在性能步骤内出现数十秒无任何亮屏保活的 `sleep`
- 示例（长等待）：

```python
def _wait_keep_screen_on(self, seconds: float, chunk: float = 10):
    remaining = seconds
    while remaining > 0:
        self.driver.wake_up_display()
        time.sleep(min(chunk, remaining))
        remaining -= chunk
```

- 在对话/轨迹中说明：`app_specific_rationale=`、`screen_keep_alive=…`（哪些等待做了亮屏处理）。

**步骤注释（MUST，便于人工审阅与后续改脚本）**

Agent 编写的 `PerfLoad_*.py` 须让**不读源码的人也能看懂每一步意图**，注释用**简体中文**（与业务场景一致即可）。

| 位置 | 必须写清的内容 |
|------|----------------|
| **文件头** | 模块 docstring：应用名、包名、压测场景（用户原话摘要）、`ui_mapping_mode`、坐标采集分辨率（若 `coordinate-only`） |
| **`process()`** | 用注释块列出**步骤总览**（Step1…StepN 各一句） |
| **每个 `execute_performance_step`** | 步骤函数**上方** 2～5 行注释：本步目标、预期界面、与上一步关系 |
| **每次 UI 操作前** | 单行注释：**做什么**（如「进入播放页 Tab」）+ **依据**（源码文案 / Inspector bounds / 截图点位） |
| **坐标与等待** | 裸数字旁注释含义，例如 `# 中心 (608,1344)，来自 inspector 首页「播放」bounds`；`sleep` 注明「等列表加载 / 等播放稳定」 |
| **辅助方法** | `_wait_keep_screen_on`、`_tap_bounds_center` 等须有 docstring 说明用途 |

**禁止**：连续多行 `touch_by_coordinates` / `sleep` 无任何说明；仅用晦涩变量名代替注释；注释与实际操作不一致（改代码须同步改注释）。

**结构示例**（节选，Agent 须按本应用扩写）：

```python
"""
PerfLoad 用例：<应用中文名>（<包名>）
场景：<用户场景，如「首页进入播放并后台播放 30s」>
ui_mapping_mode: coordinate-only | text | id
坐标基准分辨率: 1216x2688（与 §1.5 探测一致）
"""


class PerfLoadExample0001(PerfTestCase):
    """<应用> — <一条主路径压测>"""

    def process(self):
        # setup() 已 stop_app + swipe_to_home；此处打开应用（非「冷启动专测」场景）
        self.start_app(page_name='EntryAbility')
        self.driver.wait(3)

        # --- 步骤总览 ---
        # Step1: 应用内点击底部「发现」Tab
        # Step2: 播放第一首，保持前台采集 N 秒（teardown 会自动 stop_app）

        self.execute_performance_step('进入发现 Tab', 5, self._step_open_discover)
        self.execute_performance_step('打开播放并保持采集', 15, self._step_play_first)

    def _step_open_discover(self):
        # 应用内 Tab 切换（勿 swipe_to_home / stop_app）
        self.touch_by_text('发现', wait_seconds=2)
        time.sleep(2)  # 等列表骨架渲染

    def _step_play_first(self):
        # 点击列表第一项播放按钮 — 坐标来自 inspector_page_1.json 可点击节点中心
        self.touch_by_coordinates(608, 1200, wait_seconds=2)  # bounds [..][..] @ 探测目录
        self._wait_keep_screen_on(25)  # 播放稳定期，perf 主要采集窗口；分段亮屏
```

#### 3) `prepare` 完整试跑（硬门禁，未通过禁止 `perf`）

> **说明**：落盘后必须用 **`prepare`** 在真机上**完整执行**该 `PerfLoad_*` 一次（与 xDevice 跑用例路径一致，见 `prepare_action.py`）。**禁止**未跑 `prepare` 就 `perf`；**禁止**把「日志无异常但息屏/卡住/操作未生效」判为通过。

**前置**（每次 `prepare` 前）：

1. 确认设备在线；用例会先走 `setup()`（杀进程、回桌面），再在 `process()` 里 `start_app`，**无需**人工预先打开 app。  
2. 命令确认包名：

```bash
hdc list targets
hdc shell bm dump -n <包名>
```

**执行**（源码轨；二进制轨在 `<RUNTIME_ROOT>` 用等价 `hapray`/`perf-testing` 子命令）：

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main prepare \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  [--device <设备序列号>]
```

**通过标准**（须**全部**满足；缺一即 `prepare_passed=false`，**禁止** `perf`）：

| 类别 | 要求 |
|------|------|
| **命令结果** | 进程 **exit code = 0**；日志含 `✅ Test case completed: PerfLoad_...`；**无** `❌ Test case failed`、无未处理 Traceback |
| **逐步操作成功** | 通读 `prepare` 全程日志：不得存在 `touch_by_text not found`、关键 `Error`/`Exception`/`ConnectedError`；每个点击/滑动应对应**有效 UI 反馈**（不能靠空 `sleep` 混过）。**采集步骤中途**不得 `stop_app`/回桌面/切应用；`process()` 开头应有 `start_app`。若 §1.5 为 `coordinate-only`，不得出现未转换坐标或错分辨率导致的连续误点 |
| **完整跑完** | 所有 `execute_performance_step` 均执行完毕；总耗时与脚本设计量级相符（**禁止**某步卡死拖到超时仍算过） |
| **流畅、非假跑** | 试跑过程中（Agent **须**目视真机或结合试跑中截图）：**目标 app 保持前台**；**屏幕保持亮屏**（脚本须已按 §2 做 `wake_up_display` / `_wait_keep_screen_on`）；界面随步骤**连续变化**，非长时间静止/锁屏/停在桌面 |
| **场景达成** | 与用户约定的一条主路径在试跑中**实际走完**（非仅启动后休眠结束） |

**不算通过（MUST 判失败）**：

- 仅因 `sleep` 耗时而结束，但中途**息屏**、**回到桌面/退出目标 app**（采集步骤内误 `swipe_to_home`/`stop_app`）、或停在启动页/弹窗未处理。  
- `process()` **未** `start_app` 即采 perf，或做成冷启动专测（`reboot_device`、仅冷启一条路径）而用户未要求。  
- 日志大量 `touch_by_text not found` 或点击无效仍继续。  
- 应用 ANR、明显卡顿无响应、用例挂起需人工干预才结束。  
- `prepare` 报错或 exit code 非 0。

**失败时**：根据日志 + 真机现象修正**本应用**脚本（勿抄他案）→ **重新 `prepare`**，直至满足上表 → **禁止**带缺陷脚本进入 `perf`。

**轨迹记录**：`prepare_attempts=`、`prepare_log_notes=`、`prepare_passed=true|false`。

> **补充**：编写**前**可用 `hdc` 探路（查 Ability、截图、文案），但**不可替代** `prepare` 完整试跑。

#### 4) `prepare` 通过后执行 `perf` → `update`

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  --apps <包名> \
  --round 1 \
  -o ./reports
```

- `perf` 仍失败：结合 `prepare` / `perf` 日志修正脚本后，须重跑 `prepare` 通过再 `perf`。  
- 随后 **必须** `update`（§0 路径）。`collection_mode=agent-authored`。

> **二进制轨**：在 `<REPO_ROOT>` 写脚本、`prepare` 通过后源码轨 `perf`；**仍禁止**默认 `gui-agent`。

### `gui-agent` 触发条件（仅优先级 3）

- **仅当**用户在同一会话中**明确要求** `gui-agent`、AI 探索、或拒绝/无法编写 `PerfLoad_*` 脚本时。  
- 缺 `GLM_API_KEY`：**STOP** 并提示配置；**不得**改用 `perf --manual` 或编造未落盘的用例名。  
- `gui-agent` 完成后仍须 `update`（§0 路径）。

### `perf --manual`（30 秒）— 仅显式请求

- 对应用例 `testcases/manual/PerfLoad_Manual.py`。  
- **仅当**用户明确说「手动测试 / 手动 30 秒 / `--manual`」时使用。  
- **禁止**作为无预设脚本、不想写脚本、或 `gui-agent` 失败的自动兜底。

### 采集后（与模式无关）

- `perf` 或 `gui-agent` 产出报告目录后，**必须**执行 `update`（符号恢复 + 默认 root-cause），携带 §0 的 `--so_dir` / `--app-packages-dir`。

---

## §6 update、双路径参数与符号恢复

### 6.1 双路径参数（§0 确认后写入 update）

下列路径应在 **§0 必问模板** 中向用户索取（**不要**等到 perf 跑完才在内心「补问」而不发消息）：

| 用途 | 用户需提供 | CLI | 环境变量 |
|------|------------|-----|----------|
| 符号恢复（strip `.so`） | 含 `*.so` 的文件夹（如 `libs/arm64`） | `--so_dir <路径>` | `HAPRAY_SO_DIR` |
| 空刷 root-cause | **反编译源码**（`*.ts` / `decompiled/` / `src/main/ets`）或 **仅 HAP**（`*.hap`） | `--app-packages-dir <路径>` | `HAPRAY_APP_PACKAGES_DIR` |

### 6.2 路径决策顺序（与 `update_action.py` 一致）

1. **用户已提供路径** → 直接使用，**不再** `hdc file recv` 拉 SO 或 HAP。
2. **用户未提供** → 尝试从在线设备拉取（需 `hdc` + `bm dump`）；SO → `.symbol_recovery_libs/`，HAP → `.app_packages/<包名>/`。
3. **用户未提供且设备拉取失败** → **跳过符号恢复**（无 `--so_dir` 有效目录）与 **跳过集成 root-cause**（无 HAP）；继续其余 report 分析，并在对话/独立报告中写明跳过原因。

> 必问话术以 **§0 必问模板** 为准（会话开头发出）。若用户先跑完 `perf` 才补路径，仍须先完成 §0 式确认再执行 `update`。

**update 示例（§0 已确认路径，不拉设备）**：

```bash
uv run python -m scripts.main update \
  --report_dir ./reports/<timestamp> \
  --so_dir "D:/local/libs/arm64" \
  --app-packages-dir "D:/local/hap_or_app_packages"
```

---

## §2 路径术语与运行轨分叉

### 2.1 术语

- `<RUNTIME_ROOT>`：HapRay 二进制解压目录（含可执行文件），用于二进制模式运行 CLI。  
- `<REPO_ROOT>`：HapRay 源码克隆目录（包含 `perf_testing/`），用于源码回退模式运行 CLI。  
- `<PROJECT_ROOT>`：当前 IDE 工作区根目录，默认用于存放独立分析 Markdown。  
- `reports_path`：HapRay 工具采集产物目录（契约字段），**不是**独立分析报告目录。

### 2.2 `<PROJECT_ROOT>` 与报告目录

| 场景 | `<RUNTIME_ROOT>` | `<PROJECT_ROOT>` | 独立报告默认目录 |
|------|---------------|------------------|------------------|
| 工作区只打开 HapRay 二进制目录 | 二进制根 | 同上 | `<RUNTIME_ROOT>/reports/` |
| 外层项目 + 内层 HapRay 二进制目录 | 内层二进制根 | 外层项目根 | `<PROJECT_ROOT>/reports/` |
| 用户指定输出路径 | 按实际 | 按实际 | 用户指定优先 |

### 2.3 运行轨二选一（必读）

Agent **必须先二选一判定**当前会话主路径属于哪一轨，再加载对应门禁；**禁止**把「源码 7 步构建」套在已解压的 release 包上，也**禁止**在裸 clone 上假设「像装过 app 一样」已有 `dist/` 与 `symbol_recovery` venv。

| 维度 | 源码轨 `<REPO_ROOT>` | 二进制轨 `<RUNTIME_ROOT>` |
|------|----------------------|---------------------------|
| **典型判据** | 存在 `perf_testing/pyproject.toml`、`tools/symbol_recovery/pyproject.toml` | 存在 `hapray`/`hapray.exe`、`perf-testing`/`perf-testing.exe` 等发布可执行文件，且无完整 monorepo 构建义务 |
| **门禁入口** | **§4** 源码工作区硬门禁 | **§5** 二进制发布包 + **§3** 下载/解压 |
| **web / 报表模板** | 必须 `cd web && npm run build` 等写入 `perf_testing/resource/web/` | 依赖发布包已打入的 `resource/`；若运行时报缺模板，补全资源或换完整包，**不是**在二进制轨上从零跑 vite 工作流（除非团队明确该包为 dev 布局） |
| **static_analyzer / trace_streamer** | 必须本地构建与 `npm run prebuild` | 依赖发布包内 `dist/tools/sa-cmd/`、`dist/tools/bin/`；缺失则换包或联系发布方 |
| **符号恢复** | `tools/symbol_recovery` 下 `uv sync` + r2；由 `hapray`/`perf-testing` 同进程或子进程调 `main.py` | 常与主程序 **分包**；须满足 **可发现性**（见二进制节）：同级/上级目录中的 `symbol-recovery(.exe)`，或 `HAPRAY_SYMBOL_RECOVERY_ROOT` / `HAPRAY_SYMBOL_RECOVERY_EXE` / `HAPRAY_SYMBOL_RECOVERY_PYTHON` |
| **写回 perf.json** | 默认同进程 `import` 工具库即可 | 无源码树时由 **子进程** 调用 `symbol-recovery --apply-excel-to-perf-json --symbol-mapping-excel … --perf-json …`（与引擎实现一致；无需手工执行） |
| **update / LLM / Agent** | 两轨共用 **§6**（符号恢复 / root-cause / LLM→Agent） | 同上 |

**共用规则（两轨相同）**：`perf` 后须 `update`（§6）；禁止无故 `--symbol-recovery-no-llm`；LLM 失败须 Agent 闭环（§6.4）；交付验收见 §6.5。

---

## §4 源码工作区硬门禁（高于 Quick/Full，默认 MUST；**仅 `<REPO_ROOT>` 源码轨**）

> **范围**：本节 **7 步构建、禁止行为、详细命令、验证脚本、失败速查、自检规范**，**仅**在已判定为 **源码仓库** 时执行。若已判定为 **二进制发布包**，整段跳过，改读 **§5**。

### 为何「每次新下载源码必炸」？

- **根因**：`git clone` 只拿到源码，不包含 `web/dist/` 构建产物、`dist/tools/sa-cmd/` 静态分析器、`tools/bin/` 下的 trace_streamer、以及 `tools/symbol_recovery/.venv`。任何一项缺失都会导致后续步骤失败。**这不是采集逻辑 Bug，而是环境未就绪。**
- **为何 Skill「写了仍被跳过」**：旧版把步骤放在「二进制失败后的源码回退」章节，Agent 在用户**已持有源码仓库**时不会走「先下载二进制」分支，因而**根本不会执行**那段回退 checklist；必须把「源码模式」单独做成**第一道门禁**。另：若 Cursor 会话未挂载本 Skill、或未读 YAML `description`/本节，也会出现省略构建。**执行前必须自检本节，不能只依赖记忆的 TL;DR 第 4 步「跑命令」。**

### 判定为源码模式（满足其一即可）

- 工作区根（或确认的 `<REPO_ROOT>`）存在 `perf_testing/pyproject.toml` 或 `perf_testing/scripts/`（可执行 `python -m scripts.main`）；或  
- 用户明确表态「刚从仓库 clone / 新目录 / 仅此机器仅此副本」。

**只要进入源码模式，下一节「禁止行为」无条件生效**，与是否尝试过下载 release **无关**。

### 禁止行为（未完成下方「完整构建清单」之前）

不得执行包括但不限于：

- `uv run python -m scripts.main perf ...`、`update`、`static`、`dbtools` 相关采集与报告链路；  
- 依赖 **`web/dist/`** 或 **`perf_testing/resource/web/`**（报告模板资源）的任何报告生成步骤；  
- 依赖 **`dist/tools/sa-cmd/`**（`hapray-sa-cmd`）的静态分析步骤；  
- **symbol_recovery**：`tools/symbol_recovery/main.py`（含 `--skip-step1`）、以及 `hapray update` 触发的符号恢复子进程。

若用户坚持「我就要现在跑」，必须先输出**阻塞原因**：缺哪项构建/安装 + 本节对应命令。

---

### 完整构建清单（7步，必须全部完成）

| 步骤 | 模块 | 性质 | 构建命令 | 验证方法 |
|:----:|------|:----:|----------|----------|
| 1 | **perf_testing Python** | 必选 | `cd perf_testing && uv sync` | `python -m scripts.main --help` 正常输出 |
| 2 | **web** | 必选 | `cd web && npm install && npm run build` | `web/dist/index.html`、`report_template.html`、`hiperf_report_template.html` 均存在 |
| 3 | **static_analyzer** | 必选 | `cd tools/static_analyzer && npm install && npm run build` | `dist/tools/sa-cmd/hapray-sa-cmd.js` 或 `.exe` 存在 |
| 4 | **trace_streamer** | 必选 | 执行 `npm run prebuild` 解压 `third-party/trace_streamer_binary.zip` | `dist/tools/bin/trace_streamer_* --version` 可执行 |
| 5 | **symbol_recovery** | 必选（venv）／ radare2+反编译 **建议** | `cd tools/symbol_recovery && uv venv .venv && uv sync`；radare2、r2dec/r2ghidra 见第5步正文（**能装则装**） | **硬门禁仅** `.venv` 下 `main.py --help` 可运行；**不**将 `r2` / `r2pm` 反编译插件缺失算作 ✗ 或 STOP 条件 |
| 6 | hilogtool | 可选 | 从 release 复制到 `tools/bin/` | `tools/bin/hilogtool --help` 可执行 |
| 7 | opt_detector | 可选 | 从 release 复制到 `tools/opt_detector/` | `tools/opt_detector/opt-detector --help` 可执行 |

> **必选说明**：第5步 **硬门禁**仅为 `tools/symbol_recovery` 的 Python venv 与 `main.py --help`（涉及 `perf.data→perf.db`、`update` 符号恢复子进程等）。**radare2 与 r2dec/r2ghidra 反编译插件为建议项**：能装则装，装不上或网络差**不阻塞**后续 `perf`/`update`/报告链路；反编译与 LLM 证据质量可能降级，须在对话或报告中注明即可。国内拉 GitHub 慢时见第5步「国内网络」：**勿死等裸连**。

---

### 详细执行步骤

#### 第1步：Python 环境（perf_testing）

```bash
cd <REPO_ROOT>/perf_testing
uv sync
```

- 失败时降级：`pip install -r requirements.txt`
- 国内网络建议先配置 uv 镜像：
  - PowerShell: `$env:UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"`
  - Bash: `export UV_DEFAULT_INDEX=https://pypi.tsinghua.edu.cn/simple`

**验证**：
```bash
uv run python -m scripts.main --help
```

#### 第2步：Web 构建（报告界面资源）

```bash
cd <REPO_ROOT>/web
npm install
npm run build
```

**构建流程**：
1. `npm run build` 执行 `vite build` 生成 `web/dist/index.html`
2. `postbuild` 钩子自动复制到 `perf_testing/resource/web/report_template.html`

**验证（必须同时满足，3个文件）**：
```bash
# Linux/macOS
test -f web/dist/index.html && echo "✓ web/dist/index.html"
test -f perf_testing/resource/web/report_template.html && echo "✓ report_template.html"
test -f perf_testing/resource/web/hiperf_report_template.html && echo "✓ hiperf_report_template.html"

# PowerShell
Test-Path web/dist/index.html
Test-Path perf_testing/resource/web/report_template.html
Test-Path perf_testing/resource/web/hiperf_report_template.html
```

**⚠️ 警告**：不要直接复制模板文件，必须通过 `npm run build` 生成正确的 Vite 构建产物。`hiperf_report_template.html` 是火焰图报告专用模板，缺失会导致火焰图报告生成失败。

#### 第3步：Static Analyzer（静态分析器）

**前置要求**：
- Node.js：满足仓库根 `package.json` 的 `engines`（当前 Node 24.x 范围）
- Bun：`tools/static_analyzer` 的构建需要 Bun，执行 `bun --version` 验证已安装

```bash
cd <REPO_ROOT>/tools/static_analyzer
npm install
npm run build
```

**验证**：
```bash
# Linux/macOS
test -f dist/tools/sa-cmd/hapray-sa-cmd.js && echo "✓ hapray-sa-cmd.js"

# Windows
Test-Path dist/tools/sa-cmd/hapray-sa-cmd.exe
```

#### 第4步：Trace Streamer（htrace→db 转换工具）

**前置说明**：trace_streamer 二进制文件位于源码 `third-party/trace_streamer_binary.zip` 中，**不需要从 release 下载**。

**构建方式**（二选一）：

**方式 A（推荐）**：执行根目录 prebuild 脚本
```bash
cd <REPO_ROOT>
npm run prebuild
# 会自动解压 third-party/trace_streamer_binary.zip 到 dist/tools/bin/
```

**方式 B**：直接解压（如果只需要 trace_streamer）
```bash
cd <REPO_ROOT>
# Windows PowerShell
Expand-Archive -Path third-party/trace_streamer_binary.zip -DestinationPath dist/tools/bin/trace_streamer_binary
# 然后将当前平台对应的文件从 dist/tools/bin/trace_streamer_binary/ 移动到 dist/tools/bin/

# Linux/macOS
unzip third-party/trace_streamer_binary.zip -d dist/tools/bin/
# 然后清理其他平台文件，只保留当前平台的可执行文件
```

**验证**：
```bash
dist/tools/bin/trace_streamer_windows.exe --version
# Linux: dist/tools/bin/trace_streamer_linux --version
# macOS: dist/tools/bin/trace_streamer_mac --version
```

#### 第5步：Symbol Recovery（必选）+ Radare2 / 反编译（建议）

先创建 venv 并安装 Python 依赖（**以下为硬门禁**）：

```bash
cd <REPO_ROOT>/tools/symbol_recovery
uv venv .venv
uv sync
# 或：uv pip install -e .
```

**安装 radare2 + 反编译插件（建议，非硬门禁；能安则安，安不上可跳过）**：

macOS：
```bash
brew install radare2
r2pm install r2dec        # 轻量快速，推荐优先
# 或：r2pm install r2ghidra  # 更高质量，需 Java，复杂函数可选
```

Windows：
```powershell
# 方式一：winget（推荐，Win 10 1709+）
winget install radare2
# 方式二：Chocolatey
choco install radare2

# 安装完成后安装反编译插件
r2pm install r2dec
# 或：r2pm install r2ghidra
```

> **国内网络（安装 radare2 / r2pm 时）**：**默认禁止**为装 radare2/r2pm 访问 GitHub（见文首「全局规范」）。**①** 优先 `brew` / `winget` / `choco`；**②** `r2pm install` 若 **2～3 分钟无进度则直接跳过**（不影响硬门禁）；**③** 企业内网若有 radare2 离线 zip，解压并加 `PATH`；**④** macOS 可配 Homebrew 镜像后 `brew install radare2`。**禁止**死等 `github.com` 或要用户去 GitHub Releases 下载。

**验证**：
```bash
# 1. 硬门禁：symbol_recovery 入口
.venv/bin/python main.py --help        # Linux/macOS
.venv/Scripts/python main.py --help     # Windows

# 2–3. 建议项（有则更好，缺失不阻塞后续命令）
r2 -v
r2pm list | grep -E "r2dec|r2ghidra"
```

#### 第6-7步：可选工具

从 release 二进制包复制到对应目录即可：
- **hilogtool** → `tools/bin/hilogtool`（或 `hilogtool.exe`）
- **opt_detector** → `tools/opt_detector/opt-detector`

---

### 快速验证脚本

在 `<REPO_ROOT>` 根目录执行以下验证：

**Linux/macOS Bash 验证脚本**：
```bash
#!/bin/bash
echo "=== HapRay 源码模式构建验证 ==="
echo ""

# 1. Python 环境
cd perf_testing
if uv run python -m scripts.main --help >/dev/null 2>&1; then
    echo "✓ 第1步: perf_testing Python 环境"
else
    echo "✗ 第1步: perf_testing Python 环境缺失，执行: cd perf_testing && uv sync"
fi
cd ..

# 2. Web 构建（3个文件必须同时存在）
if [ -f web/dist/index.html ] && [ -f perf_testing/resource/web/report_template.html ] && [ -f perf_testing/resource/web/hiperf_report_template.html ]; then
    echo "✓ 第2步: Web 构建产物（3/3）"
else
    echo "✗ 第2步: Web 构建产物缺失，执行: cd web && npm install && npm run build"
    [ -f web/dist/index.html ] || echo "  - 缺失: web/dist/index.html"
    [ -f perf_testing/resource/web/report_template.html ] || echo "  - 缺失: perf_testing/resource/web/report_template.html"
    [ -f perf_testing/resource/web/hiperf_report_template.html ] || echo "  - 缺失: perf_testing/resource/web/hiperf_report_template.html"
fi

# 3. Static Analyzer
if [ -f dist/tools/sa-cmd/hapray-sa-cmd.js ] || [ -f dist/tools/sa-cmd/hapray-sa-cmd.exe ]; then
    echo "✓ 第3步: static_analyzer 构建产物"
else
    echo "✗ 第3步: static_analyzer 构建产物缺失，执行: cd tools/static_analyzer && npm install && npm run build"
fi

# 4. Trace Streamer
if ls dist/tools/bin/trace_streamer_* >/dev/null 2>&1; then
    echo "✓ 第4步: trace_streamer 可执行文件"
else
    echo "✗ 第4步: trace_streamer 缺失，执行: npm run prebuild"
fi

# 5. Symbol Recovery（必选）
if [ -f tools/symbol_recovery/.venv/bin/python ] && \
   tools/symbol_recovery/.venv/bin/python tools/symbol_recovery/main.py --help >/dev/null 2>&1; then
    echo "✓ 第5步: symbol_recovery 虚拟环境"
else
    echo "✗ 第5步: symbol_recovery 虚拟环境缺失"
    echo "   执行: cd tools/symbol_recovery && uv venv .venv && uv sync"
fi

# radare2 + 反编译插件（建议，非硬门禁）
if command -v r2 >/dev/null 2>&1; then
    echo "○ 第5步(建议): radare2 已安装 ($(r2 -v 2>&1 | head -1))"
    if r2pm list 2>/dev/null | grep -qE "r2dec|r2ghidra"; then
        echo "○ 第5步(建议): 反编译插件已安装 (r2dec/r2ghidra)"
    else
        echo "○ 第5步(建议): 反编译插件未装，可执行 r2pm install r2dec（装不上不阻塞 perf/update）"
    fi
else
    echo "○ 第5步(建议): radare2 未安装，可按上文安装（不阻塞 perf/update）"
fi

echo ""
echo "=== 验证完成 ==="
echo "第1–4步与第5步 Python/venv 全部 ✓ 后方可执行 perf/update/static；radare2/插件仅为建议项"
```

**Windows PowerShell 验证脚本**：
```powershell
Write-Host "=== HapRay 源码模式构建验证 ===" -ForegroundColor Cyan
Write-Host ""

# 1. Python 环境
Set-Location perf_testing
$pythonCheck = uv run python -m scripts.main --help 2>$null
Set-Location ..
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 第1步: perf_testing Python 环境" -ForegroundColor Green
} else {
    Write-Host "✗ 第1步: perf_testing Python 环境缺失" -ForegroundColor Red
    Write-Host "   执行: cd perf_testing && uv sync" -ForegroundColor Yellow
}

# 2. Web 构建（3个文件必须同时存在）
$webFiles = @(
    "web/dist/index.html",
    "perf_testing/resource/web/report_template.html",
    "perf_testing/resource/web/hiperf_report_template.html"
)
$webAllExist = $webFiles | ForEach-Object { Test-Path $_ } | Where-Object { $_ -eq $false } | Measure-Object
if ($webAllExist.Count -eq 0) {
    Write-Host "✓ 第2步: Web 构建产物（3/3）" -ForegroundColor Green
} else {
    Write-Host "✗ 第2步: Web 构建产物缺失" -ForegroundColor Red
    Write-Host "   执行: cd web && npm install && npm run build" -ForegroundColor Yellow
    foreach ($file in $webFiles) {
        if (!(Test-Path $file)) {
            Write-Host "   - 缺失: $file" -ForegroundColor Yellow
        }
    }
}

# 3. Static Analyzer
if ((Test-Path dist/tools/sa-cmd/hapray-sa-cmd.js) -or (Test-Path dist/tools/sa-cmd/hapray-sa-cmd.exe)) {
    Write-Host "✓ 第3步: static_analyzer 构建产物" -ForegroundColor Green
} else {
    Write-Host "✗ 第3步: static_analyzer 构建产物缺失" -ForegroundColor Red
    Write-Host "   执行: cd tools/static_analyzer && npm install && npm run build" -ForegroundColor Yellow
}

# 4. Trace Streamer
if (Get-ChildItem dist/tools/bin/trace_streamer_* -ErrorAction SilentlyContinue) {
    Write-Host "✓ 第4步: trace_streamer 可执行文件" -ForegroundColor Green
} else {
    Write-Host "✗ 第4步: trace_streamer 缺失" -ForegroundColor Red
    Write-Host "   执行: npm run prebuild" -ForegroundColor Yellow
}

# 5. Symbol Recovery（必选）
$srPython = "tools/symbol_recovery/.venv/Scripts/python.exe"
if ((Test-Path $srPython) -and (& $srPython tools/symbol_recovery/main.py --help 2>$null)) {
    Write-Host "✓ 第5步: symbol_recovery 虚拟环境" -ForegroundColor Green
} else {
    Write-Host "✗ 第5步: symbol_recovery 虚拟环境缺失" -ForegroundColor Red
    Write-Host "   执行: cd tools/symbol_recovery && uv venv .venv && uv sync" -ForegroundColor Yellow
}

# radare2 + 反编译插件（建议，非硬门禁）
$r2check = Get-Command r2 -ErrorAction SilentlyContinue
if ($r2check) {
    Write-Host "○ 第5步(建议): radare2 已安装" -ForegroundColor Cyan
    $r2pmList = & r2pm list 2>$null
    if ($r2pmList -match "r2dec|r2ghidra") {
        Write-Host "○ 第5步(建议): 反编译插件已安装 (r2dec/r2ghidra)" -ForegroundColor Cyan
    } else {
        Write-Host "○ 第5步(建议): 反编译插件未装，可 r2pm install r2dec（装不上不阻塞 perf/update）" -ForegroundColor Yellow
    }
} else {
    Write-Host "○ 第5步(建议): radare2 未安装，可按上文安装（不阻塞 perf/update）" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 验证完成 ===" -ForegroundColor Cyan
Write-Host "第1-4步与第5步 Python/venv 全部 OK 后方可执行 perf/update/static；radare2/插件仅为建议项" -ForegroundColor White
```

---

### 6.3 为何 perf 后必须 update

| 步骤 | 产出 | 火焰图符号状态 |
|------|------|----------------|
| `perf` 采集 | `hiperf_report.html`、原始火焰图 | ❌ 仅有地址（`libxxx.so+0x1234`） |
| `update` 符号恢复 | `hiperf_report_with_inferred_symbols.html` | ✅ 显示推断函数名 |

不执行 update：火焰图无法函数级定位，热点无语义，优化缺少依据。采集步骤见 **§7**；命令模板见 **§14**。

### 6.4 update 命令关键参数

```bash
uv run python -m scripts.main update \
  --report_dir <REPORT_DIR>              # 必填：perf 采集输出目录（含 hiperf/ 子目录）
  --so_dir <SO_DIR>                      # 推荐：本地 .so 目录（提供则跳过设备 SO 拉取）
  --app-packages-dir <HAP_DIR>           # 推荐：本地 HAP/应用包目录（提供则跳过设备 HAP 拉取）
  --symbol-recovery-llm-mode             # 可选：先走在线 LLM 符号恢复（默认不走）
  --no-root-cause                        # 可选：跳过集成空刷 root-cause
  --root-cause-skip-llm                  # 可选：root-cause 仅导出证据/Agent 任务
```

**符号恢复（默认 Agent，与代码一致）**：
- **默认**：`agent_mode=true`，直接走 Agent 编排（导出 tasks → Step2/外部 Agent → import → Step4 增强火焰图）
- **仅当需要在线 LLM**：加 `--symbol-recovery-llm-mode` 或 `HAPRAY_SYMBOL_RECOVERY_LLM_MODE=1`；探活/执行失败仍回退 Agent
- ❌ **禁止**无故使用 `--symbol-recovery-no-llm`（除非用户明确跳过符号恢复）

**root-cause（默认开启）**：
- update 在符号恢复与总报告刷新后，对含 `report/trace_emptyFrame.json` 的用例自动执行 `hapray root-cause` 等价逻辑（默认 **Agent**，见 `analysis/empty-frame-root-cause.md`）
- 跳过：`--no-root-cause` 或 `HAPRAY_UPDATE_NO_ROOT_CAUSE=1`
- 结果写入：`<用例>/report/root_cause.md`，并合并进 `hapray_report.json` 的 `more.root_cause` 与 `hapray_report.html` 嵌入面板

**设备侧产物拉取（仅当用户未提供对应路径时尝试；需 hdc + 在线设备，易失败）**：

| 内容 | 本地路径 | 用途 | 用户提供时 |
|------|----------|------|------------|
| `.so` / `libs` | `--report_dir/.symbol_recovery_libs/<包名>/` | 符号恢复 | `--so_dir` / `HAPRAY_SO_DIR` → **不拉** |
| **HAP 文件** | `--report_dir/.app_packages/<包名>/hap/*.hap` | root-cause 反编译输入 | `--app-packages-dir` / `HAPRAY_APP_PACKAGES_DIR` → **不拉** |
| **安装目录树**（尽力） | `.app_packages/<包名>/bundle/` | 完整包资源 | 同上 |
| 清单 | `.app_packages/<包名>/app_packages_manifest.json` | 记录路径、反编译/索引目录 | 同上 |

**拉取/路径皆不可用时的行为**：无有效 SO → 跳过符号恢复；无 HAP → 自动关闭集成 root-cause（等价于本 run 加 `--no-root-cause` 效果，但无需用户手改参数）。

可选反编译（配置后 update 自动执行）：

```bash
# 占位符：{hap} {output} {bundle} {out_dir}
export HAPRAY_HAP_DECOMPILER_CMD='python /path/to/decompiler.py --input {hap} --output {output}'
```

反编译成功后索引位于 `.app_packages/<包名>/decompiled/index/`，root-cause 自动使用 **with_source** 模式。

**SO 目录获取方式**（优先级）：

1. **用户本地路径（推荐）**：`--so_dir` 或 `HAPRAY_SO_DIR`（Agent 在 update 前交互索取）
2. **报告内已有**：`.symbol_recovery_libs/` 或 `.app_packages/<包名>/bundle/` 中已有 `.so`
3. **设备自动拉取（兜底）**：仅当未提供 `--so_dir` 且设备在线时，`hdc file recv` libs

**root-cause 输入获取方式**（优先级；**自动识别源码 vs HAP**）：

1. **用户本地路径（推荐）**：`--app-packages-dir` 或 `HAPRAY_APP_PACKAGES_DIR`
   - 识别为 **源码/反编译树**（`*.ts`、`decompiled/`、`src/main/ets`）→ 直接 **with_source** 分析，**不**反编译 HAP
   - 识别为 **仅 HAP**（`*.hap`）→ 走 HAP 反编译 + 索引（需 `HAPRAY_HAP_DECOMPILER_CMD`）
2. **报告内已有**：`.app_packages/<包名>/decompiled/` 或 `hap/*.hap`
3. **设备自动拉取（兜底）**：仅当未提供路径且设备在线时拉 HAP（拉取结果按 HAP 路径处理）

#### 包名获取（必须通过设备查询，禁止臆造）

> 真机采集前亦须确认包名，见 **§7**「发现预设用例」。包名禁止臆造。

**查询设备应用列表命令**：

```bash
# 列出设备上所有第三方应用（推荐）
hdc shell bm dump -a | grep -E "^(  |bundleName)" | head -50

# 或列出所有系统+第三方应用
hdc shell bm dump -a

# 模糊搜索特定应用（如抖音）
hdc shell bm dump -a | grep -i "douyin\|抖音\|aweme"
```

**包名确认流程**：

| 步骤 | 命令 | 目的 |
|------|------|------|
| 1 | `hdc list targets` | 确认设备已连接 |
| 2 | `hdc shell bm dump -a \| grep <关键词>` | 搜索目标应用 |
| 3 | `hdc shell bm dump -n <包名>` | 验证包名存在并查看安装路径 |
| 4 | 记录正确包名 | 用于 perf 采集的 `--apps` 参数 |

**常见错误**：
- ❌ 编造包名如 `com.example.app`（不存在会导致采集失败）
- ❌ 使用旧包名（应用更新后可能变更）
- ❌ 大小写错误（包名区分大小写）

**正确示例**：
```bash
# 查询抖音包名
$ hdc shell bm dump -a | grep -i aweme
  bundleName: com.ss.hm.ugc.aweme

# 验证包名存在
$ hdc shell bm dump -n com.ss.hm.ugc.aweme
{"bundleName":"com.ss.hm.ugc.aweme",...}

# 使用正确包名执行 perf
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --apps com.ss.hm.ugc.aweme
```

### 6.5 符号恢复交付验收（必须检查）

update 执行完成后，必须验证以下产物存在：

| 产物文件 | 路径 | 说明 |
|----------|------|------|
| `symbol_recovery_llm_tasks.json` | `reports/<timestamp>/.symbol_recovery/<step>/` | LLM 任务清单（Step1 导出） |
| `symbol_recovery_external_results.json` | 同上 | LLM 推断结果（Step2 产出） |
| `symbol_recovery_replacements.json` | `reports/<timestamp>/hiperf/<step>/` | 符号替换映射表 |
| `hiperf_report_with_inferred_symbols.html` | `reports/<timestamp>/hiperf/<step>/` | **增强版火焰图（最终交付物）** |
| `root_cause.md` | `<用例>/report/` | **空刷根因分析主报告**（update 集成，默认 Agent） |
| `root_cause_evidence.md` | 同上 | 规则引擎证据（调试） |
| `root_cause_agent_task.json` | 同上 | Agent 待处理任务（无 API 时） |
| `hapray_report.json` → `more.root_cause` | `<用例>/report/` | 总报告 JSON 内嵌根因 Markdown |

> 若 `hiperf_report_with_inferred_symbols.html` 不存在，说明符号恢复未完成，火焰图仍显示原始地址。  
> 若存在空刷数据但无 `root_cause.md`，检查是否误加 `--no-root-cause` 或 `trace_emptyFrame.json` 缺失。

### 6.6 符号恢复：默认 Agent；LLM 仅按需（`--symbol-recovery-llm-mode`）

**自动降级策略（必须执行）**：

update 符号恢复按以下优先级处理（**默认不走在线 LLM**）：

| 场景 | 自动行为 | 必须产出 |
|------|----------|----------|
| **默认**（未加 `--symbol-recovery-llm-mode`） | **直接 Agent 模式** | tasks → 推断 → external_results → 增强火焰图 |
| 显式 `--symbol-recovery-llm-mode` 且探活通过 | 先在线 LLM | 成功则增强火焰图；失败回退 Agent |
| LLM 探活/执行失败 | **同次切换 Agent** | 同上 |
| Agent 也失败 | 标记失败并给重试命令 | 不得伪称完成 |

**🚨 关键修复要求（LLM 失败时的正确处理）**：

**问题**：LLM 失败后可能已生成包含错误结果的 Excel，直接切换到 Agent 模式会导致错误结果被写入 perf.json。

**强制修复策略**：
1. **检测 LLM 失败**：检查 `symbol_recovery` 子进程输出，如果包含 `auto_recovered_*` 占位符或 LLM 错误，判定为失败
2. **清理错误产物**：**必须删除**以下文件（如果存在）：
   - `.symbol_recovery/<step>/event_count_topN_analysis.xlsx`
   - `.symbol_recovery/<step>/call_count_topN_analysis.xlsx`
   - `.symbol_recovery/<step>/symbol_recovery_external_results.json`（如果含错误结果）
3. **重新执行 Agent 模式**：清理后重新调用 `symbol_recovery`，使用 `--prompt-only` 导出 tasks，然后执行 Agent 推断，最后 `--import-llm-results` 回填
4. **验证结果正确性**：检查 `symbol_recovery_replacements.json` 中的 `replaced` 字段，确保**不包含** `auto_recovered_*` 占位符

**禁止行为（MUST NOT）**：
- ❌ LLM 失败时直接结束，不尝试 Agent 模式
- ❌ **不清理错误产物就直接切换到 Agent 模式**（会导致错误结果被写入 perf.json）
- ❌ 仅导出 `tasks` 文件就声称"完成"
- ❌ 不生成有效的 `symbol_recovery_external_results.json`（含真实函数名，非占位符）就结束 update
- ❌ 允许 `auto_recovered_*` 占位符写入最终火焰图

**强制检查点**：update 执行后必须验证：
1. `hiperf_report_with_inferred_symbols.html` 存在
2. `symbol_recovery_replacements.json` 中**无** `auto_recovered_*` 占位符
3. 火焰图中的函数名是**语义化名称**（如 `Function: processVideoFrame`），而非地址（`libxxx.so+0x1234`）或占位符（`auto_recovered_f96fc`）

若检查失败，必须重新执行符号恢复流程。

---

### 常见失败场景速查表

| 报错信息 | 缺少的构建步骤 | 修复命令 |
|----------|---------------|----------|
| `report_template.html` 或 `hiperf_report_template.html` 或 `web/dist/index.html` 不存在 | 第2步 web 未构建 | `cd web && npm install && npm run build` |
| `hapray-sa-cmd not found` / `ExeUtils.get_hapray_cmd_path` 失败 | 第3步 static_analyzer 未构建 | `cd tools/static_analyzer && npm install && npm run build` |
| `trace_streamer not found` / `ExeUtils.get_trace_streamer_path` 失败 | 第4步 trace_streamer 未解压 | 执行 `npm run prebuild` 解压 `third-party/trace_streamer_binary.zip` |
| `symbol_recovery 子进程退出` / `perf.db` 生成失败 | **源码轨**：第5步 symbol_recovery 未配置 | `cd tools/symbol_recovery && uv venv .venv && uv sync` |
| `symbol_recovery 子进程退出` / 跳过符号恢复 | **二进制轨**：分体包未被发现或未配置 `HAPRAY_SYMBOL_RECOVERY_*` | 见 **§5** 符号恢复可发现性 |
| `hilogtool not found` | 第6步 hilogtool 未复制（可选） | 从 release 复制 `tools/bin/hilogtool` |
| 静态分析命令 `static` 失败 | 第3步 static_analyzer 缺失 | 见上 |

---

### 自检执行规范（MUST）

1. **进入源码轨时必须执行 §4 全部 7 步验证**（第 **5** 步硬门槛为 venv + `main.py --help`；radare2/反编译为建议项），不可假设「以前配置过」；**二进制轨**不做 §4，改做 **§5** 最小自检。
2. **每步必须有验证证据**，在对话中输出验证结果（✓ 或 ✗）
3. **任一必备步骤（1–4，以及第5步的 Python venv / `main.py --help`）为 ✗ 时，必须 STOP**，禁止继续执行 perf/update/static 等命令；**第5步中的 radare2 / r2dec / r2ghidra 缺失不算 ✗，不触发 STOP**  
4. **可选步骤（第5步建议栈、第6–7步）为未就绪时，可降级继续**，但需告知用户哪些能力降级或不可用
5. **全部通过后，在报告中记录构建状态**，包括版本信息和验证时间

---

---

## §5 二进制发布包模式（`<RUNTIME_ROOT>`）

> **范围**：已判定**非** `<REPO_ROOT>` 源码 monorepo、而是以 **release 解压目录 / 安装目录** 运行 CLI 时使用本节。**不要**执行 **§4** 的 7 步本地构建（除非缺资源且团队要求在该目录内补构建）。

### 判定为二进制轨（满足其一即可）

- 用户从 GitCode / 镜像下载 zip、dmg 等并解压到固定目录，在该目录内直接运行 `hapray`、`perf-testing` 等；或  
- 工作区根下**无**完整 `perf_testing/pyproject.toml` + 源码树，但存在发布版可执行文件。

### 最小自检（二进制轨 MUST，替代源码 7 步）

| 检查项 | 说明 |
|--------|------|
| 主 CLI 可运行 | `<RUNTIME_ROOT>` 下 `./hapray --help` 或 `perf-testing.exe --help`（Windows 用 `.\perf-testing.exe --help`） |
| 报告模板 / 资源 | 缺 `report_template.html` / `hiperf_report_template.html` 等 → **换完整 release 包**或按发布说明补 `resource/`，**不是**自动套用源码轨「cd web && npm run build」（除非当前工作区实为 `<REPO_ROOT>`） |
| trace_streamer / sa-cmd | 缺则换包或从官方制品补 `dist/tools/bin/`、`dist/tools/sa-cmd/` |
| **符号恢复可发现** | `update` 会启动符号恢复子进程；**分体包**（`perf-testing` 与 `symbol-recovery` 分开发行）时**必须**满足其一：① 解压到**同一安装树根**下，使从主程序 exe 目录**向上**能搜到 `symbol-recovery(.exe)` 或 `symbol_recovery/`、`tools/symbol_recovery/` 等约定路径；② 或设置 **`HAPRAY_SYMBOL_RECOVERY_ROOT`**（指向含 `symbol-recovery` 可执行文件或 `main.py` 的目录）、**`HAPRAY_SYMBOL_RECOVERY_EXE`**（直接指向可执行文件）、必要时 **`HAPRAY_SYMBOL_RECOVERY_PYTHON`** |
| LLM / Agent | 与源码轨相同：配置 `LLM_API_KEY`+`LLM_BASE_URL` 等；LLM 失败走 Agent 闭环（见 **§6.6**） |

### update / 符号恢复在二进制下的注意点

- **Excel → perf.json 写回**：若安装目录中**无可 import 的** `tools/symbol_recovery/core/` 源码树，引擎会**自动**再调一次 `symbol-recovery` 子进程执行 `--apply-excel-to-perf-json`（无需人工拆分命令）。  
- **Agent Step2**（`--step2-openai` / `--step2-split` / `--step2-merge`）：应通过 **`symbol-recovery` 可执行文件或 `main.py` 子进程**完成；不要假设能在 `perf-testing` 进程内 `import` 符号恢复 one-file 包内嵌代码。

### 命令形态示例（二进制轨）

```powershell
Set-Location <RUNTIME_ROOT>
.\perf-testing.exe update --report_dir .\reports\<timestamp> --so_dir <SO_DIR>
# 若符号恢复与主程序分处两目录，先设置例如：
# $env:HAPRAY_SYMBOL_RECOVERY_ROOT = "D:\tools\symbol_recovery_install"
```

（Linux/macOS 将 `.\perf-testing.exe` 换为 `./perf-testing` 或发布包约定入口即可。）

### 常见失败（二进制轨速查）

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| 提示找不到 symbol_recovery / 符号恢复 skip | 分体包路径无关或未设环境变量 | 调整解压布局或设置 `HAPRAY_SYMBOL_RECOVERY_ROOT` / `EXE` |
| 子进程成功但 perf.json 未符号化（旧版本） | 仅 exe、无 `core` 目录导致宿主 import 失败 | 升级到含「apply-excel 子进程回退」的版本，或临时把带 `main.py`+`core/` 的符号恢复目录加入 `HAPRAY_SYMBOL_RECOVERY_ROOT` |

---

---

## §3 环境获取：二进制直链与源码回退

在执行任何 HapRay 命令前，必须先完成以下检查：

1. **二进制**：按 **§3.1** 识别系统 → 拼**唯一**直链 → **`curl` 直接下载**（不访问发布页、不枚举附件、不 `curl -fIL` 探测多候选）。失败则 **§3.2** 源码回退。  
2. 已下载解压到 `<RUNTIME_ROOT>`，或已准备 `<REPO_ROOT>`（§4 七步）。  
3. 真机场景：`hdc` 可用且设备在线。  
4. 场景依赖已满足（如 `GLM_API_KEY` 仅 **§7** 优先级 3 的 `gui-agent` 需要）。

### 3.1 二进制下载（识别系统 → 拼直链 → 下载）

> **核心原则**：Release **只有固定命名**的制品（见下表）。Agent **禁止**打开 GitCode `.../releases` 列表页、Release 详情页、`releases/latest`，也**禁止**为「确认附件名」去网页或 API 查询。流程只能是：**判定本机平台 → 查表得到唯一 `asset_name` → 拼 URL → `curl -fL` 下载**。

#### 步骤（按序执行，禁止跳步或改去「查发布页」）

| 步 | 动作 |
|:--:|------|
| 1 | **识别平台**（见 §3.1.1），得到唯一一行 `asset_name` |
| 2 | **确定 `tag`**：用户整链 URL 中的 tag → 否则 `HAPRAY_RELEASE_TAG` → 否则 Skill YAML `version` → `v{version}`（如 `1.5.4` → `v1.5.4`） |
| 3 | **确定 `version`**：`tag` 去掉前缀 `v`（`v1.5.4` → `1.5.4`），代入 `asset_name` 模板 |
| 4 | **拼直链**：用户已给整链则直接用；否则 `{BASE}releases/download/{tag}/{asset_name}` |
| 5 | **`curl -fL` 下载**（见 §3.1.2），解压到 `<RUNTIME_ROOT>`，`hapray --help` 自检 |
| 6 | 记录轨迹：`download_url`、`asset_name`、`tag`、`tag_source`、`platform` |

**`BASE`（站点根，末尾须 `/`，不含 `releases/download`）**

| 顺序 | 来源 |
|:----:|------|
| 1 | 用户给出的整链中解析出的 host 路径，或整链本身 |
| 2 | 环境变量 **`HAPRAY_RELEASES_DOWNLOAD_BASE`**（镜像根，格式同官方） |
| 3 | 默认 **`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/`** |

下载 404/失败且已设 `HAPRAY_RELEASES_DOWNLOAD_BASE` 时：可用镜像 **BASE 重拼同一 URL 再下载一次**；仍失败则 **§3.2**，**禁止**转去发布页核对附件。

#### 3.1.1 平台 → 唯一 `asset_name`（查表即用，禁止多候选探测）

先识别本机，再**只取表中一行**文件名（`<version>` = 上节去掉 `v` 后的版本号）：

| 本机判定 | `asset_name`（Release 固定名） |
|----------|-------------------------------|
| Windows x64 | `ArkAnalyzer-HapRay-win32-x64-<version>.zip` |
| Linux + `uname -m`=`x86_64` + Ubuntu **22.04** | `ArkAnalyzer-HapRay-linux-x64-ubuntu22.04-<version>.zip` |
| Linux + `uname -m`=`x86_64` + Ubuntu **24.04** | `ArkAnalyzer-HapRay-linux-x64-ubuntu24.04-<version>.zip` |
| macOS + `uname -m`=`arm64` | `ArkAnalyzer-HapRay_<version>_aarch64.dmg` |
| macOS + `uname -m`=`x86_64` | `ArkAnalyzer-HapRay_<version>_x64.dmg` |

**识别命令（仅供映射，不是去 GitCode 查询）**

- Windows：当前为 Win x64 环境。  
- Linux：`uname -s`=`Linux` 且 `uname -m`=`x86_64`；Ubuntu 版本用 `lsb_release -rs` 或 `/etc/os-release`（仅 **22.04 / 24.04** 有官方包；其他版本 → §3.2 或请用户给整链）。  
- macOS：`uname -s`=`Darwin`；`uname -m`=`arm64` 对应附件后缀 **`aarch64`**（勿拼 `_arm64`）。

**直链示例**（`tag=v1.5.4`，`version=1.5.4`）：

- Windows：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay-win32-x64-1.5.4.zip`
- Ubuntu 24.04：`.../ArkAnalyzer-HapRay-linux-x64-ubuntu24.04-1.5.4.zip`
- macOS Apple Silicon：`.../ArkAnalyzer-HapRay_1.5.4_aarch64.dmg`
- macOS Intel：`.../ArkAnalyzer-HapRay_1.5.4_x64.dmg`

> 命名与 CI 一致（仓库内 `.gitcode/workflows` 或 `.github/workflows` 仅作文件名参考，**禁止**为核对附件去访问 GitHub）：Linux 仅 Ubuntu 22.04/24.04 x64；macOS 仅 DMG，`aarch64` / `x64` 后缀。

#### 3.1.2 `curl` 下载（MUST，禁止先探测再下载）

> **禁止**对多个候选 URL 做 `curl -fIL` 轮询；**禁止**浏览器、`requests`、发布页 HTML 解析。仅当 `curl` 不可用时降级 `wget` / `Invoke-WebRequest` 并记 `download_tool`。

**超时（MUST）**：Release 包（zip/dmg）体积大、国内网络慢，设置**最长30分钟（1800秒）**超时。**必须使用** `--max-time 1800` 限制整包传输时间，避免无限等待；同时可用 `--connect-timeout 30` 控制连接建立超时。须在30分钟内**阻塞等待**直至 `curl` 正常结束或超时；超30分钟未完成的下载视为失败，降级到源码回退流程（§3.2）。

**直接下载**：

```bash
# Linux / macOS / Windows（Git Bash、Win11 自带 curl）
# --max-time 1800 = 30分钟总超时，--connect-timeout 30 = 30秒连接超时
curl -fL --retry 3 --retry-delay 5 \
  --max-time 1800 --connect-timeout 30 \
  -o "<本地保存路径/ArkAnalyzer-HapRay-....zip>" \
  "<完整直链URL>"
```

```powershell
# Windows PowerShell：同样优先 curl.exe（不要用 Invoke-WebRequest 除非 curl 不存在）
# --max-time 1800 = 30分钟总超时，--connect-timeout 30 = 30秒连接超时
curl.exe -fL --retry 3 --retry-delay 5 `
  --max-time 1800 --connect-timeout 30 `
  -o "<本地保存路径>" `
  "<完整直链URL>"
```

**降级 `wget`（同样设置 `-T`/`--timeout` 为30分钟）**：

```bash
# --timeout=1800 连接超时30分钟，--tries=3 重试3次
wget --timeout=1800 --tries=3 -O "<本地保存路径>" "<完整直链URL>"
```

**下载后**：校验文件存在且大小 **> 0**；zip/dmg 解压到 `<RUNTIME_ROOT>`，执行 **§3.3** `hapray --help`。

**URL 形态（固定，禁止改去发布页核对）**：`{BASE}releases/download/{tag}/{asset_name}`

### 3.2 源码回退（二进制不可下载或不可运行时）

触发条件（满足任一项）：

1. 直链 `curl` 下载失败（404 / 连接中断 / 校验失败 / 文件为空；**非**因人为 `--max-time` 过短导致的中途截断）。  
2. 二进制解压后 `hapray --help`（或 Windows `."."./hapray.exe --help`）执行失败。  
3. 二进制可执行但运行核心命令阶段出现明确的“不可运行/崩溃/缺依赖”错误。  

**回退步骤（权威在 §4）**：与 **§4 源码工作区硬门禁** 为**同一套 7 步**。凡检出 `<REPO_ROOT>`，无论是否尝试过下载二进制，**都必须完整执行 §4**（含验证脚本与自检规范），不得仅因从「二进制失败」分支进入而只做下列简略列举：

1. 执行 `git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git`（已有目录则 `git pull` 更新）。  
2. 进入 `<REPO_ROOT>/perf_testing`，优先执行 `uv sync`；失败可降级 `uv pip install -r requirements.txt`。  
   - 建议在国内网络先配置 `uv` 镜像，避免默认源超时：  
     - PowerShell：`$env:UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"`  
     - Bash：`export UV_DEFAULT_INDEX=https://pypi.tsinghua.edu.cn/simple`  
   - 若同时配置了 `PIP_INDEX_URL`，建议保持与 `UV_DEFAULT_INDEX` 一致，避免源不一致导致解析抖动。  
3. **构建 static_analyzer（必需）**：
   - 进入 `<REPO_ROOT>/tools/static_analyzer`
   - 安装依赖：`npm install`
   - 执行构建：`npm run build`
   - 验证：`ls ../../dist/tools/sa-cmd/` 目录存在且包含构建产物
4. **安装 symbol_recovery（必选 venv；radare2/反编译为建议项，见 §4 第 5 步）**：
   - 进入 `<REPO_ROOT>/tools/symbol_recovery`
   - 创建虚拟环境：`uv venv .venv`
   - 安装依赖：`uv pip install --python ./.venv/bin/python -e .`（Linux/macOS）或 `uv pip install --python ./.venv/Scripts/python.exe -e .`（Windows）
   - **安装 radare2 / 反编译插件（建议，装不上可跳过）**：
     - macOS：`brew install radare2` 后尝试 `r2pm install r2dec`（国内网络慢见上文第5步「国内网络」，**勿死等**）
     - Windows：`winget install radare2` 或 `choco install radare2` 后尝试 `r2pm install r2dec`
   - 验证（硬门禁仅前两行）：
     ```bash
     .venv/bin/python main.py --help        # Linux/macOS
     .venv/Scripts/python main.py --help     # Windows
     r2 -v                                    # 以下建议项，缺失不阻塞
     r2pm list | grep -E "r2dec|r2ghidra"
     ```
5. 自检 `uv run python -m scripts.main --help`。  
6. 后续采集命令改为源码方式执行：`uv run python -m scripts.main ...`。  
7. 在执行轨迹中显式记录 `binary_failed_reason`、`fallback_mode=source`、`repo_commit`。

### 3.3 `<RUNTIME_ROOT>` 判定（可执行检查）

`<RUNTIME_ROOT>` 必须是包含 HapRay 可执行文件的目录。推荐在执行前做一次检查：

```bash
cd <RUNTIME_ROOT>
./hapray --help
```

若为 Windows，使用：

```powershell
Set-Location <RUNTIME_ROOT>
.\"./hapray.exe --help
```

帮助命令无法运行时，禁止继续二进制采集流程，必须切换到源码回退模式。

---

## §8 分析模式（Quick / Full）

### Quick（快速闭环）

适用：用户只需一次结论、时效优先。

- 按 **§7** 执行一次采集（预设 → `perf`；无预设 → 写脚本 → `prepare` 通过 → `perf`；仅用户要求时 `gui-agent`）。
- 解析 `reports_path`，至少枚举 `trace.db`/`hiperf`/日志。
- 至少执行一个匹配子 Skill。
- 输出并落盘独立 `.md`（含证据路径与执行轨迹）。

### Full（深入分析）

适用：用户强调深入、交叉验证、找新发现。

- 完整执行流程 + 按顺序评估全部子 Skill（见下节）。
- 每个子 Skill 输出状态：`执行中` / `已完成` / `已跳过（原因）`。
- 报告中显式写“已覆盖项/未覆盖项/数据缺口”。

## Quick → Full 升级触发（默认门禁）

满足任一项，必须从 Quick 升级到 Full：

- Quick 结论为“异常”或“高风险可疑”。
- 观察到持续高负载（非瞬时尖峰）或多轮 `round` 趋势恶化。
- 出现内存持续增长、频繁 GC、温控/掉频迹象。
- 日志命中高风险关键词（ANR、watchdog、fatal、crash、binder timeout）。
- 用户明确要求“根因定位 / 深度分析 / 优化路线图 / 版本对比”。
- 存在 `trace_emptyFrame.json` 或空刷相关指标异常（应加载 `empty-frame-root-cause` 子 Skill）。

若未命中：输出 Quick 结论 + 下一轮建议，不强制执行 Full。

## §9 子 Skill 路由（单一事实源）

主 Skill 只做路由与门禁，细则一律以下列子文档为准：

| 信号 | 必须加载的子 Skill | 说明 |
|------|---------------------|------|
| 有 `trace.db` 且涉及滑动/掉帧/手势 | `analysis/scroll-jank-trace-analysis.md` | 帧规则以该文档为唯一权威（含 `depth=0` 规则） |
| 深挖高负载/未知瓶颈/多源交叉/新发现 | `analysis/high-load-analysis.md` | 以原始侧为主，不以 `summary.json` 为主线 |
| `libxxx.so+0x...` 缺失符号或提及符号恢复 | `analysis/symbol-recovery-analysis.md` | 按该文档执行符号恢复与验证 |
| 存在 `trace_emptyFrame.json` / 空刷 / VSync 无效刷新 / 根因定位 | `analysis/empty-frame-root-cause.md` | **必读**；update 已集成时读产物 + Agent 闭环；独立跑用 `hapray root-cause` |

推荐评估顺序：`scroll-jank` → `high-load` → `symbol-recovery` → **`empty-frame`（root-cause）**（以 `analysis/README.md` 最新索引为准）。

## §10 强制约束与门禁索引

### MUST（细则见对应 §）

| 主题 | 要求 | 权威章节 |
|------|------|----------|
| 双路径 | `path_prompt_done=false` → **零 Shell**；首条实质性回复仅 §0 模板（或同条确认路径但**仍无 Shell**）；「继续」不算路径 | §0、文首硬门禁 |
| 真机采集 | 预设 → `perf`；无则本应用脚本 + **`prepare` 通过** → `perf`；自写须 `start_app` 开头、采集中勿退应用、结束靠 `teardown` 退出；禁止冷启动专测；禁止抄他案、未 prepare 就 perf、默认 gui-agent/manual | §7 |
| 源码门禁 | 源码轨须完成 §4 七步（含 venv + `main.py --help`）；radare2/r2dec **不**算硬门禁 | §4 |
| update | `perf` 后必须 `update`；禁止无故 `--symbol-recovery-no-llm` | §6 |
| 符号恢复 | 同次 `update` 内闭环；默认 Agent；LLM 失败同次切 Agent 并清理错误产物 | §6.4–§6.6 |
| root-cause | 默认开启；仅 `root_cause_agent_task.json` 时 Agent 须补全并重跑 | §6 |
| 产出路径 | 生成文件落在 **`<PROJECT_ROOT>`** 树下，禁止无关路径乱放 | 文首全局规范 |
| 网络 | **无特殊说明禁止 GitHub**；源码/Release 用 GitCode；radare2 用包管理器 | 文首全局规范 |
| 证据与报告 | 先跑 CLI 再结论；枚举真实 `reports_path`；子 Skill 跳须写原因；落盘独立 `.md`；结论绑证据 | §9、§13 |
| 校验 | `result-file` 可读、`outputs.reports_path` 存在 | §11 |

### SHOULD

- 优先 `--result-file`；分析优先 `trace.db`/hiperf/日志；多轮同主题更新同一 `.md`；维护证据索引表；不确定结论标置信度。

### MAY

- 用户收窄子专题或只要摘要时，写明未执行项。

### 门禁索引（避免与 §0/§7/§6 重复展开）

| 门禁 | 要点 |
|------|------|
| **双路径** | 同 §0；未完成 FAIL-CLOSED |
| **真机 / gui-agent** | 先 §7 用例发现；有预设不要 GLM；仅用户明确要求 gui-agent 时检查 `GLM_API_KEY`，缺则 STOP（[智谱 API Key](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)），禁止改 `perf --manual`。默认：`GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`，`GLM_MODEL=autoglm-phone` |
| **symbol-recovery** | 源码轨先 §4；按 `analysis/symbol-recovery-analysis.md` Step 0；默认主 Agent 一次闭环（§6.4–§6.6）；仅用户明确时才在线 LLM 或 `--no-llm` |

### `hapray update` 集成（以代码为准，`update_action.py` + `perf_analyzer.py`）

1. **SO**：`--so_dir` → `HAPRAY_SO_DIR` →（无则且 hdc 在线）`bm dump -n <包名>` + `file recv` 至 `.symbol_recovery_libs/`（细节见 `analysis/symbol-recovery-analysis.md`）。用户已提供路径 → **不拉**。  
2. **符号恢复模式**：默认 Agent；`--symbol-recovery-llm-mode` 失败回退 Agent。  
3. **root-cause 输入**：`--app-packages-dir` 优先（源码 vs HAP 自动识别）；未提供才拉 HAP。  
4. **root-cause**：update 末段默认执行；`--no-root-cause` 可跳过。  
5. **前提**：有 SO 才符号恢复；有输入或拉取成功才 root-cause；须 `trace_emptyFrame.json`。

**Agent Step2**：优先 `HAPRAY_SYMBOL_RECOVERY_AGENT_CMD`（`{tasks}` `{output}` `{out_dir}` `{scene}`）；否则 `symbol-recovery` / `main.py` 子进程 `--step2-openai`（**禁止** `scripts/run_step2.py`）；批处理用 `--step2-split` / `--step2-merge`。

**交付验收**（缺一即失败）：见 **§6.5**；仅 tasks 无 external_results → 结论「符号恢复未完成」。

**离线编排（主 Agent）**：导出 tasks → 外部推断 → 校验 → import。结果约束：`function_name` 非空、语义化英文无地址后缀；`functionality` / `performance_analysis` 为中文；不合规须修正再回填。

---

## §11 执行主流程（统一版）

> **§11 前置**：下列步骤 1–8 **全部**要求 `path_prompt_done=true`。步骤 0 未完成时**禁止**执行步骤 1 及以后（含构建、下载、`hdc`）。

0. **§0（`PATH_PROMPT`）**：`path_prompt_done=false` → 仅对话发必问模板，**本轮零 Shell** → 用户下一条消息 → `path_prompt_done=true`，记录路径。  
1. 定位 `<RUNTIME_ROOT>`、`<REPO_ROOT>` 与 `<PROJECT_ROOT>`。**若确认为源码仓库**：必须已实质完成 **§4**；未完成则 **STOP**。  
2. 真机场景先检查 `hdc list targets`（或 `hdc version`）。  
3. **COLLECT + 采集**：预设 → `perf`；无预设 → 写脚本 → **`prepare` 试跑通过** → `perf`；仅用户要求时 `gui-agent`。  
4. **采集后必须 update**：携带 §0 确认的 `--so_dir`、`--app-packages-dir`（及用户要求的 `--no-root-cause` 等）。  
5. 读取 `--result-file` 或 `hapray-tool-result.json`，解析 `outputs.reports_path`。  
6. 枚举关键产物：`report/*.html`、`htrace/**/trace.db`、`hiperf/**`、日志。  
7. 按子 Skill 路由做深入分析（满足则执行，不满足写跳过原因）。  
8. 生成并更新独立报告（默认 `<PROJECT_ROOT>/reports/`）。

## §12 异常与降级策略（Fail-Closed + 可交付）

- 二进制下载失败（含超时/404/校验失败）或二进制不可运行：自动回退到源码下载与运行流程；源码流程失败后再停止并提示用户介入。  
- **无预设用例**：按本应用编写 `PerfLoad_*` → **`prepare` 完整试跑通过** → `perf`；失败则改脚本重跑 `prepare`；**禁止**未通过就 `perf`、抄他案用例、自动 `gui-agent` / `perf --manual`。  
- **用户要求的 `gui-agent` 不可用**（缺 GLM / 失败）：提示配置 GLM，或编写脚本 + `prepare` / SIMPLE；**禁止**自动 `perf --manual`。  
- **有预设或 `prepare` 已通过脚本**：不得因 GLM 改走 `gui-agent` / `--manual`。  
- `symbol-recovery`：若已配置 LLM 环境但请求仍失败（额度/鉴权/网络），单次子进程内已尽力；若**未配置** LLM 环境，则必须走离线 tasks + 外部结果 JSON 回填，禁止把“仅导出 tasks”当作最终交付。  
- `result-file` 缺失或损坏：尝试读取默认 `hapray-tool-result.json`；仍失败则进入“仅执行证据报告”，禁止输出伪分析结论。  
- 关键产物缺失（如无 `trace.db`）：对应子 Skill 标记 `已跳过（数据不足）`，并给最小补采命令。  
- 多命令场景：采集命令可失败不中断，但最终结论必须显式标注数据完备度（完整/部分/不足）。

## §13 固定输出结构与独立分析报告

每次执行建议遵循以下结构，保证可复用与可审计：

1. `路由决策`：Quick 或 Quick+Full，及触发理由。  
2. `执行轨迹`：状态机阶段、关键命令、成功率。  
3. `关键证据`：指标/日志/trace 路径与观测摘要。  
4. `结论分级`：高置信度 / 中置信度 / 低置信度。  
5. `优化建议`：P0（立即）/ P1（短期）/ P2（中期）。  
6. `未覆盖项`：缺失数据、影响范围、补采计划。

## §14 命令模板（最小可用）

> ⛔ **`path_prompt_done=false` 时禁止复制执行本节任何命令。** 须先完成 §0 并在对话中收到用户路径回复。

### 完整工作流（采集 + update，推荐）

> **§0**：`path_prompt_done=true` 后方可执行下方命令。  
> **采集**：无预设时须 **按本应用编写** `PerfLoad_*`，**`prepare` 完整试跑通过** 后再 perf。

```bash
# 无预设：编写脚本 → prepare（见 §7 第 3 节）→ perf（§0 已完成）
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main prepare --run_testcases "PerfLoad_<用例名>"
cd <RUNTIME_ROOT>
./hapray --result-file <PROJECT_ROOT>/hapray-tool-result.json perf \
  --run_testcases "PerfLoad_<用例名>" \
  --apps <包名> \
  --round 1 \
  -o ./reports

# 第2步：update（携带 §0 确认的路径；未提供则 hdc 兜底）
./hapray --result-file <PROJECT_ROOT>/hapray-tool-result.json update \
  --report_dir ./reports/<timestamp> \
  --so_dir "<§0_SO路径>" \
  --app-packages-dir "<§0_root-cause输入路径>"
# 可选：--no-root-cause | --root-cause-skip-llm | --symbol-recovery-llm-mode
```

### 单独 root-cause（补跑）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main root-cause \
  --report-dir <用例>/report \
  --index-dir <report_dir>/.app_packages/<包名>/decompiled/index \
  --decompiled-dir <report_dir>/.app_packages/<包名>/decompiled
```

### gui-agent 模式（仅用户明确要求时）

> **前置**：已确认无可用 `PerfLoad_*`，且用户**明确要求** gui-agent（非默认；默认应为本应用编写脚本 + **`prepare` 通过** 后 `perf`）。

```bash
cd <RUNTIME_ROOT>
./hapray --result-file <PROJECT_ROOT>/hapray-tool-result.json gui-agent \
  --apps <包名> \
  --scenes "<用户场景描述>" \
  -o ./reports
# 采集完成后同样必须 update
```

### 注意事项

- `--round` 建议：冒烟 `1`；对比评估 `3` 或 `5`
- **采集路由**：预设 → `perf`；无预设 → 写脚本 → **`prepare` 通过** → `perf`；**禁止**未通过 `prepare`、照搬他案 / 默认 `gui-agent` / `perf --manual`
- **update 必须执行**：`perf` / `gui-agent` 后必须执行 `update`，否则火焰图无符号、无集成 root-cause
- **禁止无故 `--symbol-recovery-no-llm`**：会跳过符号恢复

### 独立分析报告规范

- 默认位置：`<PROJECT_ROOT>/reports/`  
- 文件名：`hapray-analysis-<YYYYMMDD>-<topic>.md`  
- 正文建议：背景与问题 → 采集方式 → 执行轨迹 → 关键产物路径 → 结论与证据 → 优化建议 → 未覆盖项  
- 多轮同主题：默认更新原文件；仅用户明确要求时另存新文件。

### 文末元信息（必填）

```markdown
---

<p align="center"><small>报告由 <strong>HapRay Skill</strong> <code>1.5.4</code> 生成 · <a href="https://gitcode.com/SMAT/ArkAnalyzer-HapRay">ArkAnalyzer-HapRay</a> · 报告生成时间 <code>2026-05-13T12:00:00+08:00</code></small></p>
```

若环境不支持 HTML，可用单行斜体替代，信息字段需完整等价。

## §15 明确禁止

- **禁止产出乱放**：报告、脚本、下载物、探测结果写到与 **`<PROJECT_ROOT>`** 无关的目录（如随意 `/tmp`、桌面、仓库外路径）。  
- **禁止默认使用 GitHub**：无用户明确要求时不得 `git clone`/下载/文档引用依赖 `github.com`；用 GitCode 与 §3 直链。  
- **禁止跳过 §0**：`path_prompt_done=false` 时任何 Shell；未在**对话**中发必问模板；同条消息发问+跑命令；用户「继续」但未给路径仍执行 `perf`/`update`/构建。  
- **禁止错误的采集兜底**：无预设时默认 `gui-agent`；**未 `prepare` 通过就 `perf`**；息屏/卡住/逐步操作失败仍算过；照搬他案业务步骤；无脚本时 `perf --manual`；编造未落盘用例名。  
- **禁止自写脚本采集中途退应用**：无预设时不得在 `execute_performance_step` 内 `stop_app`/Home/切包；须 `process()` 首步 `start_app`；勿做冷启动专测（除非用户明确要求）。  
- 禁止只给通用建议而不执行 CLI（除非用户明确声明不跑工具）。  
- 禁止用自动摘要替代对原始产物的验证。  
- 禁止在门禁未通过时“伪交付”（例如 GLM 未配置却直接出完整采集结论）。  
- 禁止虚构路径、时间戳、数值、热点函数。  
- 禁止使用系统 PATH 中原有的 `hapray`（如 `hapray` / `which hapray` 指向旧版本）；必须使用 `<RUNTIME_ROOT>` 下本次下载的可执行文件。  

## §16 参考文档

- `README.md`、`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`  
- `hapray-tool-result.md`（契约字段速查）  
- `analysis/README.md`（子 Skill 索引）  
- `analysis/scroll-jank-trace-analysis.md`  
- `analysis/high-load-analysis.md`  
- `analysis/symbol-recovery-analysis.md`
- `analysis/empty-frame-root-cause.md`
