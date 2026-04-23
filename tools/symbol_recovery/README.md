# SymRecover - 二进制符号恢复工具

从已剥离符号表的 SO 文件中恢复函数名，通过反汇编（Radare2/Capstone）和 LLM 推理推断函数功能。

## 四种运行模式

### 1. Perf 模式（默认）

从 `perf.data` 性能采样数据中提取缺失符号并恢复。

```bash
# 基本用法
python3 main.py --perf-data perf.data --so-dir /path/to/so/

# 指定输出目录（--output 是 --output-dir 的别名）
python3 main.py --perf-data perf.data --so-dir so/ --output /data/my_result/

# 常用选项
python3 main.py --perf-data perf.data --so-dir so/ --top-n 50 --stat-method call_count
python3 main.py --skip-step1   # 已有 perf.db 时跳过转换
python3 main.py --only-step4 --html-input report.html  # 只做符号替换
```

流程：`perf.data` → Step 1: 转换为 `perf.db` → Step 3: LLM 分析 → Step 4: HTML 符号替换

### 2. Excel 模式

从 Excel 文件读取函数偏移量地址，对 SO 文件进行反汇编和分析。

```bash
# 单 SO
python3 main.py --excel-file offsets.xlsx --so-file /path/to/lib.so

# 多 SO（Excel 中含 SO 文件名列，自动分组）
python3 main.py --excel-file offsets.xlsx --so-dir /path/to/so/

# 不使用 LLM
python3 main.py --excel-file offsets.xlsx --so-file lib.so --no-llm

# 离线编排：只导出 prompt 任务（不调用本地 API）
python3 main.py --excel-file offsets.xlsx --so-file lib.so --prompt-only

# 导入外部 LLM 结果并回填报告
python3 main.py --excel-file offsets.xlsx --so-file lib.so \
  --import-llm-results output/symbol_recovery_external_results.json
```

### 3. KMP 模式

针对 stripped Kotlin Multiplatform `.so` 文件，在恢复符号名的同时对函数按 KMP 组件分类。

```bash
# 通用模式（业务分类标签为 "Business Logic"）
python3 main.py --kmp-mode --perf-db perf.db --so-file lib.so --top-n 50

# 指定应用名（业务标签为 "Business (AppName)"）
python3 main.py --kmp-mode --perf-db perf.db --so-file lib.so --kmp-app-name MyApp

# 附加命名空间上下文（分类最准确）
python3 main.py --kmp-mode --perf-db perf.db --so-file lib.so \
    --kmp-app-name MyApp \
    --context "libexample.so 是目标应用的KMP核心库，业务命名空间包含 kfun:com.example.*"
```

KMP 分类列输出：`KMP Runtime` / `androidx.compose.*` / `Business (AppName)` / `Skia/Skiko` / `Other`

> KMP 模式强制使用 inclusive 口径（Total 列），与 perf 模式的 exclusive 口径不同。

### 4. 内存模式

从内存分析火焰图 HTML 文件中提取符号地址并恢复，支持批量处理多个 HTML 文件。

```bash
python3 main.py --memory-mode --html-dir /path/to/flamegraphs/ --so-dir /path/to/so/
```

输入 HTML 需包含 base64+gzip 编码的火焰图 JSON 数据（符号格式：`libxxx.so+0x1234`）。

---

## 安装

```bash
uv venv .venv
uv pip install --python ./.venv/bin/python -e .
```

**可选但推荐：**
- **Radare2**（性能提升 10 倍+）：`brew install radare2` 或 `apt-get install radare2`
- **反编译插件**：`r2pm install r2dec`（轻量）或 `r2pm install r2ghidra`（高质量，需 Java）

## 配置 LLM

在项目根目录创建 `.env` 文件，通过 `LLM_SERVICE_TYPE` 选择服务：

| 服务 | 环境变量 |
|------|---------|
| `poe`（默认） | `POE_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `claude` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `custom` | `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` |

## 离线编排模式（无需本地 API Key）

不想在本机配置 API Key，或希望由外部 LLM（如主 Agent）负责推断时，可使用两步离线编排：

### 第一步：导出 LLM 任务

```bash
python3 main.py \
    --perf-data perf.data --so-dir so/ \
    --top-n 50 --output-dir output/ \
    --prompt-only
# 输出：output/symbol_recovery_llm_tasks.json
```

- 完成反汇编 + 字符串提取，**不调用任何 LLM**，不读取 `.env`
- 产出 `symbol_recovery_llm_tasks.json`，每条任务包含：

```json
{
  "function_id": "func_1",
  "rank": 1,
  "address": "libxxx.so+0x12b8b0",
  "offset": "0x12b8b0",
  "so_file": "libxxx.so",
  "instruction_count": 500,
  "prompt": "请分析以下 ARM64 反汇编函数……（含反汇编代码、字符串常量、反编译代码）",
  "expected_schema": {
    "functionality": "str",
    "function_name": "str|null",
    "performance_analysis": "str",
    "confidence": "高|中|低",
    "reasoning": "str"
  }
}
```

### 第二步：外部 LLM 处理，生成结果 JSON

外部 LLM（主 Agent、批量 API、人工标注等）读取每条任务的 `prompt` 字段，按 `expected_schema` 返回结果，保存为：

```json
[
  {
    "function_id": "func_1",
    "functionality": "AES T-table 加密轮变换，通过四张 256 项查找表……",
    "function_name": "aes_encrypt_round",
    "performance_analysis": "计算热点，建议评估 ARMv8 硬件 AES 加速……",
    "confidence": "高",
    "reasoning": "四路字节查表 + EOR 累加是 AES T-table 的强指纹"
  }
]
```

匹配键优先级：`function_id`（`func_<rank>`）> `rank` > `address`（三者任一均可）。  
字段同义词：`functionality`/`description`、`function_name`/`inferred_name` 均被接受。  
顶层格式：裸数组 `[...]` 或 `{"functions":[...]}` / `{"results":[...]}` / `{"tasks":[...]}` 均可。

### 第三步：回填并生成报告

```bash
python3 main.py \
    --perf-data perf.data --so-dir so/ \
    --top-n 50 --output-dir output/ \
    --skip-step1 --perf-db output/perf.db \
    --import-llm-results /path/to/results.json
# 输出：Excel 报告（含函数名、功能描述）+ HTML 符号替换报告
```

- `--skip-step1 --perf-db output/perf.db`：复用第一步已生成的 perf.db，跳过 perf.data 重转换
- `--import-llm-results` 自动设置 `--no-llm`，全程不调用本地 LLM
- 回填后生成与在线模式完全相同的 Excel / HTML 产物，`hapray-tool-result.json` 中含 `import_applied` / `import_unmatched` 计数

> **Excel 模式**同样支持两步离线编排，替换 `--perf-data`/`--so-dir` 为 `--excel-file`/`--so-file`（或 `--so-dir`）；**KMP 模式**同样支持，替换为 `--kmp-mode --perf-db ... --so-file ...`。第二次调用均无需 `--skip-step1`。

## 主要参数

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--top-n` | 分析前 N 个函数 | `100` |
| `--output-dir`（别名 `--output`） | 输出目录，所有分析结果、JSON 契约文件均写入此处 | `output/`（可选） |
| `--no-llm` | 仅反汇编，不调用 LLM | `False` |
| `--batch-size` | 每个 prompt 包含的函数数（>1 时启用批量分析） | 按服务自动选择 |
| `--use-capstone-only` | 强制使用 Capstone，不使用 Radare2 | `False` |
| `--skip-decompilation` | 跳过反编译，提升速度 | `False` |
| `--save-prompts` | 保存生成的 prompt 到文件（调试用） | `False` |
| `--prompt-only` | 仅导出 LLM 任务（prompt），不直接调用模型 | `False` |
| `--import-llm-results PATH` | 导入外部 LLM 结果 JSON 并回填分析报告 | 可选 |
| `--open-source-lib` | 指定开源库（如 `ffmpeg`），提升 LLM 推断准确性 | 可选 |
| `--context` | 自定义上下文信息 | 自动推断 |
| `--llm-model` | LLM 模型名称 | 按服务默认 |

### perf 模式参数

| 参数 | 说明 |
|------|------|
| `--perf-data` | perf.data 文件路径（默认 `perf.data`） |
| `--perf-db` | perf.db 文件路径（默认自动生成） |
| `--so-dir` | SO 文件目录 |
| `--so-file` | 单个 SO 文件路径 |
| `--stat-method` | `event_count`（默认）或 `call_count` |
| `--skip-step1/3/4` | 跳过对应步骤 |
| `--only-step1/3/4` | 只执行对应步骤 |
| `--html-input` | HTML 输入文件路径（Step 4 用） |

### KMP 模式参数

| 参数 | 说明 |
|------|------|
| `--kmp-mode` | 启用 KMP 模式 |
| `--kmp-app-name` | 应用名，生成 `Business (AppName)` 分类标签 |
| `--perf-db` | perf.db 文件路径（必需） |
| `--so-file` | KMP .so 文件路径（必需） |

### 内存模式参数

| 参数 | 说明 |
|------|------|
| `--memory-mode` | 启用内存模式 |
| `--html-dir` | 火焰图 HTML 文件目录（必需） |
| `--so-dir` | SO 文件目录（必需） |

### 工具契约参数

| 参数 | 说明 |
|------|------|
| `--result-file PATH` | 将 `hapray-tool-result.json` 写入该路径（默认 `<output-dir>/hapray-tool-result.json`） |
| `--machine-json` | 契约文件无法写入时，在 stdout 输出一行 JSON |

## 输出文件

**perf / KMP / 内存模式**（位于 `{output_dir}/`）：
- `perf.db` — SQLite 数据库（Step 1）
- `event_count_top{N}_analysis.xlsx` — 分析结果
- `event_count_top{N}_report.html` — HTML 报告
- `hiperf_report_with_inferred_symbols.html` — 替换符号后的 HTML（Step 4）

**Excel 模式**（位于 `output/`）：
- `excel_offset_analysis_{n}_functions.xlsx`
- `excel_offset_analysis_{n}_functions_report.html`

**缓存**（`cache/`）：
- `llm_analysis_cache.json` — LLM 结果缓存
- `llm_token_stats.json` — Token 用量统计

**离线编排辅助文件**（位于 `{output_dir}/`）：
- `symbol_recovery_llm_tasks.json` — 待外部模型处理的任务（含 function_id、prompt、地址元数据）

## 常见问题

**Q: 分析速度慢？**
1. 安装 Radare2（性能提升 10 倍+）
2. 使用 `--skip-decompilation`（速度提升 20-30%）
3. 安装 `r2dec`（比 r2ghidra 快 2-5 倍）
4. 减少 `--top-n`

**Q: batch-size 如何选择？**
推荐 3-10，过大会导致 LLM 响应截断。未指定时按服务自动选择（claude=10, openai=5, deepseek/poe=3）。

**Q: 如何清理缓存？**
```bash
rm -rf cache/llm_analysis_cache.json cache/llm_token_stats.json
```

## 相关文档

- [ANALYSIS_FLOW.md](ANALYSIS_FLOW.md) — 详细分析流程
- [MEMORY_MODE_USAGE.md](MEMORY_MODE_USAGE.md) — 内存模式说明
