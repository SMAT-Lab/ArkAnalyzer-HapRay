## 特性清单

> 本文档根据代码自动整理生成，用于统一查看各特性的能力、入口与输入输出。


### 特性清单
| 大类   | 小类      | 特性                                                                | 描述                                                                                    | 输入                                                              | 输出                                                          |
| ---- | ------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------- |
| GUI  | 桌面工具    | [桌面 GUI 应用](#feature-desktop-tool)                                | 桌面端（Tauri+Vue）提供统一工具运行平台，通过插件机制加载不同 CLI 工具并记录执行历史，在 UI 中回看参数与结果。                      | 插件元数据、用户选择工具与参数、ExecutionRecord                                 | ToolWorkspace 运行状态、HistorySidebar 历史清单、持久化记录                |
| 静态分析 | 软件成份分析  | [HAP/HSP 技术栈分析](#feature-hap-zip-static)                          | 对单个 HAP/HSP/ZIP 文件或应用包目录以及包含多个应用包目录的根目录进行静态分析与批量扫描，识别技术栈并生成 JSON/HTML/Excel 报告及多应用汇总。 | `-i` 输入路径 `.hap/.hsp/.zip` 文件                         | JSON/HTML/Excel 报告、`summary_*.xlsx` 汇总                      |
| 静态分析 | so编译优化  | [SO 编译优化级别与 LTO 检测（opt-detector）](#feature-optimization-detector) | 对 SO/AR/HAP/HSP/APK/HAR 等二进制或其目录进行批量扫描，识别编译优化级别、LTO 启用情况及优化质量评分。                      | `--input` `SO/AR/HAP/HSP/APK/HAR`文件路径                               | Excel/JSON/CSV/XML 优化检测报告                                   |
| 静态分析 | 符号恢复    | [ELF so 调用符号分析（elf 子命令）](#feature-elf-analysis)                   | 对单个 so 文件结合性能报告目录，分析其调用符号并生成 JSON 输出，用于性能诊断或与负载数据交叉分析。                                | `-i` so 路径、`-r` 报告目录、`-o` 输出 JSON                               | so 符号分析 JSON                                                |
| 静态分析 | 符号恢复    | [符号恢复与函数语义分析（symbol-recovery）](#feature-symbol-recovery)          | 基于 perf.data 或 Excel 偏移量，对 SO 库中缺失符号的函数进行符号恢复与语义分析，并可回填 HTML 报告。                      | `--perf-data`/`--excel-file`、`--so-dir`、`--top-n`               | perf.db、`*_analysis.xlsx`、`*_report.html`、hiperf HTML       |
| 动态分析 | 自动化测试   | [测试准备执行（perf_testing prepare）](#feature-perf-testing-prepare)     | 面向预埋性能场景的一键回归，在已有 hapray 测试用例集上，按指定模式或自动筛选 `_0000` 结尾用例，在真实设备上依次执行性能/内存等测试。           | `--run_testcases`、`--all_0000`、`--device`、hdc/node              | 用例输出目录（hiperf/htrace）、执行统计                                  |
| 动态分析 | 自动化测试   | [GUI Agent 自动化（perf_testing gui-agent）](#feature-gui-agent)       | 基于 LLM 的 AI 手机自动化，支持自然语言描述场景在真机上执行，采集 perf/trace/内存数据并生成报告。                           | `--apps` 包名、`--scenes` 场景描述、`-o` 输出、LLM 配置                      | `output/reports/<timestamp>` 步骤数据与报告                        |
| 动态分析 | 自动化测试   | [自动化性能测试（perf_testing perf）](#feature-perf-action)                | 多设备并行执行性能测试用例，支持多轮次、手动模式、HapFlow、UI 技术栈识别等，生成汇总 Excel。                                | `--run_testcases`、`--round`、`--devices`、`--so_dir`              | `reports/<timestamp>` 报告目录、汇总 Excel                         |
| 动态分析 | 自动化测试   | [HapTest 策略驱动 UI 自动化（perf_testing haptest）](#feature-haptest)     | 无需预埋用例，按深度优先/广度优先/随机等策略自动探索应用 UI，采集 perf/trace/内存数据并生成报告。                             | `--app-package`、`--app-name`、`--strategy`、`--max-steps`         | `reports/haptest_<app>_<ts>`、hapray_report.html             |
| 动态分析 | 数据分析    | [覆盖率报告触发（CovAnalyzer）](#feature-cov-analyzer)                     | 在场景分析阶段检测 bjc_cov.json，若存在则调用 hapray bjc 生成覆盖率报告，将性能报告与覆盖率打通。                         | 每步 `perf.db` 目录中的 `bjc_cov.json`、`Config.cov.hapProjectPath`    | bjc 覆盖率报告（写到 perf.db 目录）                                    |
| 动态分析 | 数据分析    | [白盒负载拆解（hapray-sa-cmd perf）](#feature-perf-scene-load)            | 对性能测试场景目录进行联合分析（多步骤）或单步 db 文件分析，生成步骤级性能 JSON 报告及 summary 信息，用于 Web 端可视化负载分析。          | `-i` 场景路径或 db、`--choose`、`--time-ranges`、perf.data/trace.htrace | `report/` 性能 JSON、`hiperf_info.json`、`summary_info.json`    |
| 动态分析 | 数据分析    | [轮次选择与最优轮次判定](#feature-round-selection)                           | 在多轮次测试数据下，对多个轮次的同一步骤进行分析，计算负载总值并自动选择最优轮次，复制其数据用于后续报告。                                 | 多轮次场景目录、perf.data/trace.htrace/db                               | RoundInfo、拷贝后的 testInfo.json、steps.json、result              |
| 动态分析 | 数据分析    | [单版本故障树分析](#feature-single-step-fault-tree)                       | 基于性能数据构建步骤级故障树，展示潜在性能问题的层级结构和归因路径。                                                    | perf 场景 JSON 故障树数据、步骤 ID、`perf.db` 与 `trace.db` 的 DB 查询 | 故障树视图、节点权重统计                                                |
| 动态分析 | 数据分析    | [组件复用率分析（ComponentReusableAnalyzer）](#feature-component-reuse)    | 基于 trace.db 中的组件构建/回收调用，统计构建次数与复用率，帮助发现复用不足的 UI 组件。                                   | `trace.db`、callstack 表、app_pids                                 | `trace/componentReuse` JSON、复用指标字典                          |
| 动态分析 | 数据分析    | [性能火焰图与场景 Perf 分析（PerfAnalyzer）](#feature-perf-analyzer)          | 对每个步骤的 perf.db 生成 hiperf 火焰图报告，并在 step1 调用 hapray perf 完成场景级 Perf 分析。                 | scene_dir、perf.db、trace.db、time_ranges                          | perf.json、hiperf_report.html、report 目录 perf JSON            |
| 动态分析 | 数据分析    | [内存分配与泄漏分析（MemoryAnalyzer）](#feature-memory-analyzer)             | 对 hiperf 内存采样与 meminfo 数据进行聚合与精简存储，构建多张内存分析表用于前端展示与对比导出。                              | scene_dir、perf.db/trace.db                                      | hapray_report.db 内存表、refined Excel、summary JSON             |
| 动态分析 | 数据分析    | [统一帧分析（UnifiedFrameAnalyzer）](#feature-unified-frame)             | 统一完成帧负载、空帧、卡顿帧、VSync 异常以及 RS Skip 分析，输出多个帧相关 JSON。                                    | trace.db、perf.db、app_pids                                       | trace_frameLoads/emptyFrame/frames/vsyncAnomaly/rsSkip JSON |
| 动态分析 | 数据分析    | [冷启动冗余文件分析（ColdStartAnalyzer）](#feature-cold-start)               | 基于 redundant_file.txt 统计冷启动阶段访问文件的使用/未使用情况及耗时 Top10，帮助优化启动时间。                         | redundant_file.txt、scene_dir                                    | trace/coldStart JSON、Summary、Top10 列表                       |
| 动态分析 | 数据分析    | [GC 负载与频率分析（GCAnalyzer）](#feature-gc)                             | 分析 GC 线程事件和 GC 运行次数，计算 GC 负载占比和各类 GC 调用频次，用于识别 GC 过于频繁或过重的场景。                         | trace.db、perf.db、app_pids                                       | trace/gc_thread JSON、GC 次数与占比                               |
| 动态分析 | 数据分析    | [故障树指标分析（FaultTreeAnalyzer）](#feature-fault-tree-analyzer)        | 从 trace/perf 中抽取 ArkUI、RS、av_codec、Audio、IPC Binder 等多维度指标，构建前端故障树视图所需数据。             | trace.db、perf 表、app_pids                                        | trace/fault_tree JSON、指标字典                                  |
| 动态分析 | 数据分析    | [UI 动画与页面结构分析（UIAnalyzer）](#feature-ui-analyzer)                  | 基于 UI 采集目录中的页面结构和截图，分析 CanvasNode、图片资源和页面差异，识别 UI 动画区域并生成标记截图。                        | pages.json、element_tree、screenshot、rs_tree                      | ui/animate JSON、canvasNodeCnt、animations、标记截图               |
| 动态分析 | 数据分析    | [IPC Binder 事务分析（IpcBinderAnalyzer）](#feature-ipc-binder)         | 从 trace.db 中提取 binder 相关调用并自动配对请求/响应，按进程对、线程对和接口维度统计调用次数与耗时。                          | trace.db process/thread/callstack、app_pids                      | trace/ipc_binder JSON、process/thread/interface 统计           |
| 动态分析 | 数据分析    | [冗余线程与唤醒链分析（ThreadAnalyzer）](#feature-thread-analyzer)            | 结合唤醒链与线程负载识别冗余线程模式，量化冗余指令数和内存占用，输出可排序的冗余线程列表。                                         | trace.db、perf.db、app_pids                                       | redundant_thread_analysis.json、冗余线程清单                       |
| 报告生成 | 覆盖率报告   | [覆盖率报告生成（bjc 子命令）](#feature-bjc-coverage)                         | 基于 bjc 库对 HAP 工程生成代码覆盖率报告，用于评估测试覆盖情况。                                                 | `-i` HAP 文件、`-o` 输出目录、`--project-path`                          | 覆盖率报告文件                                                     |
| 报告生成 | 场景报告    | [场景报告/HTML 导入与本地 DB 初始化](#feature-import-html-db)                 | 从用户上传的场景报告或本地目录解析数据，将 perf/内存/日志等信息写入浏览器端数据库，供 Web 前端查询分析。                            | HTML 报告/压缩包、本地场景目录                                              | IndexedDB 表、jsonDataStore、导入统计                              |
| 报告生成 | 场景报告    | [单版本场景负载总览](#feature-single-scene-overview)                       | 在 Web 端对单个性能场景的所有步骤进行汇总展示，包括各步骤指令数、耗能等指标分布。                                           | perfData.steps、#/overview                                       | 步骤总览图表、指标卡片、跳转链接                                            |
| 报告生成 | 场景报告    | [单版本步骤负载分析](#feature-single-step-load)                            | 针对单个步骤进行线程/进程/文件/符号维度的负载分析，展示热点线程和函数。                                                 | steps[stepIndex]、DB 查询、step-id                                  | PerfThread/Process/File/SymbolTable、趋势图                     |
| 报告生成 | 场景报告    | [单版本帧率与渲染分析](#feature-single-step-frame)                          | 针对单个步骤的 UI 帧数据进行分析，展示帧率、卡顿和渲染耗时。                                                      | perfData、frame_step_                                            | 帧时间线、FPS、掉帧数                                                |
| 报告生成 | 场景报告    | [火焰图分析](#feature-flame-graph)                                     | 通过火焰图可视化负载热点与调用栈，支持按步骤查看调用路径和消耗。                                                      | 火焰图 JSON、flame_step_                                            | 交互式火焰图、热点统计                                                 |
| 报告生成 | 场景报告    | [内存分析](#feature-memory)                                           | 对步骤级内存数据进行分析，包括 meminfo 时间线、Native Memory 列表和 outstanding 分析。                         | DB queryMemoryMeminfo/Results、memory_step_                      | 内存时间线图、Native Memory 列表、outstanding 火焰图                     |
| 报告生成 | 场景报告    | [UI 动画与 UI 性能分析](#feature-ui-animate)                             | 对 UI 动画和界面切换进行分析，展示每个步骤的 UI 动画数据和页面对比，并支持版本间 UI 差异对比。                                 | uiAnimateData、uiCompareData、ui_animate_step_                    | UI 动画视图、多版本对比视图                                             |
| 报告生成 | 场景报告    | [日志分析（HilogAnalysis）](#feature-hilog)                             | 基于 Hilog 日志与性能步骤的关联，展示按步骤切分的日志内容和统计信息。                                                | summary.log、hilog_step_                                         | 按步骤日志列表、错误率统计                                               |
| 报告生成 | 场景报告    | [版本对比分析](#feature-version-compare)                                | 对不同版本的性能结果进行对比分析，包括场景负载、步骤负载、详细数据、新增数据、Top10 热点以及故障树/UI 多维度比对。                        | comparePerfData、uiCompareData、/compare                          | 负载曲线、单步差异、Top10、故障树/UI 对比                                   |
| 报告生成 | 场景报告    | [多版本趋势分析（PerfMulti）](#feature-perf-multi)                         | 从多版本 perf 数据中提取关键指标，生成趋势图展示性能随版本演进的变化。                                                | 多版本 perfData、/perf_multi                                        | 趋势曲线、对比柱状图、版本标注                                             |
| 报告生成 | 报告更新与对比 | [报告更新与重算（perf_testing update）](#feature-perf-testing-update)      | 针对已有 hapray 场景结果目录做离线重算，根据最新规则/配置对多个用例报告进行批量更新并生成汇总 Excel。                            | `--report_dir`、`--so_dir`、`--mode`、`--time-ranges`              | 更新后报告、汇总 Excel、refined comparison Excel                     |
| 报告生成 | 报告更新与对比 | [报告目录对比分析（perf_testing compare）](#feature-perf-testing-compare)   | 对两个 hapray 报告目录进行场景/步骤维度的性能对比，导出对比 Excel，支撑性能回归与审计。                                   | `--base_dir`、`--compare_dir`、`--output`、summary_info.json       | compare_result.xlsx、base/compare/percent 列                  |


<a id="feature-desktop-tool"></a>

### 桌面 GUI 应用

- **描述**：桌面端（Tauri+Vue）提供统一工具运行平台，通过插件机制加载不同 CLI 工具并记录执行历史，在 UI 中回看参数与结果。
- **入口**：
  - `desktop/src/App.vue`
  - `desktop/src/components/Sidebar.vue`
  - `desktop/src/components/ToolWorkspace.vue`
  - `desktop/src/components/HistorySidebar.vue`
  - `desktop/src/components/HistoryView.vue`
  - `desktop/src/composables/usePlugins.ts#usePlugins`
  - `desktop/src-tauri/src/cli.rs`
- **输入**：
  - 插件元数据（`pluginId/action/参数定义` 等）
  - 用户侧边栏选择工具和 action 并填写参数
  - `ExecutionRecord`（参数/执行时间/状态/输出路径）
  - Tauri 命令与本地 CLI 工具
- **输出**：
  - `ToolWorkspace` 中的运行状态与结果摘要
  - `HistorySidebar` 中的历史记录清单
  - `HistoryView` 中的执行详情
  - 本地持久化的历史记录文件或存储
- **备注**：偏平台和运维工具层，可扩展接入更多命令行工具，对具体分析算法有一定解耦。

<a id="feature-hap-zip-static"></a>

### HAP/HSP 技术栈分析

- **描述**：对单个 HAP/HSP/ZIP 文件或应用包目录进行静态分析，并支持对包含多个应用包目录的根目录进行批量扫描，识别技术栈、文件类型、依赖及导出符号，生成 JSON/HTML/Excel 报告及多应用汇总。
- **入口**：
  - `tools/static_analyzer/src/cli/commands/hap_analyzer_cli.ts#HapAnalyzerCli`
  - `tools/static_analyzer/src/services/analysis/hap_analysis.ts#HapAnalysisService.analyzeMultipleHaps`
  - CLI：`hapray-sa-cmd hapray hap -i <path>`
  - CLI：`hapray-sa-cmd hapray hap --help`
- **输入**：
  - CLI 参数：`-i/--input` 分析输入路径（HAP/ZIP 文件或目录，支持单应用或多应用根目录）
  - CLI 参数：`-o/--output` 输出目录，默认 `./output`
  - CLI 参数：`-j/--jobs` 并发分析数量，默认为 CPU 核心数
  - CLI 参数：`--beautify-js` 美化压缩的 JS 文件并保存到输出目录
  - 输入路径下的 `.hap/.hsp/.zip` 文件及应用包目录
  - 多应用时：根目录下符合 `name@version` 模式的子目录
  - `DetectorEngine` 技术栈检测规则、`ZipUtils.scanZipWithNestedSupport` 解析 ZIP、`Hap.loadFromHap` 解析 HAP 元信息
- **输出**：
  - 单应用/单包输出：
    - 输出目录下按文件/应用包划分的 JSON 报告
    - 输出目录下对应的 HTML 报告
    - 输出目录下对应的 Excel 报告（含应用汇总、技术栈详情、技术栈分析、Dart 开源库表）
    - 控制台日志中的分析进度和统计信息
    - `HapFileError`/`ZipParsingError`/`AnalysisError` 等错误信息
  - 多应用批量输出：
    - 每个应用目录下的 JSON/HTML/Excel 技术栈报告
    - 根输出目录下 `summary_*.xlsx` 汇总 Excel（应用汇总、技术栈详情、技术栈分析、Dart 开源库四个 sheet）
    - 各技术栈的应用/文件数量统计及 Top10 排名
    - 控制台日志中的应用处理结果与失败列表
- **备注**：
  - 与 `DetectorEngine`、技术栈匹配规则和 Excel 报告格式强耦合，支持按应用包目录聚合多 HAP 结果并输出汇总报表。
  - 优先识别 `entry.hap` 或 `entry` 模块作为主应用包，集成 Dart/Flutter 开源库统计。

<a id="feature-optimization-detector"></a>

### SO 编译优化级别与 LTO 检测（opt-detector）

- **描述**：对 SO/AR/HAP/HSP/APK/HAR 等二进制或其目录进行批量扫描，基于模型推理识别每个文件的编译优化级别（O0~Os）、是否启用 LTO 以及整体优化质量评分，输出可用于质量审计与性能优化追踪的报表。
- **入口**：
  - `tools/optimization_detector/cli.py#OptAction.execute`
  - CLI：`opt-detector`
- **输入**：
  - 命令行参数：`--input/-i`（二进制文件或目录，支持 `.so/.a/.hap/.hsp/.apk/.har`）
  - `--output/-o`（输出文件路径，支持 `xlsx/json/csv/xml`）
  - `--format/-f`（输出格式列表，可多选）
  - `--jobs/-j`（并行任务数）
  - `--timeout/-t`（单文件分析超时秒数）
  - `--no-lto`/`--no-opt`（关闭对应检测）
  - `--verbose`/`--log-file`（日志控制）
  - 内部依赖：`FileCollector.collect_binary_files`、`OptimizationDetector.detect_optimization`、TensorFlow 模型与 LTO 特征配置
- **输出**：
  - 一个或多个按文件维度汇总的优化检测报告（默认 Excel，可选 JSON/CSV/XML）
  - 控制台日志（扫描进度、错误信息）
  - 可选日志文件
- **备注**：适合作为编译质量/性能基线检查工具，可与 hapray 输出的 so 列表结合，用于发现未开启优化或未启用 LTO 的热点库。

<a id="feature-elf-analysis"></a>

### ELF so 调用符号分析（elf 子命令）

- **描述**：对单个 so 文件结合性能报告目录，分析其调用符号并生成 JSON 输出，用于性能诊断或与负载数据交叉分析。
- **入口**：
  - `tools/static_analyzer/src/cli/commands/elf_analyzer_cli.ts#ElfAnalyzerCli`
  - `tools/static_analyzer/src/core/elf/elf_analyzer.ts#ElfAnalyzer.getInstance`
  - CLI：`hapray-sa-cmd hapray elf`
- **输入**：
  - CLI：`-i/--input` so 文件路径
  - `-r/--report_dir` 报告目录
  - `-o/--output` 输出 JSON 路径
  - 报告目录下的元数据和符号信息
- **输出**：
  - 指定路径下的 so 符号分析 JSON 文件
  - 输入检查和错误日志信息
- **备注**：专注于 so 的符号级分析，结果可与 perf 场景分析联用。

<a id="feature-symbol-recovery"></a>

### 符号恢复与函数语义分析（symbol-recovery）

- **描述**：基于 `perf.data` 或 Excel 偏移量，对 SO 库中缺失符号的函数进行反汇编/（可选）反编译，并结合 LLM 推断函数名、功能、性能瓶颈与优化建议，同时支持将推断符号写回原始 HTML 性能报告，形成可读性极高的分析结果。
- **入口**：
  - `tools/symbol_recovery/main.py#main`
  - `tools/symbol_recovery/main.py#create_argument_parser`
  - CLI：`symbol-recovery`
- **输入**：
  - perf 模式输入：`--perf-data`（`perf.data` 路径，默认 `perf.data`）
  - `--perf-db`（可选已有 `perf.db`）
  - `--so-dir` 或 `--so-file`（SO 目录或单个 SO 文件）
  - `--stat-method`（`event_count`/`call_count`）
  - `--top-n`（分析前 N 个函数）
  - LLM/分析控制：`--no-llm`、`--batch-size`、`--use-capstone-only`、`--skip-decompilation`、`--save-prompts`、`--llm-model`、`--context`、`--open-source-lib`
  - 流程控制：`--skip-step1/3/4`、`--only-step1/3/4`、`--html-input/--html-pattern`
  - Excel 模式输入：`--excel-file`（包含偏移量的 Excel）+ `--so-file/--so-dir`
  - 内部依赖：`PerfDataToSqliteConverter`、`MissingSymbolFunctionAnalyzer`、`EventCountAnalyzer`、`ExcelOffsetAnalyzer`、`Radare2/Capstone`、LLM 模块等
- **输出**：
  - perf 模式输出：`perf.db`、按 `event_count` 或 `call_count` 的 Top N 符号恢复 Excel 报告（`*_analysis.xlsx`）、对应 HTML 报告（`*_report.html`）、时间统计 JSON、带推断符号的 hiperf HTML（`*_with_inferred_symbols.html`）
  - Excel 模式输出：`excel_offset_analysis_{n}_functions.xlsx` / `.html` 与时间统计 JSON
  - 缓存输出：`cache/llm_analysis_cache.json` 与 `llm_token_stats.json`
  - 控制台与日志中的详细时间与步骤信息
- **备注**：可作为 hapray 性能链路的“符号增强”与“语义解释”工具：对热点函数做高质量语义标注和瓶颈分析，并将结果回填到 HTML 报告，为后续 Agent 自动诊断与优化建议提供语义基础。

<a id="feature-perf-testing-prepare"></a>

### 测试准备执行（perf_testing prepare）

- **描述**：面向预埋性能场景的一键回归：在已有 hapray 测试用例集上，按指定模式或自动筛选 `_0000` 结尾用例，在真实 HarmonyOS 设备上依次执行性能/内存等测试，并为每条用例生成标准化的结果目录，供后续静态/可视化分析使用。
- **入口**：
  - `perf_testing/hapray/actions/prepare_action.py#PrepareAction.execute`
  - CLI：`ArkAnalyzer-HapRay prepare`
- **输入**：
  - 命令行参数：`--run_testcases`（支持正则的用例名列表）
  - `--all_0000`（是否自动执行所有 `_0000` 结尾用例）
  - `--device`（设备序列号，可选）
  - 环境依赖：PATH 中可用的 `hdc` 与 `node`
  - 测试用例元数据：`CommonUtils.load_all_testcases()` 返回的"用例名 -> (目录, 扩展名)"映射
- **输出**：
  - 每条用例对应的临时输出目录（包含 `hiperf/htrace` 等结果，下游可被 hapray 分析链路消费）
  - 控制台日志中的执行进度与成功/失败统计
  - 执行结果状态（成功计数/失败用例）
- **备注**：对 xDevice/DSL 用例执行做了简化封装，适合作为大规模预检/回归的前置动作。

<a id="feature-gui-agent"></a>

### GUI Agent 自动化（perf_testing gui-agent）

- **描述**：基于 LLM 的 AI 手机自动化，支持用自然语言描述场景在真机上执行，自动完成操作步骤并采集 perf/trace/内存数据，输出标准化报告目录供后续分析。
- **入口**：
  - `perf_testing/hapray/actions/gui_agent_action.py#GuiAgentAction.execute`
  - `perf_testing/hapray/core/gui_agent/__init__.py#execute_scenes`
  - CLI：`ArkAnalyzer-HapRay gui-agent`
- **输入**：
  - `--glm-base-url`、`--glm-model`、`--glm-api-key` LLM 配置（或环境变量 GLM_BASE_URL/GLM_MODEL/GLM_API_KEY）
  - `--max-steps` 每任务最大步数（默认 20）
  - `--device-id` 设备序列号
  - `--package-name`/`--apps` 应用包名（必选，支持多包）
  - `--scenes` 自然语言描述的场景列表
  - `-o/--output` 输出目录
  - `--no-trace`、`--no-perf` 关闭 trace/perf 采集
  - `--memory`、`--snapshot` 启用内存分析与堆快照
- **输出**：
  - `output/reports/<timestamp>` 下各场景的步骤数据与报告
  - 控制台执行状态与步骤日志
- **备注**：依赖 GLM 等 LLM 服务，适合探索性场景或无需预埋用例的自动化测试。

<a id="feature-perf-action"></a>

### 自动化性能测试（perf_testing perf）

- **描述**：多设备并行执行性能测试用例，支持多轮次、手动模式、HapFlow 全链路、UI 技术栈动态识别等，为每条用例生成报告并汇总 Excel。
- **入口**：
  - `perf_testing/hapray/actions/perf_action.py#PerfAction.execute`
  - `perf_testing/hapray/actions/perf_action.py#PerfAction.run`
  - CLI：`ArkAnalyzer-HapRay perf`
- **输入**：
  - `--run_testcases` 用例名或正则（支持多选）
  - `--round` 测试轮次（默认 5）
  - `--devices` 设备序列号列表（多设备并行）
  - `--so_dir` 符号化 so 目录
  - `--circles` 启用 CPU 周期采样
  - `--no-trace`、`--no-perf`、`--memory`、`--snapshot` 采集模式
  - `--manual` 手动模式（30 秒性能采集）
  - `--package-name` 手动模式目标包名
  - `--hapflow` HapFlow 根目录（串联全链路分析）
  - `--ui-tech-stack` UI 技术栈动态识别模式
  - 环境依赖：`hdc`、`node`
- **输出**：
  - `reports/<timestamp>` 下各用例报告目录
  - 汇总 Excel（`create_perf_summary_excel`）
  - 控制台执行进度与报告统计
- **备注**：通过 `DeviceManager` 与 `DeviceBoundTestRunner` 实现多设备并行，`ParallelReportGenerator` 并行生成报告，与 prepare 的串行执行形成互补。

<a id="feature-haptest"></a>

### HapTest 策略驱动 UI 自动化（perf_testing haptest）

- **描述**：无需预埋测试用例，按策略（深度优先/广度优先/随机）自动探索应用 UI，在真机上执行并采集 perf/trace/内存数据，动态生成 HapTest 用例后通过 xDevice 执行，最终生成性能报告。
- **入口**：
  - `perf_testing/hapray/actions/haptest_action.py#HapTestAction.execute`
  - `perf_testing/hapray/actions/haptest_action.py#HapTestRunner.run`
  - CLI：`ArkAnalyzer-HapRay haptest`
- **输入**：
  - `--app-package` 目标应用包名（必选）
  - `--app-name` 应用可读名称（必选）
  - `--ability-name` 主 Ability 名称（可选，不指定则自动检测）
  - `--strategy` 探索策略：`depth_first`（默认）、`breadth_first`、`random`
  - `--max-steps` 最大探索步数（默认 30）
  - `--round` 测试轮次（默认 1）
  - `--devices` 设备序列号列表
  - `--trace`/`--no-trace` 是否采集 trace（默认启用）
  - `--memory` 启用内存分析
  - `--no-perf` 关闭 perf 采集（仅内存模式）
  - 环境依赖：`hdc`、`node`
- **输出**：
  - `reports/haptest_<app_package>_<timestamp>` 下报告目录
  - 动态生成的用例文件：`testcases/__haptest_generated__/HapTest_<app>.py` 与 `.json`
  - `ReportGenerator.generate_report` 生成的 hapray_report.html 等
- **备注**：基于 `HapTest` 基类与 xDevice 框架，适合无预埋用例时的应用探索与性能摸底。

<a id="feature-cov-analyzer"></a>

### 覆盖率报告触发（CovAnalyzer）

- **描述**：在场景分析阶段检测是否存在 `bjc_cov.json`，若存在则调用 hapray 的 bjc 子命令生成覆盖率报告，将性能报告与代码覆盖率打通。
- **入口**：
  - `perf_testing/hapray/analyze/cov_analyzer.py#CovAnalyzer`
  - `tools/static_analyzer/src/cli/commands/bjc_cli.ts#BjcCli`
- **输入**：
  - 输入：每步 `perf.db` 所在目录中的 `bjc_cov.json`
  - `Config.cov.hapProjectPath` 指向源码工程路径
  - 底层依赖 `ExeUtils.execute_hapray_cmd` 调用 `hapray-sa-cmd hapray bjc`
- **输出**：
  - 使用 bjc 生成的覆盖率报告文件（写到 `perf.db` 所在目录）
  - 日志中的执行信息
- **备注**：把外部覆盖率结果纳入 hapray 场景输出链路，便于后续在平台或报表中进行覆盖率与性能的联合分析。

<a id="feature-perf-scene-load"></a>

### 白盒负载拆解（hapray-sa-cmd perf）

- **描述**：对性能测试场景目录进行联合分析，加载多步骤 `perf.data/trace.htrace` 与 db 文件，生成步骤级性能 JSON 报告及 summary 信息；也支持单步模式，直接针对单个 `perf.db` 或 `trace.db` 文件进行分析，推断所属步骤和场景目录，输出该步骤的性能 JSON。用于 Web 端可视化负载分析。
- **入口**：
  - `tools/static_analyzer/src/cli/commands/perf_cli.ts#PerfCli`
  - `tools/static_analyzer/src/services/analysis/perf_analysis.ts#PerfAnalysisService.generatePerfReport`
  - `tools/static_analyzer/src/services/analysis/perf_analysis.ts#PerfAnalysisService.generatePerfReportFromDbFile`
  - `tools/static_analyzer/src/services/analysis/analysis_service_base.ts#AnalysisServiceBase.loadSteps`
  - CLI：`hapray-sa-cmd hapray perf`
- **输入**：
  - CLI：`-i/--input` 场景报告路径、db 文件或单个 `perf.db`/`trace.db`
  - `--choose` 是否进行轮次选择（联合模式）
  - `--disable-dbtools`、`-k/--kind-config`、`--compatibility`、`--ut`
  - `--time-ranges` 时间区间、`--package-name` 包名
  - 联合模式：input 目录下 `report/result/hiperf/step*/perf.data` 与 `htrace/step*/trace.htrace`
  - 单步模式：db 文件路径中包含的 `step<idx>` 约定
  - `GlobalConfig` 配置、`traceStreamerCmd`/`PerfAnalyzer` 依赖
- **输出**：
  - `input/report` 目录下性能分析输出 JSON
  - `input/hiperf/hiperf_info.json`、`input/hiperf/stepX/hiperf_info.json`
  - `input/summary_info.json`
  - 日志中轮次选择、缺失数据、时间过滤及单步模式说明
- **备注**：作为 Web 端负载/帧/火焰图等分析的数据源，支持兼容模式从旧格式推导 `TestReportInfo`；单步模式用于只拿到 db 文件时的快速诊断。

<a id="feature-round-selection"></a>

### 轮次选择与最优轮次判定

- **描述**：在多轮次测试数据下，对多个轮次的同一步骤进行分析，计算负载总值并自动选择最优轮次，复制其数据用于后续报告。
- **入口**：
  - `tools/static_analyzer/src/services/analysis/perf_analysis.ts#PerfAnalysisService.chooseRound`
  - `tools/static_analyzer/src/services/analysis/perf_analysis.ts#PerfAnalysisService.calculateRoundResults`
  - `tools/static_analyzer/src/services/analysis/perf_analysis.ts#PerfAnalysisService.selectOptimalRound`
  - CLI：`hapray-sa-cmd hapray perf --choose`
- **输入**：
  - 包含多个轮次子目录的场景目录
  - 各轮次的 `perf.data/trace.htrace/db` 文件
  - `Steps/Step/StandardTestInfo/Round` 等内部类型
  - `PerfAnalyzer.analyzeOnly` 返回的 total 指标
- **输出**：
  - 每个步骤的 `RoundInfo` 选择结果
  - 拷贝后的 `testInfo.json`、`steps.json`、`result`、`ui/stepX` 等标准文件
  - 日志中的轮次负载总数和最终选择轮次
- **备注**：以 cycles/instructions 总和为指标，排除极值后按均值选最接近的轮次，为 `generatePerfReport` 提供稳定输入。

<a id="feature-single-step-fault-tree"></a>

### 单版本故障树分析

- **描述**：基于性能数据构建步骤级故障树，展示潜在性能问题的层级结构和归因路径。
- **入口**：
  - `web/src/views/HomeView.vue#FaultTreeAnalysis`
  - `web/src/components/single-analysis/step/fault-tree/FaultTreeAnalysis.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：perf 场景 JSON 中的故障树数据
  - 步骤 ID：`fault_tree_step_<id>`
  - `perf.db` 与 `trace.db` 的 DB 查询
- **输出**：
  - 可视化的故障树视图（节点包含模块/函数/资源等信息）
  - 节点权重和影响度统计
  - 与版本对比故障树视图的联动
- **备注**：用于辅助定位导致高负载或卡顿的根因。

<a id="feature-component-reuse"></a>

### 组件复用率分析（ComponentReusableAnalyzer）

- **描述**：基于 `trace.db` 中的 `H:CustomNode:Build`* 调用，统计各组件的构建次数与回收构建次数，评估组件复用率，帮助发现频繁重建但复用不足的 UI 组件。
- **入口**：
  - `perf_testing/hapray/analyze/component_reusable_analyzer.py#ComponentReusableAnalyzer`
- **输入**：
  - 输入：`scene_dir` 下当前步骤的 `trace.db`
  - `callstack` 表中包含 `H:CustomNode:BuildItem [...]` 和 `H:CustomNode:BuildRecycle` 日志
  - 应用进程 PID 列表（`app_pids`）
- **输出**：
  - 每步一个组件复用指标字典（`max_component`、`total_builds`、`recycled_builds`、`reusability_ratio` 以及各组件明细）
  - 写入 `trace/componentReuse` 相关 JSON，并合并进主 `result`
- **备注**：用于定位 ArkUI 组件树中复用效果不佳的组件，为 UI 结构与状态管理优化提供依据。

<a id="feature-perf-analyzer"></a>

### 性能火焰图与场景 Perf 分析（PerfAnalyzer）

- **描述**：对每个步骤的 `perf.db` 生成 hiperf 火焰图报告，并在 step1 调用 hapray CLI 的 perf 子命令完成场景级 Perf 分析，是 CPU 负载和火焰图数据的核心生产者。
- **入口**：
  - `perf_testing/hapray/analyze/perf_analyzer.py#PerfAnalyzer`
  - `tools/static_analyzer/src/cli/commands/perf_cli.ts#PerfCli`
- **输入**：
  - 输入：`scene_dir`、每步 `perf.db` 与 `trace.db`
  - 可选 `time_ranges` 时间过滤
  - 可选 `Config.kind`（`APP_SO` 组件划分）
  - 可选 `Config.so_dir`（符号化 so 目录）
- **输出**：
  - 每步 `perf.json` 与对应 `hiperf_report.html`（嵌入压缩 JSON）
  - 在 step1 触发 `hapray perf` 完整分析（生成 `report` 目录下 perf 相关 JSON/DB）
  - 为前端负载、火焰图等视图提供底层数据
- **备注**：是从原始 hiperf 采样到 Web 可视化之间的关键桥梁，决定 CPU 视图的数据粒度与可用性。

<a id="feature-memory-analyzer"></a>

### 内存分配与泄漏分析（MemoryAnalyzer）

- **描述**：对 hiperf 内存采样与 `meminfo` 数据进行聚合与精简存储，构建 `memory_results`、`memory_records`、`memory_callchains` 等表，用于前端内存时间线、Outstanding 火焰图和精细化内存定位，并支持 refined 模式和对比导出。
- **入口**：
  - `perf_testing/hapray/analyze/memory_analyzer.py#MemoryAnalyzer`
- **输入**：
  - 输入：`scene_dir`、每步 `perf.db/trace.db`
  - Global memory 配置
  - 可选 `use_refined_lib_symbol/export_comparison` 开关
  - 底层依赖 `MemoryAnalyzerCore`、`MemoryMeminfoParser`、`MemoryAggregator` 等
- **输出**：
  - `scene_dir/report/hapray_report.db` 中的内存相关表与视图（`memory_results`、`memory_records`、`memory_callchains` 等）
  - 可选 refined 内存结果和 comparison Excel
  - `summary` 中的内存统计 JSON
- **备注**：为前端 Memory 视图和 Symbol refined 分析提供高密度但结构化的数据，是内存调优和泄漏排查的基础。

<a id="feature-unified-frame"></a>

### 统一帧分析（UnifiedFrameAnalyzer）

- **描述**：统一完成帧负载、空帧、卡顿帧、VSync 异常以及 RS Skip 分析，并输出多个帧相关 JSON（`frameLoads/emptyFrame/frames/vsyncAnomaly/rsSkip`），用于前端帧率、卡顿和动画质量的多维度展示。
- **入口**：
  - `perf_testing/hapray/analyze/unified_frame_analyzer.py#UnifiedFrameAnalyzer`
- **输入**：
  - 输入：每步 `trace.db`（必需）与可选 `perf.db`
  - `app_pids` 作为目标应用进程过滤
  - 底层依赖 `FrameAnalyzerCore`（封装帧负载、空帧、卡顿帧、VSync/RS Skip 分析逻辑）
- **输出**：
  - `scene_dir/report` 下的帧相关 JSON（`trace_frameLoads.json`、`trace_emptyFrame.json`、`trace_frames.json`、`trace_vsyncAnomaly.json`、`trace_rsSkip.json` 等）
  - 并将合并后的帧结果注入主 `result`
- **备注**：帧分析所有子能力的汇聚点，是单场景帧率、卡顿、空刷和 VSync 问题诊断的主数据源。

<a id="feature-cold-start"></a>

### 冷启动冗余文件分析（ColdStartAnalyzer）

- **描述**：基于工具生成的 `redundant_file.txt`，统计冷启动阶段被访问的文件中"使用/未使用"的数量与耗时 Top10，帮助识别可以剔除或延后加载的资源，优化启动时间。
- **入口**：
  - `perf_testing/hapray/analyze/cold_start_analyzer.py#ColdStartAnalyzer`
- **输入**：
  - 输入：每步 `trace.db` 所在目录下的 `redundant_file.txt`（包含 Summary 与 used/unused file 列表）
  - `scene_dir` 和 `step_dir` 标识
- **输出**：
  - 冷启 Summary（总文件数、总时长、使用/未使用文件数及耗时）
  - used/unused files Top10 列表
  - 写入 `trace/coldStart` 相关 JSON 并合并进 `result`
- **备注**：提供文件粒度的冷启动冗余视角，可与 hap 包内容和资源打包策略结合做启动优化。

<a id="feature-gc"></a>

### GC 负载与频率分析（GCAnalyzer）

- **描述**：分析指定应用进程在 perf/trace 中的 GC 线程事件和 GC 运行次数，计算 GC 在线程总负载中的占比以及 Full/Shared/Partial GC 调用频次，用于识别 GC 过于频繁或过重的场景。
- **入口**：
  - `perf_testing/hapray/analyze/gc_analyzer.py#GCAnalyzer`
- **输入**：
  - 输入：每步 `trace.db` 与 `perf.db`
  - `app_pids` 作为目标进程过滤
  - `perf_sample/perf_thread/perf_process/callstack/thread/process` 等表中的 GC 相关记录
- **输出**：
  - 各类 GC 次数统计（`FullGC/SharedFullGC/SharedGC/PartialGC`）
  - GC 总负载占比 `perf_percentage` 以及 `GCStatus`（OK 或 Too many GC）等 JSON 结果
  - 写入 `trace/gc_thread` 相关报告并合并进 `result`
- **备注**：用于判断场景是否存在 GC 抖动或 GC 过重问题，为堆内存配置与对象生命周期优化提供量化依据。

<a id="feature-fault-tree-analyzer"></a>

### 故障树指标分析（FaultTreeAnalyzer）

- **描述**：从 trace/perf 中抽取 ArkUI、RS、av_codec、Audio 以及 IPC Binder 等多维度指标，构建用于前端故障树视图的数据（如动画数量、区域变化监听、ProcessedNodes、视频解码帧数、音频回调负载等），支撑一步到位的性能问题归因。
- **入口**：
  - `perf_testing/hapray/analyze/fault_tree_analyzer.py#FaultTreeAnalyzer`
- **输入**：
  - 输入：每步 `trace.db`（`callstack/thread/process/trace_range` 等）与 perf 相关表
  - `app_pids`
  - 以及 step 级别的 IPC Binder 统计 JSON
- **输出**：
  - 以 `arkui/RS/av_codec/Audio/ipc_binder` 等节点组织的指标字典
  - 写入 `trace/fault_tree` 相关 JSON，并作为前端单场景和版本对比的故障树数据来源
- **备注**：把分散在 UI、渲染、编解码、音频、IPC 中的关键指标汇总成可视化故障树，是复杂场景性能归因的核心输入。

<a id="feature-ui-analyzer"></a>

### UI 动画与页面结构分析（UIAnalyzer）

- **描述**：基于 UI 采集目录中的 `pages.json`、元素树和截图，对每个页面的 CanvasNode 数量/上树情况、图片资源大小及两次截图/Element 树差异进行分析，识别可能的 UI 动画区域并生成标记截图。
- **入口**：
  - `perf_testing/hapray/analyze/ui_analyzer.py#UIAnalyzer`
- **输入**：
  - 输入：`scene_dir/ui/stepX` 下的 `pages.json`、`element_tree/rs_tree` 文件、`screenshot/screenshot_2` 图片以及 inspector 元信息
  - 底层依赖 ArkUI tree parser 与 `RegionImageComparator` 等
- **输出**：
  - 每页面的分析结果列表（`canvasNodeCnt`、on/off tree 统计、`image_size_analysis`、`animations`、标记后的截图路径等）
  - 写入 `ui/animate` 相关 JSON，并注入主 `result`
- **备注**：为前端 UI 动画分析视图提供离线分析结果，是发现复杂动画/过大图片/未上树 Canvas 等 UI 性能问题的基础。

<a id="feature-ipc-binder"></a>

### IPC Binder 事务分析（IpcBinderAnalyzer）

- **描述**：从 `trace.db` 中提取 binder 相关 callstack 及参数，自动配对请求/响应，按进程对、线程对和接口维度统计调用次数与耗时分布，识别跨进程调用的热点与潜在瓶颈。
- **入口**：
  - `perf_testing/hapray/analyze/ipc_binder_analyzer.py#IpcBinderAnalyzer`
- **输入**：
  - 输入：每步 `trace.db` 中的 `process/thread/callstack/data_dict/args` 等表
  - `app_pids` 用于筛选与目标应用相关的 binder 事件
  - 内部使用 `REQUEST/RESPONSE` 关键词来区分请求与响应
- **输出**：
  - `process_stats`（进程对维度）、`thread_stats`（线程对维度）、`interface_stats`（接口维度）的聚合结果 JSON
  - 写入 `trace/ipc_binder` 相关报告并注入主 `result`
- **备注**：提供跨进程通信视角，帮助发现高频、慢响应或不合理的 IPC 接口，为服务拆分与接口设计优化提供依据。

<a id="feature-thread-analyzer"></a>

### 冗余线程与唤醒链分析（ThreadAnalyzer）

- **描述**：结合 trace/perf 中的唤醒链与线程负载，识别频繁唤醒立即睡眠、从未被唤醒、忙等等冗余线程模式，量化其冗余指令数和内存占用，输出可排序的冗余线程列表。
- **入口**：
  - `perf_testing/hapray/analyze/thread_analyzer.py#ThreadAnalyzer`
- **输入**：
  - 输入：每步 `trace.db` 与 `perf.db`（或 `trace.db`）
  - `app_pids` 作为应用进程过滤
  - 底层依赖 `analyze_all_threads_wakeup_chain` 与 `analyze_optimization_opportunities`
- **输出**：
  - `redundant_thread_analysis.json`（以及注入 `result['redundant_thread_analysis']`）
  - 包含冗余类型定义、总冗余线程数、总冗余指令数、冗余指令占比与按冗余得分排序的线程清单
- **备注**：帮助快速找到对整体性能收益最大的线程级优化点，是 CPU 与能耗层面的重要优化抓手。

<a id="feature-bjc-coverage"></a>

### 覆盖率报告生成（bjc 子命令）

- **描述**：基于 bjc 库对 HAP 工程生成代码覆盖率报告，用于评估测试覆盖情况。
- **入口**：
  - `tools/static_analyzer/src/cli/commands/bjc_cli.ts#BjcCli`
  - CLI：`hapray-sa-cmd hapray bjc`
- **输入**：
  - CLI：`-i/--input` HAP 文件
  - CLI：`-o/--output` 输出目录
  - `--project-path` 项目源码根目录
  - `bjc.Report` 依赖
- **输出**：
  - 覆盖率报告文件（写入指定输出目录）
  - 日志中的生成路径信息
- **备注**：与 bjc 库强耦合，关注覆盖率而非性能。

<a id="feature-import-html-db"></a>

### 场景报告/HTML 导入与本地 DB 初始化

- **描述**：从用户上传的场景报告或本地目录解析数据，将 perf/内存/日志等信息写入浏览器端数据库，供 Web 前端查询分析。
- **入口**：
  - `web/src/components/common/UploadHtml.vue`
  - `web/src/db/client/dbClient.ts`
  - `web/src/db/serviceWorker/dbServiceWorker.ts`
  - `web/src/utils/dbApi.ts#getDbApi`
- **输入**：
  - 用户上传的 HTML 报告或压缩包
  - 本地场景结果目录
  - IndexedDB/sqlite wasm 数据库
  - 从 HTML/JSON 中抽取的 `perfData/steps/summary/memory/log` 等结构
- **输出**：
  - 浏览器本地数据库中的 `perfData/steps/summary/memory/uiAnimate/comparePerfData` 等表
  - `jsonDataStore` 初始化状态
  - 导入成功/失败提示与统计信息
- **备注**：Web 端链路入口能力，无后端 HTTP API，采用本地 DB + service worker 架构。

<a id="feature-single-scene-overview"></a>

### 单版本场景负载总览

- **描述**：在 Web 端对单个性能场景的所有步骤进行汇总展示，包括各步骤指令数、耗能等指标分布。
- **入口**：
  - `web/src/views/HomeView.vue#PerfLoadOverview`
  - `web/src/components/single-analysis/overview/PerfLoadOverview.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`useJsonDataStore().perfData.steps`
  - 路由/hash：`#/overview`
  - 用户通过导航菜单或欢迎页 feature-card 触发 `changeContent('perf_load_overview')`
- **输出**：
  - 场景步骤总览图表
  - 步骤关键指标卡片（指令数、功耗估算、占比）
  - 到步骤负载分析/帧分析页面的跳转
- **备注**：消费 CLI 生成的 `perfData` JSON，是单场景分析链路的入口。

<a id="feature-single-step-load"></a>

### 单版本步骤负载分析

- **描述**：针对单个步骤进行线程/进程/文件/符号维度的负载分析，展示热点线程和函数。
- **入口**：
  - `web/src/views/HomeView.vue#PerfStepLoad`
  - `web/src/components/single-analysis/step/load/PerfStepLoad.vue`
  - `web/src/components/single-analysis/step/load/PerfLoadAnalysis.vue`
  - `web/src/components/single-analysis/step/load/PerfSingle.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`jsonDataStore.perfData.steps[stepIndex]`
  - `jsonDataStore.steps`
  - DB API：`getDbApi()` 查询线程/进程/文件/符号表
  - 页面参数中的 `step-id`
- **输出**：
  - `PerfThreadTable`/`PerfProcessTable`/`PerfFileTable`/`PerfSymbolTable` 表格数据
  - 趋势和分布图
  - 顶部步骤指标与功耗估算
- **备注**：与 Memory/帧/火焰图等视图共享步骤信息，是精细化定位瓶颈的核心功能。

<a id="feature-single-step-frame"></a>

### 单版本帧率与渲染分析

- **描述**：针对单个步骤的 UI 帧数据进行分析，展示帧率、卡顿和渲染耗时。
- **入口**：
  - `web/src/views/HomeView.vue#PerfFrameAnalysis`
  - `web/src/components/single-analysis/step/frame/FrameAnalysis.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`jsonDataStore.perfData` 或帧数据结构
  - 步骤 ID：`frame_step_<id>`
  - 底层帧统计数据
- **输出**：
  - 帧时间线和分布图
  - 平均 FPS、掉帧数等指标
  - 与负载/火焰图/故障树的导航关联
- **备注**：与 UI 动画分析一同构成 UI 性能诊断视图。

<a id="feature-flame-graph"></a>

### 火焰图分析

- **描述**：通过火焰图可视化负载热点与调用栈，支持按步骤查看调用路径和消耗。
- **入口**：
  - `web/src/views/HomeView.vue#FlameGraph`
  - `web/src/components/single-analysis/step/flame/FlameGraph.vue`
  - `web/src/components/single-analysis/step/memory/MemoryOutstandingFlameGraph.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：火焰图 JSON/折叠调用栈数据
  - 步骤 ID：`flame_step_<id>`
  - 内存场景下的 outstanding/meminfo 采样数据
- **输出**：
  - 交互式火焰图
  - 按函数/模块聚合的热点统计
  - 与线程/进程/文件表格的联动
- **备注**：是热点诊断的关键视图之一，支持 CPU 与内存 outstanding 两类火焰图。

<a id="feature-memory"></a>

### 内存分析

- **描述**：对步骤级内存数据进行分析，包括 `meminfo` 时间线、Native Memory 列表和 outstanding 分析。
- **入口**：
  - `web/src/components/single-analysis/step/memory/NativeMemory.vue`
  - `web/src/components/single-analysis/step/memory/MemoryTimelineChart.vue`
  - `web/src/components/single-analysis/step/memory/MeminfoStackedAreaChart.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - DB API：`queryMemoryMeminfo` / `queryMemoryResults` / `queryOverviewTimeline`
  - `jsonDataStore.steps`
  - 步骤 ID：`memory_step_<id>`
  - 底层 Python 内存分析结果和 trace 导出记录
- **输出**：
  - 内存使用时间线图
  - Native Memory 列表与统计
  - outstanding 内存火焰图
- **备注**：导航栏通过检查是否有内存相关表和记录决定是否展示 Memory 菜单。

<a id="feature-ui-animate"></a>

### UI 动画与 UI 性能分析

- **描述**：对 UI 动画和界面切换进行分析，展示每个步骤的 UI 动画数据和页面对比，并支持版本间 UI 差异对比。
- **入口**：
  - `web/src/components/single-analysis/step/ui-animate/PerfUIAnimate.vue`
  - `web/src/components/single-analysis/step/ui-animate/PageComparison.vue`
  - `web/src/components/compare/UICompare.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`jsonDataStore.uiAnimateData`
  - 前端状态：`jsonDataStore.uiCompareData`
  - 步骤 ID：`ui_animate_step_<id>` 与 `compare_step_ui_<id>`
  - UI 日志/快照数据
- **输出**：
  - 单步骤 UI 动画分析视图
  - 多版本 UI 对比视图
  - 页面行为对比组件输出
- **备注**：与帧分析和日志分析一起构成 UI 性能诊断组合能力。

<a id="feature-hilog"></a>

### 日志分析（HilogAnalysis）

- **描述**：基于 Hilog 日志与性能步骤的关联，展示按步骤切分的日志内容和统计信息。
- **入口**：
  - `web/src/components/single-analysis/step/hilog/HilogAnalysis.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`jsonDataStore.summary`（含 `log` 字段的 summary 列表）
  - 步骤 ID：`hilog_step_<id>` 或 `stepX` 字符串
  - 底层日志采集文件或数据库
- **输出**：
  - 按步骤筛选的日志列表/聚合视图
  - 与步骤负载及帧/UI 分析的跳转联动
  - 每步日志条目数量与错误率统计
- **备注**：`getHasLogData` 通过 `summary.log` 判断某步是否有日志分析数据，从而决定菜单展示。

<a id="feature-version-compare"></a>

### 版本对比分析

- **描述**：对不同版本的性能结果进行对比分析，包括场景负载、步骤负载、详细数据、新增数据、Top10 热点以及故障树/UI 多维度比对。
- **入口**：
  - `web/src/views/HomeView.vue#CompareOverview/PerfCompare`
  - `web/src/components/compare/CompareOverview.vue`
  - `web/src/components/compare/SceneLoadCompare.vue`
  - `web/src/components/compare/StepLoadCompare.vue`
  - `web/src/components/compare/CompareStepLoad.vue`
  - `web/src/components/compare/DetailDataCompare.vue`
  - `web/src/components/compare/NewDataAnalysis.vue`
  - `web/src/components/compare/Top10DataCompare.vue`
  - `web/src/components/compare/FaultTreeCompare.vue`
  - `web/src/components/compare/UICompare.vue`
  - `web/src/components/compare/PerfCompare.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：`jsonDataStore.comparePerfData`
  - 前端状态：`jsonDataStore.uiCompareData`
  - 路由/hash：`/compare` 与子路径
  - 步骤 ID：`compare_step_load_<id>` 等
  - 多版本 perf JSON/故障树/UI 对比数据文件
- **输出**：
  - 场景级多版本负载曲线和柱状图
  - 单步负载差异视图
  - 详细/新增/Top10 数据对比视图
  - 故障树对比视图
  - UI 对比视图
- **备注**：`hasCompareData` 通过 `comparePerfData.steps` 判断是否展示 compare 菜单，用户通过上传多版本数据触发能力。

<a id="feature-perf-multi"></a>

### 多版本趋势分析（PerfMulti）

- **描述**：从多版本 perf 数据中提取关键指标，生成趋势图展示性能随版本演进的变化。
- **入口**：
  - `web/src/views/HomeView.vue#PerfMulti`
  - `web/src/components/multi-version/PerfMulti.vue`
  - `web/src/components/common/AppNavigation.vue`
- **输入**：
  - 前端状态：多版本 `perfData` 或专门趋势数据
  - 路由/hash：`/perf_multi`
  - 图表组件：`TrendChart` / `BarChart` / `PieChart`
- **输出**：
  - 关键指标的多版本趋势曲线
  - 版本间对比柱状图
  - 对显著性能变化版本的标注信息
- **备注**：与版本对比分析互补，聚焦长期趋势而非单次对比。

<a id="feature-perf-testing-update"></a>

### 报告更新与重算（perf_testing update）

- **描述**：针对已有 hapray 场景结果目录做离线重算：在不重新采集数据的前提下，根据最新规则/配置对多个用例报告进行批量更新，支持 SIMPLE 模式从一组 perf/trace 文件自动构造报告目录，并生成汇总 Excel，必要时串联 HapFlow 全链路分析。
- **入口**：
  - `perf_testing/hapray/actions/update_action.py#UpdateAction.execute`
  - `perf_testing/hapray/actions/update_action.py#UpdateAction.process_reports`
  - CLI：`ArkAnalyzer-HapRay update`
- **输入**：
  - 命令行参数：`--report_dir`（报告根目录，必选）
  - `--so_dir`（符号化 so 目录，可选）
  - `--mode`（`COMMUNITY`/`SIMPLE`）
  - SIMPLE 模式参数：`--perfs`、`--traces`、`--package-name`、`--pids`、`--steps`
  - 时间过滤：`--time-ranges` 多个纳秒区间
  - 内存分析增强：`--use-refined-lib-symbol`、`--export-comparison`、`--symbol-statistic`
  - 线程分析开关：`--no-thread-analysis`
  - 可选链路：`--hapflow` 指定 Homecheck 根目录
- **输出**：
  - 为每个测试用例目录重算并更新性能/内存等报告（通过 `ReportGenerator.update_report`）
  - 在报告根目录生成/更新汇总 Excel（`create_perf_summary_excel`）
  - 可选输出 refined 内存分析 comparison Excel 及符号统计结果
  - 控制台日志中的每个用例处理状态与时间区间信息
- **备注**：核心用于"已有数据的规则/视图升级"，避免重新采集，且向 HapFlow 等上层平台输出所需结构化结果。

<a id="feature-perf-testing-compare"></a>

### 报告目录对比分析（perf_testing compare）

- **描述**：对两个 hapray 报告目录进行场景/步骤维度的性能对比：递归收集各自的 `summary_info.json`，按 `scene+step_id+step_name` 对齐后按版本展开为列，计算 base/compare 之间的 count 差异及百分比，并导出对比 Excel，支撑性能回归与审计。
- **入口**：
  - `perf_testing/hapray/actions/compare_action.py#CompareAction.execute`
  - `perf_testing/hapray/actions/compare_action.py#load_summary_info`
  - CLI：`ArkAnalyzer-HapRay compare`
- **输入**：
  - 命令行参数：`--base_dir`（基线报告目录，必选）
  - `--compare_dir`（对比报告目录，必选）
  - `--output`（输出 Excel 路径，可选，默认 `compare_result.xlsx`）
  - 输入数据：两个目录下递归找到的 `summary_info.json` 列表（支持 dict 或 list 结构）
- **输出**：
  - 输出 Excel（默认 `compare_result.xlsx`），包含场景/步骤为行、不同版本（`rom_version|app_version`）为列的 `base_xxx` / `compare_xxx` 指标，以及 `percent_xxx` 百分比变化
  - 控制台日志中的扫描结果与错误信息
- **备注**：使用 `ExcelReportSaver` 保存单表 Compare，是更偏离线分析的能力，可与 web 端多版本/对比视图搭配使用。



### 分类说明

| 大类       | 小类                 |
| -------- | ------------------ |
| **GUI**  | 桌面工具               |
| **静态分析** | so编译优化、软件成份分析、符号恢复 |
| **动态分析** | 自动化测试、数据采集、数据分析    |
| **报告生成** | 覆盖率报告、场景报告、报告更新与对比 |

