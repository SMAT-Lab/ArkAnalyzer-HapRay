---
name: hapray
description: |
  HapRay (ArkAnalyzer-HapRay): Agent MUST run real CLI and MUST save final analysis as a standalone .md file. Modular analysis/ sub-docs (scroll-jank trace.db). Testcases MemLoad_*/PerfLoad_*. `update` = rare migration. perf/opt/gui-agent. Triggers: 鸿蒙性能, 滑动卡顿, trace, HAP/SO/LTO, 负载/内存, gui-agent, @hapray / HapRay.
---

# HapRay 引导式工作流

面向 **HapRay 工具使用者**：从环境到结果的可重复步骤。工程主文档见克隆仓库根目录 `README.md` 与 `docs/使用说明.md`。

## Skill 包结构（主 Skill + 数据分析子模块）

本目录采用 **一个主 `SKILL.md` + 可扩展的 `analysis/` 子文档**：

| 部分 | 路径 | 职责 |
|------|------|------|
| **主 Skill** | `SKILL.md`（本文件） | 环境、构建、CLI 选路、Agent 强制约束、与子模块的衔接方式 |
| **数据分析子 Skill** | `analysis/*.md` + [`analysis/README.md`](analysis/README.md) | 各专题的 **深度分析步骤**（SQL、表结构、诊断规律）；按需嵌入，避免主文件过长 |

发布或复制到 `~/.cursor/skills/hapray/` 时，请 **整个 `hapray/` 目录** 一并同步，否则 `analysis/` 下的子 Skill 会丢失。

## 数据分析子 Skill 索引

当用户问题涉及下表「触发场景」时，Agent 除运行 CLI 外，应 **读取对应子文档** 再作答（路径相对于本 Skill 根目录，与 `SKILL.md` 同级）：

| ID | 子文档 | 触发场景 | 核心内容 |
|----|--------|----------|----------|
| `scroll-jank` | [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) | 滑动卡顿、掉帧、列表/WaterFlow 滑动、周期性 jank、从 Trace 还原手势 | `trace.db` 表（`process`/`thread`/`callstack`/`frame_slice`）、**`frame_slice` 仅 `type_desc=actural` 且 `depth=0`**、卡顿分级、手势与 `mainDelta`、隔次卡/触顶/拉动、SQL 与 Python 脚本、Hitrace 标记表 |

**嵌入规则**：主 Skill **不重复**子文档中的长 SQL、长脚本与完整标记表；回答「卡顿原因/修复」时须与子文档规则一致，并标明依据 **`trace.db`** 路径。后续新增专题（如启动时延、内存火焰图解读）时，在 `analysis/` 下增加新 `.md`，并更新 **本表** 与 [`analysis/README.md`](analysis/README.md)。

## Agent 执行约束（强制；本 Skill 被加载时适用）

本 Skill 的目标不是「口述性能知识」，而是 **驱动本机已克隆仓库中的 HapRay CLI 实际运行**。在 Cursor / IDE Agent 中你必须使用 **终端（或等价的 run command 能力）** 执行命令；**禁止**在未尝试执行相关 CLI 的情况下，仅用泛泛的通用建议充当「分析结果」。

### 必须执行（按顺序尝试）

1. **定位仓库根目录**：以用户当前工作区 / 打开的路径为准（例如包含 `perf_testing/`、`package.json` 的目录）；若未知，先向用户确认或列目录查找，**不得臆造路径**。
2. **需要真机时**：先运行 `hdc list targets`（或 `hdc version`）。若设备未授权或不可用，**明确告知用户**并在本回合内**不得假装已生成报告**。
3. **进入 Python CLI 目录**：所有 `python -m scripts.main ...` 必须在 **`<REPO_ROOT>/perf_testing`** 下执行（先 `cd` 再跑，或使用 `-C` 等效方式）。
4. **根据意图选择子命令并真正运行**（至少执行到命令返回或明确报错）：
   - **负载 / 场景复现 / 抖音类浏览 + 原因与建议** → `gui-agent`（需 LLM：`GLM_BASE_URL`、`GLM_API_KEY`、`GLM_MODEL` 或 `--glm-*`）；若用户**未配置 LLM**，应改跑 **`perf --run_testcases`**，用例从 **`perf_testing/hapray/testcases/<应用包名>/`** 下按命名挑选（见下文「预置用例」），**同样必须执行命令**，不得改为纯文字分析。
   - **SO/HAP 优化检测** → 仓库文档中的 `opt` 入口（如 `hapray-gui/cmd.py` 或 `tools/optimization_detector`）。
   - **`update`**：仅在 **HapRay 工具版本变更后**，需把 **旧版 HapRay 生成的报告** 迁移到当前版本格式时使用；**绝大多数日常场景不会调用**。若用户未提及「升级 HapRay / 迁移历史报告」，**不要**默认选 `update`。
5. **需要机器可读结果时**：在全局参数中附加 `--result-file <绝对路径>`（见 `python -m scripts.main --help`），执行后 **读取该文件** 或 `hapray-tool-result.json` 获取 `reports_path`，再向用户说明结果位置。
6. **解读「原因与建议」**：须在 **命令已成功产出报告/JSON** 之后，结合产物路径中的 HTML/JSON 做归纳；若无成功产物，只能说明失败原因与下一步，**不得编造热点函数或数据**。
7. **卡顿帧 / 滑动 jank**：须在 **已存在 `htrace/.../trace.db`**（或先跑 `perf`/`gui-agent` 采集）的前提下解读；**统计规则**以子 Skill [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md) 为准（**`frame_slice` 仅 `depth=0` 且 `actural`**）。**禁止**把 `depth>0` 当真实单帧时长；无 Trace 时不得编造帧数据。
8. **最终分析报告落盘**：在完成基于 HapRay 产物（及子 Skill）的归纳后，须将 **完整分析结论** 写入 **独立 Markdown 文件**（`.md`），**不得**仅在对话中输出而不落盘；路径与命名见下文「最终分析报告（独立 Markdown）」。

### 明确禁止

- 禁止用「通常可以检查 CPU/内存…」等**通用清单**替代一次真实的 `gui-agent` / `perf` / `opt` 执行（除非用户明确只要文档、且声明不跑工具）。**`update`** 仅用于报告迁移，见上文；勿为「重新分析」而滥用。
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

无 LLM 时改用 `perf`（用例从 **`hapray/testcases/<应用包名>/`** 中选 **`PerfLoad_*.py`** 负载类或 **`MemLoad_*.py`** 内存类；`--run_testcases` 传 Hypium 用例名/正则；`--so_dir` 有符号化 so 时再附加）。

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

- 需要：**搭环境 → 构建 → 选能力 → 执行 → 看结果**
- 用户用自然语言描述「测性能」「查 SO 优化」「分析 HAP」等（「更新报告」若指 **迁移旧版工具产出的报告**，才涉及 `update`）
- **负载与体验类**：优先 **`gui-agent`**（设备上复现场景 + 采集 trace/perf + 报告）
- **滑动卡顿 / 掉帧 / jank**：先确保有 **trace**；再结合 **`trace.db`**，并加载 **`analysis/scroll-jank-trace-analysis.md`** 做深度分析

## 验证场景：自然语言 → 预期三步（以抖音为例）

**用户表述示例**：「请分析抖音浏览视频的负载情况，给出高负载的原因和修复建议」

本节是业务步骤说明；**终端是否实际执行**以 **「Agent 执行约束（强制）」** 为准。

| 步骤 | 目标 | 做什么 |
|------|------|--------|
| **1. 前置条件准备** | 可执行 `gui-agent` | 完成 §2 检查清单 + §3 `npm run build`；真机 `hdc`；**LLM** 配置见仓库根 `README.md` GUI Agent 章节 |
| **2. 驱动 gui-agent 测抖音** | 复现场景并采集数据 | **`gui-agent`**；包名 **`com.ss.hm.ugc.aweme`**；**`--scenes`** 与用户表述对齐 |
| **3. 输出报告** | 原因与修复建议 | 报告在 **`output/reports/<时间戳>/`** 等；**若涉及滑动卡顿**，叠加 **数据分析子 Skill `scroll-jank`** |

**示例命令**（`perf_testing` 目录）：

```bash
cd perf_testing
uv run python -m scripts.main gui-agent --apps com.ss.hm.ugc.aweme \
  --scenes "浏览视频推荐流，滑动多屏并进入播放页，关注滑动与播放时的负载" \
  -o ./
```

未传 `--scenes` 时，工具会按 `config.yaml` 的 `gui-agent.scenes.video` 等加载预设场景。

**说明**：若只要固定 Hypium 用例，可 **`perf --run_testcases`**，在 **`hapray/testcases/com.ss.hm.ugc.aweme/`** 下选 **`PerfLoad_*.py`** 或 **`MemLoad_*.py`**。

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

`gui-agent` 必填 **`--package-name` 或 `--apps`**（文档若写 `--app` 以 `--help` 为准）。

## 5. 执行与机器可读结果（自动化/Agent）

见 **`docs/工具契约式输入输出方案.md`**：全局 `--result-file`、`--machine-json`；优先读 `hapray-tool-result.json` 的 `reports_path`。

## 6. 读结果与 Trace 路径

- **报告目录**：契约 JSON 的 `outputs.reports_path`（若存在）。
- **典型产物**：HTML、Excel、`report/` 下 JSON、`hapray-tool-result.json`。
- **滑动卡顿深度分析**：原始库 **`trace.db`** 路径形如 **`<report_dir>/<TestCase>/htrace/stepN/trace.db`**；分析方法见 **数据分析子 Skill** [`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)。

## 最终分析报告（独立 Markdown）

在 **已结合 HapRay 产物与子 Skill 完成分析** 后，Agent 须 **新建并保存** 一份 **独立的 `.md` 文件**（与 HapRay 自动生成的 HTML/Excel 区分，供人读、可版本管理、可分享）。

| 项 | 建议 |
|----|------|
| **位置** | 用户工作区根目录，或 `<REPO_ROOT>` 下如 `docs/hapray-reports/`、`dist/hapray-analysis/`（目录不存在则创建）；若用户指定路径则从其指定。 |
| **文件名** | `hapray-analysis-<YYYYMMDD>-<简短主题>.md`（例：`hapray-analysis-20260330-douyin-perf.md`）；避免与工具输出目录同名覆盖。 |
| **正文结构** | 建议包含：**背景与问题**、**测试/采集方式**（对应 CLI 与子命令）、**HapRay 报告路径**（`reports_path`、`trace.db` 等真实路径）、**结论与数据依据**、**原因与优化建议**、**未解决问题或后续动作**（按需）。 |
| **原则** | 可复述对话中的要点，但以 **单文件自洽** 为准；引用数据须与产物一致，**禁止**虚构路径与数值。 |

## 7. 常见问题（简短）

- **命令找不到**：当前目录是否为 `perf_testing`，是否 `uv run` 或已激活 `.venv`。
- **Node/Python 不符**：重新 `bootstrap_env`，以锚点文件为准。
- **设备**：`hdc` 与 USB 调试授权。

## 8. 深入阅读

- 克隆仓库根目录：`docs/使用说明.md`、`docs/工具契约式输入输出方案.md`、`README.md`
- 本 Skill 内：**[`analysis/README.md`](analysis/README.md)**（数据分析子 Skill 总索引）
- 滑动卡顿 Trace：**[`analysis/scroll-jank-trace-analysis.md`](analysis/scroll-jank-trace-analysis.md)**
