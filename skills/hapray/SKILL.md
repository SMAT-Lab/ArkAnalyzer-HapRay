---
name: hapray
version: "1.5.5"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
description: |
  HapRay (ArkAnalyzer-HapRay) 精简主 Skill：命令执行、路径判定、analysis 路由、报告落盘。默认 `<PROJECT_ROOT>/reports/`。**新 clone 源码：未完成 `web` 构建（vite）则报告模板资源缺失；未完成 `tools/static_analyzer` 构建则 `dist/tools/sa-cmd/` 无 `hapray-sa-cmd`；未执行 `npm run prebuild` 则 `dist/tools/bin/` 无 trace_streamer；未完成 `tools/symbol_recovery` 环境则符号恢复失败。必须先做正文「源码工作区硬门禁」再走 perf/update/dbools。update 执行符号恢复时，若 LLM 失败则强制切换到 Agent 模式完成火焰图替换，禁止直接结束。**
metadata:
  short-description: >-
    HapRay workflow: source clone requires web build + static_analyzer build + symbol_recovery venv before perf/update/dbools. LLM symbol-recovery failure must fallback to agent mode to complete flame graph replacement, never stop at tasks-only state.
  zh-Hans: >-
    精简主流程：`perf_testing`/`update`/`dbtools`/符号恢复前必读「源码工作区硬门禁」。
    update 符号恢复时 LLM 失败强制切 Agent 模式完成火焰图替换，禁止停在 tasks-only 状态。再执行 CLI→读 reports_path→子 Skill→独立报告 `<PROJECT_ROOT>/reports/`。
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
---

# HapRay 引导式工作流

目标：让 Agent 以更短路径完成 **下载最新二进制（失败回退源码）→ 采集/执行 → 解析产物 → 子 Skill 深入分析 → 独立报告落盘**，并具备可恢复、可审计、可机读的执行闭环。

## TL;DR（30 秒）

1. **源码工作区（硬门禁）**：若当前是 `<REPO_ROOT>`（检出代码、存在 `perf_testing/`）：**先于任何** `perf` / `update` / **perf.data→perf.db（hiperf Step1）** / **负载拆解（dbtools）** / **symbol_recovery**，必须完成本节下方「源码工作区硬门禁」自检并通过；失败时**禁止**继续跑链路并写明缺哪一步。仅「已长期配置好的目录」≠ 新克隆可省略；二进制 release 与用户「单独 git clone」是两条线，**不得以「有 hapray 源码」代替已构建产物。**  
2. 判定路径：先分清 `<RUNTIME_ROOT>`（二进制运行目录）、`<REPO_ROOT>`（源码运行目录）与 `<PROJECT_ROOT>`（写报告）。  
3. 先快诊后升级：默认 Quick，命中触发条件再升级 Full。  
4. 跑命令：必须实际执行 `gui-agent/perf/opt/static` 之一（按意图）。  
5. 读产物：从 `hapray-tool-result.json`（或 `--result-file`）取 `outputs.reports_path`。  
6. 路由分析：按 `analysis/README.md` 逐项评估子 Skill；满足条件则执行，不满足写跳过原因。  
7. 落盘报告：写到 `<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<topic>.md`，正文固定结构 + 文末元信息与执行轨迹。

> **🚨 关键强制要求（新增）**：
> - `perf` 采集后**必须**执行 `update` 进行符号恢复
> - **禁止**在 `update` 中使用 `--no-llm` 参数（除非用户**明确**要求跳过符号恢复）
> - LLM 失败时**必须**自动切换到 Agent 模式完成，禁止直接结束

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

## 源码工作区硬门禁（高于 Quick/Full，默认 MUST）

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
| 5 | **symbol_recovery** | 必选 | `cd tools/symbol_recovery && uv venv .venv && uv sync`，然后安装 radare2 + 反编译插件（r2dec 或 r2ghidra） | `.venv/bin/python main.py --help` 可运行 + `r2 -v` 正常 + `r2pm list` 含 r2dec 或 r2ghidra |
| 6 | hilogtool | 可选 | 从 release 复制到 `tools/bin/` | `tools/bin/hilogtool --help` 可执行 |
| 7 | opt_detector | 可选 | 从 release 复制到 `tools/opt_detector/` | `tools/opt_detector/opt-detector --help` 可执行 |

> **必选说明**：symbol_recovery（第5步）涉及 `perf.data→perf.db` 转换、火焰图符号推断或 `update` 符号恢复时必须。radare2 及其反编译插件（r2dec/r2ghidra）是符号恢复的核心依赖，反编译质量直接影响 LLM 推断准确率，未安装时无法使用反编译功能。

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

#### 第5步：Symbol Recovery + Radare2（必选）

先创建 venv 并安装 Python 依赖：

```bash
cd <REPO_ROOT>/tools/symbol_recovery
uv venv .venv
uv sync
# 或：uv pip install -e .
```

**安装 radare2 + 反编译插件（必选，选装 r2dec 或 r2ghidra 之一）**：

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

> Windows 下 `r2pm` 需要联网；若企业内网受限，可从 [radare2 GitHub Releases](https://github.com/radareorg/radare2/releases) 下载 `.zip` 解压后将 `bin/` 加入 `PATH`。

**验证**：
```bash
# 1. symbol_recovery 入口
.venv/bin/python main.py --help        # Linux/macOS
.venv/Scripts/python main.py --help     # Windows

# 2. radare2 已安装
r2 -v

# 3. 反编译插件已安装（r2dec 或 r2ghidra 至少一个）
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

# radare2 + 反编译插件（必选）
if command -v r2 >/dev/null 2>&1; then
    echo "✓ 第5步: radare2 已安装 ($(r2 -v 2>&1 | head -1))"
    if r2pm list 2>/dev/null | grep -qE "r2dec|r2ghidra"; then
        echo "✓ 第5步: 反编译插件已安装 (r2dec/r2ghidra)"
    else
        echo "✗ 第5步: 反编译插件缺失，执行: r2pm install r2dec"
    fi
else
    echo "✗ 第5步: radare2 未安装"
    echo "   macOS: brew install radare2"
    echo "   Windows: winget install radare2"
fi

echo ""
echo "=== 验证完成 ==="
echo "所有 ✓ 通过后方可执行 perf/update/static 等命令"
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

# radare2 + 反编译插件（必选）
$r2check = Get-Command r2 -ErrorAction SilentlyContinue
if ($r2check) {
    Write-Host "✓ 第5步: radare2 已安装" -ForegroundColor Green
    $r2pmList = & r2pm list 2>$null
    if ($r2pmList -match "r2dec|r2ghidra") {
        Write-Host "✓ 第5步: 反编译插件已安装 (r2dec/r2ghidra)" -ForegroundColor Green
    } else {
        Write-Host "✗ 第5步: 反编译插件缺失，执行: r2pm install r2dec" -ForegroundColor Red
    }
} else {
    Write-Host "✗ 第5步: radare2 未安装" -ForegroundColor Red
    Write-Host "   执行: winget install radare2 或 choco install radare2" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 验证完成 ===" -ForegroundColor Cyan
Write-Host "所有 ✓ 通过后方可执行 perf/update/static 等命令" -ForegroundColor White
```

---

### 完整执行流程（含符号恢复）

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
  --report_dir <REPORT_DIR>          # 必填：perf 采集输出目录（含 hiperf/ 子目录）
  --so_dir <SO_DIR>                  # 可选：符号库目录（含 .so 文件的目录）
  --symbol-recovery-agent-mode       # 可选：强制使用离线 Agent 模式（跳过在线 LLM 探活）
```

**⚠️ 禁止使用的参数（除非用户明确要求）**：
- ❌ `--symbol-recovery-no-llm`：**绝对禁止**使用，这会完全跳过符号恢复，导致火焰图无函数名
- ❌ `--no-llm`：**绝对禁止**使用，同上

**正确的心态**：
- 默认执行 `update` **不加任何 LLM 相关参数**，让系统自动处理（先探活 LLM，失败自动切 Agent）
- 只有用户**明确说"不需要符号恢复"**时，才考虑使用 `--symbol-recovery-no-llm`

**SO 目录获取方式**（三选一）：

1. **自动拉取**（推荐）：update 自动检测设备在线时，通过 `hdc shell bm dump -n <包名>` 获取安装路径，再 `hdc file recv` 拉取符号库
2. **手动指定**：`--so_dir <本地 .so 文件目录>`
3. **环境变量**：`export HAPRAY_SO_DIR=<本地 .so 文件目录>`

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

> 若 `hiperf_report_with_inferred_symbols.html` 不存在，说明符号恢复未完成，火焰图仍显示原始地址。

#### ⚠️ LLM 失败时强制走 Agent 模式（禁止结束）

**自动降级策略（必须执行）**：

update 执行时会自动探测 LLM 可用性（探活），按以下优先级处理：

| 场景 | 自动行为 | 必须产出 |
|------|----------|----------|
| LLM 探活通过 → 在线执行成功 | 使用在线 LLM 完成符号推断 | `symbol_recovery_external_results.json` + 增强火焰图 |
| LLM 探活失败（402/鉴权/网络） | **强制自动切换到 Agent 模式** | `symbol_recovery_llm_tasks.json` → 外部推断 → `symbol_recovery_external_results.json` |
| 在线执行中途失败 | **强制同次切换到 Agent 模式** | 同上 |
| Agent 模式也失败 | 标记为失败，给出重试命令 | 明确结论"符号恢复失败" |

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
| `symbol_recovery 子进程退出` / `perf.db` 生成失败 | 第5步 symbol_recovery 未配置 | `cd tools/symbol_recovery && uv venv .venv && uv sync` |
| `hilogtool not found` | 第6步 hilogtool 未复制（可选） | 从 release 复制 `tools/bin/hilogtool` |
| 静态分析命令 `static` 失败 | 第3步 static_analyzer 缺失 | 见上 |

---

### 自检执行规范（MUST）

1. **进入源码模式必须执行全部7步验证**，不可假设「以前配置过」或「应该没问题」
2. **每步必须有验证证据**，在对话中输出验证结果（✓ 或 ✗）
3. **任一必备步骤（1-4，以及涉及时的5）为 ✗ 时，必须 STOP**，禁止继续执行 perf/update/static 等命令
4. **可选步骤（6-7）为 ✗ 时，可降级继续**，但需告知用户哪些功能将不可用
5. **全部通过后，在报告中记录构建状态**，包括版本信息和验证时间

---

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
   - **安装 radare2（必选）**：
     - macOS：`brew install radare2 && r2pm install r2dec`
     - Windows：`winget install radare2` 或 `choco install radare2`，然后 `r2pm install r2dec`
   - 验证：
     ```bash
     .venv/bin/python main.py --help        # Linux/macOS
     .venv/Scripts/python main.py --help     # Windows
     r2 -v
     r2pm list | grep -E "r2dec|r2ghidra"
     ```
5. 自检 `uv run python -m scripts.main --help`。  
6. 后续采集命令改为源码方式执行：`uv run python -m scripts.main ...`。  
7. 在执行轨迹中显式记录 `binary_failed_reason`、`fallback_mode=source`、`repo_commit`。

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
8. **可执行自检**：Windows 执行 `.\"./hapray.exe --help`，Linux/macOS 执行 `./hapray --help`；禁止执行系统 PATH 中的 `hapray`。  
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

若未命中：输出 Quick 结论 + 下一轮建议，不强制执行 Full。

## 执行状态机与检查点（可恢复）

按以下状态推进，并在对话与报告中打印阶段状态：

1. `DISCOVER`：路径判定、设备与依赖检查；**若工作区为 `<REPO_ROOT>`，在此阶段完成「源码工作区硬门禁」自检**，缺构建产物不得进入 `EXECUTE`。  
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

- **若为源码仓库（判定见「源码工作区硬门禁」），必须先完成该节最小自检清单（perf_testing、web 构建、`dist/tools/sa-cmd`、trace_streamer、symbol_recovery venv）并留证据**，再执行 `perf`/`update`/符号恢复链路；未完成时禁止谎称环境就绪。  
- **符号恢复必须一次性闭环交付**：若进入符号恢复链路，必须在同一次 `update` 内完成 `tasks -> symbol_recovery_external_results.json -> import -> 替换产物`，禁止“做一半停一半”。  
- **🚨 LLM 失败时必须强制切换到 Agent 模式（最强制要求）**：update 执行符号恢复时，若 LLM 探活失败（402/鉴权/网络）或在线执行中途失败，**必须立即同次切换到 Agent 模式**，继续完成 `tasks -> external_results -> import -> 火焰图替换`，禁止直接结束或仅停留在 tasks 导出状态。这是硬性要求，不得因“LLM 不可用”就结束 update。  
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

- **源码模式前置**：必须与「源码工作区硬门禁」一致——**已构建** `<REPO_ROOT>/dist/tools/sa-cmd/`（static_analyzer）、**已在** `<REPO_ROOT>/tools/symbol_recovery` 装好 venv 且 `main.py --help` 可通过；**radare2 + 反编译插件（r2dec/r2ghidra）已安装**（`r2 -v` 正常且 `r2pm list` 含 r2dec 或 r2ghidra）；未完成则本条门禁为 **FAIL-CLOSED**（跳过 LLM/OpenAI 讨论，先做构建）。  
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
2. **LLM**：在已配置 Key/Base URL 且未 `--symbol-recovery-no-llm`、非强制纯 agent 时，**先运行时探活**；探活失败（如 `402` 额度、鉴权、网络）则**自动进入 agent 模式**，后续在同一次 `update` 内走 **prompt-only** 或在线失败后再 **prompt-only**（见下「一次性完成」）。  
3. **前提**：无论在线还是 agent，**都必须有可用 SO 目录**；自动拉库失败时日志会出现 `Failed to auto-download libs for bundle`，此时集成符号恢复整段**跳过**（不是 LLM 逻辑未生效），需用户补 `--so_dir` 或排查设备/路径。

**一次性完成（强制）**：

- 目标是“单次 `update` 内闭环”：默认先尝试在线直连；一旦探活失败或在线执行失败，**立即同次切换 Agent**，完成 `tasks -> external_results -> import`，禁止要求用户二次执行 `update`/二次回填。  
- **Agent 默认执行**：子进程导出 `symbol_recovery_llm_tasks.json` 后，必须在同一次 `update` 内执行真实 Agent 推断并生成 `symbol_recovery_external_results.json`。默认调用内置 `tools/symbol_recovery/scripts/run_step2.py openai --tasks ... --output ...`；`HAPRAY_SYMBOL_RECOVERY_AGENT_CMD` 仅作覆盖（支持 `{tasks}`、`{output}`、`{out_dir}`、`{scene}`）。  
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

1. 定位 `<RUNTIME_ROOT>`、`<REPO_ROOT>` 与 `<PROJECT_ROOT>`。**若确认为源码仓库**：必须已实质完成「源码工作区硬门禁」（web 构建产物、`dist/tools/sa-cmd/`、trace_streamer、symbol_recovery 可运行等），未完成则在此处 **STOP**，不得强行执行后续步骤。  
2. 真机场景先检查 `hdc list targets`（或 `hdc version`）。  
3. 按运行模式执行命令：二进制模式在 `<RUNTIME_ROOT>` 执行（Windows `.\"./hapray.exe`，Linux/macOS `./hapray`）；源码模式在 `<REPO_ROOT>/perf_testing` 执行 `uv run python -m scripts.main ...`（须在步骤 1 已满足硬门禁）。  
4. **perf 采集后必须执行 update**：`uv run python -m scripts.main update --report_dir <perf输出目录>`，**禁止**使用 `--no-llm` 参数。  
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

```bash
# 第1步：perf 采集（生成原始报告）
cd <RUNTIME_ROOT>
./hapray --result-file /tmp/hapray-tool-result.json perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --round 1 \
  -o ./reports

# 第2步：update 符号恢复（必须执行，生成增强火焰图）
./hapray --result-file /tmp/hapray-tool-result.json update \
  --report_dir ./reports/<timestamp>
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
- **update 必须执行**：`perf` 后必须执行 `update`，否则火焰图无符号
- **禁止 `--no-llm`**：update 时**绝对禁止**加 `--no-llm`，这会跳过符号恢复

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
