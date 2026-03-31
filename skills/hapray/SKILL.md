---
name: hapray
version: "1.5.2"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
homepage: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay#readme"
issues: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay/issues"
description: |
  HapRay (ArkAnalyzer-HapRay): MUST clearly narrate steps and sub-skills. Standalone .md default `<PROJECT_ROOT>/reports/` (workspace root, not HapRay clone subdir unless same). Header: skill version, report time. Execution trace. scroll-jank, llm-high-load (raw; not summary.json primary), symbol-recovery. MemLoad_*/PerfLoad_*. `update` = rare migration. Triggers: 鸿蒙性能, 深入分析, 滑动卡顿, trace, HAP/SO/LTO, 负载/内存, gui-agent, 高负载挖掘, 新发现, @hapray / HapRay.
metadata:
  short-description: >-
    Guides HapRay CLI (perf, gui-agent, opt, static), hapray-tool-result.json contract, and analysis/*.md for trace.db deep dives; OpenHarmony performance.
  zh-Hans: >-
    鸿蒙 ArkAnalyzer-HapRay：perf/gui-agent 采集、tool-result 契约；执行过程须逐步输出主步骤与子 Skill；独立 Markdown 默认写入 **项目根目录**（工作区根）下 `reports/`；**报告元信息置于文末一行小字**（Skill 版本、仓库链接、生成时间，见「最终分析报告」）；含执行轨迹。
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

面向 **HapRay 工具使用者**：从环境到结果的可重复步骤。工程主文档见克隆仓库根目录 `README.md` 与 `docs/使用说明.md`。

## Skill 包结构（主 Skill + 数据分析子模块）

本目录采用 **一个主 `SKILL.md` + 可扩展的 `analysis/` 子文档**：

| 部分 | 路径 | 职责 |
|------|------|------|
| **主 Skill** | `SKILL.md`（本文件） | 环境、构建、CLI 选路、Agent 强制约束、与子模块的衔接方式 |
| **tool-result 字段速查** | [`hapray-tool-result.md`](hapray-tool-result.md) | **`hapray-tool-result.json`** 顶层与 `outputs` 常用键；Schema 见仓库 **`docs/schemas/hapray-tool-result-v1.json`** |
| **数据分析子 Skill** | `analysis/*.md` + [`analysis/README.md`](analysis/README.md) | 对 **`perf_testing` 采集产物** 的 **深度分析**（SQL、表结构、诊断规律）；主 Skill 只负责索引与触发策略 |

发布或复制到 `~/.cursor/skills/hapray/` 时，请 **整个 `hapray/` 目录** 一并同步，否则 `analysis/` 与子文档会丢失；仅装 Skill 无整仓时 Schema 链接需依赖本机克隆的仓库路径。

## 数据分析子 Skill 索引

子文档路径相对于本 Skill 根目录（与 `SKILL.md` 同级）。**目标：`perf` / `gui-agent` 等产生报告后，对 `perf_testing` 采集数据深入分析，而不是只读 HTML 摘要。**

### 数据分析默认流程（逐一子 Skill）

在 **`perf_testing` 采集已完成且产物可解析** 的前提下，进行 **数据分析** 时 **默认** 按 **[`analysis/README.md`](analysis/README.md) 索引表顺序**，**逐个** 打开并评估 `analysis/` 下各子 Skill；**满足该子文档的前置条件则必须按其方法做深入分析**，**不满足则跳过该条**并在最终 **`.md`** 或对话中 **写明跳过原因**（例如无 `trace.db`、无 `perf.data`/无可恢复热点、用户仅要摘要等）。**禁止**在未逐条评估的情况下只选用「最省事」的一个子文档代替全套流程。

**推荐顺序**（与 `analysis/README.md` 当前索引一致，若该文件增删子 Skill 则以最新索引为准）：`scroll-jank` → `llm-high-load` → `symbol-recovery`。各子文档内部的 **必须 / 禁止 / 触发条件** 仍以对应 `.md` 为准。

### 采集产物 → 应触发的子 Skill（优先匹配）

| 采集或报告中的信号 | 应 **读取并遵循** 的子文档 | 说明 |
|--------------------|---------------------------|------|
| 存在 **`htrace/**/trace.db`**，且问题含 **滑动、列表、掉帧、卡顿、帧耗时、WaterFlow、手势** 等 | **[`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)** | **默认应触发**：用子文档中的表结构、SQL、手势与 `frame_slice` 规则做 **二次分析**；禁止仅用 HTML 结论代替对 `trace.db` 的可验证推理 |
| 存在 **`trace.db`** 但用户未明确场景 | 仍建议 **至少浏览** `scroll-jank` 中的「帧统计 / 进程线程定位」章节，再决定是否跑 SQL | 避免漏掉 `depth=0` 等硬规则 |
| 报告热点中出现 **`libxxx.so+0xXXXXX`** 格式大量缺失符号，或用户提及 **符号恢复、stripped SO、无法定位热点函数、KMP/RN 应用** | **[`analysis/symbol-recovery-analysis.md`](analysis/symbol-recovery-analysis.md)** | 用 SymRecover 工具恢复函数名；KMP 模式区分框架与业务开销；结合调用链判断是否为性能瓶颈 |
| 已采集 **perf/trace/log/UI** 多源数据，且意图含 **深挖负载、未知瓶颈、报告未覆盖、多源交叉、LLM 挖掘新发现** | **[`analysis/llm-high-load-analysis.md`](analysis/llm-high-load-analysis.md)** | **以 `trace.db`/hiperf/日志等原始数据挖掘未知问题**；**不以 `summary.json` 等规则化摘要为主线**；与 `scroll-jank` 帧规则兼容 |
| 未来在 `analysis/` 新增专题（如启动、内存） | 对应新 `.md` | 索引表同步增行；采集产物匹配时 **同样优先加载** |

| ID | 子文档 | 触发场景 | 核心内容 |
|----|--------|----------|----------|
| `scroll-jank` | [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) | 滑动卡顿、掉帧、列表/WaterFlow 滑动、周期性 jank、从 Trace 还原手势 | `trace.db` 表（`process`/`thread`/`callstack`/`frame_slice`）、**`frame_slice` 仅 `type_desc=actural` 且 `depth=0`**、卡顿分级、手势与 `mainDelta`、隔次卡/触顶/拉动、SQL 与 Python 脚本、Hitrace 标记表 |
| `llm-high-load` | [`analysis/llm-high-load-analysis.md`](analysis/llm-high-load-analysis.md) | 已落盘采集数据、深挖高负载、多源交叉、**新发现**（非仅读自动报告） | **高负载特征**；`trace.db`+`hiperf`+日志等**原始侧**挖掘；**禁止**以 `summary.json` 替代原始挖掘；与 HTML 结论可选对照、独立 `.md`「新发现」结构、禁止臆造证据 |
| `symbol-recovery` | [`analysis/symbol-recovery-analysis.md`](analysis/symbol-recovery-analysis.md) | 报告中出现 `libxxx.so+0xXXXXX` 缺失符号、stripped SO 热点无法定位、KMP/RN 应用框架与业务负载区分 | SymRecover 工具（perf.data/Excel/KMP 三种模式）、LLM 推断函数名与功能、负载类型判断（热点 vs 瓶颈）、调用链信息、HTML 符号替换 |

**嵌入规则（强化）**：

1. **`perf_testing` 采集成功且产物已落盘** → Agent 在给出「原因与建议」前，须 **先按上文「数据分析默认流程（逐一子 Skill）」** 逐条评估；**不得**仅用「至少一个」子 Skill 敷衍了事。对 **`scroll-jank`**：有 **`trace.db`** 且适用场景时 **必须** 深入分析（或明确不满足的前置并跳过）；对 **`llm-high-load`**：符合其文档触发条件时 **必须** 加载并对 **`trace.db`、`hiperf`、日志** 等 **原始侧** 做 **主动枚举与交叉印证**（**禁止**将 **`summary.json`** 等规则化摘要作为挖掘主线，见该子文档）；对 **`symbol-recovery`**：出现 strip/地址热点等时 **必须** 按该文档处理，否则 **写明跳过原因**。不得仅凭常识或只读自动报告摘要。若用户 **明确只**要某单一子专题或只要摘要，可在对话中可核对后 **收窄范围**，并**仍须**说明未执行的子 Skill 及原因。
2. 主 Skill **不重复**子文档中的长 SQL、长脚本与完整标记表；**深入分析步骤以子文档为唯一详述来源**。
3. 最终 **独立 `.md` 报告**须体现：**报告元信息**（**文末单行小字**，须含 Skill 版本、仓库链接、生成时间，见「最终分析报告」）+ **执行轨迹**（见「执行过程输出」）+ **各子 Skill 是否已执行或已跳过**（跳过须写原因），以及是否对 `frame_slice`/`callstack` 等做了查询或等价核对，并写明 **`trace.db` 等关键产物实际路径**。
4. 后续在 `analysis/` 增加新 `.md` 时，更新 **本索引** 与 [`analysis/README.md`](analysis/README.md)。

## Agent 执行约束（强制；本 Skill 被加载时适用）

本 Skill 的目标不是「口述性能知识」，而是 **驱动本机已克隆仓库中的 HapRay CLI 实际运行**。在 IDE Agent 中你必须使用 **终端（或等价的 run command 能力）** 执行命令；**禁止**在未尝试执行相关 CLI 的情况下，仅用泛泛的通用建议充当「分析结果」。

### 执行过程输出（主 Skill 步骤与子 Skill 可见性）

执行本 Skill **全程**须 **在对话中分步、清晰输出**当前在做什么，**禁止**静默跳步或只给最终结论而不交代过程。

| 输出类型 | 要求 |
|----------|------|
| **主 Skill 步骤** | 每进入一阶段，用**简短可辨的标题**标明（与上文 **「必须执行」** 步骤对应，例如：定位仓库、`hdc`、进入 `perf_testing`、运行 `gui-agent`/`perf`、`--result-file` 解析、`reports_path` 枚举、数据分析、落盘 `.md`）。**执行命令前**说明将运行什么；**命令结束后**说明结果（成功路径 / 失败原因）。 |
| **子 Skill** | 每评估或执行一个 `analysis/` 子文档时，**必须**写出：**子 Skill ID**（`scroll-jank` / `llm-high-load` / `symbol-recovery`）+ **对应文件名**（如 `analysis/scroll-jank-trace-analysis.md`）+ **状态**：`执行中` → `已完成（概要：如已跑 SQL / 已做多源交叉）` 或 `已跳过（原因：…）`。同一子 Skill **进入、结束或跳过至少各输出一次**，便于用户对照。 |
| **格式** | 推荐 **分级列表** 或 **编号小节**（`####`），保持可读；长输出可拆多条消息，但**顺序须连贯**。 |

**落盘对齐**：独立 **`hapray-analysis-*.md`** **文末**须含 **「报告元信息」**（文末单行小字：HapRay Skill **`version`**、仓库链接、报告生成时间，见下文「最终分析报告」），并含 **「执行轨迹」**（或同义小节，可在元信息之前），汇总主步骤与子 Skill 状态，与对话过程一致。

### 必须执行（按顺序尝试）

0. **前置自检（先于任何「结论」或更新 `.md`）**：

   **（0-A）`symbol-recovery` 路径**：若本轮意图涉及 **符号恢复**（用户提及 stripped SO、缺失符号、`libxxx.so+0x...`、KMP 热点定位、SymRecover），在运行命令前，**必须先**检查 `tools/symbol_recovery/.env` 是否含有效 API Key（`grep API_KEY .env`）。若**未配置**：**第一条必须完成的动作**是向用户展示 `analysis/symbol-recovery-analysis.md` Step 0 中的 A/B 选项并等待回复，**禁止**在用户未确认前自行继续分析或运行命令。若用户选择 `--no-llm`，后续所有命令须附加该参数。

   **（0-B）`gui-agent` 路径**：若本轮意图需要 **`gui-agent`**（负载/场景复现/自然语言驱动 UI），在运行命令或撰写长篇分析前，**必须先**确认 **`GLM_API_KEY`** 是否已配置（可询问用户或检查环境）。若**未配置**且用户未声明「不配置 LLM」：**第一条必须完成的动作**是 **§2.1「交互与等待」**（展示交互对话框或等效分条提示 + 阻塞等待），**禁止**跳过该步骤，也 **禁止**先输出「基于行业共性 / 对标某报告结构 / 仅对话补充」类结论、或 **先** 更新 `hapray-analysis-*.md` 的 **「对话补充」** 等小节来冒充已完成 HapRay 采集分析。

1. **定位路径（区分两类根目录）**：  
   - **HapRay 仓库根目录**（`<REPO_ROOT>`）：包含 **`perf_testing/`** 的目录，用于 **运行 CLI**（见步骤 3）。通过工作区内向上查找 `perf_testing` 或用户确认确定。  
   - **项目根目录**（`<PROJECT_ROOT>`）：Cursor / IDE **当前工作区文件夹的根**（用户打开的工程顶层，例如 **`hapray-skill-test`**）。**独立分析 `hapray-analysis-*.md` 默认写入 `<PROJECT_ROOT>/reports/`**（不存在则创建）。**禁止**在「工作区为外层项目 + 内层 `ArkAnalyzer-HapRay` 克隆」时，把默认落盘写成 **`<REPO_ROOT>/reports/`**（错误示例：`hapray-skill-test/ArkAnalyzer-HapRay/reports/`）；**正确示例**：`hapray-skill-test/reports/`。若工作区 **仅打开** HapRay 单仓库且无外层目录，则 `<PROJECT_ROOT>` 与 `<REPO_ROOT>` **相同**，此时 `reports/` 在该仓库下即可。  
   若未知，先向用户确认或列目录查找，**不得臆造路径**。
2. **需要真机时**：先运行 `hdc list targets`（或 `hdc version`）。若设备未授权或不可用，**明确告知用户**并在本回合内**不得假装已生成报告**。
3. **进入 Python CLI 目录**：所有 `python -m scripts.main ...` 必须在 **`<REPO_ROOT>/perf_testing`** 下执行（先 `cd` 再跑，或使用 `-C` 等效方式）。**`<REPO_ROOT>` 见步骤 1，勿与 `<PROJECT_ROOT>` 混淆。**
4. **根据意图选择子命令并真正运行**（至少执行到命令返回或明确报错）：
   - **负载 / 场景复现 / 抖音类浏览 + 原因与建议** → 首选 **`gui-agent`**（需 LLM：默认 **`GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`**、**`GLM_MODEL=autoglm-phone`**、**`GLM_API_KEY`** 在 [智谱 API Key 页面](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) 配置；详见 **§2.1**）。若检测到 **未配置 `GLM_API_KEY`**（且未传 `--glm-api-key`）：Agent **须展示交互式对话框**（见 **§2.1**「交互与等待」；若环境无原生对话框，则用**结构化分条消息**模拟，并明确请用户回复进度），并 **阻塞等待**用户完成配置；**不得**立刻改跑其它命令；**仅当用户在对话中明确表示不配置 LLM / 改用预置 Hypium 用例** 时，再改用 **`perf --run_testcases`**，从 **`perf_testing/hapray/testcases/<应用包名>/`** 选 **`PerfLoad_*`/`MemLoad_*`**（见「预置用例」），**同样必须执行命令**，不得改为纯文字分析。
   - **SO/HAP 优化检测** → 仓库文档中的 `opt` 入口（如 `hapray-gui/cmd.py` 或 `tools/optimization_detector`）。
   - **`update`**：仅在 **HapRay 工具版本变更后**，需把 **旧版 HapRay 生成的报告** 迁移到当前版本格式时使用；**绝大多数日常场景不会调用**。若用户未提及「升级 HapRay / 迁移历史报告」，**不要**默认选 `update`。
5. **需要机器可读结果时**：在全局参数中附加 `--result-file <绝对路径>`（见 `python -m scripts.main --help`），执行后 **读取该文件** 或 `hapray-tool-result.json` 获取 `reports_path`，再向用户说明结果位置。
6. **解读「原因与建议」**：须在 **命令已成功产出报告/JSON** 之后，先解析 **`reports_path`**（或契约中的报告根目录），**枚举产物**（如 `report/*.html`、`htrace/**/trace.db`、`hiperf/**` 等），再结合 HTML/JSON；若无成功产物，只能说明失败原因与下一步，**不得编造热点函数或数据**。
7. **数据分析子 Skill（与第 6 步衔接）**：在 **`perf_testing` 采集已完成** 的前提下，**必须**按上文 **「数据分析默认流程（逐一子 Skill）」** 顺序处理：**逐个** 评估 [`analysis/README.md`](analysis/README.md) 所列子文档，**条件满足则深入执行**，**不满足则跳过并记录原因**；其中 **`trace.db`** 存在且适用时 **须** 使用 [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) 做 **深入分析**（SQL/脚本/诊断规律），**禁止**仅用自动生成的 HTML 摘要代替对原始 Trace 的验证。
8. **卡顿帧 / 滑动 jank**：统计与表述须与子 Skill `scroll-jank` 一致（**`frame_slice` 仅 `type_desc=actural` 且 `depth=0`**）。**禁止**把 `depth>0` 当真实单帧时长；无 Trace 时不得编造帧数据。
9. **最终分析报告落盘**：在完成基于 HapRay 产物 **及数据分析子 Skill 的深入分析** 后，须将 **完整分析结论** 写入 **独立 Markdown 文件**（`.md`），**不得**仅在对话中输出而不落盘；**默认路径**为 **`<PROJECT_ROOT>/reports/`**（见步骤 1 与下文「最终分析报告」表）；路径与命名见该节；**文末须含「报告元信息」**（单行小字，见该节 **「报告元信息（文末单行小字）」**）+ **「执行轨迹」小节**（与上文 **「执行过程输出」** 一致；建议放在元信息 **之前**）。**多轮分析同一落盘报告**时默认 **更新原 `.md` 文件**，除非用户明确要求另存为新文件（见该节）；**更新时须刷新「报告生成时间」**（可保留首次生成时间另加一行「修订时间」）。

### 明确禁止

- 禁止用「通常可以检查 CPU/内存…」等**通用清单**替代一次真实的 `gui-agent` / `perf` / `opt` 执行（除非用户明确只要文档、且声明不跑工具）。**`update`** 仅用于报告迁移，见上文；勿为「重新分析」而滥用。
- **禁止**在已存在 **`trace.db`** 且匹配「采集产物 → 应触发的子 Skill」时，**跳过**子 Skill、仅根据 HTML 摘要下结论（除非用户明确只要摘要）。
- **禁止**在 **`GLM_API_KEY` 未就绪** 时 **未展示交互提示、未等待用户** 就擅自改跑 **`perf`**；须先经 **对话框或等效交互**（§2.1）**阻塞等待**用户配置或 **明确表态不配置 LLM**，再选用预置用例。
- **禁止（GLM 未配置时的「伪交付」）**：在 **未完成 §2.1 交互与等待**、且用户 **未明确**「不配置 LLM / 只要纯文档」时，**禁止**以「工作区无 trace / 无法采集」为由，直接给出 **「基于 HapRay 分析维度 + 行业共性 + 对标某结构」** 的**替代结论**，并写入 **`hapray-analysis-*.md` 的「对话补充」** 等小节作为主要成果——此类行为属于 **跳过配置提示**，与本 Skill 冲突。**允许**的唯一路径是：先 **§2.1** → 用户配置后跑 **`gui-agent`/`perf`**；或用户 **明确不配置** 后改 **`perf` 预置用例**；或用户 **明确只要文档、不跑工具**（需在对话中可核对）。
- 禁止输出虚构的 **报告路径、时间戳、负载数值**。
- 禁止因「问题较长」就跳过终端步骤直接给结论。
- **禁止**在执行本 Skill 时 **不交代当前步骤与子 Skill** 就直接给出汇总结论（除非用户 **书面声明**只要结论、不要过程）。

### 若当前环境无法执行（沙箱无设备、用户拒绝终端等）

- 说明**具体阻断原因**，并给出 **一条可复制的手动命令**（含 `cd` 到 `perf_testing` 的完整示例），不得留空路径占位符。

### Agent 推荐命令模板（含契约输出，便于解析）

将 `<REPO_ROOT>` 换为 **含 `perf_testing/` 的 HapRay 克隆根路径**（见步骤 1，勿与工作区 `<PROJECT_ROOT>` 混淆）；`RESULT.json` 换为可写绝对路径：

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main --result-file /tmp/hapray-tool-result.json gui-agent \
  --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页" \
  -o ./
```

**未配置 `GLM_API_KEY` 时**：先按 **§2.1** **展示交互对话框（或等效交互）** 并 **阻塞等待**用户配置；**勿**直接执行下方 `perf`。仅当用户 **在对话中明确表示不配置 LLM、改用预置用例** 时，再使用 `perf`（用例从 **`hapray/testcases/<应用包名>/`** 选 **`PerfLoad_*.py`** / **`MemLoad_*.py`**；`--run_testcases` 传 Hypium 用例名/正则；`--so_dir` 按需附加）。

**`--round`（测试轮次）**：

- **日常 / 冒烟**：建议显式传 **`--round 1`**（单轮、耗时短）。若命令行**未写** `--round`，以当前 `perf` 实现的默认值为准（见 `python -m scripts.main perf --help` 或仓库 README，可能与 1 不同）。
- **精确测量 CPU 指令数收益**，或 **横向对比**（多版本 / 多配置）：使用 **`--round 3`** 或 **`--round 5`** 做多轮；**解读时以各轮测得指标中最接近整轮平均值的那一轮作为代表结果**（或与团队约定的汇总方式一致）。

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main --result-file /tmp/hapray-tool-result.json perf \
  --run_testcases "PerfLoad_Douyin_0010" \
  --round 1
```

## 何时使用本 Skill

- 需要：搭环境 → 构建 → 选能力 → 执行 → 读产物 → **按 `analysis/` 索引逐一子 Skill 深入分析（条件不满足再跳过）** → 落盘 `.md`
- 用户用自然语言描述「测性能」「查 SO 优化」「分析 HAP」等（「更新报告」若指 **迁移旧版工具产出的报告**，才涉及 `update`）
- **负载与体验类**：优先 **`gui-agent`**（设备上复现场景 + 采集 trace/perf + 报告），随后 **按索引表加载子 Skill**
- **`perf` / `gui-agent` 已跑出 `perf_testing` 报告目录**：**默认应** 按 **「逐一子 Skill」** 流程评估 **`analysis/README.md`** 中每个子文档；对 **`trace.db`**、hiperf、日志等 **原始产物** 深入推理（**`llm-high-load` 不以 `summary.json` 为主线**，见该子文档），而非只浏览 HTML
- **深挖高负载 / 挖掘报告未写的问题 / 多源交叉分析**：在已有采集数据时 **应加载** [`analysis/llm-high-load-analysis.md`](analysis/llm-high-load-analysis.md)，按其中流程 **主动解析** perf、trace、log 等 **原始落盘** 挖掘未知问题；**不**以 `summary.json` 规则化摘要替代（见该文档）
- **滑动卡顿 / 掉帧 / jank**：在 **`trace.db`** 存在时 **必须** 结合 **`analysis/scroll-jank-trace-analysis.md`**

## 验证场景：自然语言 → 预期三步（以抖音为例）

**用户表述示例**：「请分析抖音浏览视频的负载情况，给出高负载的原因和修复建议」

本节是业务步骤说明；**终端是否实际执行**以 **「Agent 执行约束（强制）」** 为准。

| 步骤 | 目标 | 做什么 |
|------|------|--------|
| **1. 前置条件准备** | 可执行 `gui-agent` | 完成 §2 检查清单 + §3 `npm run build`；真机 `hdc`；**GLM** 见 **§2.1**；缺 **`GLM_API_KEY`** 时 **交互对话框 + 等待配置**，勿直接跑 `perf`（除非用户明确不配置） |
| **2. 驱动 gui-agent 测抖音** | 复现场景并采集数据 | **`gui-agent`**；包名 **`com.ss.hm.ugc.aweme`**；**`--scenes`** 与用户表述对齐 |
| **3. 输出与深入分析** | 原因与修复建议 | 报告在契约/`reports_path` 指向的目录；**按「逐一子 Skill」** 执行（**有 `trace.db` 则 `scroll-jank` 须满足或写明跳过原因**；**高负载/多源交叉** 满足则 `llm-high-load`；**strip 热点** 满足则 `symbol-recovery`）；最终写入独立 **`.md`** |

**示例命令**（`perf_testing` 目录）：

```bash
cd perf_testing
uv run python -m scripts.main gui-agent --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页，关注滑动与播放时的负载" \
  -o ./
```

未传 `--scenes` 时，工具会按 `config.yaml` 的 `gui-agent.scenes.video` 等加载预设场景。

**说明**：若用户 **明确选择** 固定 Hypium 用例（含「不配置 GLM」场景），再 **`perf --run_testcases`**，在 **`hapray/testcases/com.ss.hm.ugc.aweme/`** 等下选 **`PerfLoad_*.py`** 或 **`MemLoad_*.py`**；**不要**在仍缺 `GLM_API_KEY` 且用户未表态时默认走 `perf`。

## 预置用例：`perf_testing/hapray/testcases`

Hypium 预置用例按 **应用包名（一级目录）** 组织：

| 文件模式 | 含义 |
|----------|------|
| **`MemLoad_**.py`** | **内存检测** |
| **`PerfLoad_**.py`** | **负载 / 性能检测** |

**示例**：`com.ss.hm.ugc.aweme/PerfLoad_Douyin_0010.py`；`--run_testcases` 传类名或正则。其它前缀（如 `ResourceUsage_PerformanceDynamic_*.py`）以用例类为准。

## 1. 获取代码

```bash
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git
cd ArkAnalyzer-HapRay
```

## 2. 环境准备（检查清单）

**版本以仓库内** `.nvmrc`、`.python-version`、`package.json` 的 `engines` **为准**。

| 步骤 | 动作 | 成功标准（示例） |
|------|------|------------------|
| 2.1 | macOS/Linux：`source ./bootstrap_env.sh`；Windows：`.\bootstrap_env.ps1` | 约定版本 Node / uv |
| 2.2 | 仓库根：`npm install` | `perf_testing` postinstall 完成 |
| 2.3 | 真机：`hdc version` | 有输出 |
| 2.4 | `perf_testing`：`uv run python -m scripts.main --help` | 打印子命令 |
| 2.5 | 运行 **`gui-agent`** 前配置 **GLM**（见下节 **§2.1**）；缺 **`GLM_API_KEY`** 时 **交互对话框 + 阻塞等待**，勿擅自改用 `perf` | 见 §2.1 |

### 2.1 GLM 环境变量（智谱 BigModel，`gui-agent`）

运行 **`gui-agent`** 需要可调用的 **大模型 API**。若当前环境 **未设置 `GLM_API_KEY`**（且未传 `--glm-api-key`），Agent **不得**直接执行 `gui-agent`（必失败），也 **不得**擅自改用 **`perf`**，须先完成下列 **交互与等待**。

#### 交互与等待（缺 `GLM_API_KEY` 时）

1. **展示交互式对话框**（优先）：若 IDE Agent 提供 **AskQuestion、确认框、输入框** 等能力，应用其向用户说明：需配置 **`GLM_API_KEY`**，并给出 **[智谱 API Key 管理页](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)** 链接，以及默认 **`GLM_BASE_URL`** / **`GLM_MODEL`**（见下表）。  
2. **无原生对话框时**：用 **结构化分条消息** 模拟对话框（标题 + 步骤 + 链接 +「请配置后回复已就绪」），效果等价于一次可读的交互面板。  
3. **阻塞等待**：在本话题内 **暂停后续自动化步骤**，直至用户 **已配置环境变量或粘贴密钥**（可在后续用户消息中确认），或用户 **明确回复不配置 LLM**。  
4. **降级为预置用例**：**仅当用户明确表示不配置 LLM**（例如「不用 gui-agent」「只用 Hypium 用例」）时，再选用 **`perf --run_testcases`** + **`PerfLoad_*` / `MemLoad_*`**；此前默认仍以 **补齐 `GLM_API_KEY` + `gui-agent`** 为主。  
5. **禁止用「对话补充」逃避配置**：在 **`GLM_API_KEY` 未配置** 且 **未完成本条交互** 前，**不得**用更新 Markdown「对话补充」「定性对标」等方式代替 **先提示用户配置**；若工作区确无 `trace.db`/报告，仍须 **先** 走本条交互，再决定采集或降级。

| 变量 | 默认值（与 CLI 一致） | 说明 |
|------|----------------------|------|
| **`GLM_BASE_URL`** | **`https://open.bigmodel.cn/api/paas/v4`** | 智谱 OpenAPI 兼容 Base URL；也可用命令行 **`--glm-base-url`** |
| **`GLM_MODEL`** | **`autoglm-phone`** | 模型名；也可用 **`--glm-model`** |
| **`GLM_API_KEY`** | 无内置默认值，**必填** | 用户须在 **[智谱开放平台 → API Key 管理](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)** 创建项目并复制密钥；也可用 **`--glm-api-key`** |

**Shell 示例**（配置后再运行 `gui-agent`）：

```bash
export GLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export GLM_MODEL="autoglm-phone"
export GLM_API_KEY="<在 https://bigmodel.cn/usercenter/proj-mgmt/apikeys 获取后粘贴>"
```

其它模型与第三方网关仍见仓库根 **`README.md`** 中 GUI Agent 章节（如 ModelScope 等）。

## 3. 构建

```bash
npm run build
```

更重步骤（桌面、`prebuild`、`dist/tools`）见根 `README.md`、`docker/README.md`。

## 4. 自然语言 → 子命令（选能力）

| 用户意图（示例） | 典型子命令 | 工作目录 |
|------------------|------------|----------|
| 性能测试、trace、用例（`PerfLoad_*` / `MemLoad_*`） | `perf` | `perf_testing` |
| 快速跑用例 | `prepare` | `perf_testing` |
| SO/HAP 优化、LTO | `opt` | 见根 README |
| HAP 静态分析 | `static` | 见根 README |
| 旧版 HapRay 报告需迁移到新版（版本升级后） | `update` | `perf_testing` |
| 报告对比 | `compare` | `perf_testing` |
| hilog | `hilog` | `perf_testing` |
| GUI 自动化 | `gui-agent` | `perf_testing` |
| 浏览场景负载、原因与建议（真机 + LLM） | `gui-agent` + `--apps` + `--scenes` | `perf_testing` |
| 滑动卡顿、掉帧、列表 jank（需 `trace.db`） | 先 `perf`/`gui-agent` 采 trace；深度分析见 **`analysis/scroll-jank-trace-analysis.md`** | `perf_testing` |
| **`perf_testing` 已产出报告目录**，需对采集数据深入分析 | 按 **「采集产物 → 应触发的子 Skill」** 打开 `analysis/*.md`，对照 `trace.db`/JSON | 报告路径 + 本 Skill `analysis/` |
| **深挖高负载、多源交叉、挖掘报告未覆盖问题**（已有 trace/perf/log/UI 落盘） | 不新增子命令；分析阶段须加载 **`analysis/llm-high-load-analysis.md`**，配合 **`scroll-jank`**（涉及帧时） | 报告路径 + 本 Skill `analysis/` |

`gui-agent` 必填 **`--package-name` 或 `--apps`**（文档若写 `--app` 以 `--help` 为准）。

## 5. 执行与机器可读结果（自动化/Agent）

- **契约总述**：仓库 **`docs/工具契约式输入输出方案.md`**（全局 `--result-file`、`--machine-json`、落盘优先级）。
- **字段速查（Skill 内）**：[**`hapray-tool-result.md`**](hapray-tool-result.md) — 期望 **`hapray-tool-result.json`** 顶层与 `outputs` 常用键；**Schema** 见仓库 **`docs/schemas/hapray-tool-result-v1.json`**。
- Agent 优先读契约文件中的 **`outputs.reports_path`**（若存在），再打开业务报告。

## 6. 读结果与 Trace 路径

- **报告目录**：契约 JSON 的 `outputs.reports_path`（若存在）。
- **典型产物**：HTML、Excel、`report/` 下 JSON、`hapray-tool-result.json`、`htrace/**/trace.db`、`hiperf/**` 等。
- **深入分析顺序**：先定位 **`trace.db`**（若存在）→ **加载** [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) → 再对照 HTML/摘要；**`trace.db`** 路径形如 **`<report_dir>/<TestCase>/htrace/stepN/trace.db`**。
- **LLM 高负载挖掘**：当需要 **从原始数据挖掘自动报告未强调的问题** 时，额外加载 [`analysis/llm-high-load-analysis.md`](analysis/llm-high-load-analysis.md)，枚举 **`hiperf`、日志** 等与 trace **时间轴交叉**；**不以 `summary.json` 为挖掘主线**（见该文档）。
- **原则**：对 **`perf_testing` 采集的原始数据**（尤其 SQLite Trace）优先用 **子 Skill** 中的可重复方法分析，自动报告作交叉验证。

## 最终分析报告（独立 Markdown）

在 **已结合 HapRay 产物与子 Skill 完成分析** 后，Agent 须 **新建并保存** 一份 **独立的 `.md` 文件**（与 HapRay 自动生成的 HTML/Excel 区分，供人读、可版本管理、可分享）。

| 项 | 建议 |
|----|------|
| **位置** | **默认**：`<PROJECT_ROOT>/reports/`。**`<PROJECT_ROOT>`** = Cursor / IDE **工作区根目录**（工程顶层文件夹，例如 **`hapray-skill-test`**）。完整示例：`hapray-skill-test/reports/hapray-analysis-<YYYYMMDD>-<主题>.md`（**不存在则创建** `reports/`）。**禁止**在「工作区根为 `hapray-skill-test`、克隆在 `hapray-skill-test/ArkAnalyzer-HapRay`」时，将默认路径写成 **`hapray-skill-test/ArkAnalyzer-HapRay/reports/`**——应使用 **`hapray-skill-test/reports/`**。若工作区 **仅含** HapRay 单仓库一层，则 `<PROJECT_ROOT>` 与该仓库根一致，此时 `reports/` 在该仓库下即可。**`<REPO_ROOT>`**（含 `perf_testing/`）**仅用于运行 CLI**，**不**作为独立分析 Markdown 的默认父目录（除非与 `<PROJECT_ROOT>` 相同）。此处的 **`reports/`** 是 **Agent 独立分析 Markdown** 的落盘目录，**不要**与契约里的 **`outputs.reports_path`**（工具采集输出）混为一谈。若用户 **指定**其它路径则从其指定。 |
| **文件名** | `hapray-analysis-<YYYYMMDD>-<简短主题>.md`（例：`hapray-analysis-20260330-douyin-perf.md`）；避免与工具输出目录同名覆盖。 |
| **报告元信息（必填；置于文末）** | 独立 `.md` **文件末尾**须按下文 **「报告元信息（文末单行小字）」** 唯一版式书写（**禁止**仅放在文首）。须包含：<br>• **HapRay Skill 版本号**：从当前使用的 Skill 根目录下 **`SKILL.md`** 的 YAML 顶栏读取 **`version`**（例如 `1.5.2`）。Skill 路径典型为 **`~/.cursor/skills/hapray/SKILL.md`** 或工作区内 **`.../skills/hapray/SKILL.md`**；若无法读取则写 **`version: 未知`** 并简述原因。<br>• **报告生成时间**：写入 **本文件落盘时刻** 的日期时间，**须带时区**（推荐 ISO 8601，如 `2026-03-30T14:30:00+08:00`；或 `2026-03-30 14:30:00 CST` 等可解析形式）。**禁止**使用无日期的模糊表述代替。<br>• **仓库链接**：须可点击（Markdown 链接或 HTML `<a>`），指向 `https://gitcode.com/SMAT/ArkAnalyzer-HapRay`，与版本号、生成时间 **同处文末一行小字**。 |
| **正文结构** | 建议顺序：**背景与问题** → **测试/采集方式**（对应 CLI 与子命令）→ **执行轨迹** → **HapRay 报告路径**（`reports_path`、`trace.db` 等真实路径）→ **结论与数据依据** → **原因与优化建议** → **未解决问题或后续动作**（按需）→ **文末：报告元信息**（见上）。 |
| **原则** | 可复述对话中的要点，但以 **单文件自洽** 为准；引用数据须与产物一致，**禁止**虚构路径与数值。 |
| **多轮分析（同一落盘报告）** | 针对 **同一份已存在的分析 `.md`**（同一套 HapRay 报告目录、同一分析主题）开展 **第二轮及后续** 补充/修订时：**默认在原文件上更新**（编辑、覆盖或追加修订说明），使结论保持 **单一事实来源**。**除非**用户明确要求「另存为新文件」「复制一份」「导出到新路径」或给出新文件名，否则 **不要** 新建并行的 `hapray-analysis-*.md`。 |

**多轮分析默认行为**：先定位已有 `.md` 路径 → **更新该文件**；仅在用户显式要求时 **另存为新文件**。

**报告元信息（文末单行小字）**

元信息 **必须出现在全文最后**、**唯一**采用下列版式。在 **全文最末一行** 用 **小字号** 注明：报告由 **HapRay Skill** 某版本生成、**仓库链接**、**报告生成时间**。不占版面；**不**再额外加 `## 附录` 大标题（若与正文间需留白，可单独一行 `---` 再跟本行）。

```markdown
---

<p align="center"><small>报告由 <strong>HapRay Skill</strong> <code>1.5.2</code> 生成 · <a href="https://gitcode.com/SMAT/ArkAnalyzer-HapRay">ArkAnalyzer-HapRay</a> · 报告生成时间 <code>2026-03-30T14:30:00+08:00</code></small></p>
```

（若渲染环境 **禁用 HTML**，可改为单行斜体 + 链接：`*报告由 HapRay Skill \`1.5.2\` 生成 · [ArkAnalyzer-HapRay](https://gitcode.com/SMAT/ArkAnalyzer-HapRay) · 报告生成时间 \`2026-03-30T14:30:00+08:00`*`。）

**展示效果（渲染后示意）**：页面底部 **一行**、**字号小于正文**（`<small>` 生效时）；**仓库** 为可点击链接；时间与版本多为等宽 `code` 样式。

```text
────────────────────────────────────────（可选：与正文分隔线）

        报告由 HapRay Skill 1.5.2 生成 · ArkAnalyzer-HapRay（链接，下划线） · 报告生成时间 2026-03-30T14:30:00+08:00
        （整行字号略小、居中；实际以浏览器 / VS Code 预览为准。）
```

（版本号随 **`SKILL.md` 实际 `version`** 替换；时间以 **落盘时** 为准。）

## 7. 常见问题（简短）

- **命令找不到**：当前目录是否为 `perf_testing`，是否 `uv run` 或已激活 `.venv`。
- **Node/Python 不符**：重新 `bootstrap_env`，以锚点文件为准。
- **设备**：`hdc` 与 USB 调试授权。

## 8. 深入阅读

- 克隆仓库根目录：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`、`README.md`
- 本 Skill 内：**[`hapray-tool-result.md`](hapray-tool-result.md)**（`hapray-tool-result.json` 字段说明；Schema：`docs/schemas/hapray-tool-result-v1.json`）
- **[`analysis/README.md`](analysis/README.md)**（数据分析子 Skill 总索引）
- 滑动卡顿 Trace：**[`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)**
