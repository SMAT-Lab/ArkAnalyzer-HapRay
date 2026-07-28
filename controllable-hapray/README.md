# Controllable HapRay

这是对 HapRay Skill 的可观察、可控制 TypeScript 服务封装。外部 Skill 文档和确定性脚本作为每阶段的执行规范；服务负责固定阶段边界、调用 OpenCode Agent、传递结构化阶段结果、持久化状态，并通过 HTTP/SSE 暴露整个工作流。

**本仓库不复制或维护 HapRay Skill，请通过 `HAPRAY_SKILL_ROOT` 指向包含 `SKILL.md` 的外部目录。**

流水线固定为：

```text
0 path-gate → 1 setup → 2 collect → [3 symbol-recovery] → 4 analysis → [5 root-cause] → 6 deliver
```

- `existing-report` 会显式跳过 setup 和 collect。
- 符号恢复默认 `auto`：只有明确需要符号级热点且存在 stripped 地址时才运行；也可设为 `always` 或 `never`。
- `quick` 模式跳过综合 root-cause；`full` 模式执行独立 root-cause CLI 和 Agent 源码补充深挖。
- 每个 Agent 阶段使用独立 OpenCode session。上游只通过结构化结果进入下游，避免重新形成一个不可见的端到端 Agent session。

## 运行

要求 Node.js 20+、可执行的 `opencode` CLI、已配置好的 OpenCode model/provider 凭据，以及本地可用的 HapRay Skill 目录。Web 设备预览还需要 `hdc` 位于 `PATH`（或通过 `HDC_PATH` 指定）。

```bash
npm install
npm run build
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm start
```

构建完成后，单个 HTTP 服务同时提供 Web Dashboard 和 API：打开 `http://127.0.0.1:8787/` 使用 GUI，`/v1/*` 继续提供程序化接口。`npm install` 通过 npm workspace 安装根服务和 dashboard 的全部依赖，`npm run build` 同时构建两者。

### Web Dashboard

`dashboard/` 提供与本服务 API 直接对接的 React GUI。它使用服务端的 `RunState`、结构化 findings/artifacts 和可重放 SSE 事件作为唯一状态来源，不再运行独立的 OpenCode bridge 或工作流状态机。生产构建由同一个 Node HTTP 服务从 `dashboard/dist` 提供，不需要额外的静态服务器或反向代理。

```bash
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm run dashboard:dev
```

该命令同时启动 HapRay 服务（`127.0.0.1:8787`）和 Vite（默认 `localhost:5173`）。页面左侧创建完整的 `RunRequest`：目录字段通过服务端目录选择器填写；`full` 显示 HapRay 工具目录以及实时发现的 HDC device、package 和 `PerfLoad_*` testcase；`existing-report` 只显示报告路径。OpenCode 顶级 agent、已连接 provider 和 model 也来自实时服务候选，不能提交任意值。中间展示七阶段进度、Session、实时耗时/Token、可复制的阶段详情、产物与事件，右侧展示结构化性能问题和根因。检测到 HDC 设备后可点击 **Monitor** 打开持续刷新的设备截图，点击 **Hide** 收起。

设备预览由 Web 服务入口启动的单个 HDC worker 提供；它选择 `hdc list targets -v` 返回的第一台 Connected 设备，只维护一份连接状态和 JPEG 截图缓存，所有浏览器共享。启动时 HDC 缺失或没有 Connected 设备会禁用 Monitor，但不会阻止 HTTP 服务；后续瞬时采集错误会保留上一帧并在状态中报告错误。`npm run analyze` 的 CLI 入口不会启动该预览 worker（完整采集流程仍可按 HapRay 规范使用请求中的 HDC 设备）。

服务默认监听 `127.0.0.1:8787`，并通过 SDK 自动启动一个随机端口的 headless OpenCode server。如果已有 OpenCode server，可直接连接：

```bash
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill \
  OPENCODE_BASE_URL=http://127.0.0.1:4096 npm start
```

可用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `127.0.0.1` | 服务监听地址 |
| `PORT` | `8787` | 服务端口 |
| `OPENCODE_BASE_URL` | 自动启动 | 连接已有 OpenCode server |
| `HAPRAY_SKILL_ROOT` | 必填 | 外部 HapRay Skill 目录；必须直接包含 `SKILL.md` |
| `DASHBOARD_DIST` | `<repo>/dashboard/dist` | 可选的 Dashboard 生产构建目录；目录不存在时仅提供 API |
| `HDC_PATH` | `hdc` | Web 设备预览使用的 HDC 可执行文件 |
| `HDC_PREVIEW_INTERVAL_MS` | `1000` | Web 设备截图刷新间隔，最小 100 ms |

## 发起工作流

### 通过 CLI 发起工作流

无需先启动 HTTP 服务。通过 `--kind full` 从已连接设备采集并分析；通过 `--kind existing-report` 分析已有报告。为兼容原有命令，省略 `--kind` 时若提供 `--reports` 则推断为 `existing-report`，否则推断为 `full`。

完整采集与分析：

```bash
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm run analyze -- \
  --kind full \
  --project-root /absolute/path/to/workspace \
  --hapray-root /absolute/path/to/hapray-tool \
  --request "采集首页滑动场景并完成全面性能分析" \
  --package-name com.example.app \
  --testcase PerfLoad_home_scroll \
  --device <hdc-target-serial> \
  --runtime-track auto \
  --source /absolute/path/to/app/source \
  --so /absolute/path/to/app/libs \
  --output-dir /absolute/path/to/final/reports \
  --model deepseek/deepseek-v4-flash \
  --mode full \
  --symbol-recovery auto
```

`HAPRAY_SKILL_ROOT` 是所有 run 都会读取的服务/CLI 规范目录；`full` run 还必须用 `--hapray-root` 指定 Agent 实际执行的、已存在的 HapRay 工具目录。只有一台 HDC 设备在线时可省略 `--device`。源码轨可另外通过 `--runtime-track source --repo-root /absolute/path/to/HapRay-source` 显式指定源码仓库；`repoRoot` 与工具执行根目录含义不同。

分析已有报告：

```bash
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm run analyze -- \
  --kind existing-report \
  --project-root /absolute/path/to/workspace \
  --reports /absolute/path/to/workspace/reports/<timestamp>/<case> \
  --source /absolute/path/to/app/source \
  --so /absolute/path/to/app/libs \
  --output-dir /absolute/path/to/final/reports \
  --model deepseek/deepseek-v4-flash \
  --mode full \
  --symbol-recovery auto
```

CLI 使用同一套 pipeline、状态持久化和 OpenCode SDK。创建持久化 Run 前会执行 Path Gate，并对用户提供的 agent/model 以及 Full Run 的 device/package/testcase 做实时 preflight；无效配置以状态码 2 退出。CLI 不启动 Web 设备预览 worker。`full` run 执行 setup 和 collect，`existing-report` run 显式跳过这两阶段。终端输出阶段生命周期，完成后打印报告、finding 和 `state.json` 路径；添加 `--json` 可输出 JSON Lines 事件流。

### HTTP API

路径门禁不再通过同一个 Agent session 分两轮询问，而是变成请求契约：服务在创建 run 前一次性校验并 canonicalize 路径。`projectRoot` 必须存在；`full` 必须提供 `haprayRoot`，`existing-report` 必须提供位于工作区内的 `reportsPath`。中间产物位于 `projectRoot` 内，最终报告可写入显式指定且已存在的 `outputDir`。源码、SO、HapRay 工具目录和源码仓路径可以是外部输入。

```bash
curl -X POST http://127.0.0.1:8787/v1/runs \
  -H 'content-type: application/json' \
  -d '{
    "request": "采集首页滑动场景并完成全面性能分析",
    "projectRoot": "/absolute/path/to/workspace",
    "kind": "full",
    "haprayRoot": "/absolute/path/to/hapray-tool",
    "sourceDir": "/absolute/path/to/app/source",
    "soDir": "/absolute/path/to/app/libs/arm64",
    "packageName": "com.example.app",
    "testcase": "PerfLoad_scroll",
    "mode": "full",
    "runtimeTrack": "auto",
    "symbolRecovery": "auto",
    "opencode": {
      "agent": "build",
      "model": { "providerID": "anthropic", "modelID": "claude-sonnet-4-6" }
    }
  }'
```

分析已有报告：

```json
{
  "request": "分析已有报告并定位根因",
  "projectRoot": "/absolute/path/to/workspace",
  "kind": "existing-report",
  "reportsPath": "/absolute/path/to/workspace/reports/20260715/PerfLoad_scroll",
  "sourceDir": "/absolute/path/to/app/source",
  "mode": "full",
  "symbolRecovery": "never"
}
```

主要请求字段：

| 字段 | 值 | 说明 |
|---|---|---|
| `kind` | `full` / `existing-report` | 默认 `full` |
| `haprayRoot` | 绝对目录路径 | `full` 必填且目录必须已存在；Agent 执行 HapRay 的工具/运行时根目录；`existing-report` 禁止传入 |
| `mode` | `quick` / `full` | 默认 `full` |
| `runtimeTrack` | `auto` / `binary` / `source` | 默认 `auto`，二进制优先 |
| `symbolRecovery` | `auto` / `always` / `never` | 默认 `auto` |
| `outputDir` | 路径 | 最终报告目录；CLI 对应 `--output-dir`，默认 `<projectRoot>/reports` |
| `sourceDir` | 绝对或可解析路径 | root-cause 源码级定位输入，可省略并降级 |
| `soDir` | 绝对或可解析路径 | 符号恢复输入，可省略并按原 Skill 尝试设备拉取 |
| `repoRoot` | 路径 | HapRay 源码轨仓库；与 `haprayRoot` 分离 |
| `packageName` | bundle/package ID | CLI 对应 `--package-name`，用于采集目标应用 |
| `testcase` | `PerfLoad_*` 名称 | CLI 对应 `--testcase`，可指定预设或待生成用例 |
| `device` | HDC target serial | CLI 对应 `--device`；单设备时可省略 |
| `opencode.baseUrl` | URL | 单次 run 覆盖全局 OpenCode endpoint |

## 查询、订阅与取消

创建接口返回 `Location` 和 `events`。因为状态严格落在各个 `projectRoot` 内，查询 URL 必须携带该路径。

```bash
curl 'http://127.0.0.1:8787/v1/runs/<run-id>?projectRoot=/absolute/path/to/workspace'

curl -N -H 'accept: text/event-stream' \
  'http://127.0.0.1:8787/v1/runs/<run-id>?projectRoot=/absolute/path/to/workspace&stream=true'

curl -X DELETE \
  'http://127.0.0.1:8787/v1/runs/<run-id>?projectRoot=/absolute/path/to/workspace'
```

Web 初始化接口为 `GET /v1/fs/directories`（本地目录浏览）和 `GET /v1/options`（OpenCode、HDC、package、testcase 候选）。`POST /v1/runs` 会重新校验选择值，不能依赖前端校验。设备预览接口为 `GET /v1/device`（worker 可用性、连接状态、当前 target 和 frame 时间）和 `GET /v1/device/frame`（最新缓存 JPEG，`Cache-Control: no-store`）。

SSE 使用递增 `id`，支持 `Last-Event-ID` 或 `after=<id>` 断线续传。事件包括：

- run 生命周期：`run.created/started/completed/failed/cancelled`
- stage 生命周期：`stage.started/completed/skipped/failed`
- 内容更新：`artifact.updated`
- 诊断发现：`finding.discovered`，区分 performance bug、root cause 和 observation
- OpenCode 压缩进度：`agent.event`，包含消息、tool 和 session 状态快照；逐字符 token delta 不持久化

每个 run 持久化到：

```text
<projectRoot>/.hapray-service/runs/<run-id>/
├── state.json
└── events.jsonl
```

## 开发验证

```bash
npm run typecheck
npm test
npm --workspace controllable-hapray-dashboard test
npm --workspace controllable-hapray-dashboard run lint
npm run build
```
