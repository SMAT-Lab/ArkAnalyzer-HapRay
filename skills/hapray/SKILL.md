---
name: hapray
version: "1.5.4"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
description: |
  HapRay (ArkAnalyzer-HapRay) 精简主 Skill。**会话开头 STOP**：凡将跑 perf/update/符号恢复/root-cause，须先向用户索取 SO 目录与 root-cause 输入目录（源码或 HAP），收到明确回复前禁止执行任何 HapRay CLI。再判定源码轨/二进制轨与硬门禁。update 默认 Agent 符号恢复 + 集成 root-cause；用户提供路径则跳过 hdc 拉取。
metadata:
  short-description: >-
    HapRay workflow: STOP at session start to ask user for SO and root-cause input paths before any CLI; then source/binary gate; perf/update with optional hdc fallback.
  zh-Hans: >-
    会话开头阻塞询问双路径 → 源码/二进制门禁 → perf/update → 子 Skill 分析 → 报告落盘。未回复路径前禁止跑命令。
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

目标：让 Agent 以更短路径完成 **按直链获取二进制发布包（失败回退源码）→ 采集/执行 → 解析产物 → 子 Skill 深入分析 → 独立报告落盘**，并具备可恢复、可审计、可机读的执行闭环。

## §0 会话开头阻塞门禁：双路径确认（最高优先级，默认 MUST）

> **为何 Agent「从不交互」**：若只把询问写在「update 之前」，模型常在用户一说「跑 perf」后就直接执行 CLI，永远走不到 update 前那一段。**本节要求：在本会话第一次即将执行任何 HapRay CLI 之前就必须 STOP 并向用户提问，且须等待用户下一条回复。**

### 何时触发（满足任一即触发，且尚未在本会话完成过 §0 确认）

- 用户要跑 **`perf`**、**`update`**、**`perf`→`update` 全流程**、**`gui-agent`**（且后续会做 update）、**`root-cause`**，或分析已有报告且需要 **符号恢复 / 空刷根-cause**；
- 用户说「分析性能」「跑一遍 hapray」「生成报告」等，且按本 Skill 会进入上述命令。

### Agent 必须执行（不可省略）

1. **STOP**：**禁止**在本步骤完成前执行 `perf` / `update` / `gui-agent` / `static` / `root-cause` 等任何 HapRay CLI（含后台命令）。
2. **输出下方「必问模板」全文**（可替换 `<包名>` / 示例路径，但须保留两项路径 + 三种回复方式）。
3. **等待用户下一条消息**：用户给出路径、`跳过`、或 `从设备拉取` 后，方可进入 §0 记录与后续 TL;DR 步骤。
4. **记录到执行轨迹**（对话或独立报告）：`so_dir_user`、`app_packages_dir_user`、`path_prompt_done=true`。

### 视为「用户已答复」的判定（满足其一即可进入后续 CLI）

| 用户表述 | Agent 记录 |
|----------|------------|
| 给出 **SO 目录** 绝对/相对路径 | `so_dir_user=<路径>`，update 时加 `--so_dir` |
| 给出 **root-cause 输入** 路径（源码树或 HAP 目录） | `app_packages_dir_user=<路径>`，update 时加 `--app-packages-dir` |
| 「跳过 SO」「不要符号恢复」 | 不填 SO；update 可加 `--symbol-recovery-no-llm`（须用户明确） |
| 「跳过 root-cause」「不要根因」 | `--no-root-cause` |
| 「都从手机拉」「设备拉取」 | 两路径留空，允许后续 hdc 兜底 |
| 消息中已含 `--so_dir` / `--app-packages-dir` 或 `HAPRAY_SO_DIR` / `HAPRAY_APP_PACKAGES_DIR` | 直接采用，仍可向用户复述确认 |

### 必问模板（会话开头原样发出，禁止只写进报告不发给用户）

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

### 禁止行为（§0 违反 = 流程失败）

- ❌ 未发必问模板就执行 `perf` / `update`
- ❌ 在用户**下一条消息**之前自行假设路径、默认从设备拉取并开跑
- ❌ 把「路径询问」只写在独立分析报告里而不在对话中向用户提问
- ❌ 用户仅说「继续」但从未给路径时，仍应用臆造路径执行 update

---

## TL;DR（30 秒）

0. **§0 双路径确认（先于一切 CLI）**：见上一节；**未向用户提问并收到答复前，禁止执行步骤 4 及之后任何命令**。  
1. **先判定运行轨（二选一，勿混用）**：  
   - **源码轨 `<REPO_ROOT>`**：存在 `perf_testing/pyproject.toml` 等 → **仅适用**下方「源码工作区硬门禁」；**先于任何** `perf` / `update` / dbtools / 符号恢复跑通 7 步构建自检（第 5 步 **硬门禁**为 `symbol_recovery` 的 venv + `main.py --help`；**radare2 / r2dec / r2ghidra 为建议项**，未装不阻塞）。  
   - **二进制轨 `<RUNTIME_ROOT>`**：以 release 解压目录运行 `hapray`/`perf-testing` 可执行文件 → **不适用**源码 7 步本地构建；改走正文「二进制发布包模式」中的资源检查、**符号恢复与主程序的发现关系**（分体包必配环境变量或约定目录）。  
   两条线不得以「有源码」代替「发布包已带齐模板/trace_streamer」或反之。  
2. 判定路径：先分清 `<RUNTIME_ROOT>`（二进制运行目录）、`<REPO_ROOT>`（源码运行目录）与 `<PROJECT_ROOT>`（写报告）。  
3. 先快诊后升级：默认 Quick，命中触发条件再升级 Full。  
4. 跑命令：必须实际执行 `gui-agent/perf/opt/static` 之一（按意图）；**update 须带 §0 确认后的** `--so_dir` / `--app-packages-dir`（若用户已提供）。  
5. 读产物：从 `hapray-tool-result.json`（或 `--result-file`）取 `outputs.reports_path`。  
6. 路由分析：按 `analysis/README.md` 逐项评估子 Skill；满足条件则执行，不满足写跳过原因。  
7. 落盘报告：写到 `<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<topic>.md`，正文固定结构 + 文末元信息与执行轨迹。

> **🚨 关键强制要求**：
> - `perf` 采集后**必须**执行 `update`（符号恢复 + 可选 root-cause 集成）
> - **禁止**在 `update` 中使用 `--symbol-recovery-no-llm`（除非用户**明确**要求跳过符号恢复）
> - 符号恢复**默认 Agent 模式**；仅 `--symbol-recovery-llm-mode` 时先走在线 LLM，失败仍回退 Agent
> - **root-cause 默认开启**（空刷根因）；用 `--no-root-cause` 跳过；Agent 编排与符号恢复一致（`HAPRAY_ROOT_CAUSE_AGENT_CMD`）
> - **§0 双路径（MUST）**：**会话开头**向用户索取 SO + root-cause 输入路径，**收到回复前禁止任何 CLI**（见 §0）；非仅在 update 前才问
> - **路径用法**：用户已提供 → update 带 `--so_dir` / `--app-packages-dir`，**禁止 hdc 拉取**；未提供 → 设备兜底；皆无 → 跳过符号恢复与 root-cause

## 双路径参数说明（§0 确认后写入 update 命令）

下列路径应在 **§0 必问模板** 中向用户索取（**不要**等到 perf 跑完才在内心「补问」而不发消息）：

| 用途 | 用户需提供 | CLI | 环境变量 |
|------|------------|-----|----------|
| 符号恢复（strip `.so`） | 含 `*.so` 的文件夹（如 `libs/arm64`） | `--so_dir <路径>` | `HAPRAY_SO_DIR` |
| 空刷 root-cause | **反编译源码**（`*.ts` / `decompiled/` / `src/main/ets`）或 **仅 HAP**（`*.hap`） | `--app-packages-dir <路径>` | `HAPRAY_APP_PACKAGES_DIR` |

**决策顺序（与 `update_action.py` 一致）**：

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

## 运行模式分叉：源码仓库 vs 二进制发布包（必读）

Agent **必须先二选一判定**当前会话主路径属于哪一轨，再加载对应门禁；**禁止**把「源码 7 步构建」套在已解压的 release 包上，也**禁止**在裸 clone 上假设「像装过 app 一样」已有 `dist/` 与 `symbol_recovery` venv。

| 维度 | 源码轨 `<REPO_ROOT>` | 二进制轨 `<RUNTIME_ROOT>` |
|------|----------------------|---------------------------|
| **典型判据** | 存在 `perf_testing/pyproject.toml`、`tools/symbol_recovery/pyproject.toml` | 存在 `hapray`/`hapray.exe`、`perf-testing`/`perf-testing.exe` 等发布可执行文件，且无完整 monorepo 构建义务 |
| **门禁入口** | 下文 **「源码工作区硬门禁」** 全文 | 下文 **「二进制发布包模式」** + 下载/解压见 **「环境前置条件」** |
| **web / 报表模板** | 必须 `cd web && npm run build` 等写入 `perf_testing/resource/web/` | 依赖发布包已打入的 `resource/`；若运行时报缺模板，补全资源或换完整包，**不是**在二进制轨上从零跑 vite 工作流（除非团队明确该包为 dev 布局） |
| **static_analyzer / trace_streamer** | 必须本地构建与 `npm run prebuild` | 依赖发布包内 `dist/tools/sa-cmd/`、`dist/tools/bin/`；缺失则换包或联系发布方 |
| **符号恢复** | `tools/symbol_recovery` 下 `uv sync` + r2；由 `hapray`/`perf-testing` 同进程或子进程调 `main.py` | 常与主程序 **分包**；须满足 **可发现性**（见二进制节）：同级/上级目录中的 `symbol-recovery(.exe)`，或 `HAPRAY_SYMBOL_RECOVERY_ROOT` / `HAPRAY_SYMBOL_RECOVERY_EXE` / `HAPRAY_SYMBOL_RECOVERY_PYTHON` |
| **写回 perf.json** | 默认同进程 `import` 工具库即可 | 无源码树时由 **子进程** 调用 `symbol-recovery --apply-excel-to-perf-json --symbol-mapping-excel … --perf-json …`（与引擎实现一致；无需手工执行） |
| **update / LLM / Agent** | 两轨共用下文「完整执行流程」「LLM 失败 Agent」等规则 | 同上 |

**共用规则（两轨相同）**：`perf` 后须 `update` 做符号恢复（除非用户明确跳过）、禁止无故 `--symbol-recovery-no-llm`、LLM 失败须 Agent 闭环与验收清单。

---

## 源码工作区硬门禁（高于 Quick/Full，默认 MUST；**仅 `<REPO_ROOT>` 源码轨**）

> **范围**：自本节起至「自检执行规范」结束的 **7 步构建、禁止行为、详细命令**，**仅**在已判定为 **源码仓库** 时执行。若已判定为 **二进制发布包**，整段跳过，改读 **「二进制发布包模式」**。

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

> **国内网络（安装 radare2 / r2pm 时）**：`r2pm install r2dec/r2ghidra` 与手动拉 [radare2 GitHub Releases](https://github.com/radareorg/radare2/releases) **常直连 `github.com`**。若 **明显卡顿或约 2～3 分钟仍几乎无进度，禁止死等**，可换路径或**直接跳过**（**不影响**硬门禁）：**①** 优先 `brew` / `winget` / `choco`；**②** 策略允许时，为 Git 配置 **`https://github.com/` 的镜像或加速前缀**（`git config --global url."<前缀>".insteadOf "https://github.com/"`）后再 `r2pm install`；**③** 企业/国内镜像的官方 **zip 离线** 解压，`bin/` 加 `PATH`；**④** macOS 可先配 **Homebrew 镜像** 再 `brew install radare2`。

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

### 完整执行流程（含符号恢复）

> **命令示例**：以下 `uv run python -m scripts.main` 为 **`<REPO_ROOT>` 源码轨**。二进制轨在 `<RUNTIME_ROOT>` 下直接调用发布包提供的 `hapray`/`perf-testing` 可执行文件，参数相同，路径换为解压目录。

**⚠️ 重要：perf 采集后必须执行 update 进行符号恢复**，否则火焰图将只显示地址（`libxxx.so+0x1234`）而非函数名。

#### 标准工作流（两步必须都执行）

```bash
# 第1步：perf 采集（仅生成原始报告，无符号恢复）
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --round 1 \
  -o ./reports

# 第2步：update 进行符号恢复（必须执行，火焰图符号化关键步骤）
uv run python -m scripts.main update \
  --report_dir ./reports/<timestamp> \
  --so_dir <可选：符号库目录>
```

#### 为什么必须执行 update？

| 步骤 | 产出 | 火焰图符号状态 |
|------|------|----------------|
| `perf` 采集 | `hiperf_report.html`、原始火焰图 | ❌ 仅有地址（`libxxx.so+0x1234`） |
| `update` 符号恢复 | 增强版火焰图（`hiperf_report_with_inferred_symbols.html`） | ✅ 显示推断函数名 |

**不执行 update 的后果**：
- 火焰图显示 `libxxx.so+0x1234` 等原始地址，无法定位具体函数
- 无法识别热点函数的语义含义
- 性能优化缺少关键函数级信息

#### update 命令关键参数

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

#### 包名获取方式（必须通过设备查询，禁止臆造）

**⚠️ 重要**：包名必须从连接的设备上查询获取，禁止随意编造。

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

#### 符号恢复交付验收（必须检查）

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

#### ⚠️ 符号恢复：默认 Agent；LLM 仅按需（`--symbol-recovery-llm-mode`）

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
| `symbol_recovery 子进程退出` / 跳过符号恢复 | **二进制轨**：分体包未被发现或未配置 `HAPRAY_SYMBOL_RECOVERY_*` | 见「二进制发布包模式」符号恢复可发现性 |
| `hilogtool not found` | 第6步 hilogtool 未复制（可选） | 从 release 复制 `tools/bin/hilogtool` |
| 静态分析命令 `static` 失败 | 第3步 static_analyzer 缺失 | 见上 |

---

### 自检执行规范（MUST）

1. **进入「源码轨」时必须执行全部 7 步验证**（其中第 **5** 步以 **Python venv + `main.py --help`** 为硬门槛，radare2/反编译为建议项），不可假设「以前配置过」或「应该没问题」；**二进制轨**不做本 7 步，改做「二进制发布包模式」最小自检。
2. **每步必须有验证证据**，在对话中输出验证结果（✓ 或 ✗）
3. **任一必备步骤（1–4，以及第5步的 Python venv / `main.py --help`）为 ✗ 时，必须 STOP**，禁止继续执行 perf/update/static 等命令；**第5步中的 radare2 / r2dec / r2ghidra 缺失不算 ✗，不触发 STOP**  
4. **可选步骤（第5步建议栈、第6–7步）为未就绪时，可降级继续**，但需告知用户哪些能力降级或不可用
5. **全部通过后，在报告中记录构建状态**，包括版本信息和验证时间

---

## 二进制发布包模式（`<RUNTIME_ROOT>`）

> **范围**：已判定**非** `<REPO_ROOT>` 源码 monorepo、而是以 **release 解压目录 / 安装目录** 运行 CLI 时使用本节。**不要**执行上文「源码工作区硬门禁」的 7 步本地构建（除非缺资源且团队要求在该目录内补构建）。

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
| LLM / Agent | 与源码轨相同：配置 `LLM_API_KEY`+`LLM_BASE_URL` 等；LLM 失败走 Agent 闭环（见上文「LLM 失败时强制走 Agent 模式」） |

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

## 环境前置条件（新增）

在执行任何 HapRay 命令前，必须先完成以下检查：

1. **二进制下载策略（仅直链，禁止发布页）**：Agent **禁止**为取版本或附件名而访问或解析 GitCode **发布列表** `.../releases`、**发布详情** `.../releases/<tag>` HTML、或 **`.../releases/latest`** 重定向做「自动探测最新」。**唯一允许**的远程形态是对已知的 `.../releases/download/<tag>/<asset_name>` 发起下载（或用户给出的等价整链）。`tag` 与站点根来源见下文 **§1.0**；无直链可用时进入源码回退，**禁止**在发布站上「自己查」耗时间。  
2. 已确定当前平台与架构（Windows / Linux Ubuntu 22.04/24.04 x64 / macOS Intel / macOS Apple Silicon）。  
3. 已按 §1.0 / §1.1 直链策略下载并解压对应平台二进制到 `<RUNTIME_ROOT>`，或在二进制不可用时已准备源码目录 `<REPO_ROOT>`。  
4. 真机链路可用（`hdc` 可执行且设备在线，若为真机场景）。  
5. 目标场景所需门禁已满足（如 `GLM_API_KEY`、symbol-recovery API Key）。

### 1.0) 直链来源与镜像（禁止打开发布页）

按 **严格顺序** 确定 `BASE` + `tag` 并拼 `releases/download/<tag>/<asset_name>`，**先成功者采用**；全程须在执行轨迹记录 `download_url`、`url_source`、`tag_source`。

| 优先级 | 来源 | 用法 |
|:------:|------|------|
| P0 | 用户/调用方给出的 **整条** `.../releases/download/<tag>/<asset_name>` 直链 | 直接使用；失败再降 P1（换 BASE 重拼，见下）。 |
| P1 | 环境变量 **`HAPRAY_RELEASES_DOWNLOAD_BASE`** | 值为 **站点根**，须以 `/` 结尾、**不含** `releases/download` 段。与已确定的 `tag`、`asset_name` 拼接：`${HAPRAY_RELEASES_DOWNLOAD_BASE}releases/download/${tag}/${asset_name}`。示例：`export HAPRAY_RELEASES_DOWNLOAD_BASE=https://your-mirror.example.com/SMAT/ArkAnalyzer-HapRay/` |
| P2 | **Skill 内置备用根**（与 GitCode **同路径后缀**，仅换主机；由团队维护镜像时填写） | 按下表「备用下载根」自上而下尝试；每行与 §1.1 的命名规则生成候选 `asset_name`，拼完整直链并做下载校验。 |

**`tag` 确定顺序（均不得访问发布页 / latest）**

1. P0 直链 URL 路径中的 `<tag>`。  
2. 环境变量 **`HAPRAY_RELEASE_TAG`**（形如 `v1.5.4`，须带 `v` 前缀并与制品一致）。  
3. **Skill 正文顶部 YAML `version`** → `v{version}`（例如 `version: "1.5.4"` → `v1.5.4`）。执行轨迹记 `tag_source=skill_version`。  
4. 若以上皆无且用户也未声明 tag：**停止**二进制下载分支，提示用户提供 **P0 整链** 或设置 **`HAPRAY_RELEASE_TAG`**，或直接进入 **§1.2 源码回退**；**禁止**访问 `.../releases`、`.../releases/latest` 或详情页补全 tag。

**备用下载根（P2，维护者随 Release 更新镜像后同步改 URL）**

> 路径段均为 `SMAT/ArkAnalyzer-HapRay/releases/download/`。若某行主机不可达，Agent 跳过该行试下一行。

| 序号 | 备用根 `BASE`（末尾须带 `/`） | 说明 |
|:----:|-------------------------------|------|
| 1 | `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/` | 官方同源直链根。 |
| 2 | `https://<MIRROR_HOST>/SMAT/ArkAnalyzer-HapRay/` | **由团队填写**：与官方相同的 `releases/download/<tag>/<asset>` 结构；无镜像则删除本行。 |

### 1.1) 二进制直链下载（禁止列表/详情页）

必须遵守：

1. **仅**使用 `.../releases/download/<tag>/<asset_name>`（或 P0 等价整链）；**禁止**打开 `.../releases`、**禁止**抓取 `.../releases/<tag>` 附件列表、**禁止**用 `releases/latest` 推断版本。  
2. `tag` 来自 §1.0 顺序；`asset_name` 由 **下文「标准命名约定」+ 平台规则** 生成候选集（允许多个文件名候选以覆盖 dmg 双命名等）；**禁止**臆造与约定无关的文件名。  
3. 对每个 `(BASE 来自 P1/P2 或 P0 已解析的 host, tag, candidate_asset)` 拼直链，用 **GET 实际下载或流式校验**（禁止使用 HEAD）；唯一命中则下载落盘。  
4. 解压到 `<RUNTIME_ROOT>`，记录 `tag`、`asset_name`、`download_url`、`tag_source` 到执行轨迹。  
5. 零命中或多命中且无法按 §1.1 规则消歧：**不得**再爬发布页；应提示用户给 **P0 整链** 或 **`HAPRAY_RELEASE_TAG` + 明确平台**，或进入 **§1.2 源码回退**。

直链形态（唯一允许的制品 URL 形态）：

`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/<tag>/<asset_name>`

示例（`tag` 与文件名须与 §1.0、`version` 一致）：

- `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay-win32-x64-1.5.4.zip`（`version: "1.5.4"` → `tag=v1.5.4`）
- `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay_1.5.4_aarch64.dmg`（macOS Apple Silicon；`uname -m` 为 `arm64`，**附件名后缀为 `aarch64`**）
- `https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay_1.5.4_x64.dmg`（macOS Intel）

### 直链候选探测（无用户整链时的默认流程）

当用户未提供 P0 整链时，**不得**要求用户先打开发布页；按以下顺序执行：

1. 按 §1.0 得到 `tag`；若无 tag 则停止二进制分支（见 §1.0 第 4 点）。  
2. **平台候选名生成**：按平台规则生成 `asset_name` 候选集合（mac Apple Silicon **优先** `ArkAnalyzer-HapRay_<version>_aarch64.dmg`；mac Intel **优先** `ArkAnalyzer-HapRay_<version>_x64.dmg`，可次选 `ArkAnalyzer-HapRay-darwin-x64-<version>.dmg`）。  
3. **逐一 GET 校验**：对每个 `(P1 或 P2 的 BASE, tag, candidate)` 拼直链并下载校验；先成功者采用。  
4. **零命中 / 多命中无法消歧**：进入源码回退，执行轨迹记 `binary_failed_reason`；**禁止**再抓取 `.../releases` 或详情页 HTML。

### 1.2) 源码回退（当二进制不可下载或不可运行时必须执行）

触发条件（满足任一项即触发）：

1. 二进制下载失败（超时 / 404 / 校验失败 / 无法唯一匹配资产名）。  
2. 二进制解压后 `hapray --help`（或 Windows `."."./hapray.exe --help`）执行失败。  
3. 二进制可执行但运行核心命令阶段出现明确的“不可运行/崩溃/缺依赖”错误。  

回退步骤（与「源码工作区硬门禁」自检**同一套**：凡检出 `<REPO_ROOT>`，无论是否尝试过下载二进制，**都必须完成第 2–5 步**；不得仅因在「二进制失败」分支读到本节才构建）：

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
4. **安装 symbol_recovery 依赖（必选）+ radare2 + 反编译插件（必选）**：
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

Agent 执行规范 TL;DR（优先执行）：

1. 若用户已提供 `releases/download/<tag>/<asset_name>` 整链（P0），优先直接下载；否则按 §1.0 取 `tag`（`HAPRAY_RELEASE_TAG` → Skill `version` 推导 `vX.Y.Z`），**禁止**访问 `releases` 列表页、`releases/<tag>` 详情页或 `releases/latest`。  
2. 识别当前平台与架构（Windows / Ubuntu22|24 x64 / macOS Intel|Apple Silicon）。  
3. 按命名约定生成 `asset_name` 候选，在 P1/P2 的 `BASE` 上拼直链并 GET 下载校验；**禁止**为匹配附件名去爬 HTML。  
4. 下载到本地后做最小完整性校验（存在、非空、可读）。下载阶段必须等待完成，最长等待 10 分钟。  
5. 解压到 `<RUNTIME_ROOT>` 并执行 `hapray --help`（Windows 用 `hapray.exe --help`）。  
6. 任一步失败必须显式报错并进入 §1.2 源码回退；禁止伪造“下载成功”。

Agent 执行规范（标准 Skill 描述，替代脚本模板）：

1. **直链与 tag**：P0 整链优先；否则 `tag` 仅来自 `HAPRAY_RELEASE_TAG` 或 Skill YAML `version`→`v{version}`（见 §1.0）。**禁止**用发布页或 `releases/latest` 推断 tag；需要非锚定版本时用户须给整链或设置 `HAPRAY_RELEASE_TAG`。  
2. **识别平台**：识别 OS 与 CPU 架构（Windows/Linux/macOS，`x64` 或 `arm64`）。  
3. **构造资产名**：按“平台选择规则”生成候选 `asset_name`；若无法消歧，提示用户给 P0 整链或 `HAPRAY_RELEASE_TAG` + 平台说明，或进入 §1.2。  
4. **构造下载链接**：仅使用 `…/releases/download/<tag>/<asset_name>`（可配合 `HAPRAY_RELEASES_DOWNLOAD_BASE` / P2 根）。  
5. **执行下载**：将文件下载到本地临时目录或用户指定目录；必须阻塞等待下载结束，超时时间上限为 10 分钟。  
6. **完整性校验**：校验文件存在且非空，并执行最小可读性检查（可列目录/可读取镜像信息）。  
7. **解压与落位**：将二进制解压到 `<RUNTIME_ROOT>`，保持目录结构完整。  
8. **可执行自检**：Windows 执行 `.\"./hapray.exe --help`，Linux/macOS 执行 `./hapray --help`；禁止执行系统 PATH 中的 `hapray`。  
9. **失败策略（二进制优先 + 源码回退）**：下载或校验失败时，先输出失败原因，再自动回退源码流程；仅当源码流程也失败时才停止并要求用户人工介入。

标准命名约定（用于自动拼接，需与 release 实际附件名一致）：

- Windows x64：`ArkAnalyzer-HapRay-win32-x64-<version>.zip`
- Linux Ubuntu 22.04 x64：`ArkAnalyzer-HapRay-linux-x64-ubuntu22.04-<version>.zip`
- Linux Ubuntu 24.04 x64：`ArkAnalyzer-HapRay-linux-x64-ubuntu24.04-<version>.zip`
- macOS Apple Silicon（**仅 DMG**，Tauri 产物；与 `desktop/scripts/build.js` 一致）：**`ArkAnalyzer-HapRay_<version>_aarch64.dmg`**（GitCode Release 附件名；**勿**用 `_arm64` 或 `darwin-arm64` 拼直链，会 404）
- macOS Intel（**仅 DMG**）：**`ArkAnalyzer-HapRay_<version>_x64.dmg`**（优先）；次选 `ArkAnalyzer-HapRay-darwin-x64-<version>.dmg`（若存在）

其中 `<version>` = `tag` 去掉前缀 `v`（例如 `v1.5.4 -> 1.5.4`）。

> **macOS 与 `uname` 的对应关系**：`uname -m` 为 `arm64` 时，Release DMG 后缀为 **`aarch64`**（非 `arm64`）；为 `x86_64` 时后缀为 **`x64`**。CI 上传路径为 `*_${dmg_arch}.dmg`，`dmg_arch` 在 Apple Silicon job 为 `aarch64`（见 `.github/workflows/build.yml`）。

macOS 直链示例（已验证可用，与 GitCode `v1.5.4` Release 一致）：

- Apple Silicon：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay_1.5.4_aarch64.dmg`
- Intel：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.4/ArkAnalyzer-HapRay_1.5.4_x64.dmg`

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
| macOS Intel | 附件名含 `_x64.dmg` 或 `x64` + `darwin`/`macos` | `windows` / `arm64` / `aarch64` / `_arm64` |
| macOS Apple Silicon | 附件名含 **`_aarch64.dmg`**（首选）或 `aarch64` | `windows` / `x64` / `x86_64` / **`_arm64.dmg`** / `darwin-arm64`（非 Release 附件名） |

> 依据 `.github/workflows/build.yml`：Linux 仅构建 Ubuntu 22.04/24.04 的 x64 产物，不构建 Linux ARM64；macOS 仅发布 **DMG**（`npm run release` 在 darwin 上跳过 zip），附件名为 `ArkAnalyzer-HapRay_<version>_{aarch64|x64}.dmg`。

Linux 选包执行步骤（必须全部满足）：

1. 先识别系统：`uname -s` 必须为 `Linux`。  
2. 再识别架构：`uname -m` 必须为 `x86_64`（非 `arm64`/`aarch64`）。  
3. 识别 Ubuntu 版本：优先 `lsb_release -rs`，失败再读 `/etc/os-release`。  
4. 当版本为 `22.04`：仅允许匹配 `linux + x64 + ubuntu22.04` 的附件名。  
5. 当版本为 `24.04`：仅允许匹配 `linux + x64 + ubuntu24.04` 的附件名。  
6. 若候选数不为 1（0 或 >1）：禁止下载，输出“版本匹配不唯一/无匹配”，并要求用户提供 P0 整链或设置 `HAPRAY_RELEASE_TAG`，或进入 §1.2 源码回退（**禁止**打开发布页核对附件列表）。  
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
.\"./hapray.exe --help
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
- 存在 `trace_emptyFrame.json` 或空刷相关指标异常（应加载 `empty-frame-root-cause` 子 Skill）。

若未命中：输出 Quick 结论 + 下一轮建议，不强制执行 Full。

## 执行状态机与检查点（可恢复）

按以下状态推进，并在对话与报告中打印阶段状态：

1. `PATH_PROMPT`（**§0，阻塞**）：向用户发出双路径必问模板，**等待用户回复**；记录 `so_dir_user` / `app_packages_dir_user`。未完成 **禁止** 进入 `DISCOVER`/`EXECUTE`。  
2. `DISCOVER`：路径判定、设备与依赖检查；**若工作区为 `<REPO_ROOT>`（源码轨）**，完成「源码工作区硬门禁」自检；**若为 `<RUNTIME_ROOT>`（二进制轨）**，完成「二进制发布包模式」最小自检。缺关键产物不得进入 `EXECUTE`。  
3. `EXECUTE`：执行 HapRay CLI 采集（`update` 携带 §0 确认的路径参数）。  
4. `PARSE`：读取 `result-file`，解析 `reports_path` 与关键字段。  
5. `ANALYZE`：按子 Skill 路由做专题分析。  
6. `REPORT`：更新或写入独立报告并附元信息。

每个阶段输出：`状态(成功/失败/降级)`、`证据`、`下一动作`。  
若阶段失败，默认进入“可降级继续”而非整任务终止（除路径错误或用户取消）。

## 子 Skill 路由（单一事实源）

主 Skill 只做路由与门禁，细则一律以下列子文档为准：

| 信号 | 必须加载的子 Skill | 说明 |
|------|---------------------|------|
| 有 `trace.db` 且涉及滑动/掉帧/手势 | `analysis/scroll-jank-trace-analysis.md` | 帧规则以该文档为唯一权威（含 `depth=0` 规则） |
| 深挖高负载/未知瓶颈/多源交叉/新发现 | `analysis/high-load-analysis.md` | 以原始侧为主，不以 `summary.json` 为主线 |
| `libxxx.so+0x...` 缺失符号或提及符号恢复 | `analysis/symbol-recovery-analysis.md` | 按该文档执行符号恢复与验证 |
| 存在 `trace_emptyFrame.json` / 空刷 / VSync 无效刷新 / 根因定位 | `analysis/empty-frame-root-cause.md` | **必读**；update 已集成时读产物 + Agent 闭环；独立跑用 `hapray root-cause` |

推荐评估顺序：`scroll-jank` → `high-load` → `symbol-recovery` → **`empty-frame`（root-cause）**（以 `analysis/README.md` 最新索引为准）。

## 强制约束（MUST / SHOULD / MAY）

### MUST

- **§0 双路径（最高优先级）**：凡本 Skill 驱动的 `perf`/`update`/`root-cause`/符号恢复链路，**会话第一条实质性回复**必须是 §0 必问模板（除非用户同条消息已给出两路径或明确「跳过/设备拉取」）。**在用户下一条消息回复路径之前，禁止执行任何 HapRay CLI。**  
- **若为源码仓库（判定见「源码工作区硬门禁」），必须先完成该节最小自检清单（perf_testing、web 构建、`dist/tools/sa-cmd`、trace_streamer、**symbol_recovery 的 venv + `main.py --help`**）并留证据**，再执行 `perf`/`update`/符号恢复链路；**radare2 / r2dec / r2ghidra 未装不构成未完成硬门禁**。未完成硬门禁时禁止谎称环境就绪。  
- **符号恢复必须一次性闭环交付**：若进入符号恢复链路，必须在同一次 `update` 内完成 `tasks -> symbol_recovery_external_results.json -> import -> 替换产物`，禁止“做一半停一半”。  
- **符号恢复默认 Agent**：不得因未配置在线 LLM 就跳过符号恢复；`--symbol-recovery-llm-mode` 失败时**必须**同次切 Agent 完成闭环。  
- **root-cause 默认执行**：update 后检查 `report/root_cause.md`；若仅 `root_cause_agent_task.json` 无结果，主 Agent **必须**按任务 JSON 完成推断并写 `root_cause_agent_result.json` 后重跑 update 或单独 `root-cause`。  
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

## 前置门禁（三条）

### 0) 双路径确认门禁（§0，高于 gui-agent / 源码构建）

与正文 **§0** 相同：**先于一切 CLI**。未完成则 **FAIL-CLOSED**，不得进入 `perf`/`update`。

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

- **源码模式前置**：必须与「源码工作区硬门禁」一致——**已构建** `<REPO_ROOT>/dist/tools/sa-cmd/`（static_analyzer）、**已在** `<REPO_ROOT>/tools/symbol_recovery` 装好 venv 且 `main.py --help` 可通过。**radare2 与 r2dec/r2ghidra 为建议项**：能装则装，未装**不**将本条判为 FAIL-CLOSED；仅 venv / `main.py` 未就绪时才 FAIL-CLOSED（先做构建）。  
- 必须先按 `analysis/symbol-recovery-analysis.md` 的 Step 0 与用户确认运行路径，不得默认假设。  
- **补充检查**（与非源码模式或细节一致时）：  
  1. `<REPO_ROOT>/tools/symbol_recovery` 已执行 `uv pip install -e .` 安装依赖
  2. 虚拟环境存在且 `main.py` 可正常导入 `core` 模块
- 默认路径（必须）：**主 Agent 一次性闭环**。即在同一次 `update` 中完成  
  `导出 symbol_recovery_llm_tasks.json -> Agent 推断 -> 生成 symbol_recovery_external_results.json -> --import-llm-results 回填`。  
- 可选路径（仅在用户明确指定时）：
  1. **在线直连 LLM**：检查 `tools/symbol_recovery/.env` 中 API Key。  
  2. **无 LLM 快速模式**：`--no-llm`，仅反汇编与基础证据输出（用户明确接受“无语义化函数名回填”时才允许）。  
- 若用户未明确指定“在线直连”或“no-llm”，则必须按默认路径执行，**不得停在 tasks 导出态**。

**`hapray update` 集成路径（与上述“三选一”并行，以代码为准）**：

集成符号恢复由 `perf_testing/hapray/actions/update_action.py` + `perf_analyzer.py` 实现，**默认行为**为：

1. **SO**：解析顺序为 `update --so_dir` → 环境变量 `HAPRAY_SO_DIR` → 若仍无有效目录，则在 **`hdc` 可用且设备在线** 时，按 `testInfo.json` 的 **`app_id`（包名）**：先 **`hdc shell bm dump -n <包名>`** 从安装信息 JSON 中取模块/安装路径，再在 `--report_dir/.symbol_recovery_libs/<bundle>/` 上对对应 **`libs` / `libs/arm64`** 做 **`file recv`**；若仍拿不到 `.so`，再用**仅靠包名字符串**的常见兜底路径（细节见 `analysis/symbol-recovery-analysis.md`）。**不靠 PID/ps 作为主拉取路径。**  
2. **符号恢复模式**：**默认 Agent**；仅 `--symbol-recovery-llm-mode` 时先 LLM 探活+在线执行，失败回退 Agent（见 `update_action` / `symbol_recovery_bridge`）。  
3. **应用包 / root-cause 输入**：优先 §0 用户 `--app-packages-dir`（自动识别源码 vs HAP）；未提供且设备在线时才拉 HAP；源码树 **不** 走 HAP 反编译。  
4. **root-cause**：默认在 update 末段执行（`--no-root-cause` 可跳过），结果写入 `report/root_cause.md` 与总报告 `more.root_cause`。  
5. **前提**：符号恢复须有 SO（§0 或拉取）；无则跳过。root-cause 须有 §0 输入或拉取成功；无则跳过。须 `trace_emptyFrame.json`。

**一次性完成（强制）**：

- 目标是“单次 `update` 内闭环”：在线 LLM 可用且探活通过则走在线子进程；否则在同一次 `update` 内走 **Agent 编排**（`prompt-only` 导出 → Step2 推断 → `--import-llm-results`），禁止停在仅导出 `tasks` 即宣称完成。  
- **Agent Step2 推断（默认）**：在已配置 `HAPRAY_SYMBOL_RECOVERY_AGENT_CMD` 时优先执行该命令（占位符 `{tasks}`、`{output}`、`{out_dir}`、`{scene}`）；否则由 `perf_testing` 通过 **`symbol_recovery` 启动器**（`symbol-recovery` / `python main.py`）子进程调用 **`--step2-openai --step2-tasks … --step2-output …`**（实现位于 `core.utils.step2_agent`，**禁止**再依赖 `scripts/run_step2.py` 路径）；仅当无启动器且存在可导入的源码树时，才回退同进程导入 Step2。手工切批/合并请使用 **`main.py --step2-split` / `--step2-merge`**（见 `main.py --help`），勿再以集成路径调用 `scripts/run_step2.py`。  
- 若本次执行结束仍未产出可用 `symbol_recovery_external_results.json`，必须标记为“未完成真实推断（失败）”，不得输出“与无外填设定一致”之类成功语义；应给出阻塞原因与一次性重试命令。

**交付验收门禁（必须全部满足，缺一即判失败）**：

1. `reports/.../.symbol_recovery/<step>/symbol_recovery_llm_tasks.json` 存在。  
2. 同目录存在 `symbol_recovery_external_results.json`，且包含非空 `function_name`。  
3. `hiperf/<step>/symbol_recovery_replacements.json` 存在，且 `replaced` 不得是 `auto_recovered_*` 占位名。  
4. `hiperf/<step>/hiperf_report_with_inferred_symbols.html` 存在。  

若仅满足第 1 条（只有 tasks），必须明确结论为“**符号恢复未完成**”，禁止写“已完成更新流程/已完成符号恢复”。

当用户选择“离线编排（主 Agent）”时，主 Agent 负责以下编排职责：

1. 调用 `symbol_recovery` 产出待分析任务（含 `function_id` 与 prompt/上下文）。  
2. 将任务分发给外部模型通道（可由 GUI Agent、平台代理或人工调用）。  
3. 对返回结果做结构与内容规范校验（`function_id` 对齐、JSON 字段完整、命名与语言约束满足）。  
4. 回填到 `symbol_recovery` 并触发最终报告更新（Excel/HTML/替换报告）。

离线编排结果约束（写入 Skill，不在代码中硬校验）：

- 每条结果都必须有 `function_name`，不得为空或 `null`。  
- `function_name` 必须是语义化英文函数名，禁止携带地址/偏移后缀（如 `_f96fc`、`_0x1a2b`、`+0x1a2b`、`libxx.so+0x1a2b`）。  
- `functionality` 必须为中文描述。  
- `performance_analysis` 必须为中文描述。  
- 若任一条不满足上述约束，必须在导入前由 Agent 先修正，不得把不合规结果直接回填。

## 执行主流程（统一版）

0. **§0 双路径确认**：发出必问模板并 **等待用户回复**；记录路径。未完成 **STOP**（见 §0）。  
1. 定位 `<RUNTIME_ROOT>`、`<REPO_ROOT>` 与 `<PROJECT_ROOT>`。**若确认为源码仓库**：必须已实质完成「源码工作区硬门禁」；未完成则 **STOP**。  
2. 真机场景先检查 `hdc list targets`（或 `hdc version`）。  
3. 按运行模式执行命令（**仅 §0 完成后**）：二进制轨 / 源码轨 CLI。  
4. **perf 后必须 update**：携带 §0 确认的 `--so_dir`、`--app-packages-dir`（及用户要求的 `--no-root-cause` 等）。  
5. 读取 `--result-file` 或 `hapray-tool-result.json`，解析 `outputs.reports_path`。  
6. 枚举关键产物：`report/*.html`、`htrace/**/trace.db`、`hiperf/**`、日志。  
7. 按子 Skill 路由做深入分析（满足则执行，不满足写跳过原因）。  
8. 生成并更新独立报告（默认 `<PROJECT_ROOT>/reports/`）。

## 异常与降级策略（Fail-Closed + 可交付）

- 二进制下载失败（含超时/404/校验失败）或二进制不可运行：自动回退到源码下载与运行流程；源码流程失败后再停止并提示用户介入。  
- `gui-agent` 不可用：在获得用户确认后降级到 `perf --run_testcases`，并记录“能力降级影响”。  
- `symbol-recovery`：若已配置 LLM 环境但请求仍失败（额度/鉴权/网络），单次子进程内已尽力；若**未配置** LLM 环境，则必须走离线 tasks + 外部结果 JSON 回填，禁止把“仅导出 tasks”当作最终交付。  
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

### 完整工作流（perf + update，推荐）

> **§0**：先向用户发出双路径必问模板并 **等待回复**，再执行下方命令。

```bash
# 第1步：perf 采集（§0 已完成）
cd <RUNTIME_ROOT>
./hapray --result-file /tmp/hapray-tool-result.json perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --round 1 \
  -o ./reports

# 第2步：update（携带 §0 确认的路径；未提供则 hdc 兜底）
./hapray --result-file /tmp/hapray-tool-result.json update \
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

### gui-agent 模式

```bash
cd <RUNTIME_ROOT>
./hapray --result-file /tmp/hapray-tool-result.json gui-agent \
  --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页" \
  -o ./
```

### 注意事项

- `--round` 建议：冒烟 `1`；对比评估 `3` 或 `5`
- **update 必须执行**：`perf` 后必须执行 `update`，否则火焰图无符号、无集成 root-cause
- **禁止无故 `--symbol-recovery-no-llm`**：会跳过符号恢复

## 独立分析报告规范

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

## 明确禁止

- **禁止跳过 §0**：未在对话中向用户索取双路径、未等用户回复就执行 `perf`/`update`。  
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
- `analysis/empty-frame-root-cause.md`
