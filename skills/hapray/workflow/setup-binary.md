> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 1a**

# 环境获取：二进制直链与源码回退（§3）

在执行任何 HapRay 命令前，必须先完成以下检查：

0. **工作区**：已执行 `<SKILL_DIR>/scripts/ensure-workspace-layout.sh "<PROJECT_ROOT>"`（见主 Skill「工作区落盘」）。  
1. **二进制**：按 **§3.1** 识别系统 → 拼**唯一**直链 → **`curl` 直接下载**到 `<PROJECT_ROOT>/hapray-release/`（不访问发布页、不枚举附件、不 `curl -fIL` 探测多候选）。失败则 **§3.2** 源码回退。  
2. 已下载解压到 `<RUNTIME_ROOT>`（= `<PROJECT_ROOT>/hapray-release/runtime/`），或已准备 `<REPO_ROOT>`（§4 七步）。  
3. 真机场景：`hdc` 可用且设备在线。  
4. 场景依赖已满足（如 `GLM_API_KEY` 仅 **§7** 优先级 3 的 `gui-agent` 需要）。

### 3.1 二进制下载（识别系统 → 拼直链 → 下载）

> **核心原则**：**禁止**访问 GitCode API、Release 页面、`releases/latest` 或任何版本查询接口。Release 文件名是**固定命名**（见下表），直接使用直链下载。

#### 步骤（直接使用直链，禁止版本查询）

| 步 | 动作 |
|:--:|------|
| 1 | **识别平台**（见 §3.1.1），得到唯一 `asset_name` |
| 2 | **确定 `tag`**：用户整链 URL 中的 tag → 否则 `HAPRAY_RELEASE_TAG` → 否则 Skill YAML `version` → `v{version}`（如 `1.5.6` → `v1.5.6`） |
| 3 | **确定 `version`**：`tag` 去掉前缀 `v`（`v1.5.6` → `1.5.6`），代入 `asset_name` 模板 |
| 4 | **拼直链**：用户已给整链则直接用；否则 `{BASE}releases/download/{tag}/{asset_name}` |
| 5 | **`curl -fL` 下载**（见 §3.1.2）到 `<PROJECT_ROOT>/hapray-release/`，解压到 `<RUNTIME_ROOT>`，`hapray --help` 自检 |
| 6 | 记录轨迹：`download_url`、`asset_name`、`tag`、`tag_source`、`platform` |

**`BASE`（站点根，末尾须 `/`，不含 `releases/download`）**

| 顺序 | 来源 |
|:----:|------|
| 1 | 用户给出的整链中解析出的 host 路径，或整链本身 |
| 2 | 环境变量 **`HAPRAY_RELEASES_DOWNLOAD_BASE`**（镜像根，格式同官方） |
| 3 | 默认 **`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/`** |

下载 404/失败且已设 `HAPRAY_RELEASES_DOWNLOAD_BASE` 时：可用镜像 **BASE 重拼同一 URL 再下载一次**；仍失败则 **§3.2**，**禁止**转去发布页核对版本或附件。

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

**直链示例**（`tag=v1.5.6`，`version=1.5.6`）：

- Windows：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases/download/v1.5.6/ArkAnalyzer-HapRay-win32-x64-1.5.6.zip`
- Ubuntu 24.04：`.../ArkAnalyzer-HapRay-linux-x64-ubuntu24.04-1.5.6.zip`
- macOS Apple Silicon：`.../ArkAnalyzer-HapRay_1.5.6_aarch64.dmg`
- macOS Intel：`.../ArkAnalyzer-HapRay_1.5.6_x64.dmg`

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
  -o "<PROJECT_ROOT>/hapray-release/ArkAnalyzer-HapRay-....zip>" \
  "<完整直链URL>"
```

```powershell
# Windows PowerShell：同样优先 curl.exe（不要用 Invoke-WebRequest 除非 curl 不存在）
# --max-time 1800 = 30分钟总超时，--connect-timeout 30 = 30秒连接超时
curl.exe -fL --retry 3 --retry-delay 5 `
  --max-time 1800 --connect-timeout 30 `
  -o "<PROJECT_ROOT>/hapray-release/<文件名>" `
  "<完整直链URL>"
```

**降级 `wget`（同样设置 `-T`/`--timeout` 为30分钟）**：

```bash
# --timeout=1800 连接超时30分钟，--tries=3 重试3次
wget --timeout=1800 --tries=3 -O "<PROJECT_ROOT>/hapray-release/<文件名>" "<完整直链URL>"
```

**下载后**：校验文件存在且大小 **> 0**；zip/dmg 解压到 `<RUNTIME_ROOT>`，执行 **§3.3** `hapray --help`。

**URL 形态（固定，禁止改去发布页核对）**：`{BASE}releases/download/{tag}/{asset_name}`

### 3.2 源码回退（二进制不可下载或不可运行时）

触发条件（满足任一项）：直链 `curl` 404/中断/空文件；解压后 `hapray --help` 失败；核心命令不可运行。

**回退步骤**：见 [`workflow/setup-source.md`](setup-source.md) 完整 7 步构建与验证。概要：

1. `git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git`（已有则 `git pull`）
2. 执行 [`scripts/validate-env.sh`](../scripts/validate-env.sh) 或 [`scripts/validate-env.ps1`](../scripts/validate-env.ps1) 直至全部 ✓
3. 后续命令改用 `uv run python -m scripts.main ...`

### 3.3 `<RUNTIME_ROOT>` 判定（可执行检查）

`<RUNTIME_ROOT>` **固定为** `<PROJECT_ROOT>/hapray-release/runtime/`（DMG/ZIP 解压后的可执行目录）。推荐在执行前做一次检查：

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

---

---

# 二进制发布包模式（§5）

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
| **符号恢复可发现（仅做符号恢复时需要）** | **可选阶段3** `update --so_dir` 会启动符号恢复子进程；**仅当**你要符号级热点时才需满足以下其一。默认高负载分析（读 `report/`）**不依赖**符号恢复。**分体包**（`perf-testing` 与 `symbol-recovery` 分开发行）时**必须**满足其一：① 解压到**同一安装树根**下，使从主程序 exe 目录**向上**能搜到 `symbol-recovery(.exe)` 或 `symbol_recovery/`、`tools/symbol_recovery/` 等约定路径；② 或设置 **`HAPRAY_SYMBOL_RECOVERY_ROOT`**（指向含 `symbol-recovery` 可执行文件或 `main.py` 的目录）、**`HAPRAY_SYMBOL_RECOVERY_EXE`**（直接指向可执行文件）、必要时 **`HAPRAY_SYMBOL_RECOVERY_PYTHON`** |
| LLM / Agent | 与源码轨相同：配置 `LLM_API_KEY`+`LLM_BASE_URL` 等；LLM 失败走 Agent 闭环（见 [gen-perf-report.md §3.5](gen-perf-report.md)） |

### update / 符号恢复在二进制下的注意点（仅可选阶段3）

> 仅当执行可选符号恢复（`update --so_dir`）时相关；默认流程读 `report/` 做高负载分析，不涉及本节。

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
