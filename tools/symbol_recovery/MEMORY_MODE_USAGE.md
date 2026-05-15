# 内存模式使用说明

## 概述

内存模式是符号恢复工具的新功能，用于从内存分析的火焰图 HTML 文件中提取符号地址并进行符号恢复。

## 功能特点

- **自动提取符号**: 从火焰图 HTML 文件中自动提取所有缺失的符号地址
- **批量处理**: 支持处理目录中的多个 HTML 文件
- **符号恢复**: 使用与 perf 模式相同的符号恢复流程
- **自动替换**: 自动将恢复的符号替换回原始 HTML 文件

## 使用方法

### 基本用法

```bash
python3 main.py --memory-mode --html-dir /path/to/flamegraphs --so-dir /path/to/so/directory
```

### 参数说明

- `--memory-mode`: 启用内存模式（必需）
- `--html-dir`: 火焰图 HTML 文件目录（必需）
- `--so-dir`: SO 文件目录（必需）
- `--output-dir`: 输出目录（可选，默认: `output/`）
- `--top-n`: 分析前 N 个函数（可选，默认: 100）
- `--stat-method`: 统计方式，`event_count` 或 `call_count`（可选，默认: `event_count`）
- `--no-llm`: 不使用 LLM 分析（可选）
- `--batch-size`: 批量分析大小（可选，默认: 3）
- `--use-capstone-only`: 只使用 Capstone 反汇编（可选）
- `--skip-decompilation`: 跳过反编译（可选）
- `--open-source-lib`: 指定开源库名称（可选，如 `ffmpeg`, `openssl` 等）

### 完整示例

```bash
# 基本使用
python3 main.py --memory-mode \
    --html-dir /path/to/memory/flamegraphs \
    --so-dir /path/to/so/files

# 指定分析数量
python3 main.py --memory-mode \
    --html-dir /path/to/memory/flamegraphs \
    --so-dir /path/to/so/files \
    --top-n 200

# 不使用 LLM（仅反汇编）
python3 main.py --memory-mode \
    --html-dir /path/to/memory/flamegraphs \
    --so-dir /path/to/so/files \
    --no-llm

# 指定开源库（提高 LLM 分析准确性）
python3 main.py --memory-mode \
    --html-dir /path/to/memory/flamegraphs \
    --so-dir /path/to/so/files \
    --open-source-lib ffmpeg
```

## 工作流程

1. **提取符号地址**
   - 扫描 HTML 目录中的所有 `.html` 文件
   - 从每个 HTML 文件中提取 JSON 数据（支持 base64 + gzip/zlib 压缩）
   - 从 JSON 数据中提取所有符号地址（格式: `libxxx.so+0x1234`）

2. **创建 perf.db**
   - 将所有提取的符号地址合并
   - 创建类似 perf.db 的 SQLite 数据库

3. **符号恢复分析**
   - 使用与 perf 模式相同的分析流程
   - 反汇编、提取字符串、LLM 分析等

4. **替换符号**
   - 将恢复的符号替换回原始 HTML 文件
   - 输出到 `output/memory_flamegraphs_recovered/` 目录

## 输入要求

### HTML 文件格式

HTML 文件应包含火焰图数据，通常有以下格式：

```html
<script id="record_data" type="application/gzip+json;base64">
<!-- base64 编码的压缩 JSON 数据 -->
</script>
```

或

```html
<script id="record_bz_data" type="application/gzip+json;base64">
<!-- base64 编码的压缩 JSON 数据 -->
</script>
```

### JSON 数据格式

JSON 数据中应包含符号信息，符号地址格式为：
- `libxxx.so+0x1234`
- 可能出现在 `symbol` 字段或 `f` 字段中

## 输出文件

- `memory_flamegraph_perf.db`: 从 HTML 文件提取的符号数据库
- `event_count_top{N}_analysis.xlsx`: 符号分析结果（Excel 格式）
- `event_count_top{N}_report.html`: 符号分析报告（HTML 格式）
- `memory_flamegraphs_recovered/*.html`: 替换了符号的火焰图 HTML 文件

## 注意事项

1. **HTML 文件格式**: 确保 HTML 文件包含正确的火焰图数据格式
2. **SO 文件**: 确保 SO 文件目录包含所有需要的 SO 库文件
3. **符号格式**: 符号地址必须是 `libxxx.so+0x1234` 格式
4. **文件数量**: 支持处理多个 HTML 文件，会自动合并所有符号

## 与 perf 模式的区别

| 特性 | perf 模式 | 内存模式 |
|------|-----------|----------|
| 输入 | perf.data | 火焰图 HTML 文件 |
| 符号提取 | 从 perf.db | 从 HTML JSON 数据 |
| 统计信息 | 有（调用次数、指令数） | 无（仅提取地址） |
| 输出 | 替换单个 HTML | 替换多个 HTML |

## 故障排除

### 问题：未找到符号地址

**可能原因**:
- HTML 文件格式不正确
- JSON 数据未正确解压缩
- 符号格式不匹配

**解决方法**:
- 检查 HTML 文件是否包含 `<script id="record_data">` 标签
- 检查 JSON 数据是否包含符号地址
- 确认符号格式为 `libxxx.so+0x1234`

### 问题：SO 文件找不到

**可能原因**:
- SO 文件目录路径错误
- SO 文件名不匹配

**解决方法**:
- 确认 `--so-dir` 路径正确
- 检查 SO 文件名是否与符号中的库名匹配

### 问题：LLM 分析失败

**可能原因**:
- API Key 未配置
- 网络问题
- 模型不可用

**解决方法**:
- 配置 `.env` 文件中的 API Key
- 使用 `--no-llm` 跳过 LLM 分析
- 检查网络连接

## 示例场景

### 场景 1: 分析内存泄漏火焰图

```bash
python3 main.py --memory-mode \
    --html-dir ./memory_leak_flamegraphs \
    --so-dir ./app/libs \
    --top-n 50
```

### 场景 2: 批量处理多个内存分析报告

```bash
python3 main.py --memory-mode \
    --html-dir ./memory_analysis_reports \
    --so-dir ./app/libs \
    --top-n 100 \
    --stat-method event_count
```

## 相关文档

- [主 README](README.md)
- [分析流程说明](ANALYSIS_FLOW.md)

