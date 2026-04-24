---
name: hapray
version: "1.5.3"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
description: |
  HapRay (ArkAnalyzer-HapRay) 精简主 Skill：负责命令执行、路径判定、子 Skill 路由与落盘规范。深入分析规则统一由 analysis/*.md 提供。默认独立报告写入 `<PROJECT_ROOT>/reports/`。
metadata:
  short-description: >-
    Lean workflow for HapRay CLI execution, reports_path parsing, analysis routing, and markdown report output.
  zh-Hans: >-
    精简版主流程：先执行 CLI，再按产物路由到 analysis 子 Skill 深入分析；默认写 `<PROJECT_ROOT>/reports/`，报告文末保留元信息与执行轨迹。
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
---

# HapRay 引导式工作流

目标：让 Agent 以更短路径完成 **下载最新二进制（失败回退源码）→ 采集/执行 → 解析产物 → 子 Skill 深入分析 → 独立报告落盘**，并具备可恢复、可审计、可机读的执行闭环。

## TL;DR（30 秒）

1. 判定路径：先分清 `<RUNTIME_ROOT>`（二进制运行目录）、`<REPO_ROOT>`（源码运行目录）与 `<PROJECT_ROOT>`（写报告）。  
2. 先快诊后升级：默认 Quick，命中触发条件再升级 Full。  
3. 跑命令：必须实际执行 `gui-agent/perf/opt/static` 之一（按意图）。  
4. 读产物：从 `hapray-tool-result.json`（或 `--result-file`）取 `outputs.reports_path`。  
5. 路由分析：按 `analysis/README.md` 逐项评估子 Skill；满足条件则执行，不满足写跳过原因。  
6. 落盘报告：写到 `<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<topic>.md`，正文固定结构 + 文末元信息与执行轨迹。

## 术语与路径判定

- `<RUNTIME_ROOT>`：HapRay 二进制解压目录（含可执行文件），用于二进制模式运行 CLI。  
- `<REPO_ROOT>`：HapRay 源码克隆目录（包含 `perf_testing/`），用于源码回退模式运行 CLI。  
- `<PROJECT_ROOT>`：当前 IDE 工作区根目录，默认用于存放独立分析 Markdown。  
- `reports_path`：HapRay 工具采集产物目录（契约字段），**不是**独立分析报告目录。

| 场景 | `<RUNTIME_ROOT>` | `<PROJECT_ROOT>` | 独立报告默认目录 |
|------|---------------|------------------|------------------|
| 工作区只打开 HapRay 二进制目录 | 二进制根 | 同上 | `<RUNTIME_ROOT>/reports/` |
| 外层项目 + 内层 HapRay 二进制目录 | 内层二进制根 | 外层项目根 | `<PROJECT_ROOT>/reports/` |
| 用户指定输出路径 | 按实际 | 按实际 | 用户指定优先 |

## 环境前置条件（新增）

在执行任何 HapRay 命令前，必须先完成以下检查：

1. 本地可访问发布页：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases`。  
2. 已确定当前平台与架构（Windows / Linux Ubuntu 22.04/24.04 x64 / macOS Intel / macOS Apple Silicon）。  
3. 已下载并解压**最新 release**的对应平台二进制到 `<RUNTIME_ROOT>`，或在二进制不可用时已准备源码目录 `<REPO_ROOT>`。  
4. 真机链路可用（`hdc` 可执行且设备在线，若为真机场景）。  
5. 目标场景所需门禁已满足（如 `GLM_API_KEY`、symbol-recovery API Key）。

### 1) 二进制获取（必须下载最新 release）

默认从发布页下载：

`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases`

必须执行以下策略：

1. 读取发布列表并定位“最新发布版本”（最新 tag / latest release）。  
2. 按当前平台只选择一个匹配附件下载，禁止下载无关平台包。  
3. 下载后解压到 `<RUNTIME_ROOT>`，并记录 `version`、`asset_name`、`download_url` 到执行轨迹。
4. 若用户已显式提供 `releases/download/<tag>/<asset_name>` 直链，必须先按该直链直接下载与校验；仅在直链失败时再走“自动获取最新 tag + 自动拼接”流程。

下载链接生成规则（必须遵循）：

1. 发布详情页形态：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/<tag>`（示例：`.../releases/v1.5.3`）。  
2. 资产下载直链形态：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/<tag>/<asset_name>`。  
3. `tag` 必须来自“最新 release”的真实 tag（如 `v1.5.3`、`v1.5.4`），禁止写死版本。  
4. `asset_name` 必须来自该 release 的真实附件名，禁止臆造。  
5. 若已知 Windows 命名规则为 `ArkAnalyzer-HapRay-win32-x64-<version>.zip`，则可按模板拼接：
   - `version = tag` 去掉前缀 `v`（例如 `v1.5.3 -> 1.5.3`）
   - `asset_name = ArkAnalyzer-HapRay-win32-x64-<version>.zip`
   - 示例直链：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.3/ArkAnalyzer-HapRay-win32-x64-1.5.3.zip`
6. 拼接后必须做可达性校验（HTTP 200 或可成功下载）；失败时回退为“从 release 附件列表中按平台规则重新匹配”。
7. 只要 `releases/download/<tag>/<asset_name>` 直链可达，即按匿名直链下载处理；下载流程不以“登录门禁”作为前置条件。

### 自动推断下载直链（无用户直链时必须执行）

当用户未提供具体下载 URL，禁止直接要求用户补全直链；必须先执行以下自动推断流程：

1. **自动获取最新 tag（优先）**：优先访问 `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/latest`，跟随重定向并从最终 URL 解析 `vX.Y.Z`。  
2. **获取 tag 失败回退**：读取 `.../releases` 页面并提取最新 `.../releases/vX.Y.Z`。  
3. **平台候选名生成**：按平台规则生成 `asset_name` 候选集合（mac Intel 必须同时包含 `ArkAnalyzer-HapRay-darwin-x64-<version>.dmg` 与 `ArkAnalyzer-HapRay_<version>_x64.dmg`）。  
4. **逐一连通性校验**：对每个候选构造 `.../releases/download/<tag>/<asset_name>`，必须使用 GET 发起请求并进行最小下载校验（禁止使用 HEAD）；以“可达且文件可读”为通过条件。  
5. **唯一命中即采用**：若仅 1 个候选通过，直接下载并进入后续流程。  
6. **多命中/零命中回退**：抓取 `.../releases/<tag>` 的附件链接再匹配平台关键字；仍无法唯一确定时，进入源码回退模式，并在执行轨迹记录该失败原因。  

说明：必须先自动推断；若自动推断或下载校验失败，必须进入“源码回退模式”，而不是直接停止。

### 1.1) 源码回退（当二进制不可下载或不可运行时必须执行）

触发条件（满足任一项即触发）：

1. 二进制下载失败（超时 / 404 / 校验失败 / 无法唯一匹配资产名）。  
2. 二进制解压后 `hapray --help`（或 Windows `.\hapray.exe --help`）执行失败。  
3. 二进制可执行但运行核心命令阶段出现明确的“不可运行/崩溃/缺依赖”错误。  

回退步骤：

1. 执行 `git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git`（已有目录则 `git pull` 更新）。  
2. 进入 `<REPO_ROOT>/perf_testing`，优先执行 `uv sync`；失败可降级 `uv pip install -r requirements.txt`。  
   - 建议在国内网络先配置 `uv` 镜像，避免默认源超时：  
     - PowerShell：`$env:UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"`  
     - Bash：`export UV_DEFAULT_INDEX=https://pypi.tsinghua.edu.cn/simple`  
   - 若同时配置了 `PIP_INDEX_URL`，建议保持与 `UV_DEFAULT_INDEX` 一致，避免源不一致导致解析抖动。  
3. 自检 `uv run python -m scripts.main --help`。  
4. 后续采集命令改为源码方式执行：`uv run python -m scripts.main ...`。  
5. 在执行轨迹中显式记录 `binary_failed_reason`、`fallback_mode=source`、`repo_commit`。

Agent 执行规范 TL;DR（优先执行）：

1. 若用户已提供 `releases/download/<tag>/<asset_name>` 直链，优先直接下载；否则自动获取最新 `tag`（失败则要求用户提供 `vX.Y.Z`）。  
2. 识别当前平台与架构（Windows / Ubuntu22|24 x64 / macOS Intel|Apple Silicon）。  
3. 按命名约定生成唯一 `asset_name`，构造 `releases/download/<tag>/<asset_name>` 直链。  
4. 下载到本地后做最小完整性校验（存在、非空、可读）。下载阶段必须等待完成，最长等待 10 分钟。  
5. 解压到 `<RUNTIME_ROOT>` 并执行 `hapray --help`（Windows 用 `hapray.exe --help`）。  
6. 任一步失败必须显式报错并进入源码回退流程；禁止伪造“下载成功”。

Agent 执行规范（标准 Skill 描述，替代脚本模板）：

1. **确定版本/直链优先**：若用户提供了 `releases/download/<tag>/<asset_name>` 直链，必须优先使用该直链；仅在未提供直链时才自动获取最新 `tag`（格式 `vX.Y.Z`）。若自动获取失败，必须提示用户手动提供 `tag`，不得假设版本。  
2. **识别平台**：识别 OS 与 CPU 架构（Windows/Linux/macOS，`x64` 或 `arm64`）。  
3. **构造资产名**：按“平台选择规则”生成唯一候选 `asset_name`；若无法唯一确定，必须中止并要求人工确认。  
4. **构造下载链接**：使用标准直链 `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/<tag>/<asset_name>`。  
5. **执行下载**：将文件下载到本地临时目录或用户指定目录；必须阻塞等待下载结束，超时时间上限为 10 分钟。  
6. **完整性校验**：校验文件存在且非空，并执行最小可读性检查（可列目录/可读取镜像信息）。  
7. **解压与落位**：将二进制解压到 `<RUNTIME_ROOT>`，保持目录结构完整。  
8. **可执行自检**：Windows 执行 `.\hapray.exe --help`，Linux/macOS 执行 `./hapray --help`；禁止执行系统 PATH 中的 `hapray`。  
9. **失败策略（二进制优先 + 源码回退）**：下载或校验失败时，先输出失败原因，再自动回退源码流程；仅当源码流程也失败时才停止并要求用户人工介入。

标准命名约定（用于自动拼接，需与 release 实际附件名一致）：

- Windows x64：`ArkAnalyzer-HapRay-win32-x64-<version>.zip`
- Linux Ubuntu 22.04 x64：`ArkAnalyzer-HapRay-linux-x64-ubuntu22.04-<version>.zip`
- Linux Ubuntu 24.04 x64：`ArkAnalyzer-HapRay-linux-x64-ubuntu24.04-<version>.zip`
- macOS Apple Silicon：`ArkAnalyzer-HapRay-darwin-arm64-<version>.dmg` 或 `ArkAnalyzer-HapRay_<version>_arm64.dmg`
- macOS Intel：`ArkAnalyzer-HapRay-darwin-x64-<version>.dmg` 或 `ArkAnalyzer-HapRay_<version>_x64.dmg`

其中 `<version>` = `tag` 去掉前缀 `v`（例如 `v1.5.3 -> 1.5.3`）。

macOS Intel 直链示例（已验证可用）：

- `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.3/ArkAnalyzer-HapRay_1.5.3_x64.dmg`

平台识别建议（必须先识别再选包）：

- Windows：`$env:OS` 或 `[System.Environment]::OSVersion.Platform`。  
- Linux/macOS：`uname -s` 识别 `Linux` 或 `Darwin`，再用 `uname -m` 区分 `x86_64`（Intel/x64）和 `arm64`（ARM64/Apple Silicon）。
- Linux 发行版：优先通过 `lsb_release -rs` 或 `/etc/os-release` 判断 Ubuntu 主版本（22.04 / 24.04）。

平台选择规则（按附件文件名关键字匹配）：

| 运行平台 | 必须匹配关键字（任一） | 禁止匹配 |
|----------|------------------------|----------|
| Windows x64 | `windows` / `win` + `x64` / `amd64` | `darwin` / `mac` / `arm64` |
| Linux Ubuntu 22.04 x64 | `linux` + `x64` / `x86_64` / `amd64` + `ubuntu22.04` | `windows` / `darwin` / `mac` / `arm64` / `aarch64` / `ubuntu24.04` |
| Linux Ubuntu 24.04 x64 | `linux` + `x64` / `x86_64` / `amd64` + `ubuntu24.04` | `windows` / `darwin` / `mac` / `arm64` / `aarch64` / `ubuntu22.04` |
| macOS Intel | `darwin` / `macos` + `x64` / `x86_64` / `amd64` | `windows` / `arm64` / `aarch64` |
| macOS Apple Silicon | `darwin` / `macos` + `arm64` / `aarch64` | `windows` / `x64` / `x86_64` |

> 依据 `.github/workflows/build.yml`：Linux 仅构建 Ubuntu 22.04/24.04 的 x64 产物，不构建 Linux ARM64。

Linux 选包执行步骤（必须全部满足）：

1. 先识别系统：`uname -s` 必须为 `Linux`。  
2. 再识别架构：`uname -m` 必须为 `x86_64`（非 `arm64`/`aarch64`）。  
3. 识别 Ubuntu 版本：优先 `lsb_release -rs`，失败再读 `/etc/os-release`。  
4. 当版本为 `22.04`：仅允许匹配 `linux + x64 + ubuntu22.04` 的附件名。  
5. 当版本为 `24.04`：仅允许匹配 `linux + x64 + ubuntu24.04` 的附件名。  
6. 若候选数不为 1（0 或 >1）：禁止下载，输出“版本匹配不唯一/无匹配”，并要求人工确认。  
7. 下载后执行 `./hapray --help` 验证可执行，再进入采集与分析流程。

### 2) `<RUNTIME_ROOT>` 判定（可执行检查）

`<RUNTIME_ROOT>` 必须是包含 HapRay 可执行文件的目录。推荐在执行前做一次检查：

```bash
cd <RUNTIME_ROOT>
./hapray --help
```

若为 Windows，使用：

```powershell
Set-Location <RUNTIME_ROOT>
.\hapray.exe --help
```

帮助命令无法运行时，禁止继续二进制采集流程，必须切换到源码回退模式。

## 执行模式

### Quick（快速闭环）

适用：用户只需一次结论、时效优先。

- 运行一次核心命令（`gui-agent` 或 `perf`）。
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

若未命中：输出 Quick 结论 + 下一轮建议，不强制执行 Full。

## 执行状态机与检查点（可恢复）

按以下状态推进，并在对话与报告中打印阶段状态：

1. `DISCOVER`：路径判定、设备与依赖检查。  
2. `EXECUTE`：执行 HapRay CLI 采集。  
3. `PARSE`：读取 `result-file`，解析 `reports_path` 与关键字段。  
4. `ANALYZE`：按子 Skill 路由做专题分析。  
5. `REPORT`：更新或写入独立报告并附元信息。

每个阶段输出：`状态(成功/失败/降级)`、`证据`、`下一动作`。  
若阶段失败，默认进入“可降级继续”而非整任务终止（除路径错误或用户取消）。

## 子 Skill 路由（单一事实源）

主 Skill 只做路由与门禁，细则一律以下列子文档为准：

| 信号 | 必须加载的子 Skill | 说明 |
|------|---------------------|------|
| 有 `trace.db` 且涉及滑动/掉帧/手势 | `analysis/scroll-jank-trace-analysis.md` | 帧规则以该文档为唯一权威（含 `depth=0` 规则） |
| 深挖高负载/未知瓶颈/多源交叉/新发现 | `analysis/high-load-analysis.md` | 以原始侧为主，不以 `summary.json` 为主线 |
| `libxxx.so+0x...` 缺失符号或提及符号恢复 | `analysis/symbol-recovery-analysis.md` | 按该文档执行符号恢复与验证 |

推荐评估顺序：`scroll-jank` → `high-load` → `symbol-recovery`（以 `analysis/README.md` 最新索引为准）。

## 强制约束（MUST / SHOULD / MAY）

### MUST

- 必须先实际执行 CLI，再给“原因与建议”。  
- 必须输出阶段进度（命令前说明、命令后结果）。  
- 必须读取 `reports_path` 并枚举真实产物路径，不得臆造。  
- 必须按子 Skill 条件逐项评估，跳过时写原因。  
- 必须落盘独立 `.md`（除非用户明确只要对话结论）。
- 必须执行输入与结果的最小校验：命令参数、`result-file` 可读、`outputs.reports_path` 存在。  
- 必须为每条关键结论绑定至少 1 条可追溯证据（路径/指标/日志片段）。

### SHOULD

- 优先使用 `--result-file <绝对路径>` 便于机器解析。  
- 分析优先原始产物（`trace.db`/`hiperf`/日志），HTML 作为对照。  
- 多轮同主题默认更新同一份 `.md`，保持单一事实来源。
- 在报告中维护“证据索引表”（结论 -> 证据文件 -> 提取方式）。  
- 对不确定结论标注置信度：`高/中/低`，并给补采建议。

### MAY

- 用户明确只要某单一子专题时，可收窄范围。  
- 用户明确只要摘要时，可降低分析深度，但需写明未执行项。

## 前置门禁（两条）

### 1) `gui-agent` 门禁（GLM）

当意图需要 `gui-agent` 且缺少 `GLM_API_KEY`：

1. 明确提示用户配置（给出 [智谱 API Key 页面](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)）。  
2. 等待用户确认“已配置”或“明确不配置”。  
3. 仅在用户明确“不配置 LLM”时，降级 `perf --run_testcases`。  

默认值：

- `GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`
- `GLM_MODEL=autoglm-phone`

### 2) `symbol-recovery` 门禁

当意图涉及符号恢复：

- 先检查 `tools/symbol_recovery/.env` 中 API Key。  
- 若未配置，先按 `analysis/symbol-recovery-analysis.md` 的 Step 0 与用户确认 A/B 方案。  

## 执行主流程（统一版）

1. 定位 `<RUNTIME_ROOT>`、`<REPO_ROOT>` 与 `<PROJECT_ROOT>`。  
2. 真机场景先检查 `hdc list targets`（或 `hdc version`）。  
3. 按运行模式执行命令：二进制模式在 `<RUNTIME_ROOT>` 执行（Windows `.\hapray.exe`，Linux/macOS `./hapray`）；源码回退模式在 `<REPO_ROOT>/perf_testing` 执行 `uv run python -m scripts.main ...`。  
4. 读取 `--result-file` 或 `hapray-tool-result.json`，解析 `outputs.reports_path`。  
5. 枚举关键产物：`report/*.html`、`htrace/**/trace.db`、`hiperf/**`、日志。  
6. 按子 Skill 路由做深入分析（满足则执行，不满足写跳过原因）。  
7. 生成并更新独立报告（默认 `<PROJECT_ROOT>/reports/`）。

## 异常与降级策略（Fail-Closed + 可交付）

- 二进制下载失败（含超时/404/校验失败）或二进制不可运行：自动回退到源码下载与运行流程；源码流程失败后再停止并提示用户介入。  
- `gui-agent` 不可用：在获得用户确认后降级到 `perf --run_testcases`，并记录“能力降级影响”。  
- `result-file` 缺失或损坏：尝试读取默认 `hapray-tool-result.json`；仍失败则进入“仅执行证据报告”，禁止输出伪分析结论。  
- 关键产物缺失（如无 `trace.db`）：对应子 Skill 标记 `已跳过（数据不足）`，并给最小补采命令。  
- 多命令场景：采集命令可失败不中断，但最终结论必须显式标注数据完备度（完整/部分/不足）。

## 固定输出结构（对话与报告共用）

每次执行建议遵循以下结构，保证可复用与可审计：

1. `路由决策`：Quick 或 Quick+Full，及触发理由。  
2. `执行轨迹`：状态机阶段、关键命令、成功率。  
3. `关键证据`：指标/日志/trace 路径与观测摘要。  
4. `结论分级`：高置信度 / 中置信度 / 低置信度。  
5. `优化建议`：P0（立即）/ P1（短期）/ P2（中期）。  
6. `未覆盖项`：缺失数据、影响范围、补采计划。

## 命令模板（最小可用）

```bash
cd <RUNTIME_ROOT>
./hapray --result-file /tmp/hapray-tool-result.json gui-agent \
  --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页" \
  -o ./
```

```bash
cd <RUNTIME_ROOT>
./hapray --result-file /tmp/hapray-tool-result.json perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --round 1
```

`--round` 建议：冒烟 `1`；对比评估 `3` 或 `5`。若未显式传参，以 CLI 当前默认值为准。

## 独立分析报告规范

- 默认位置：`<PROJECT_ROOT>/reports/`  
- 文件名：`hapray-analysis-<YYYYMMDD>-<topic>.md`  
- 正文建议：背景与问题 → 采集方式 → 执行轨迹 → 关键产物路径 → 结论与证据 → 优化建议 → 未覆盖项  
- 多轮同主题：默认更新原文件；仅用户明确要求时另存新文件。

### 文末元信息（必填）

```markdown
---

<p align="center"><small>报告由 <strong>HapRay Skill</strong> <code>1.5.4</code> 生成 · <a href="https://gitcode.com/SMAT/ArkAnalyzer-HapRay">ArkAnalyzer-HapRay</a> · 报告生成时间 <code>2026-03-30T14:30:00+08:00</code></small></p>
```

若环境不支持 HTML，可用单行斜体替代，信息字段需完整等价。

## 明确禁止

- 禁止只给通用建议而不执行 CLI（除非用户明确声明不跑工具）。  
- 禁止用自动摘要替代对原始产物的验证。  
- 禁止在门禁未通过时“伪交付”（例如 GLM 未配置却直接出完整采集结论）。  
- 禁止虚构路径、时间戳、数值、热点函数。  
- 禁止使用系统 PATH 中原有的 `hapray`（如 `hapray` / `which hapray` 指向旧版本）；必须使用 `<RUNTIME_ROOT>` 下本次下载的可执行文件。  

## 参考文档

- `README.md`、`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`  
- `hapray-tool-result.md`（契约字段速查）  
- `analysis/README.md`（子 Skill 索引）  
- `analysis/scroll-jank-trace-analysis.md`  
- `analysis/high-load-analysis.md`  
- `analysis/symbol-recovery-analysis.md`
