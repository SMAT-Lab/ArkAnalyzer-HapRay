---
name: hapray
version: "1.5.2"
license: Apache-2.0
repository: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay"
homepage: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay#readme"
issues: "https://gitcode.com/SMAT/ArkAnalyzer-HapRay/issues"
description: |
  HapRay (ArkAnalyzer-HapRay): After perf/gui-agent, MUST load analysis/ sub-skills for deep dive on perf_testing artifacts (trace.db, reports). MUST save final analysis as standalone .md. scroll-jank for jank/slide. MemLoad_*/PerfLoad_*. `update` = rare migration. Triggers: 鸿蒙性能, 深入分析, 滑动卡顿, trace, HAP/SO/LTO, 负载/内存, gui-agent, @hapray / HapRay.
metadata:
  short-description: >-
    Guides HapRay CLI (perf, gui-agent, opt, static), hapray-tool-result.json contract, and analysis/*.md for trace.db deep dives; OpenHarmony performance.
  zh-Hans: >-
    鸿蒙 ArkAnalyzer-HapRay：perf/gui-agent 采集、tool-result 契约、数据分析子 Skill（滑动卡顿/trace.db）、独立 Markdown 报告。
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

子文档路径相对于本 Skill 根目录（与 `SKILL.md` 同级）。**目标：`perf` / `gui-agent` 等产生报告后，尽可能触发子 Skill，对 `perf_testing` 采集数据深入分析，而不是只读 HTML 摘要。**

### 采集产物 → 应触发的子 Skill（优先匹配）

| 采集或报告中的信号 | 应 **读取并遵循** 的子文档 | 说明 |
|--------------------|---------------------------|------|
| 存在 **`htrace/**/trace.db`**，且问题含 **滑动、列表、掉帧、卡顿、帧耗时、WaterFlow、手势** 等 | **[`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)** | **默认应触发**：用子文档中的表结构、SQL、手势与 `frame_slice` 规则做 **二次分析**；禁止仅用 HTML 结论代替对 `trace.db` 的可验证推理 |
| 存在 **`trace.db`** 但用户未明确场景 | 仍建议 **至少浏览** `scroll-jank` 中的「帧统计 / 进程线程定位」章节，再决定是否跑 SQL | 避免漏掉 `depth=0` 等硬规则 |
| 报告热点中出现 **`libxxx.so+0xXXXXX`** 格式大量缺失符号，或用户提及 **符号恢复、stripped SO、无法定位热点函数、KMP/RN 应用** | **[`analysis/symbol-recovery-analysis.md`](analysis/symbol-recovery-analysis.md)** | 用 SymRecover 工具恢复函数名；KMP 模式区分框架与业务开销；结合调用链判断是否为性能瓶颈 |
| 未来在 `analysis/` 新增专题（如启动、内存） | 对应新 `.md` | 索引表同步增行；采集产物匹配时 **同样优先加载** |

| ID | 子文档 | 触发场景 | 核心内容 |
|----|--------|----------|----------|
| `scroll-jank` | [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) | 滑动卡顿、掉帧、列表/WaterFlow 滑动、周期性 jank、从 Trace 还原手势 | `trace.db` 表（`process`/`thread`/`callstack`/`frame_slice`）、**`frame_slice` 仅 `type_desc=actural` 且 `depth=0`**、卡顿分级、手势与 `mainDelta`、隔次卡/触顶/拉动、SQL 与 Python 脚本、Hitrace 标记表 |
| `symbol-recovery` | [`analysis/symbol-recovery-analysis.md`](analysis/symbol-recovery-analysis.md) | 报告中出现 `libxxx.so+0xXXXXX` 缺失符号、stripped SO 热点无法定位、KMP/RN 应用框架与业务负载区分 | SymRecover 工具（perf.data/Excel/KMP 三种模式）、LLM 推断函数名与功能、负载类型判断（热点 vs 瓶颈）、调用链信息、HTML 符号替换 |

**嵌入规则（强化）**：

1. **`perf_testing` 采集成功且产物已落盘** → Agent 在给出「原因与建议」前，须 **根据上表尽可能加载** 至少一个相关子 Skill；有 **`trace.db`** 且场景相关时，**必须** 使用 **`scroll-jank`** 中的方法与约束，不得仅凭常识或只读自动报告摘要。
2. 主 Skill **不重复**子文档中的长 SQL、长脚本与完整标记表；**深入分析步骤以子文档为唯一详述来源**。
3. 最终 **独立 `.md` 报告**须体现：是否执行了子 Skill 中的验证（例如是否对 `frame_slice`/`callstack` 做了查询或等价核对），并写明 **`trace.db` 实际路径**。
4. 后续在 `analysis/` 增加新 `.md` 时，更新 **本索引** 与 [`analysis/README.md`](analysis/README.md)。

## Agent 执行约束（强制；本 Skill 被加载时适用）

本 Skill 的目标不是「口述性能知识」，而是 **驱动本机已克隆仓库中的 HapRay CLI 实际运行**。在 Cursor / IDE Agent 中你必须使用 **终端（或等价的 run command 能力）** 执行命令；**禁止**在未尝试执行相关 CLI 的情况下，仅用泛泛的通用建议充当「分析结果」。

### 必须执行（按顺序尝试）

0. **前置自检（先于任何「结论」或更新 `.md`）**：

   **（0-A）`symbol-recovery` 路径**：若本轮意图涉及 **符号恢复**（用户提及 stripped SO、缺失符号、`libxxx.so+0x...`、KMP 热点定位、SymRecover），在运行命令前，**必须先**检查 `tools/symbol_recovery/.env` 是否含有效 API Key（`grep API_KEY .env`）。若**未配置**：**第一条必须完成的动作**是向用户展示 `analysis/symbol-recovery-analysis.md` Step 0 中的 A/B 选项并等待回复，**禁止**在用户未确认前自行继续分析或运行命令。若用户选择 `--no-llm`，后续所有命令须附加该参数。

   **（0-B）`gui-agent` 路径**：若本轮意图需要 **`gui-agent`**（负载/场景复现/自然语言驱动 UI），在运行命令或撰写长篇分析前，**必须先**确认 **`GLM_API_KEY`** 是否已配置（可询问用户或检查环境）。若**未配置**且用户未声明「不配置 LLM」：**第一条必须完成的动作**是 **§2.1「交互与等待」**（展示交互对话框或等效分条提示 + 阻塞等待），**禁止**跳过该步骤，也 **禁止**先输出「基于行业共性 / 对标某报告结构 / 仅对话补充」类结论、或 **先** 更新 `hapray-analysis-*.md` 的 **「对话补充」** 等小节来冒充已完成 HapRay 采集分析。

1. **定位仓库根目录**：以用户当前工作区 / 打开的路径为准（例如包含 `perf_testing/`、`package.json` 的目录）；若未知，先向用户确认或列目录查找，**不得臆造路径**。
2. **需要真机时**：先运行 `hdc list targets`（或 `hdc version`）。若设备未授权或不可用，**明确告知用户**并在本回合内**不得假装已生成报告**。
3. **进入 Python CLI 目录**：所有 `python -m scripts.main ...` 必须在 **`<REPO_ROOT>/perf_testing`** 下执行（先 `cd` 再跑，或使用 `-C` 等效方式）。
4. **根据意图选择子命令并真正运行**（至少执行到命令返回或明确报错）：
   - **负载 / 场景复现 / 抖音类浏览 + 原因与建议** → 首选 **`gui-agent`**（需 LLM：默认 **`GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`**、**`GLM_MODEL=autoglm-phone`**、**`GLM_API_KEY`** 在 [智谱 API Key 页面](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) 配置；详见 **§2.1**）。若检测到 **未配置 `GLM_API_KEY`**（且未传 `--glm-api-key`）：Agent **须展示交互式对话框**（见 **§2.1**「交互与等待」；若环境无原生对话框，则用**结构化分条消息**模拟，并明确请用户回复进度），并 **阻塞等待**用户完成配置；**不得**立刻改跑其它命令；**仅当用户在对话中明确表示不配置 LLM / 改用预置 Hypium 用例** 时，再改用 **`perf --run_testcases`**，从 **`perf_testing/hapray/testcases/<应用包名>/`** 选 **`PerfLoad_*`/`MemLoad_*`**（见「预置用例」），**同样必须执行命令**，不得改为纯文字分析。
   - **SO/HAP 优化检测** → 仓库文档中的 `opt` 入口（如 `hapray-gui/cmd.py` 或 `tools/optimization_detector`）。
   - **`update`**：仅在 **HapRay 工具版本变更后**，需把 **旧版 HapRay 生成的报告** 迁移到当前版本格式时使用；**绝大多数日常场景不会调用**。若用户未提及「升级 HapRay / 迁移历史报告」，**不要**默认选 `update`。
5. **需要机器可读结果时**：在全局参数中附加 `--result-file <绝对路径>`（见 `python -m scripts.main --help`），执行后 **读取该文件** 或 `hapray-tool-result.json` 获取 `reports_path`，再向用户说明结果位置。
6. **解读「原因与建议」**：须在 **命令已成功产出报告/JSON** 之后，先解析 **`reports_path`**（或契约中的报告根目录），**枚举产物**（如 `report/*.html`、`htrace/**/trace.db`、`hiperf/**` 等），再结合 HTML/JSON；若无成功产物，只能说明失败原因与下一步，**不得编造热点函数或数据**。
7. **尽可能触发数据分析子 Skill（与第 6 步衔接）**：在 **`perf_testing` 采集已完成** 的前提下，**必须**按上文「采集产物 → 应触发的子 Skill」表 **主动加载** 匹配的 `analysis/*.md`；尤其当目录中存在 **`trace.db`** 时，**须** 使用 [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) 中的规则与方法做 **深入分析**（SQL/脚本/诊断规律），**禁止**仅用自动生成的 HTML 摘要代替对原始 Trace 的验证。
8. **卡顿帧 / 滑动 jank**：统计与表述须与子 Skill `scroll-jank` 一致（**`frame_slice` 仅 `type_desc=actural` 且 `depth=0`**）。**禁止**把 `depth>0` 当真实单帧时长；无 Trace 时不得编造帧数据。
9. **最终分析报告落盘**：在完成基于 HapRay 产物 **及数据分析子 Skill 的深入分析** 后，须将 **完整分析结论** 写入 **独立 Markdown 文件**（`.md`），**不得**仅在对话中输出而不落盘；路径与命名见下文「最终分析报告（独立 Markdown）」。**多轮分析同一落盘报告**时默认 **更新原 `.md` 文件**，除非用户明确要求另存为新文件（见该节）。

### 明确禁止

- 禁止用「通常可以检查 CPU/内存…」等**通用清单**替代一次真实的 `gui-agent` / `perf` / `opt` 执行（除非用户明确只要文档、且声明不跑工具）。**`update`** 仅用于报告迁移，见上文；勿为「重新分析」而滥用。
- **禁止**在已存在 **`trace.db`** 且匹配「采集产物 → 应触发的子 Skill」时，**跳过**子 Skill、仅根据 HTML 摘要下结论（除非用户明确只要摘要）。
- **禁止**在 **`GLM_API_KEY` 未就绪** 时 **未展示交互提示、未等待用户** 就擅自改跑 **`perf`**；须先经 **对话框或等效交互**（§2.1）**阻塞等待**用户配置或 **明确表态不配置 LLM**，再选用预置用例。
- **禁止（GLM 未配置时的「伪交付」）**：在 **未完成 §2.1 交互与等待**、且用户 **未明确**「不配置 LLM / 只要纯文档」时，**禁止**以「工作区无 trace / 无法采集」为由，直接给出 **「基于 HapRay 分析维度 + 行业共性 + 对标某结构」** 的**替代结论**，并写入 **`hapray-analysis-*.md` 的「对话补充」** 等小节作为主要成果——此类行为属于 **跳过配置提示**，与本 Skill 冲突。**允许**的唯一路径是：先 **§2.1** → 用户配置后跑 **`gui-agent`/`perf`**；或用户 **明确不配置** 后改 **`perf` 预置用例**；或用户 **明确只要文档、不跑工具**（需在对话中可核对）。
- 禁止输出虚构的 **报告路径、时间戳、负载数值**。
- 禁止因「问题较长」就跳过终端步骤直接给结论。

### 若当前环境无法执行（沙箱无设备、用户拒绝终端等）

- 说明**具体阻断原因**，并给出 **一条可复制的手动命令**（含 `cd` 到 `perf_testing` 的完整示例），不得留空路径占位符。

### Agent 推荐命令模板（含契约输出，便于解析）

将 `<REPO_ROOT>` 换为实际仓库根路径；`RESULT.json` 换为可写绝对路径：

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

- 需要：**搭环境 → 构建 → 选能力 → 执行 → 读产物 → 尽可能触发 `analysis/` 深入分析 → 落盘 `.md`**
- 用户用自然语言描述「测性能」「查 SO 优化」「分析 HAP」等（「更新报告」若指 **迁移旧版工具产出的报告**，才涉及 `update`）
- **负载与体验类**：优先 **`gui-agent`**（设备上复现场景 + 采集 trace/perf + 报告），随后 **按索引表加载子 Skill**
- **`perf` / `gui-agent` 已跑出 `perf_testing` 报告目录**：**默认应** 根据产物类型打开对应 **`analysis/*.md`**，对 **`trace.db`/报告 JSON** 做深入推理，而非只浏览 HTML
- **滑动卡顿 / 掉帧 / jank**：在 **`trace.db`** 存在时 **必须** 结合 **`analysis/scroll-jank-trace-analysis.md`**

## 验证场景：自然语言 → 预期三步（以抖音为例）

**用户表述示例**：「请分析抖音浏览视频的负载情况，给出高负载的原因和修复建议」

本节是业务步骤说明；**终端是否实际执行**以 **「Agent 执行约束（强制）」** 为准。

| 步骤 | 目标 | 做什么 |
|------|------|--------|
| **1. 前置条件准备** | 可执行 `gui-agent` | 完成 §2 检查清单 + §3 `npm run build`；真机 `hdc`；**GLM** 见 **§2.1**；缺 **`GLM_API_KEY`** 时 **交互对话框 + 等待配置**，勿直接跑 `perf`（除非用户明确不配置） |
| **2. 驱动 gui-agent 测抖音** | 复现场景并采集数据 | **`gui-agent`**；包名 **`com.ss.hm.ugc.aweme`**；**`--scenes`** 与用户表述对齐 |
| **3. 输出与深入分析** | 原因与修复建议 | 报告在契约/`reports_path` 指向的目录；**有 `trace.db` 则必须走 `analysis/scroll-jank-trace-analysis.md`**；最终写入独立 **`.md`** |

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

1. **展示交互式对话框**（优先）：若 Cursor / IDE 提供 **AskQuestion、确认框、输入框** 等能力，应用其向用户说明：需配置 **`GLM_API_KEY`**，并给出 **[智谱 API Key 管理页](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)** 链接，以及默认 **`GLM_BASE_URL`** / **`GLM_MODEL`**（见下表）。  
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

`gui-agent` 必填 **`--package-name` 或 `--apps`**（文档若写 `--app` 以 `--help` 为准）。

## 5. 执行与机器可读结果（自动化/Agent）

- **契约总述**：仓库 **`docs/工具契约式输入输出方案.md`**（全局 `--result-file`、`--machine-json`、落盘优先级）。
- **字段速查（Skill 内）**：[**`hapray-tool-result.md`**](hapray-tool-result.md) — 期望 **`hapray-tool-result.json`** 顶层与 `outputs` 常用键；**Schema** 见仓库 **`docs/schemas/hapray-tool-result-v1.json`**。
- Agent 优先读契约文件中的 **`outputs.reports_path`**（若存在），再打开业务报告。

## 6. 读结果与 Trace 路径

- **报告目录**：契约 JSON 的 `outputs.reports_path`（若存在）。
- **典型产物**：HTML、Excel、`report/` 下 JSON、`hapray-tool-result.json`、`htrace/**/trace.db`、`hiperf/**` 等。
- **深入分析顺序**：先定位 **`trace.db`**（若存在）→ **加载** [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) → 再对照 HTML/摘要；**`trace.db`** 路径形如 **`<report_dir>/<TestCase>/htrace/stepN/trace.db`**。
- **原则**：对 **`perf_testing` 采集的原始数据**（尤其 SQLite Trace）优先用 **子 Skill** 中的可重复方法分析，自动报告作交叉验证。

## 最终分析报告（独立 Markdown）

在 **已结合 HapRay 产物与子 Skill 完成分析** 后，Agent 须 **新建并保存** 一份 **独立的 `.md` 文件**（与 HapRay 自动生成的 HTML/Excel 区分，供人读、可版本管理、可分享）。

| 项 | 建议 |
|----|------|
| **位置** | 用户工作区根目录，或 `<REPO_ROOT>` 下如 `docs/hapray-reports/`、`dist/hapray-analysis/`（目录不存在则创建）；若用户指定路径则从其指定。 |
| **文件名** | `hapray-analysis-<YYYYMMDD>-<简短主题>.md`（例：`hapray-analysis-20260330-douyin-perf.md`）；避免与工具输出目录同名覆盖。 |
| **正文结构** | 建议包含：**背景与问题**、**测试/采集方式**（对应 CLI 与子命令）、**HapRay 报告路径**（`reports_path`、`trace.db` 等真实路径）、**结论与数据依据**、**原因与优化建议**、**未解决问题或后续动作**（按需）。 |
| **原则** | 可复述对话中的要点，但以 **单文件自洽** 为准；引用数据须与产物一致，**禁止**虚构路径与数值。 |
| **多轮分析（同一落盘报告）** | 针对 **同一份已存在的分析 `.md`**（同一套 HapRay 报告目录、同一分析主题）开展 **第二轮及后续** 补充/修订时：**默认在原文件上更新**（编辑、覆盖或追加修订说明），使结论保持 **单一事实来源**。**除非**用户明确要求「另存为新文件」「复制一份」「导出到新路径」或给出新文件名，否则 **不要** 新建并行的 `hapray-analysis-*.md`。 |

**多轮分析默认行为**：先定位已有 `.md` 路径 → **更新该文件**；仅在用户显式要求时 **另存为新文件**。

## 7. 常见问题（简短）

- **命令找不到**：当前目录是否为 `perf_testing`，是否 `uv run` 或已激活 `.venv`。
- **Node/Python 不符**：重新 `bootstrap_env`，以锚点文件为准。
- **设备**：`hdc` 与 USB 调试授权。

## 8. 深入阅读

- 克隆仓库根目录：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`、`README.md`
- 本 Skill 内：**[`hapray-tool-result.md`](hapray-tool-result.md)**（`hapray-tool-result.json` 字段说明；Schema：`docs/schemas/hapray-tool-result-v1.json`）
- **[`analysis/README.md`](analysis/README.md)**（数据分析子 Skill 总索引）
- 滑动卡顿 Trace：**[`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)**
