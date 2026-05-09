# 符号恢复辅助问题定位方法文档

> 适用场景：在 HapRay 性能报告或 `perf.data` 中发现大量 `libxxx.so+0xXXXXX` 格式的
> 缺失符号（stripped SO 文件），通过 SymRecover 工具恢复函数名并辅助定位性能瓶颈。

---

## 〇、源码克隆：先做主 Skill「硬门禁」（必读）

从仓库 **新 `git clone` 且无本地构建产物** 时，`perf.data`→`perf.db`（SymRecover Step1）、集成 `hapray update` 符号恢复、`dbtools`/负载拆解等链路**会成片报错**——多数是 **`tools/static_analyzer` 未 `npm run build`、`tools/symbol_recovery` 未建 venv/装依赖**，不是本章分析步骤写错。

**在读下文「何时需要」「安装依赖」之前**，必须先完成父级 **`skills/hapray/SKILL.md`** 中的 **[源码工作区硬门禁]**：**`perf_testing` 的 `uv sync`、`<REPO_ROOT>/dist/tools/sa-cmd/`、`symbol_recovery` 的 `main.py --help` + radare2 + 反编译插件（r2dec/r2ghidra）**。未完成则不要判断为「LLM/API/设备」类问题。

---

## 一、何时需要符号恢复

性能分析报告（HTML / perf.data）中出现以下情况时，符号恢复能显著提升分析效率：

| 现象 | 说明 |
|------|------|
| `libxxx.so+0xABCD` 格式地址大量出现在热点列表 | SO 文件已被 strip，函数名缺失 |
| 热点函数显示为 `fcn.000c8a7c` 或 `sub_XXXXX` | Radare2 / IDA 自动命名，语义不明 |
| KMP/Compose 类应用（RN、Flutter）的 `.so` 热点 | KMP stripped SO，需要分类分析 |
| perf.data 中某 SO 占比高但无可读符号 | 无法定位是业务逻辑还是框架开销 |

---

## 二、环境准备

### 2.1 工具位置

```
<REPO_ROOT>/tools/symbol_recovery/
├── main.py          # 唯一入口
├── .env             # LLM API Key 配置（从 .env.example 复制）
└── core/            # 分析器模块
```

### 2.2 安装依赖

```bash
cd <REPO_ROOT>/tools/symbol_recovery
uv venv .venv
uv pip install --python ./.venv/bin/python -e .
```

**安装 radare2 + 反编译插件（必选，硬门禁要求）：**

反编译质量直接影响 LLM 推断准确率，性能提升 10 倍以上。

macOS：
```bash
brew install radare2
r2pm install r2dec            # 反编译插件（轻量快速，推荐优先）
# r2pm install r2ghidra       # 更高质量，需 Java，复杂函数可选
```

Windows：
```powershell
# 方式一：winget（推荐，Win 10 1709+）
winget install radare2

# 方式二：Chocolatey
choco install radare2

# 安装完成后在同一终端执行插件安装
r2pm install r2dec
# r2pm install r2ghidra
```

> Windows 下 `r2pm` 需要联网；若企业内网受限，可从 [radare2 GitHub Releases](https://github.com/radareorg/radare2/releases) 下载 `.zip` 解压后将 `bin/` 加入 `PATH`。

### 2.3 配置 LLM API Key（在线直连模式）

复制 `.env.example` 为 `.env`，填入 API Key（以 DeepSeek 为例）：

```
LLM_SERVICE_TYPE=deepseek
DEEPSEEK_API_KEY=your_key
```

支持的服务类型：`poe`（默认）、`openai`、`claude`、`deepseek`、`custom`。

> **不配置本地 API Key 也可使用**：可选 `--no-llm` 快速模式，或由主 Agent 走离线编排模式（prompt 导出 + 外部 LLM + 回填）。

---

## 三、分析步骤

### Step 0：前置——确认符号恢复运行路径（**必须先完成，再进行后续步骤**）

> 运行路径确认（在线直连 / 离线编排 / `--no-llm` 快速模式）由主 Skill `../SKILL.md` 的「symbol-recovery 门禁」统一执行，**必须先完成该门禁再继续 Step 1**。

### Step 1：识别缺失符号

从 HapRay HTML 报告或 `perf.data` 中找到需要恢复的 SO 文件：

- HTML 报告中热点函数列：找 `libxxx.so+0x...` 地址格式
- perf.data 原始数据：用 `hiperf_report.html` 查看 Flame Graph，高占比无名称函数

确认需要分析的 SO 路径。SO 文件需从设备拉取：

```bash
# 从设备拉取 SO（以 libxxx.so 为例）
hdc file recv /proc/<pid>/root/data/storage/el1/bundle/libs/arm64/libxxx.so ./so/
# 或从 HAP/HSP 中解压
```

### Step 2：准备数据文件

**方式 A：perf.data 模式（推荐，自动处理热点排序）**

已有 `perf.data` 和对应 SO 目录即可直接运行。

**方式 B：Excel 偏移量模式**

从报告或手动分析中整理需要恢复的函数偏移量，存为 Excel 文件（含 offset 列）。

### Step 3：运行符号恢复

**perf.data 模式（最常用）：**

```bash
cd <REPO_ROOT>/tools/symbol_recovery
python3 main.py \
    --perf-data path/to/perf.data \
    --so-dir path/to/so/ \
    --top-n 100 \
    --output-dir output/
```

**针对单个 SO 文件（聚焦分析）：**

```bash
python3 main.py \
    --perf-data path/to/perf.data \
    --so-file path/to/libxxx.so \
    --top-n 50 \
    --output-dir output/
```

**针对已知开源库（如 FFmpeg、OpenSSL）提升准确率：**

```bash
python3 main.py \
    --perf-data path/to/perf.data \
    --so-file libttffmpeg.so \
    --open-source-lib ffmpeg \
    --top-n 100
```

**KMP 模式（Kotlin Multiplatform，如某些 RN 应用）：**

```bash
python3 main.py \
    --kmp-mode \
    --perf-db path/to/perf.db \
    --so-file libs/arm64/libexample.so \
    --kmp-app-name MyApp \
    --top-n 50
```

**离线编排（主 Agent 模式，无需本地 API Key）：**

当没有本地 LLM API Key，或由主 Agent 统一负责推断时，使用两步离线编排。

*第一次调用——导出待分析任务：*

```bash
python3 main.py \
    --perf-data path/to/perf.data \
    --so-dir path/to/so/ \
    --top-n 100 \
    --output-dir output/ \
    --prompt-only
# 产出：output/symbol_recovery_llm_tasks.json
```

完成反汇编和字符串提取，**不调用 LLM、不读取 `.env`**。产出文件每条包含：`function_id`（`func_<rank>`）、`address`、`prompt`（含反汇编/字符串/反编译）、`expected_schema`。

*第二步——主 Agent 处理任务（按任务数量选择方式）：*

**任务数 ≤ 30 条：Agent 在对话中直接处理**

读取 `output/symbol_recovery_llm_tasks.json`，逐条分析 `prompt` 字段（含 ARM64 反汇编、字符串常量、反编译代码），按以下格式写入 `output/llm_results.json`：

```json
[
  {
    "function_id": "func_1",
    "functionality": "函数功能描述（中文，50-200 字）",
    "function_name": "推断的语义化英文函数名（必填，禁止包含地址偏移后缀）",
    "performance_analysis": "性能问题与优化建议（中文）",
    "confidence": "高 / 中 / 低",
    "reasoning": "关键指令模式、字符串等推断依据"
  }
]
```

**命名规范（强制）**
- `function_name` 必须是语义化函数名，不得包含偏移信息。
- 禁止：`foo_bar_f96fc`、`foo_bar_0x1a2b`、`foo_bar+0x1a2b`、`libxx.so+0x1a2b`。
- 建议：`decodeFrame`、`buildRuntimeRequest`、`resolveJsBinding`。
- 该约束由 Skill 流程强制执行：在离线编排产出结果 JSON 前必须人工/Agent 校验并修正；**工具导入阶段不负责自动去偏移后缀**。

每次处理 10 条左右。任务数较多时，根据你的运行环境选择以下**两条路径之一**：

---

**路径 A — 在线模式**（有 API Key，终端直接批量调用）

适用于：配置了 `tools/symbol_recovery/.env`，希望脚本自动跑完所有函数。

```bash
cd <REPO_ROOT>/tools/symbol_recovery
python3 scripts/run_step2.py openai \
    --tasks output/symbol_recovery_llm_tasks.json \
    --output output/llm_results.json
# 可加 --resume（断点续传）、--model <名称>（覆盖 .env 模型）
```

- 依赖 `tools/symbol_recovery/.env` 中的 `api_key` / `base_url` / `model`
- 旧写法 `python3 scripts/run_step2.py --tasks ... --output ...` 等价于此（向后兼容）

---

**路径 B — 离线编排模式**（Cursor / GUI Agent，不用或不想配 `.env`，推荐）

适用于：在 Cursor 对话中让 Agent 模型做推断，推断本身**不调用外部 API**。

**强制降级规则（必须遵守）**：
- 在线直连 LLM 若出现额度不足、鉴权失败、网络/网关不可达、限流重试后仍失败，不得结束流程。  
- 必须立即降级到本路径（离线编排），并继续完成回填。  
- 目标是一次性闭环交付：在同一次任务中完成“导出 -> 推断 -> 导入 -> 报告更新”。

默认由 Skill 驱动在对话中完成，不要求额外编写临时脚本。推荐流程：
1. 读取 `symbol_recovery_llm_tasks.json`（可按 10 条分批处理）。
2. Agent 逐条基于 `prompt` 做真实推断，生成结果 JSON（保持 `function_id` 对齐）。
3. 结果直接保存为 `symbol_recovery_external_results.json`（或任意路径），供 `--import-llm-results` 回填。

> `scripts/run_step2.py split/merge` 仅作为历史兼容选项；优先使用 Skill 对话流程完成离线编排。

---

**结果 JSON 要求：**
- 必填字段：`function_id`（格式 `func_1`、`func_2`…）、`functionality`、`confidence`
- 必填字段补充约束：`function_name`、`performance_analysis` 也必须提供且不能为空
- 可选字段：`reasoning`
- 也接受同义字段：`description` = `functionality`，`inferred_name` = `function_name`
- 顶层格式：裸数组 `[...]` 或 `{"functions":[...]}` 均可
- `function_name` 必须是语义化英文函数名，禁止附带偏移后缀（如 `_f96fc` / `_0x1a2b` / `+0x1a2b` / `libxx.so+0x1a2b`）；必须在产出阶段即保证规范。
- `functionality` 与 `performance_analysis` 必须为中文；不合规结果必须在导入前修正。

*第二次调用——回填结果并生成报告：*

```bash
python3 main.py \
    --perf-data path/to/perf.data \
    --so-dir path/to/so/ \
    --top-n 100 \
    --output-dir output/ \
    --skip-step1 --perf-db output/perf.db \
    --import-llm-results /path/to/results.json
# 产出：Excel 报告 + HTML 符号替换报告（与在线模式完全相同）
```

`--skip-step1 --perf-db output/perf.db` 复用第一次产出的 perf.db，避免重复转换。  
`--import-llm-results` 自动设置 `--no-llm`，全程不调用本地 LLM。  
回填匹配优先级：`function_id` > `rank` > `address`（三者任一均可）。

---

### 与 `hapray update` 集成的默认行为（实现契约）

以下与 `perf_testing/hapray/actions/update_action.py`、`perf_testing/hapray/analyze/perf_analyzer.py` 行为一致，供对照日志排查。

| 步骤 | 行为 |
|------|------|
| **SO 目录** | 优先 `hapray update --so_dir <dir>`，其次环境变量 `HAPRAY_SO_DIR`。若仍无有效目录，且 **`hdc` 在 PATH、设备在线**：从 **`testInfo.json`** 读取 **`app_id`（包名）**，对每个包执行 **`hdc shell bm dump -n <包名>`**，从返回 JSON 中读取 **`modulePath` / `hapPath` / `bundleDataDir`** 等与安装相关的路径（见实现中的字段白名单），将每个基路径展开为 **`…/libs`、`…/libs/arm64`**（若路径指向 `.hap`/`.har` 则先取父目录）并 **`hdc file recv`** 到 `--report_dir/.symbol_recovery_libs/<bundle>/`；若仍无 `.so`，再用**仅由包名拼出的**常见路径兜底（如 `/data/storage/el1/bundle/<包名>/libs`、`/data/app/el1|el2/bundle/<包名>/libs(/arm64)`）。**不依赖进程 PID**（不以 `pidof`/`ps`/`pids.json` 为主路径）。 |
| **自动拉库失败** | 日志中会出现 `Failed to auto-download libs for bundle: <app_id>`。此时 **`effective_so` 为空，集成符号恢复整段不会执行**（与 LLM 是否配置、是否探活失败无关）。处理方式：连接设备后重试、或显式传入 `--so_dir` / 设置 `HAPRAY_SO_DIR` 指向已含 `.so` 的目录。 |
| **LLM** | 未 `--symbol-recovery-no-llm` 时：若 Key/Base URL 已配置且非强制 agent，则**先对 symbol_recovery 做运行时探活**；失败则自动 **fallback 到 agent 模式**（`llm_ready` 置假、`agent_mode` 置真，并记录 `symbol_recovery_llm_probe_ok`）。 |
| **同一步骤内降级** | `PerfAnalyzer` 中：探活失败或 offline agent 路径下先执行 **`--prompt-only`** 导出 `symbol_recovery_llm_tasks.json`，然后在同次 update 内默认调用内置 `tools/symbol_recovery/scripts/run_step2.py openai --tasks ... --output ...` 生成 `symbol_recovery_external_results.json`，再立即 `--import-llm-results` 回填 `perf.json` 与 HTML。`HAPRAY_SYMBOL_RECOVERY_AGENT_CMD` 仅作可选覆盖。若命令未产出结果，则本次判定为未完成真实推断，不进入“成功回填”。 |

**与 `update` 集成时的一次性闭环要求（默认 Agent，禁止二次回填）**：
- 默认目标：`update` 在**同一次执行**中完成 `tasks -> symbol_recovery_external_results.json -> import`，不要求用户再跑第二次 `update`。  
- 在线路径仅作为首选尝试；**探活失败**（如 402/额度、URL/鉴权问题）或 **在线子进程失败/无有效映射** 时，**同一次** `update` 立即走 agent 命令链（导出 tasks -> agent 生成结果 -> import 回填），不得停留在“只导出任务”。  
- 若默认/自定义 agent 命令均失败，本次必须标记“未完成真实推断（失败）”，并输出阻塞原因与重试命令；不得以“无外填结果设定一致”表达为成功。

**严禁半成品交付（强制）**：
- 仅有 `symbol_recovery_llm_tasks.json` 时，结论必须是“符号恢复未完成”。  
- 若 `symbol_recovery_replacements.json` 中仍出现 `auto_recovered_*`，视为占位替换，不能计为语义化恢复成功。  
- 必须以产物四件套作为完成证据：`llm_tasks`、`external_results`、`replacements`、`hiperf_report_with_inferred_symbols.html`。

**Excel 和 KMP 模式同样支持此两步流程**，分别替换为 `--excel-file`/`--so-file` 和 `--kmp-mode`/`--perf-db`/`--so-file`；Excel 和 KMP 的第二次调用无需 `--skip-step1`。

**跳过 LLM（仅反汇编，速度最快）：**

```bash
python3 main.py --no-llm --perf-data perf.data --so-dir so/
```

### Step 4：解读分析结果

输出目录下的关键文件：

| 文件 | 内容 |
|------|------|
| `event_count_top{N}_analysis.xlsx` | 符号恢复主结果（默认，按 event_count 排序） |
| `event_count_top{N}_report.html` | 交互式 HTML 报告（含技术原理、Token 统计） |
| `hiperf_report_with_inferred_symbols.html` | 原始性能报告中的符号已替换为推断函数名 |

**Excel 报告关键列说明：**

| 列名 | 含义 | 分析价值 |
|------|------|----------|
| 函数偏移量 | `libxxx.so+0x...` | 与原始报告对应 |
| 函数功能描述 | LLM 推断的功能（中文） | 快速理解函数用途 |
| 函数名推断 | 推断的英文函数名 | 替换报告中的地址 |
| 负载问题识别与优化建议 | 计算热点 vs 潜在瓶颈 | **判断是否需要优化** |
| 调用链信息 | 调用者 + 被调用者 | 定位调用路径 |
| 字符串常量 | 函数内引用的字符串 | 辅助验证推断 |

**负载类型判断：**

- **计算热点（Expected Hotspot）**：高负载但必要（如解码、FFT），无需优化
- **潜在瓶颈（Optimization Opportunity）**：存在低效逻辑（频繁内存拷贝、嵌套调用、I/O 调用），需重点关注

### Step 5：在原报告中验证替换结果

Step 3 默认会生成 `hiperf_report_with_inferred_symbols.html`，将推断的函数名替换到原始 Flame Graph 报告中。如需单独执行替换：

```bash
python3 main.py \
    --only-step4 \
    --html-input path/to/hiperf_report.html \
    --perf-db output/perf.db
```

---

## 四、典型定位场景

### 场景 A：热点 SO 功能未知

**问题**：报告中某 `libfoo.so` 占 CPU 指令数 30%+，但地址全部缺失，不知道在做什么。

**操作**：
1. 用 perf.data 模式运行符号恢复（`--so-file libfoo.so --top-n 100`）
2. 查看 Excel 报告的「函数功能描述」列
3. 根据「负载问题识别与优化建议」列判断属于哪类开销：
   - **计算热点**：解码、推理、渲染类函数，负载合理，关注算法/量化优化
   - **潜在瓶颈**：频繁内存拷贝、嵌套循环、I/O 等，优先重点审查
4. 结合「调用链信息」列确认调用路径，判断开销来自业务代码还是第三方框架

### 场景 B：KMP 应用区分业务与框架开销

**问题**：某 KMP 应用 `libcompose.so` 占比高，需判断是 Compose 渲染框架本身的开销还是业务写法问题。

**操作**：
1. 使用 `--kmp-mode` 运行，加 `--kmp-app-name` 指定应用名
2. 查看「KMP分类」列：`KMP Runtime`/`Compose UI` 为框架开销，`Business (AppName)` 为业务逻辑
3. 若业务分类函数中出现高负载，重点审查业务侧的 Composable 写法

### 场景 C：配合 trace.db 联合分析滑动卡顿

**问题**：`trace.db` 中发现某帧的 `FlushLayoutTask` 耗时高，但 perf 热点中对应地址无符号，无法确认具体是哪个组件。

**操作**：
1. 先用 `scroll-jank-trace-analysis.md` 找到卡顿帧的时间窗口
2. 从 perf.data/perf.db 中筛选该时间窗口内的高频无符号地址
3. 对高频地址所在 SO 运行符号恢复
4. 结合「调用链信息」列中的调用者，与 `callstack` 表中的 Hitrace 标记交叉验证

### 场景 D：无 LLM 快速初筛

**问题**：需快速了解某 SO 中有哪些可识别函数，不想消耗 LLM Token。

**操作**：

```bash
python3 main.py --no-llm --perf-data perf.data --so-file libxxx.so --top-n 200
```

- 输出 Excel 含「调用链信息」和「字符串常量」，即使没有 LLM 推断也能通过字符串辅助判断
- 后续对重点函数再用 `--excel-file` 模式精细分析

---

## 五、常用参数速查

| 参数 | 含义 | 常用场景 |
|------|------|----------|
| `--perf-data` | perf.data 文件路径 | 完整工作流起点 |
| `--perf-db` | 跳过转换，直接用已有 perf.db | `--skip-step1` 后再次分析 |
| `--so-dir` | SO 文件目录（多 SO 模式） | 全量分析 |
| `--so-file` | 单个 SO 文件路径 | 聚焦特定库 |
| `--top-n` | 分析前 N 个函数 | 默认 100，调小加快速度 |
| `--stat-method` | `event_count`（默认）/ `call_count` | event_count 反映 CPU 指令消耗 |
| `--open-source-lib` | 开源库名称（ffmpeg/openssl 等） | 定制版开源库，提升推断准确率 |
| `--kmp-mode` | 启用 KMP 分类分析 | Kotlin Multiplatform SO |
| `--no-llm` | 仅反汇编，不调用 LLM | 快速初筛 / 无 API Key |
| `--skip-step1` | 跳过 perf.data 转换 | 已有 perf.db 时复用 |
| `--skip-step4` | 跳过 HTML 符号替换 | 只需 Excel 报告 |
| `--batch-size` | 每个 LLM prompt 的函数数（默认 3） | 遇 JSON 截断时调小到 2 |
| `--skip-decompilation` | 跳过反编译，仅反汇编 | 加速 20~30%，质量略降 |
| `--save-prompts` | 保存 LLM prompt 到文件 | 调试分析质量 |
| `--context` | 自定义上下文信息 | 提供 SO 功能背景 |

---

## 六、输出文件说明

```
output/
├── perf.db                                   # Step 1：perf.data 转换结果
├── event_count_top100_analysis.xlsx          # 符号恢复主报告
├── event_count_top100_report.html            # 交互式 HTML 报告
├── hiperf_report_with_inferred_symbols.html  # 原 HTML 中地址已替换为函数名
└── prompts/                                  # --save-prompts 时生成，便于调试
```

---

## 七、注意事项

- **SO 文件需与采集时版本一致**：地址偏移量对应特定构建产物，版本不同会导致定位错误
- **event_count 反映 CPU 指令数（exclusive）**：更能反映函数自身的计算开销；`call_count` 反映调用频率
- **KMP 模式使用 perf.db**；`Total` 列的统计口径以代码实际实现为准，分析结果时注意与普通 perf 模式的 exclusive（leaf-frame）口径区分
- **LLM 缓存**：`cache/llm_analysis_cache.json` 自动缓存结果，相同函数不重复消耗 Token；清除缓存：`rm -rf cache/llm_analysis_cache.json`
- **batch_size 过大会导致 JSON 截断**：默认值 3 较稳定；`top-n` 大时建议保持默认或调小到 2

---

## 八、问题定位决策树

```
发现性能问题
│
├─ 热点在已知库（libskia、libhirender 等有符号）
│   └─ 直接用 analyze_so_perf.py 查看 top-N 函数，无需符号恢复
│
├─ 热点在 stripped SO（地址无符号）
│   ├─ KMP 应用（Kotlin Multiplatform，libxxx.so 包含 kfun: 符号残留）
│   │   └─ 使用 --kmp-mode 运行，关注「KMP分类」列区分框架/业务
│   ├─ 开源库（FFmpeg、OpenSSL、Skia 等已知库）
│   │   └─ 加 --open-source-lib 参数，LLM 准确率显著提升
│   └─ 未知私有库
│       ├─ 先用 --no-llm 快速初筛（看字符串常量、调用链）
│       └─ 再对关键函数用完整模式精细分析
│
└─ 已有符号恢复结果，需联合 trace 分析
    └─ 参考场景 C：trace 时间窗口 → perf 地址筛选 → 符号恢复 → 交叉验证
```

**结果解读优先级**：
1. `负载问题识别与优化建议` — 判断是否值得优化
2. `函数功能描述` — 理解函数用途
3. `调用链信息` — 定位调用路径
4. `字符串常量` — 辅助验证推断准确性
