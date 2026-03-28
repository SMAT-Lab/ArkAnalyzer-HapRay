# Desktop


## 环境准备

如未安装 Rust，可执行：
```bash
npm run install:rust
```

或手动安装各平台脚本：
- **macOS/Linux**: `sh scripts/install-rust.sh`
- **Windows**: `powershell -ExecutionPolicy Bypass -File scripts/install-rust.ps1`

## 运行/编译
**Desktop 开发：**
```bash
npm install
npm run tauri dev
```

### macOS：启动台 /「应用程序」里打开的 App 与 `hdc` / `get_installed_apps`

从终端执行 `which hdc` 正常，但从 **Finder / 启动台** 打开应用时 **`get_installed_apps` 为空**，常见原因：

1. **GUI 的 `PATH` 不含 SDK**。在 **`~/.zshrc` / `~/.bash_profile` 里 `export PATH=...toolchains` 只对终端生效**，**不会**被从启动台启动的 ArkAnalyzer-HapRay 继承，因此「我在 zshrc 里加了 path 还是不行」是正常现象。
2. **仅把 `hdc` 链到 `/usr/local/bin`** 时，动态库 `@rpath/libusb_shared.dylib` 可能仍解析失败（见上文 `hdc` 依赖说明）。

**应用内行为（`commands.rs`）**：会依次尝试

- 环境变量 **`HAPRAY_HDC_PATH`**（指向 `hdc` 的绝对路径）；
- **`$HOME/code/command-line-tools/sdk/default/openharmony/toolchains/hdc`**（若文件存在）；
- **macOS**：**`/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc`**（DevEco Studio 自带 SDK，与你在 zshrc 里加的那段 PATH 一致，但由应用**直接探测**文件，不依赖 `PATH`）；
- 否则回退到在 `PATH` 中查找 **`hdc`**。

命中上述任一绝对路径时，会把 **工作目录设为对应 `toolchains` 目录**，并 **prepend 到子进程 `PATH`**，便于加载同目录下的 `libusb_shared.dylib`。

请先 **重新编译并安装** 当前桌面端，再试；若 SDK 不在上述默认路径，可只对 GUI 设置：

```bash
# 当前登录会话（重启后需重设，或写入 LaunchAgent）
launchctl setenv HAPRAY_HDC_PATH "/你的路径/openharmony/toolchains/hdc"
```

打开应用前执行一次，或把 `HAPRAY_HDC_PATH` 写进 **LaunchAgent** 的 `EnvironmentVariables`（持久生效）。

**备选（系统级 PATH）**：把 **整个 `toolchains` 目录**（不是单独链一个 `hdc`）写入 `/etc/paths.d/` 下单独文件，需 `sudo`，改后通常需 **注销或重启**：

```bash
echo '/你的路径/openharmony/toolchains' | sudo tee /etc/paths.d/openharmony-toolchains
```

## 插件与工具契约（perf_testing）

各工具插件的 **`plugin.json`** 若声明顶层 **`tool_contract`**（参见 `perf_testing/plugin.json` 示例），Tauri 会在调用 CLI 时自动注入 **`--result-file`**（及可选 **`--machine-json`**），与命令行 `scripts/main.py` 的全局参数一致；执行结束后优先读取 **`hapray-tool-result.json`** 中的 **`outputs.reports_path`**，再打开报告目录，避免依赖人类可读日志解析。实现见 `src-tauri/src/commands.rs` 中 `execute_tool_command`。
