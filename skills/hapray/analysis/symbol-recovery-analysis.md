# 符号恢复辅助问题定位方法文档

> 适用场景：在 HapRay 性能报告或 `perf.data` 中发现大量 `libxxx.so+0xXXXXX` 格式的
> 缺失符号（stripped SO 文件），通过 SymRecover 工具恢复函数名并辅助定位性能瓶颈。

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

**强烈推荐安装（性能提升 10 倍+）：**

```bash
brew install radare2          # macOS
r2pm install r2dec            # 反编译插件（轻量快速，推荐优先）
# r2pm install r2ghidra       # 更高质量，需 Java，复杂函数可选
```

### 2.3 配置 LLM API Key

复制 `.env.example` 为 `.env`，填入 API Key（以 DeepSeek 为例）：

```
LLM_SERVICE_TYPE=deepseek
DEEPSEEK_API_KEY=your_key
```

支持的服务类型：`poe`（默认）、`openai`、`claude`、`deepseek`、`custom`。

> **不配置 LLM 也可使用**：加 `--no-llm` 只做反汇编分析（无功能推断）。

---

## 三、分析步骤

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
