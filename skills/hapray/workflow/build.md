> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 0.5 build**

# 构建阶段：debug HAP 编译与 .so 抽取（§0.5）

> **范围**：用户有 HarmonyOS 应用源码工程（含 `build-profile.json5`），需要构建 debug 模式 HAP 并抽取带符号 `.so` 文件供 HapRay 符号恢复 / root-cause 使用。
> **前置**：已安装 `devecocli`（`npm install -g @deveco/deveco-cli@latest`）+ DevEco Studio 或 Command Line Tools。
> **产出**：debug HAP 路径 + `.so` 文件目录（自动填充 §0 `so_dir`）。

## 何时触发

| 场景 | 是否触发 |
|------|----------|
| 用户有源码工程，需从源码构建 debug 包 | **必须** |
| 用户已有 debug HAP / .so 文件 | **跳过**（直接进 §0 路径门禁 → 阶段1） |
| 用户仅有 release HAP、无源码 | **跳过**（无法构建；标注「release 包符号不可用」） |

## 前置检查

1. **devecocli 可用性**：
   ```bash
   devecocli --version
   ```
   未安装时提示：`npm install -g @deveco/deveco-cli@latest`

2. **DevEco Studio / Command Line Tools**：devecocli 自动检测。未检测到时按 `DEVECO_CLI_STUDIO_PATH` / `DEVECO_CLI_CLT_PATH` 环境变量指定。

3. **华为开发者账号登录**（首次构建 debug 包时必须）：
   - `build` action 会在签名生成前自动检查登录状态（`devecocli auth status`）
   - **已登录**：直接继续签名生成 + 构建
   - **未登录**：自动执行 `devecocli auth login`，打开浏览器进行 OAuth 认证，等待用户完成登录（超时 5 分钟），登录成功后自动继续构建流程
   - 登录后凭证缓存在本地 `~/.ohos/config/`，后续构建无需再登录
   - 若自动登录失败或超时，提示用户手动执行 `devecocli auth login` 后重试

4. **工程有效性**：`--project-dir` 下含 `build-profile.json5`。

## 签名自动处理

`build` action 会自动检查 `build-profile.json5` 的 `signingConfigs`：
- **签名配置有效**（storeFile 存在且可读）：直接构建
- **签名配置缺失或无效**（storeFile 不存在、指向旧用户等）：
  1. 检查华为开发者账号登录状态（`devecocli auth status`）
  2. **未登录** → 自动执行 `devecocli auth login`（打开浏览器 OAuth，等待用户完成，超时 5 分钟）
  3. 已登录 → 自动调用 `devecocli signature generate --force` 重新生成 debug 签名材料
  4. 签名材料写入 `~/.ohos/config/`，并更新 `build-profile.json5` 的 `signingConfigs`
  5. 继续构建流程

> HarmonyOS 的 debug 包也需要签名（与 Android 的 debug keystore 不同，需从华为 AGC 云端获取 debug 证书和 profile）。

## 命令

```bash
# 源码轨：构建 debug HAP + 抽取 .so + 安装到设备（推荐）
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" \
  --build-mode debug \
  --product default \
  --install --uninstall \
  [--modules entry] \
  [--so-output-dir "<自定义so输出目录>"] \
  [--timeout 1800] \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json

# 仅构建（不安装到设备）
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" \
  --build-mode debug
```
```

**参数**：

| 参数 | 说明 | 默认 |
|------|------|------|
| `-p, --project-dir` | HarmonyOS 源码工程根（含 build-profile.json5） | **必填** |
| `--build-mode` | 构建模式 | `debug` |
| `--product` | build-profile.json5 中的 product 名 | `default` |
| `--modules` | 构建模块（格式 `module` 或 `module@target`） | 自动检测（单 entry 模块） |
| `--so-output-dir` | .so 抽取目录 | `<project_dir>/build/hapray_so_symbols/` |
| `--no-extract-so` | 跳过 .so 抽取 | — |
| `--install` | 构建后安装 HAP 到连接的设备 | — |
| `--device <serial>` | 目标设备序列号（多设备时必填） | 自动检测 |
| `--uninstall` | 安装前先卸载旧版本 | — |
| `--timeout` | 构建超时（秒） | `1800`（30 分钟） |

## 构建后路由

```text
build 成功
  ├─ hap_path 已定位 → .so 已抽取
  │   ├─ so_dir 自动填充 §0 so_dir_user → 跳过 §0 第 2 项询问
  │   └─ 进入阶段 1 setup（如需装设备：用户自行 devecocli run 或 hdc install）
  ├─ hap_path 未定位（metadata 缺失）
  │   └─ 标注「构建成功但产物定位失败」，手动查找 build/outputs/
  └─ build 失败
      └─ 检查 devecocli 日志 → 修正 → 重试
```

### 与 §0 路径门禁的关系

构建成功后，`hapray-tool-result.json` 的 `outputs` 含：
- `hap_path`：debug HAP 文件绝对路径
- `so_dir`：.so 文件目录（可直接用于 `update --so_dir`）
- `bundle_name`：应用包名（可用于 `perf --apps`）
- `build_mode` / `product` / `modules`

Agent 读取 `so_dir` 后，§0 第 2 项（SO 路径）可直接使用该值，无需再问用户。

### 与阶段 3 符号恢复的关系

构建产出的 `.so` 为 debug 符号版（含符号表），可直接用于：
- 阶段 3 `update --so_dir <so_dir>`（符号恢复）
- 阶段 5 `root-cause`（源码级根因定位）

### 安装到设备

`--install` 参数会在构建完成后自动将 signed HAP 安装到连接的设备：
- 单设备自动选择；多设备需 `--device <serial>` 指定
- `--uninstall` 先卸载旧版本（解决签名不一致问题）
- 安装后可用 `hdc shell aa start -a <Ability> -b <bundleName>` 启动应用

## 降级

| 情况 | 动作 |
|------|------|
| `devecocli` 未安装 | 提示 `npm install -g @deveco/deveco-cli@latest`；用户安装后重试 |
| DevEco Studio 未检测到 | 提示设置 `DEVECO_CLI_STUDIO_PATH` 或 `DEVECO_CLI_CLT_PATH` |
| 未登录华为开发者账号 | 自动执行 `devecocli auth login`（打开浏览器 OAuth，等待完成，超时 5 分钟）；失败则提示用户手动登录后重试 |
| 登录超时（5 分钟内未完成） | 提示用户手动执行 `devecocli auth login` 后重试 build 命令 |
| 签名配置无效（旧用户/密码错误） | 自动调用 `devecocli signature generate --force` 重新生成 |
| 构建超时 | 增大 `--timeout`；或用户直接在终端跑 `devecocli build` 后用 `--no-extract-so` 跳过构建只抽 .so |
| 多 entry 模块 | 必须指定 `--modules`；或用户先在终端 `devecocli build` 确定模块名 |
| 安装失败（签名不一致） | 加 `--uninstall` 先卸载旧版本 |

## 二进制轨

二进制轨同样支持 `build` action（`perf-testing build ...`），`devecocli` 须由用户全局安装（不随 HapRay Release 包分发）。

## 源码模式手动构建（build action 降级）

> **触发条件**：源码模式下 `hapray.core.build` 内部模块缺失，`scripts.main build` 会打印降级提示并退出。此时 **Agent 按 本章节直接执行 shell 命令** 完成构建全流程，**禁止**因 action 不可用而跳过构建。

### 0. Node 版本兼容性（MUST 先检查）

`devecocli` 的 ESM 依赖要求 **Node ≥ 20**（`string-width` 用了 `v` flag 正则）。但 `path_utils.ensure_harmony_cli_on_path()` 会把 DevEco 自带的 v18 Node 优先放到 PATH 前面，导致 devecocli 崩溃（`SyntaxError: Invalid regular expression flags`）。

```bash
# 检查 devecocli 实际用的 node 版本
node --version
# 若 < 20，找到系统 Node ≥ 20 并临时前置：
#   macOS:  export PATH=/usr/local/bin:$PATH   (Homebrew node)
#   Linux:  export PATH=/usr/local/bin:$PATH
#   Windows: set "PATH=C:\Program Files\nodejs;%PATH%"
# 验证：devecocli auth status  不再报 SyntaxError
```

### 1. 发现工具（跨平台，Agent 自己执行）

```bash
# devecocli（npm 全局安装）
which devecocli           # macOS/Linux
where devecocli           # Windows

# hdc（DevEco Studio 自带）
which hdc                 # macOS/Linux
where hdc                 # Windows
# 若不在 PATH，从 DevEco Studio 安装目录找：
#   macOS:   /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc
#   Windows: C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe
```

### 2. 检查登录 + 登录

```bash
devecocli auth status
# 未登录时：
devecocli auth login      # 会打开浏览器 OAuth，Agent 发 stdin '\n' 触发，等待用户完成（≤5 分钟）
```

### 3. 生成签名（仅首次或签名无效时）

```bash
# 检查 build-profile.json5 的 signingConfigs 是否有效（storeFile 路径存在且可读）
# 无效时执行：
cd "<HarmonyOS源码工程根>"
devecocli signature generate --force --product default
# 会自动写入 ~/.ohos/config/ 并更新 build-profile.json5
```

### 4. 构建

```bash
cd "<HarmonyOS源码工程根>"
devecocli build --product default --build-mode debug
# 指定模块：devecocli build --product default --build-mode debug --modules entry
```

### 5. 定位产物 + 抽取 .so

```bash
# 找 signed HAP
find "<HarmonyOS源码工程根>/entry/build" -name "*-signed.hap" -o -name "*-unsigned.hap"
# 常见路径：entry/build/default/outputs/default/entry-default-signed.hap

# 抽取 .so（供符号恢复）
#   macOS/Linux:
python3 -c "import zipfile,shutil,os; z=zipfile.ZipFile('<hap_path>'); os.makedirs('<so_out>',exist_ok=True); [shutil.copyfileobj(z.open(n), open(os.path.join('<so_out>',os.path.basename(n)),'wb')) for n in z.namelist() if n.endswith('.so')]"
#   Windows (PowerShell):
# Expand-Archive <hap_path> -DestinationPath <tmp>; Copy-Item <tmp>\libs\*.so <so_out>
```

### 6. 安装到设备

```bash
hdc install "<signed.hap>"
# 签名不一致时先卸载：
hdc shell bm uninstall -n <bundleName> && hdc install "<signed.hap>"
```

### 7. 写 hapray-tool-result.json（供后续阶段读取）

```bash
# Agent 收集以下字段写入 <PROJECT_ROOT>/hapray-tool-result.json：
#   outputs.hap_path / outputs.so_dir / outputs.bundle_name / outputs.build_mode
```
