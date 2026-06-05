> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 1b**

# 源码工作区硬门禁（§4）

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

- `uv run python -m scripts.main perf ...`、`static`、`dbtools` 相关采集与报告链路；以及可选的 `update`（符号恢复，阶段3）；  
- 依赖 **`web/dist/`** 或 **`perf_testing/resource/web/`**（报告模板资源）的任何报告生成步骤；  
- 依赖 **`dist/tools/sa-cmd/`**（`hapray-sa-cmd`）的静态分析步骤；  
- **symbol_recovery**：`tools/symbol_recovery/main.py`（含 `--skip-step1`）、以及**可选阶段3** `hapray update --so_dir` 触发的符号恢复子进程。

> **门禁性质澄清**：本节 7 步是「源码轨能否跑起来」的环境门禁，与「perf 后是否跑 update」无关。构建完成后，**默认流程**是 `perf` → 读 `report/` 做高负载分析（不跑 update）；符号恢复是可选阶段3，root-cause 走独立 CLI。第 5 步 symbol_recovery venv 的硬门禁主要服务于 `perf.data→perf.db` 与可选符号恢复。

若用户坚持「我就要现在跑」，必须先输出**阻塞原因**：缺哪项构建/安装 + 本节对应命令。

---

### 完整构建清单（7步，必须全部完成）

| 步骤 | 模块 | 性质 | 构建命令 | 验证方法 |
|:----:|------|:----:|----------|----------|
| 1 | **perf_testing Python** | 必选 | `cd perf_testing && uv sync` | `python -m scripts.main --help` 正常输出 |
| 2 | **web** | 必选 | `cd web && npm install && npm run build` | `web/dist/index.html`、`report_template.html`、`hiperf_report_template.html` 均存在 |
| 3 | **static_analyzer** | 必选 | `cd tools/static_analyzer && npm install && npm run build` | `dist/tools/sa-cmd/hapray-sa-cmd.js` 或 `.exe` 存在 |
| 4 | **trace_streamer** | 必选 | 执行 `npm run prebuild` 解压 `third-party/trace_streamer_binary.zip` | `dist/tools/bin/trace_streamer_* --version` 可执行 |
| 5 | **symbol_recovery** | 必选（venv）／ radare2+源码分析 **建议** | `cd tools/symbol_recovery && uv venv .venv && uv sync`；radare2、r2dec/r2ghidra 见第5步正文（**能装则装**） | **硬门禁仅** `.venv` 下 `main.py --help` 可运行；**不**将 `r2` / `r2pm` 源码分析插件缺失算作 ✗ 或 STOP 条件 |
| 6 | hilogtool | 可选 | 从 release 复制到 `tools/bin/` | `tools/bin/hilogtool --help` 可执行 |
| 7 | opt_detector | 可选 | 从 release 复制到 `tools/opt_detector/` | `tools/opt_detector/opt-detector --help` 可执行 |

> **必选说明**：第5步 **硬门禁**仅为 `tools/symbol_recovery` 的 Python venv 与 `main.py --help`（涉及 `perf.data→perf.db`、`update` 符号恢复子进程等）。**radare2 与 r2dec/r2ghidra 源码分析插件为建议项**：能装则装，装不上或网络差**不阻塞**后续 `perf`/`update`/报告链路；源码分析与 LLM 证据质量可能降级，须在对话或报告中注明即可。国内拉 GitHub 慢时见第5步「国内网络」：**勿死等裸连**。

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

#### 第5步：Symbol Recovery（必选）+ Radare2 / 源码分析（建议）

先创建 venv 并安装 Python 依赖（**以下为硬门禁**）：

```bash
cd <REPO_ROOT>/tools/symbol_recovery
uv venv .venv
uv sync
# 或：uv pip install -e .
```

**安装 radare2 + 源码分析插件（建议，非硬门禁；能安则安，安不上可跳过）**：

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

# 安装完成后安装源码分析插件（r2dec/r2ghidra 辅助解析二进制）
r2pm install r2dec
# 或：r2pm install r2ghidra
```

> **国内网络（安装 radare2 / r2pm 时）**：**默认禁止**为装 radare2/r2pm 访问 GitHub（见文首「全局规范」）。**①** 优先 `brew` / `winget` / `choco`；**②** `r2pm install` 若 **2～3 分钟无进度则直接跳过**（不影响硬门禁）；**③** 企业内网若有 radare2 离线 zip，解压并加 `PATH`；**④** macOS 可配 Homebrew 镜像后 `brew install radare2`。**禁止**死等 `github.com` 或要用户去 GitHub Releases 下载。
> 
> **符号恢复说明**：radare2 用于分析二进制文件中的热点函数，r2dec/r2ghidra 作为可选插件提供汇编到伪代码的转换能力，辅助 LLM 理解函数逻辑。

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

---

### 常见失败场景速查表

| 报错信息 | 缺少的构建步骤 | 修复命令 |
|----------|---------------|----------|
| `report_template.html` 或 `hiperf_report_template.html` 或 `web/dist/index.html` 不存在 | 第2步 web 未构建 | `cd web && npm install && npm run build` |
| `hapray-sa-cmd not found` / `ExeUtils.get_hapray_cmd_path` 失败 | 第3步 static_analyzer 未构建 | `cd tools/static_analyzer && npm install && npm run build` |
| `trace_streamer not found` / `ExeUtils.get_trace_streamer_path` 失败 | 第4步 trace_streamer 未解压 | 执行 `npm run prebuild` 解压 `third-party/trace_streamer_binary.zip` |
| `symbol_recovery 子进程退出` / `perf.db` 生成失败 | **源码轨**：第5步 symbol_recovery 未配置 | `cd tools/symbol_recovery && uv venv .venv && uv sync` |
| `symbol_recovery 子进程退出` / 跳过符号恢复 | **二进制轨**：分体包未被发现或未配置 `HAPRAY_SYMBOL_RECOVERY_*` | 见 **workflow/setup-binary.md §5** 符号恢复可发现性 |
| `hilogtool not found` | 第6步 hilogtool 未复制（可选） | 从 release 复制 `tools/bin/hilogtool` |
| 静态分析命令 `static` 失败 | 第3步 static_analyzer 缺失 | 见上 |

---

### 自检执行规范（MUST）

1. **进入源码轨时必须执行 本节 全部 7 步验证**（第 **5** 步硬门槛为 venv + `main.py --help`；radare2/源码分析为建议项），不可假设「以前配置过」；**二进制轨**不做 本节，改做 **workflow/setup-binary.md §5** 最小自检。
2. **每步必须有验证证据**，在对话中输出验证结果（✓ 或 ✗）
3. **任一必备步骤（1–4，以及第5步的 Python venv / `main.py --help`）为 ✗ 时，必须 STOP**，禁止继续执行 perf/update/static 等命令；**第5步中的 radare2 / r2dec / r2ghidra 缺失不算 ✗，不触发 STOP**  
4. **可选步骤（第5步建议栈、第6–7步）为未就绪时，可降级继续**，但需告知用户哪些能力降级或不可用
5. **全部通过后，在报告中记录构建状态**，包括版本信息和验证时间

---

---

---

### 快速验证脚本

在 `<REPO_ROOT>` 根目录执行：

```bash
bash <SKILL_DIR>/scripts/validate-env.sh
```

Windows PowerShell：

```powershell
powershell -File skills/hapray/scripts/validate-env.ps1
```

