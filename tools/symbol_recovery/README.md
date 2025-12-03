# SymRecover - 二进制符号恢复工具

## 项目简介

SymRecover（Symbol Recovery）是一个专业的二进制符号恢复工具，专注于恢复缺失的函数名并推断函数功能。通过反汇编分析（Radare2/Capstone）和 LLM 推理，该工具能够从二进制文件中恢复函数符号，特别适用于分析已剥离符号表的 SO 库文件。

## 核心功能

### 1. 多模式分析
- **perf 数据模式**：从 `perf.data` 性能采样数据中提取缺失符号的偏移量，进行符号恢复
- **Excel 偏移量模式**：从 Excel 文件读取函数偏移量，直接进行符号恢复

### 2. 多维度统计
- **调用次数（call_count）**：按函数调用频率统计
- **指令数（event_count）**：按指令执行次数统计（默认）

### 3. 智能分析
- **双反汇编引擎**：优先使用 Radare2（自动函数识别），回退到 Capstone
- **实例缓存优化**：同一 SO 文件复用 Radare2 实例，性能提升 10 倍+
- **反编译支持**：支持多种反编译插件（r2dec/r2ghidra/pdq），自动按优先级选择
- **精准字符串提取**：通过分析 ARM64 指令引用（`adrp`/`add`/`ldr`），精准提取函数相关的字符串常量，自动过滤错误消息和调试信息
- **LLM 分析**：使用 GPT-5、Claude-Sonnet-4.5 等大模型分析函数功能和推断函数名
- **性能分析**：针对高指令数负载的热点函数，自动识别性能瓶颈、分析高指令数负载原因，并提供优化建议
- **上下文信息增强**：自动提取函数边界信息（起始/结束地址、大小）、复杂度指标（基本块、控制流边、参数、局部变量）和调用堆栈信息
- **批量分析**：支持批量 LLM 分析，一个 prompt 包含多个函数（默认 batch_size=3），显著提高效率
- **Prompt 调试**：支持保存生成的 prompt 到文件，便于调试和分析

### 4. 报告生成
- **Excel 报告**：包含所有分析结果的详细 Excel 报告（自动列宽、文本换行）
  - 函数功能描述：LLM 推断的函数功能说明
  - **负载问题识别与优化建议**：性能瓶颈分析、高指令数负载原因和优化建议（新增）
  - 函数名推断：LLM 推断的函数名（带 "Function: " 前缀）
  - 函数元信息：函数边界、大小、复杂度指标等
- **HTML 报告**：统一的交互式 HTML 报告，包含技术原理、Token 统计和时间统计
- **HTML 符号替换**：自动将推断的函数名替换到原始性能报告中

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**额外依赖（可选但强烈推荐）：**
- **Radare2**：用于高性能反汇编分析（性能提升 10 倍+）
  - macOS/Linux: `brew install radare2` 或 `apt-get install radare2`
  - Windows: 下载并安装到 `C:\radare2-5.9.4-w64\`
  - 配置路径：代码会自动添加到 PATH
  - Python 接口: `pip install r2pipe>=1.7.0`（已在 requirements.txt 中）

- **反编译插件**（可选，用于提高 LLM 分析质量）：
  - **r2dec**（推荐，轻量快速）：`r2pm install r2dec`
  - **r2ghidra**（高质量，需要 Java）：`r2pm install r2ghidra`
  - 工具会自动按优先级尝试：r2dec → r2ghidra → pdq
  - 如果未安装反编译插件，将仅使用反汇编代码

### 2. 配置 LLM API Key（可选）

如果需要使用 LLM 分析，在项目根目录创建 `.env` 文件：

**默认使用 Poe API：**
```
POE_API_KEY=your_api_key_here
```

**切换其他服务：**

可以通过环境变量 `LLM_SERVICE_TYPE` 切换服务类型：
- `poe`（默认）：使用 Poe API，环境变量 `POE_API_KEY`
- `openai`：使用 OpenAI API，环境变量 `OPENAI_API_KEY`
- `claude`：使用 Claude API，环境变量 `ANTHROPIC_API_KEY`
- `deepseek`：使用 DeepSeek API，环境变量 `DEEPSEEK_API_KEY`
- `custom`：自定义服务，通过 `LLM_BASE_URL` 和 `LLM_API_KEY_ENV` 配置

示例（使用 OpenAI）：
```bash
export LLM_SERVICE_TYPE=openai
export OPENAI_API_KEY=your_openai_key
```

示例（使用 DeepSeek）：
```bash
export LLM_SERVICE_TYPE=deepseek
export DEEPSEEK_API_KEY=your_deepseek_key
```

或在 `.env` 文件中：
```
LLM_SERVICE_TYPE=openai
OPENAI_API_KEY=your_openai_key
```

或使用 DeepSeek：
```
LLM_SERVICE_TYPE=deepseek
DEEPSEEK_API_KEY=your_deepseek_key
```

**配置说明：**
- 所有 LLM 配置都在 `utils/config.py` 中集中管理
- 支持通过环境变量覆盖配置（如 `LLM_TIMEOUT`、`LLM_BASE_URL` 等）
- 详细配置见 `utils/config.py` 中的 `get_llm_config()` 函数

### 3. 运行分析

#### 方式一：perf 数据模式（推荐）

```bash
# 运行完整工作流（默认按 event_count 统计，分析前 100 个函数）
python main.py --perf-data data/taobao/10.55.1/perf.data --so-dir data/taobao/10.55.1/so/

# 指定分析数量和输出目录
python main.py --perf-data perf.data --so-dir so/ --top-n 50 --output-dir output/

# 按调用次数统计
python main.py --stat-method call_count

# 不使用 LLM（仅反汇编）
python main.py --no-llm

# 只使用 Capstone（不使用 Radare2）
python main.py --use-capstone-only

# 跳过反编译（仅使用反汇编，提升速度）
python main.py --skip-decompilation

# 保存生成的 prompt 到文件（用于调试）
python main.py --save-prompts

# 调整批量大小（适应 token 限制）
python main.py --batch-size 3
```

#### 方式二：Excel 偏移量模式

```bash
# 基本用法
python main.py --excel-file data/test.xlsx --so-file data/wechat/libs/arm64/libxwebcore.so

# 不使用 LLM
python main.py --excel-file data/test.xlsx --so-file libxwebcore.so --no-llm

# 指定输出目录
python main.py --excel-file data/test.xlsx --so-file libxwebcore.so --output-dir output/
```

## 工作流程

### perf 数据模式

```
perf.data 
  → Step 1: 转换为 SQLite (perf.db)
  → Step 2: 已移除（逻辑已集成到 Step 3）
  → Step 3: LLM 分析恢复函数名和功能
    ├─ 从 perf.db 读取缺失符号地址
    ├─ 函数定位与切分（radare2）
    ├─ 反汇编/反编译（radare2，可选）
    ├─ 提取上下文信息（字符串、调用函数、调用堆栈）
    ├─ 构建 LLM Prompt（支持批量）
    ├─ LLM 分析推断函数名
    └─ 生成 Excel 和 HTML 报告
  → Step 4: HTML 符号替换（可选）
```

### Excel 偏移量模式

```
Excel 文件（包含偏移量）
  → 读取偏移量
  → 函数定位与切分（radare2）
  → 反汇编/反编译（radare2，可选）
  → 精准字符串提取
  → LLM 分析（可选，支持批量）
  → 生成 Excel 和 HTML 报告
```

## 主要参数

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--top-n` | 分析前 N 个函数 | `100` |
| `--output-dir` | 输出目录 | `output` |
| `--no-llm` | 不使用 LLM 分析（仅反汇编） | `False` |
| `--no-batch` | 不使用批量分析 | `False` |
| `--batch-size` | 批量分析时每个 prompt 包含的函数数量 | `3` (建议 3-10) |
| `--use-capstone-only` | 只使用 Capstone 反汇编（不使用 Radare2） | `False` |
| `--skip-decompilation` | 跳过反编译步骤（仅使用反汇编，提升速度） | `False` |
| `--save-prompts` | 保存每个函数生成的 prompt 到文件（用于调试） | `False` |
| `--llm-model` | LLM 模型名称 | `GPT-5` |
| `--context` | 自定义上下文信息（可选） | 自动推断 |

### perf 数据模式参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--perf-data` | perf.data 文件路径 | `perf.data` |
| `--perf-db` | perf.db 文件路径 | 自动生成在输出目录 |
| `--so-dir` | SO 文件目录 | **必需**（无默认值） |
| `--stat-method` | 统计方式（call_count/event_count） | `event_count` |
| `--skip-step1` | 跳过 Step 1（perf.data → perf.db） | `False` |
| `--skip-step3` | 跳过 Step 3（LLM 分析） | `False` |
| `--skip-step4` | 跳过 Step 4（HTML 符号替换） | `False` |
| `--only-step1` | 只执行 Step 1 | `False` |
| `--only-step3` | 只执行 Step 3 | `False` |
| `--only-step4` | 只执行 Step 4 | `False` |
| `--html-input` | HTML 输入文件路径或目录 | 自动查找 |

### Excel 偏移量模式参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--excel-file` | Excel 文件路径（包含函数偏移量地址） | **必需** |
| `--so-file` | SO 文件路径 | **必需** |

## 输出文件

### perf 数据模式输出

所有输出文件位于 `{output_dir}` 目录（默认：`output/`）：

- `perf.db` - SQLite 数据库（Step 1 生成）
- `event_count_top{N}_analysis.xlsx` - event_count top N 符号恢复结果（默认）
- `event_count_top{N}_report.html` - event_count top N HTML 报告
- `event_count_top{N}_time_stats.json` - 时间统计
- `top{N}_missing_symbols_analysis.xlsx` - call_count top N 符号恢复结果（当使用 `--stat-method call_count` 时）
- `top{N}_missing_symbols_report.html` - call_count top N HTML 报告
- `hiperf_report_with_inferred_symbols.html` - 替换后的 HTML 报告（Step 4）

### Excel 偏移量模式输出

- `output/excel_offset_analysis_{n}_functions.xlsx` - Excel 分析报告
- `output/excel_offset_analysis_{n}_functions_report.html` - HTML 分析报告
- `output/excel_offset_analysis_{n}_functions_time_stats.json` - 时间统计

### 缓存文件

- `cache/llm_analysis_cache.json` - LLM 分析结果缓存（自动管理）
- `cache/llm_token_stats.json` - Token 使用统计（自动更新）

### Prompt 调试文件（使用 --save-prompts 时）

- `{output_dir}/prompts/prompt_{offset}_{symbol}_{timestamp}.txt` - 单个函数的 prompt
- `{output_dir}/prompts/prompt_batch_{batch_num}_{total_batches}_{timestamp}.txt` - 批量函数的 prompt

## 技术特性

### 1. 双反汇编引擎
- **Radare2 优先**（默认）：自动函数识别、边界检测，使用 `aa` 轻量级分析替代 `aaa`
- **实例缓存**：同一 SO 文件的多个函数复用同一个 Radare2 实例，性能提升 10 倍+
- **Capstone 回退**：如果 Radare2 不可用或使用 `--use-capstone-only`，自动使用 Capstone 反汇编
- **强制 Capstone**：使用 `--use-capstone-only` 参数可强制使用 Capstone（即使已安装 Radare2）

### 2. 反编译支持（可选）
- **多插件支持**：自动按优先级尝试 r2dec → r2ghidra → pdq
- **r2dec**（推荐）：
  - 轻量快速：JavaScript 实现，无需 Java
  - 安装：`r2pm install r2dec`
  - 适合批量分析，速度比 r2ghidra 快 2-5 倍
- **r2ghidra**：
  - 高质量反编译：基于 Ghidra 引擎，类型推断准确
  - 安装：`r2pm install r2ghidra`（需要 Java 8+）
  - 适合复杂函数分析，但速度较慢
- **智能回退**：如果反编译失败，自动使用反汇编代码
- **性能优化**：使用 `--skip-decompilation` 可跳过反编译以提升速度

### 3. 精准字符串提取
- 通过分析 ARM64 指令（`adrp`/`add`、`adr`、`ldr`）中的字符串引用
- 精准提取函数相关的字符串常量，而不是扫描整个 `.rodata` 段
- 支持 Radare2 的 `axtj` 交叉引用分析

### 4. 批量 LLM 分析
- 将多个函数合并到一个 prompt 中（默认 batch_size=3）
- 显著减少 API 调用次数，提高分析效率
- 自动处理 token 限制和 JSON 解析
- 支持禁用批量分析（`--no-batch`）进行逐个函数分析

### 5. Prompt 调试支持
- 使用 `--save-prompts` 选项可保存所有生成的 prompt 到文件
- 便于调试 LLM 分析过程，优化 prompt 设计
- 支持单个函数和批量函数的 prompt 保存

### 6. 智能缓存
- LLM 分析结果自动缓存到 `cache/` 目录
- 避免重复分析相同的函数代码，节省成本
- Token 统计自动保存和累积

### 7. 时间统计
- 自动记录各分析步骤的执行时间
- 在 HTML 报告和控制台中展示
- 保存为 JSON 格式便于分析

## 项目结构

```
soanalyzer/
├── analyzers/                    # 分析器模块
│   ├── perf_analyzer.py          # perf 数据分析（支持 call_count/event_count）
│   ├── event_analyzer.py         # event_count 统计分析
│   ├── excel_analyzer.py         # Excel 偏移量分析
│   └── r2_analyzer.py            # Radare2 反汇编分析器
├── llm/                          # LLM 模块
│   ├── analyzer.py               # LLM 单函数分析器
│   ├── batch_analyzer.py         # LLM 批量分析器
│   └── initializer.py            # LLM 初始化工具（API key 加载、分析器创建）
├── utils/                        # 工具模块
│   ├── common.py                 # 通用工具（日志、反汇编器、HTML渲染等）
│   ├── config.py                 # 配置常量
│   ├── time_tracker.py           # 时间统计
│   ├── string_extractor.py       # 字符串提取器
│   ├── perf_converter.py         # perf.data → perf.db 转换器
│   └── symbol_replacer.py        # HTML 符号替换
├── bin/                          # 外部二进制工具
│   └── trace_streamer_binary/    # perf.data 转换工具
│       ├── trace_streamer_mac     # macOS 版本
│       ├── trace_streamer_linux   # Linux 版本
│       └── trace_streamer_windows.exe # Windows 版本
├── cache/                        # 缓存目录
│   ├── llm_analysis_cache.json   # LLM 分析缓存
│   └── llm_token_stats.json      # Token 统计
├── data/                         # 数据目录
│   ├── wechat/                   # 微信应用数据
│   ├── taobao/                   # 淘宝应用数据
│   └── test.xlsx                 # 测试样例
├── output/                       # 默认输出目录
├── docs/                         # 文档
│   └── CODE_DEPENDENCIES.md      # 代码依赖关系
├── main.py                       # 主入口（唯一入口）
├── requirements.txt              # Python 依赖
└── README.md                     # 项目文档
```

## 依赖要求

### Python 依赖

**核心依赖（必需）：**
- Python 3.11+
- `pyelftools>=0.29` - ELF 文件解析
- `capstone>=5.0.0` - ARM64 反汇编（回退方案）
- `pandas>=2.0.0` - 数据处理和 Excel 操作
- `openpyxl>=3.1.0` - Excel 文件读写
- `python-dotenv>=1.0.0` - 环境变量管理（.env 文件）
- `openai>=1.0.0` - LLM API 调用（Poe API 兼容）

**可选依赖（强烈推荐）：**
- `r2pipe>=1.7.0` - Radare2 Python 接口（性能提升 10 倍+）

安装所有依赖：
```bash
pip install -r requirements.txt
```

### 外部工具

- **Radare2**（可选，强烈推荐）：用于高性能反汇编
  - macOS: `brew install radare2`
  - Linux: `apt-get install radare2` 或 `yum install radare2`
  - Windows: 下载并安装到 `C:\radare2-5.9.4-w64\`
  - 性能提升：10 倍+（从 `aaa` 完整分析改为 `aa` 轻量级分析 + 实例缓存）
  - 如果未安装，会自动回退到 Capstone 反汇编

- **trace_streamer**：用于 perf.data 转换
  - 已包含在 `bin/trace_streamer_binary/` 目录
  - 支持 macOS、Linux、Windows 三个平台
  - 代码会自动检测并使用对应平台的版本

## 使用示例

### 示例 1：完整符号恢复流程（event_count 模式）

```bash
# 运行完整工作流，恢复前 100 个缺失符号（按 event_count）
python main.py \
    --perf-data data/taobao/10.55.1/perf.data \
    --so-dir data/taobao/10.55.1/so/ \
    --output-dir data/taobao/10.55.1/ \
    --top-n 100 \
    --html-input data/taobao/10.55.1/hiperf_report.html
```

### 示例 2：call_count 模式

```bash
python main.py \
    --perf-data data/taobao/perf.data \
    --so-dir data/taobao/so/ \
    --stat-method call_count \
    --top-n 50
```

### 示例 3：Excel 偏移量模式

```bash
# 从 Excel 文件读取偏移量进行符号恢复
python main.py \
    --excel-file data/test.xlsx \
    --so-file data/wechat/libs/arm64/libxwebcore.so
```

### 示例 4：仅反汇编（不使用 LLM）

```bash
# 快速反汇编分析，不调用 LLM
python main.py --perf-data perf.data --so-dir so/ --no-llm
```

### 示例 5：调整批量大小

```bash
# 减小批量大小以避免 token 截断
python main.py --batch-size 2

# 禁用批量分析（逐个函数分析，更稳定但较慢）
python main.py --no-batch
```

### 示例 6：强制使用 Capstone

```bash
# 只使用 Capstone 反汇编（不使用 Radare2）
python main.py --use-capstone-only --perf-data perf.data --so-dir so/
```

### 示例 7：跳过反编译以提升速度

```bash
# 跳过反编译步骤，仅使用反汇编代码（速度更快）
python main.py --skip-decompilation --perf-data perf.data --so-dir so/
```

### 示例 8：保存 Prompt 用于调试

```bash
# 保存所有生成的 prompt 到 output/prompts/ 目录
python main.py --save-prompts --perf-data perf.data --so-dir so/
```

## 常见问题

### Q: 如何跳过某个步骤？

A: 使用 `--skip-step{N}` 参数：
- `--skip-step1`：跳过 perf.data 转换（如果已有 perf.db）
- `--skip-step3`：跳过 LLM 分析
- `--skip-step4`：跳过 HTML 符号替换

### Q: 批量分析的 batch_size 如何选择？

A: 根据 LLM context 限制（128K tokens）：
- **默认值**：3（稳定，避免 JSON 截断）
- **推荐值**：3-5（稳定，避免 JSON 截断）
- **最大值**：40-60（需要较小的函数）
- **说明**：batch_size 过大会导致 LLM 响应被截断，出现 JSON 解析错误

### Q: 如何强制使用 Capstone 而不是 Radare2？

A: 使用 `--use-capstone-only` 参数：
```bash
python main.py --use-capstone-only --perf-data perf.data --so-dir so/
```
注意：Capstone 模式性能较慢（约慢 1.7 倍），但更稳定，无需外部工具。

### Q: 为什么分析速度慢？

A: 主要耗时在 Radare2/Capstone 反汇编和反编译。优化建议：
1. 安装 Radare2（性能提升 10 倍+）
2. 确保 Radare2 实例缓存生效（看到 "♻️ 复用 radare2 分析器实例"）
3. 使用批量 LLM 分析（默认开启）
4. 使用 `--skip-decompilation` 跳过反编译（可显著提升速度）
5. 安装 r2dec 反编译插件（比 r2ghidra 快 2-5 倍）：`r2pm install r2dec`
6. 减少 `--top-n` 数量

### Q: r2dec 和 r2ghidra 有什么区别？

A: 
- **r2dec**：轻量快速（JavaScript），适合批量分析，反编译质量中等
- **r2ghidra**：高质量反编译（基于 Ghidra），但较慢（需要 Java），适合复杂函数
- 工具会自动按优先级选择：r2dec → r2ghidra → pdq
- 推荐安装 r2dec：`r2pm install r2dec`

### Q: 如何保存和调试生成的 prompt？

A: 使用 `--save-prompts` 选项：
```bash
python main.py --save-prompts --perf-data perf.data --so-dir so/
```
Prompt 文件会保存在 `{output_dir}/prompts/` 目录下，包含完整的 prompt 内容和元信息。

### Q: 如何清理缓存？

A: 删除 `cache/` 目录下的文件：
```bash
rm -rf cache/llm_analysis_cache.json cache/llm_token_stats.json
```

### Q: 代码依赖关系在哪里？

A: 请参考 `docs/CODE_DEPENDENCIES.md` 文档。

## 性能优化

### 1. Radare2 优化（已实现）
- 从 `aaa` 改为 `aa`：初始化时间减少 10-15 倍
- 实例缓存：同一 SO 文件复用实例，避免重复分析
- 优先使用 `aflj` 读取已有函数信息

### 2. 批量 LLM 分析（已实现）
- 减少 API 调用次数：10 个函数仅需 4 次调用（batch_size=3，默认）
- 总体性能提升：约 2-3 倍
- 支持禁用批量分析（`--no-batch`）进行逐个函数分析

### 3. 反编译优化
- **r2dec**：轻量快速，适合批量分析（推荐）
- **r2ghidra**：高质量但较慢，适合复杂函数
- **跳过反编译**：使用 `--skip-decompilation` 可进一步提升速度

### 4. 总体性能
- **原始版本**（使用 `aaa`，无缓存）：174 秒 / 5 个函数
- **优化版本**（使用 `aa` + 缓存 + 批量）：16 秒 / 5 个函数
- **性能提升**：约 10.7 倍
- **跳过反编译**：可再提升 20-30% 速度（但可能降低 LLM 分析质量）

## 许可证

本项目仅供学习和研究使用。

## 更新日志

### v4.4（当前版本）
- **性能分析功能**：新增性能瓶颈识别和优化建议功能
  - LLM prompt 中添加性能分析指导，重点关注高指令数负载的原因
  - 新增"负载问题识别与优化建议"列，与功能描述分开
  - 要求 LLM 分析性能瓶颈、高指令数负载原因和优化建议
- **上下文信息增强**：
  - 添加函数边界信息（起始/结束地址、大小）
  - 添加函数复杂度指标（基本块、控制流边、参数、局部变量）
  - 添加 SO 文件信息
  - 移除调用统计信息（call_count/event_count）从 prompt，仅用于排序
- **字符串提取改进**：
  - 添加字符串过滤功能，过滤错误消息和调试信息（如 "WeakRef: target must be an object"）
  - 改进调试日志，说明找不到字符串的原因
- **HTML 报告修复**：
  - 修复 load_excel_data_for_report 函数，正确加载 performance_analysis 字段
  - 添加 performance-analysis CSS 样式

### v4.3
- **Prompt 调试支持**：新增 `--save-prompts` 选项，可保存所有生成的 prompt 到文件
- **反编译优化**：新增 `--skip-decompilation` 选项，可跳过反编译以提升速度
- **反编译插件支持**：支持 r2dec/r2ghidra/pdq 多种反编译插件，自动按优先级选择
- **性能优化**：优化反编译流程，支持智能回退机制
- **文档完善**：更新 README，添加反编译组件说明和性能优化建议

### v4.2
- **LLM 配置集中化**：所有 LLM 配置集中到 `utils/config.py`，支持多种服务类型（poe/openai/claude/deepseek/custom）
- **服务切换**：通过环境变量 `LLM_SERVICE_TYPE` 轻松切换不同的 LLM 服务
- **DeepSeek 支持**：新增 DeepSeek API 支持，可通过 `LLM_SERVICE_TYPE=deepseek` 和 `DEEPSEEK_API_KEY` 使用
- **文件重命名**：`llm/utils.py` → `llm/initializer.py`，避免与 `utils/` 目录和 `__init__.py` 混淆
- **配置管理**：统一管理 API key 环境变量、Base URL、超时时间等配置

### v4.1
- **Capstone 模式**：添加 `--use-capstone-only` 参数，支持强制使用 Capstone
- **默认模型**：LLM 默认模型改为 GPT-5
- **批量大小**：默认 batch_size 调整为 3，更稳定
- **依赖更新**：更新 requirements.txt，明确核心和可选依赖
- **文档完善**：更新 README，添加 Capstone 模式说明和安装指南

### v4.0
- **目录重构**：模块化组织（analyzers/、llm/、utils/）
- **代码精简**：统一公共逻辑到 utils/，减少 700+ 行重复代码
- **性能优化**：Radare2 实例缓存，性能提升 10 倍+
- **批量优化**：batch_size 默认调整为 3，避免 JSON 截断
- **HTML 统一**：所有模式共用同一 HTML 模板
- **路径标准化**：数据、缓存、输出分离

### v3.0
- 统一输出目录，移除 reports 目录分离
- 移除 Step 2（逻辑已集成到 Step 3）
- 移除所有独立运行的 main() 函数，统一入口
- 添加 config.py 配置模块，集中管理所有默认值
- 添加 LLM 初始化工具，消除重复代码

### v2.0
- 添加 Excel 分析模式
- 添加精准字符串提取功能
- 添加批量 LLM 分析
- 添加时间统计功能

### v1.0
- 初始版本
