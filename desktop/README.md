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

## 插件与工具契约（perf_testing）

各工具插件的 **`plugin.json`** 若声明顶层 **`tool_contract`**（参见 `perf_testing/plugin.json` 示例），Tauri 会在调用 CLI 时自动注入 **`--result-file`**（及可选 **`--machine-json`**），与命令行 `scripts/main.py` 的全局参数一致；执行结束后优先读取 **`hapray-tool-result.json`** 中的 **`outputs.reports_path`**，再打开报告目录，避免依赖人类可读日志解析。实现见 `src-tauri/src/commands.rs` 中 `execute_tool_command`。
