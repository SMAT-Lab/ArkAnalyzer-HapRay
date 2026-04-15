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

目标：让 Agent 以更短路径完成 **采集/执行 → 解析产物 → 子 Skill 深入分析 → 独立报告落盘**，并具备可恢复、可审计、可机读的执行闭环。

## TL;DR（30 秒）

1. 判定路径：先分清 `<REPO_ROOT>`（跑 CLI）与 `<PROJECT_ROOT>`（写报告）。  
2. 先快诊后升级：默认 Quick，命中触发条件再升级 Full。  
3. 跑命令：必须实际执行 `gui-agent/perf/opt/static` 之一（按意图）。  
4. 读产物：从 `hapray-tool-result.json`（或 `--result-file`）取 `outputs.reports_path`。  
5. 路由分析：按 `analysis/README.md` 逐项评估子 Skill；满足条件则执行，不满足写跳过原因。  
6. 落盘报告：写到 `<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<topic>.md`，正文固定结构 + 文末元信息与执行轨迹。

## 术语与路径判定

- `<REPO_ROOT>`：包含 `perf_testing/` 的 HapRay 克隆根目录，仅用于运行 CLI。  
- `<PROJECT_ROOT>`：当前 IDE 工作区根目录，默认用于存放独立分析 Markdown。  
- `reports_path`：HapRay 工具采集产物目录（契约字段），**不是**独立分析报告目录。

| 场景 | `<REPO_ROOT>` | `<PROJECT_ROOT>` | 独立报告默认目录 |
|------|---------------|------------------|------------------|
| 工作区只打开 HapRay 单仓 | HapRay 根 | 同上 | `<REPO_ROOT>/reports/` |
| 外层项目 + 内层 HapRay 克隆 | 内层 HapRay 根 | 外层项目根 | `<PROJECT_ROOT>/reports/` |
| 用户指定输出路径 | 按实际 | 按实际 | 用户指定优先 |

## 环境前置条件（新增）

在执行任何 HapRay 命令前，必须先完成以下检查：

1. 本地存在 `ArkAnalyzer-HapRay` 仓库（可访问 `perf_testing/`）。  
2. Python/`uv` 可用（用于运行 `uv run python -m scripts.main ...`）。  
3. 真机链路可用（`hdc` 可执行且设备在线，若为真机场景）。  
4. 目标场景所需门禁已满足（如 `GLM_API_KEY`、symbol-recovery API Key）。

### 1) 仓库获取（必须包含 git clone）

若本地尚无 HapRay 仓库，先执行：

```bash
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git
```

随后进入仓库并确认目录：

```bash
cd ArkAnalyzer-HapRay
ls perf_testing
```

若 `perf_testing/` 不存在，禁止继续执行分析流程，应先修复仓库路径。

下载代码后必须先构建前端报告模板资产（避免 `tools/web/report_template.html` 缺失）：

```bash
cd ArkAnalyzer-HapRay
npm i && npm run build:quick
```

### 2) `<REPO_ROOT>` 判定（可执行检查）

`<REPO_ROOT>` 必须是包含 `perf_testing/` 的目录。推荐在执行前做一次检查：

```bash
cd <REPO_ROOT>
test -d perf_testing && echo "REPO_ROOT_OK" || echo "REPO_ROOT_INVALID"
```

输出 `REPO_ROOT_INVALID` 时，必须先纠正路径，再进入执行主流程。

### 3) 首次环境安装（依赖闭环）

首次使用建议在 `<REPO_ROOT>/perf_testing` 完成依赖安装：

```bash
cd <REPO_ROOT>/perf_testing
uv sync
```

若项目未使用 `uv.lock` 或 `uv sync` 失败，可降级执行：

```bash
cd <REPO_ROOT>/perf_testing
uv pip install -r requirements.txt
```

若 `requirements.txt` 不存在，应先按仓库当前文档完成依赖安装，再继续执行。

### 4) 执行前最小自检（建议）

在跑 `gui-agent/perf/opt/static` 前，建议执行一次：

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main --help
```

若帮助命令无法运行，禁止继续采集流程，先修复 Python/依赖环境。

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

1. 定位 `<REPO_ROOT>` 与 `<PROJECT_ROOT>`。  
2. 真机场景先检查 `hdc list targets`（或 `hdc version`）。  
3. 在 `<REPO_ROOT>/perf_testing` 执行目标命令。  
4. 读取 `--result-file` 或 `hapray-tool-result.json`，解析 `outputs.reports_path`。  
5. 枚举关键产物：`report/*.html`、`htrace/**/trace.db`、`hiperf/**`、日志。  
6. 按子 Skill 路由做深入分析（满足则执行，不满足写跳过原因）。  
7. 生成并更新独立报告（默认 `<PROJECT_ROOT>/reports/`）。

## 异常与降级策略（Fail-Closed + 可交付）

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
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main --result-file /tmp/hapray-tool-result.json gui-agent \
  --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页" \
  -o ./
```

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main --result-file /tmp/hapray-tool-result.json perf \
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

<p align="center"><small>报告由 <strong>HapRay Skill</strong> <code>1.5.3</code> 生成 · <a href="https://gitcode.com/SMAT/ArkAnalyzer-HapRay">ArkAnalyzer-HapRay</a> · 报告生成时间 <code>2026-03-30T14:30:00+08:00</code></small></p>
```

若环境不支持 HTML，可用单行斜体替代，信息字段需完整等价。

## 明确禁止

- 禁止只给通用建议而不执行 CLI（除非用户明确声明不跑工具）。  
- 禁止用自动摘要替代对原始产物的验证。  
- 禁止在门禁未通过时“伪交付”（例如 GLM 未配置却直接出完整采集结论）。  
- 禁止虚构路径、时间戳、数值、热点函数。  

## 参考文档

- `README.md`、`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`  
- `hapray-tool-result.md`（契约字段速查）  
- `analysis/README.md`（子 Skill 索引）  
- `analysis/scroll-jank-trace-analysis.md`  
- `analysis/high-load-analysis.md`  
- `analysis/symbol-recovery-analysis.md`
