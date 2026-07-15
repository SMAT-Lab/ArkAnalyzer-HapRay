# Web 参数初始化与 CLI Preflight

## 可行性修正

- 分析请求 `request` 必须保留自由文本；“禁止随意输入”只适用于枚举、路径和可由运行环境发现的标识符。
- 浏览器原生文件输入不会可靠暴露本机绝对路径。Web 端改用后端目录浏览接口，前端只提交选择后的规范路径；最终合法性仍由服务端 Path Gate 判定。
- `testcase` 是 `PerfLoad_*` 标识符而不是路径。候选项从 Full Run 的 `haprayRoot` 下已有 `.js/.ts/.ets/.json` testcase 文件发现。
- 动态校验必须按 Run Kind 执行。Existing-report 不依赖 HDC；Full Run 才校验已提供的 device、package 和 testcase。

## 实施要求

1. 所有目录字段使用只读输入框和目录选择器。`GET /v1/fs/directories` 只列目录；后端在创建 Run 前继续检查绝对路径、存在性、目录类型和边界。
2. `GET /v1/options` 实时聚合以下候选：
   - OpenCode `/agent` 和 `/provider` 返回的非隐藏 primary/all agent、已连接 provider 及 model；
   - `hdc list targets -v` 返回的 Connected device；
   - 选中 device 上 `bm dump -a` 返回的 package；
   - `haprayRoot` 中发现的 `PerfLoad_*` testcase。
3. Web 的 agent、provider、model、device 和 testcase 使用选择框；package 支持搜索但提交值必须精确匹配候选。选项加载完成前禁止创建 Run。
4. HTTP 创建 Run 时再次校验动态值，不能信任前端。OpenCode 或 HDC 的部分发现失败应作为候选错误返回，不影响其他候选展示。
5. CLI 不启动 Web 设备预览 worker，但必须在创建持久化 Run 前完成 Path Gate 和动态值 preflight。只校验用户实际提供的动态字段；失败时打印明确错误、关闭嵌入式 OpenCode server，并以状态码 2 退出。

## 安全边界

目录浏览和运行时发现接口只适用于当前无认证的本地服务，不得暴露到不可信网络。HDC package 查询必须使用已连接的精确 target，OpenCode 候选只查询服务配置或单次 CLI 指定的 endpoint。
