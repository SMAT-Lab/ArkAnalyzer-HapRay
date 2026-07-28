# LLM 高负载挖掘（CPU 指令数 · 动态 perf + 静态 SO 交叉）

> **核心度量**：本文中 **「负载」= CPU 指令数** —— 即 `perf_sample.event_count` 的聚合值（hiperf 采集事件：`raw-instruction-retired`，每个样本代表一个周期内执行的指令数）。  
> **分析目标**：通过 **动态指令数（perf_sample）** 与 **静态 SO 分析（binary/LTO/符号）** 的交叉，挖掘 **自动报告未写出的** 高指令数热点与优化机会。  
> **与 `summary.json` 的关系**：`summary.json` 是按已知规则汇总的摘要，**禁止**将其作为本 Skill 挖掘的主线数据源；原始侧以 **`perf_sample`、`perf_callchain`、`perf_files`、`callstack`、`frame_slice`** 为准，静态侧以 **SO 二进制分析产物** 为准。

---

## 一、触发条件与最低完成标准

### 1.1 必须加载的触发条件（满足任一条即强制）

> **默认主线**：本文是 **阶段4 默认进入**的分析。`perf` 完成后**直接读 `<用例>/report/`**（**不依赖 `update`**：`more_flame_graph.json`、全部 `trace_*.json`、`summary.json`、`hiperf/step*/perf.db` 均为 perf 阶段产物）。**符号恢复（可选阶段3）非前置**——见下「无符号恢复时的降级」。

| 类别 | 用户表述或客观信号 | 必须行为 |
|------|--------------------|----------|
| **默认进入** | `perf` 已产出 `report/`（无论是否提符号恢复） | 读 `report/` + `perf.db`，执行 §四 各维度聚合 |
| **意图明确** | 含「深挖」「高负载挖掘」「LLM 挖掘」「CPU 指令数」「未知瓶颈」「报告没写」「还有没有别的问题」「弱信号」「动静交叉」等 | 全文流程 + §三 各维度逐项检索 |
| **产物已齐** | `reports_path` 下同时存在 `perf.db`（或内嵌 `perf_sample` 的 `trace.db`）与 SO 静态分析产物（`opt`/`static` 输出、`symbol_recovery` 输出等） | 动静交叉；**禁止**只读 HTML 摘要 |
| **产物部分齐** | 仅有 `perf.db`/`trace.db`（无静态产物），或仅有静态分析产物 | 最大化利用已有源，**显式写明**缺失的另一侧 |
| **结论冲突** | 自动报告「正常/无异常」，但用户描述卡顿、发热、帧率低 | 必须从 `perf_sample` 找矛盾证据 |
| **与 scroll-jank 同时需要** | 问题涉及滑动/掉帧，且同时关心 CPU 指令数 | **同时**加载 `scroll-jank` 与本文；帧结论只按 scroll-jank 规则，指令数分析按本文 |

### 1.1.1 无符号恢复时的降级（默认流程）

默认不跑符号恢复时，按以下规则处理符号维度，**不得伪造**：

| 维度 | 无符号恢复时 |
|------|-------------|
| **SO 级热点**（§四.3.A） | **照常**：`perf_files.path` 即 SO 路径，聚合不受影响 |
| **帧级 / 线程级 / IPC / 空刷**（§四.3.C-E、其余分析器产物） | **照常**：均不依赖符号名 |
| **符号级热点**（§四.3.B） | 若 `perf_files.symbol` 为有效函数名 → 照常；若大量为 `[unknown]` / 十六进制地址 → **标注「该 SO 已 strip，建议触发可选阶段3 `update --so_dir` 符号恢复后重分析」**，**禁止**假装完成符号级分析 |

触发符号恢复后再回到本文做符号级分析。符号恢复流程见 [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) 与 [`../workflow/gen-perf-report.md`](../workflow/gen-perf-report.md)。

### 1.2 最低完成标准（Agent 自检清单）

触发后，深入程度至少达到以下 6 条：

1. **枚举**：列出 `perf.db`（或含 `perf_sample` 的 `trace.db`）真实路径、`report/` 下预聚合 JSON（`so_file_load.json`、`trace_frameLoads.json`、`redundant_thread_analysis.json` 等，见 §2.4）、SO 静态产物路径、`summary.json`（标注「不参与挖掘」）。若某类不存在，写「未找到：已搜索的模式」。
2. **动态 Top 热点**：按 **§四.3.A**（SO 级）和 **§四.3.B**（符号级）的**优先读 JSON → 保底 SQL** 流程，得到 Top-N 热点（`SUM(event_count)` 排序）。
3. **帧级负载**：按 **§四.3.C** 的**优先读 `trace_frameLoads.json` → 保底 SQL** 流程，输出高负载帧列表。
4. **静态交叉**（有产物时）：将动态热点 SO 与静态分析结论（LTO 状态、代码段大小、符号可见性）对齐，在 **§四.4** 中写出「优化机会」条目。
5. **对照 HTML**：单列「HTML 已写明的结论」vs「仅从原始侧可见的额外发现」，后者标为「LLM 挖掘 - 新发现」。
6. **落盘**：独立 `hapray-analysis-*.md`，含 §四.7 结构；**禁止**仅在对话中给结论而不落盘（除非用户只要对话）。

---

## 二、数据源与表结构

### 2.1 动态数据（CPU 指令数）

**核心数据库**：`perf.db`（或 `trace.db` 中内嵌的 perf 表组）

| 表 | 关键字段 | 用途 |
|----|----------|------|
| `perf_sample` | `event_count`（指令数/周期）、`thread_id`、`timestamp_trace`（或 `timeStamp`）、`callchain_id`、`cpu_id` | **主聚合表**；`SUM(event_count)` = 该线程/时间段的总指令数 |
| `perf_callchain` | `callchain_id`、`depth`、`file_id`、`symbol_id`、`vaddr_in_file` | 每个采样的调用栈帧；`depth=0` 为栈顶（leaf 函数） |
| `perf_files` | `file_id`、`serial_id`（= symbol_id）、`symbol`（函数名）、`path`（SO 路径） | 符号与 SO 路径映射 |
| `perf_thread` | `thread_id`、`process_id`、`thread_name` | 线程元信息 |
| `perf_report` | `config_name`（事件类型，如 `raw-instruction-retired`）、`cmdline` | 采集配置核查 |
| `frame_slice` | `ts`、`dur`、`type_desc`、`depth`、`ipid`、`itid`、`flag` | 帧时间边界（与 scroll-jank 一致：`type_desc='actural'` 且 `depth=0`） |
| `callstack` | `name`、`ts`、`dur`、`callid` | trace 级函数切片（用于长耗时排查） |
| `process` / `thread` | `pid`/`tid`、`name` | 进程与线程名 |

**时间戳字段注意**：`perf_sample` 中时间戳字段名因版本而异，使用前先自省：

```bash
sqlite3 /path/to/perf.db "PRAGMA table_info(perf_sample)"
# timestamp_trace（新版）或 timeStamp（旧版）均有可能
```

**事件类型核查**（分析前建议执行）：

```bash
sqlite3 /path/to/perf.db "SELECT config_name, cmdline FROM perf_report"
# 确认 event = raw-instruction-retired，period 值，采集范围
```

> **优先读 JSON、SQL 保底**：`perf` 阶段的 12 个 analyzer 已将大部分维度预聚合到 `report/*.json`（见 §2.4）。这些 JSON 是**原始侧聚合**（非 `summary.json` 摘要），与阶段5 `signal_extractors.py` 读同一批文件。**仅当 JSON 缺失或口径不匹配时才回退到 perf.db SQL**，避免重复聚合。

### 2.2 静态数据（SO 二进制分析）

| 来源 | 路径模式（以实际枚举为准） | 可提取内容 |
|------|---------------------------|------------|
| `hapray opt` / `optimization_detector` 输出 | `<reports_path>/opt/` 下 HTML/JSON/Excel | LTO 状态、`-O2`/`-Os` 标记、符号可见性、代码段大小 |
| `hapray static` 输出 | `static-output/` 下 JSON | SO 列表、框架识别（RN/Flutter/KMP）、SO 大小 |
| `symbol_recovery` 输出 | `tools/symbol_recovery/` 下 Excel/JSON | 恢复的函数名、类型推断 |
| `perf.data` 原始文件 | 与 `perf.db` 同目录 | 可用 `scripts/analyze_so_perf.py` 提取 SO 级热点 |

**动静交叉原则**：动态热点 SO（Top-N by `SUM(event_count)`）→ 查静态产物该 SO 的 LTO 状态、代码大小 → 若未做 LTO 且指令数高，列为「优化机会」。

### 2.3 `summary.json`（排除在外）

若目录中存在 `summary.json`，**可列出路径**并注明**「不参与本次挖掘」**；**禁止**从中复述 Feed/图像/故障树/冗余线程等字段并包装成新发现。

> **禁用范围仅限 `summary.json`**。`so_file_load.json`、`trace_frameLoads.json`、`redundant_thread_analysis.json` 等是 analyzer 直接从 `perf.db`/`trace.db` 提取的**原始侧聚合**（见 §2.4），不是摘要复述，**允许且鼓励**作为主线数据源。

### 2.4 `report/` 下预聚合 JSON（优先数据源）

`perf` 阶段的 analyzer 已将以下维度预聚合为 JSON，**优先直接读取**，与阶段5 `signal_extractors.py` 读同一批文件：

| 维度 | 文件 | 生成者 | 关键字段 | 对应 SQL 保底（§四.3） |
|------|------|--------|----------|----------------------|
| **SO 级负载** | `so_file_load.json` | JS 侧 `sa-cmd` (`perf_analyzer.ts:generateFileLoadJson`)，按 step × .so 聚合 `load`（已过滤应用进程） | `file`、`file_path`、`load`、`step_id` | §四.3.A |
| **帧级负载** | `trace_frameLoads.json` | `UnifiedFrameAnalyzer`，top 高负载帧 | `frame_load`、`dur`、`flag`（1=high 2=empty）、`thread_name` | §四.3.C |
| **冗余线程** | `redundant_thread_analysis.json` | `ThreadAnalyzer` | `redundant_threads`（含 `redundant_instructions`、`waiting_ratio`） | §四.3.D（冗余线程部分） |
| **组件复用** | `trace_componentReuse.json` | `ComponentReusableAnalyzer` | `total_builds`、`recycled_builds`、`reusability_ratio` | — |
| **IPC/Binder** | `trace_ipc_binder.json` | `IpcBinderAnalyzer` | `caller_proc`、`callee_proc`、`count`、`qps` | — |
| **帧率/RS/Vsync** | `trace_frames.json` 等 | `UnifiedFrameAnalyzer` | `avg_fps`、`stutter_rate`、`rs_skip_frames` | — |
| **火焰图全量** | `more_flame_graph.json` | `PerfAnalyzer`（= `perf.json` 全量内容） | `symbolsFileList`、`SymbolMap`、`recordSampleInfo` | §四.3.B（**体积 ~40MB，不可直读，须 SQL 或 Top-N 预聚合**） |

**使用原则**：

1. **优先读 JSON**：上表前 6 个文件体积小（KB 级），直接 `Read` 或 `cat` 即可，**不必再跑 SQL 重复聚合**。
2. **SQL 保底条件**（满足其一才回退）：
   - JSON 文件不存在（analyzer 未跑或失败）
   - JSON 口径与挖掘需求不匹配（如 `trace_frameLoads.json` 的 `frame_load` ≠ 指令数 `event_count`，需要指令数时仍须 SQL）
   - 需要 JSON 未覆盖的 finer 粒度（如 `redundant_thread_analysis.json` 只含冗余线程，全线程指令数分布仍须 SQL）
3. **`more_flame_graph.json` 例外**：体积 ~40MB，**禁止直接 Read**；其符号级 Top-N 须通过 §四.3.B 的 SQL 聚合获取（当前无紧凑 Top-N JSON 产物）。

---

## 三、高指令数可疑模式（检索维度）

以下各维度的**证据须来自 `perf_sample` / `perf_callchain` / `perf_files` 等原始侧**，不得仅凭 HTML 摘要断言。

### 3.1 SO/库级热点（最优先）

- 少数 SO 占全部指令数的异常高比例（参考阈值：Top-1 SO 占比 > 30%）。
- 热点 SO 属于**第三方库或旧版本库**，且静态分析显示未做 LTO——**典型优化机会**。
- 热点 SO 为**系统框架 SO**（如 `libark_jsruntime.so`、`librender_service.so`）但业务场景单一时，可能是调用路径过深或冗余调用。

### 3.2 符号/函数级热点

- `depth=0`（叶子节点）热点符号的 `SUM(event_count)` 显著高于同文件其他符号——该函数本身耗指令多（循环密集、未内联、无 SIMD 优化等）。
- 同一符号在**多个不同调用链**中反复出现，说明该路径被多路驱动——优先优化调用频次而非函数体。
- 符号为 `[unknown]` / 十六进制地址形式——说明 SO 已 strip，需先走 `symbol-recovery` 子 Skill 再分析。

### 3.3 帧级指令数分布

- 指令数最高的帧与普通帧交替出现——尖峰型，通常为某次性操作（解码、IO 回调、首次渲染）触发。
- **连续多帧**均超过阈值——持续型负载，对应持续性循环或后台任务抢占。
- 高负载帧与**手势/滑动阶段**时间重叠——与 scroll-jank 协同，优先标注。

### 3.4 线程维度异常

- **主线程**（UI Thread）的 `SUM(event_count)` 占应用总量比例过高（> 60%），说明工作未充分分线程。
- **Worker 线程**指令数突发增高与主线程高帧延迟同一时间窗口——后台抢占 CPU 资源。
- 进程中出现大量短生命周期线程的高指令数（可能为线程池频繁新建/销毁）。

### 3.5 动静交叉发现的优化机会

| 模式 | 动态证据 | 静态证据 | 优化建议方向 |
|------|----------|----------|-------------|
| 热点 SO 未启用 LTO | `perf_sample` Top SO | `opt` 报告无 LTO 标记 | 启用 LTO 可减少跨函数冗余指令 |
| 热点 SO 代码段偏大 | 高 `event_count` | `static` 报告 `.text` 段大 | 检查是否有大量 inline 膨胀或未使用代码 |
| 符号 strip → 无名 | 大量 `[unknown]` 热点 | SO stripped | 先恢复符号再分析（`symbol-recovery`） |
| 第三方库版本旧 | 热点集中在 libXxx | 静态识别为旧版本 | 升级或替换库 |

### 3.6 跨步骤（step）对比

- 不同步骤（`step1` vs `step2`...）间总指令数差异 > 20%——可能是步骤切换触发了额外初始化或清理。
- 同一操作路径在**多轮采集**间指令数方差大——环境噪声 or 非确定性路径（JIT、懒加载）。

### 3.7 弱信号（需多源印证后才能列入新发现）

- 内核态采样占比高（`perf_callchain` 中 SO 路径含 `[kernel]`）——与 Binder、IO、锁等相关，需结合 `callstack` 中的系统调用切片印证。
- GC/Allocator 相关符号（`libark_jsruntime.so` 中 GC 前缀函数）出现在高负载帧——内存压力与指令数同时升高。

---

## 四、主动挖掘工作流

### 4.1 定位根目录

从 `hapray-tool-result.json` 或用户给出的目录读取 **`reports_path`**，记录为报告根。

### 4.2 全量枚举

列出（可表格）：

- `report/` 下预聚合 JSON（`so_file_load.json`、`trace_frameLoads.json`、`redundant_thread_analysis.json` 等，见 §2.4）——**标注哪些存在可直接读**
- `perf.db` 或内嵌 perf 表的 `trace.db` 的**真实绝对路径**（按 `step*` 子目录分列）——**保底数据源**
- SO 静态分析产物路径（`opt/`、`static-output/`、`symbol_recovery/` 等）
- `perf.data` 原始文件（若存在）
- `summary.json`（列路径并标注「不参与挖掘」）

若某类不存在，写「未找到：已搜索模式 `**/perf.db` 等」。

### 4.3 动态数据：优先读 JSON → 保底 SQL

> **核心原则**：与阶段5 `signal_extractors.py` 对齐——能读 `report/*.json` 的直接读，**不重复聚合**；SQL 仅在 JSON 缺失或口径不匹配时保底。

#### A. SO 级热点（优先执行）

**第一步：读 `so_file_load.json`（优先）**

```bash
# so_file_load.json 已由 sa-cmd 按 step × .so 聚合 load（应用进程已过滤），与下方 SQL 等价
cat <用例>/report/so_file_load.json | python -c "
import json,sys
data=json.load(sys.stdin)
# 按 load 降序，取 Top-20
top=sorted(data, key=lambda x: -x.get('load',0))[:20]
total=sum(r.get('load',0) for r in data) or 1
for r in top:
    print(f'{r[\"file\"]:40s} load={r[\"load\"]:>12,}  pct={r[\"load\"]*100/total:.2f}%  step={r.get(\"step_id\",\"?\")}')
"
```

**第二步：SQL 保底（仅当 `so_file_load.json` 不存在时）**

```sql
-- SO 级总指令数 Top-N（用实际 perf.db 路径替换）
SELECT
    pf.path                          AS so_path,
    SUM(ps.event_count)              AS total_instructions,
    COUNT(*)                         AS sample_count,
    ROUND(SUM(ps.event_count) * 100.0 /
          (SELECT SUM(event_count) FROM perf_sample), 2) AS pct
FROM perf_sample ps
JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
                       AND pc.depth = 0          -- 叶子帧（栈顶函数）
JOIN perf_files pf     ON pc.file_id = pf.file_id
                       AND pc.symbol_id = pf.serial_id
GROUP BY pf.path
ORDER BY total_instructions DESC
LIMIT 20;
```

#### B. 符号级热点（对 Top-3 SO 执行）

> **当前无紧凑 Top-N JSON 产物**（`more_flame_graph.json` ~40MB 不可直读），本维度**须 SQL 聚合**。若未来新增 `symbol_load_topN.json`，应优先读 JSON。

```sql
-- 指定 SO 内符号级 Top-N
SELECT
    pf.symbol                        AS func_name,
    pf.path                          AS so_path,
    SUM(ps.event_count)              AS total_instructions,
    ROUND(SUM(ps.event_count) * 100.0 /
          (SELECT SUM(event_count) FROM perf_sample), 2) AS pct_global
FROM perf_sample ps
JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
                       AND pc.depth = 0
JOIN perf_files pf     ON pc.file_id = pf.file_id
                       AND pc.symbol_id = pf.serial_id
WHERE pf.path LIKE '%libXxx.so%'     -- 替换为目标 SO 名
GROUP BY pf.symbol
ORDER BY total_instructions DESC
LIMIT 30;
```

#### C. 帧级负载（优先读 JSON → 保底 SQL）

**第一步：读 `trace_frameLoads.json`（优先）**

```bash
# trace_frameLoads.json 已由 UnifiedFrameAnalyzer 聚合 top 高负载帧
cat <用例>/report/trace_frameLoads.json | python -c "
import json,sys
data=json.load(sys.stdin)
for step_id, step in data.items():
    stats=step.get('statistics',{})
    print(f'=== {step_id} === total={stats.get(\"total_frames\",\"?\")} high_load={stats.get(\"high_load_frames\",\"?\")} max={stats.get(\"max_load\",\"?\")}')
    for fr in (step.get('top_frames') or [])[:10]:
        flag='empty' if fr.get('flag')==2 else 'high'
        print(f'  load={fr.get(\"frame_load\",0):>10}  dur={fr.get(\"dur\",0):>12}ns  {flag}  thread={fr.get(\"thread_name\",\"?\")}')
"
```

**第二步：SQL 保底（仅当需要「逐帧指令数」口径且 JSON 不满足时）**

> `trace_frameLoads.json` 的 `frame_load` 与 `perf_sample.event_count` 口径可能不同；**仅当明确需要 `SUM(event_count)` per frame 时才跑下方 SQL**。

先自省时间戳字段名：

```bash
sqlite3 /path/to/perf.db "PRAGMA table_info(perf_sample)"
# 若含 timestamp_trace 用该字段；否则用 timeStamp
```

再执行帧级查询（将 `ps.timestamp_trace` 替换为实际字段名）：

若 `frame_slice` 与 `perf_sample` 在**同一文件**（trace.db 内嵌 perf 表），直接执行：

```sql
SELECT
    fs.ts                            AS frame_ts,
    fs.dur                           AS frame_dur_ns,
    fs.vsync,
    COALESCE(SUM(ps.event_count), 0) AS frame_instructions
FROM frame_slice fs
LEFT JOIN perf_sample ps
       ON ps.timestamp_trace        -- ← 按自省结果替换为 timestamp_trace 或 timeStamp
          BETWEEN fs.ts AND (fs.ts + fs.dur)
WHERE fs.type_desc = 'actural'      -- 与 scroll-jank 规则一致
  AND fs.depth = 0
GROUP BY fs.id
ORDER BY frame_instructions DESC
LIMIT 30;
```

若二者在**不同文件**（trace.db + perf.db 分离），将 ATTACH 放在 SQL 开头一并执行：

```sql
ATTACH '/path/to/perf.db' AS pdb;  -- 替换为实际 perf.db 路径

SELECT
    fs.ts                            AS frame_ts,
    fs.dur                           AS frame_dur_ns,
    fs.vsync,
    COALESCE(SUM(ps.event_count), 0) AS frame_instructions
FROM frame_slice fs
LEFT JOIN pdb.perf_sample ps        -- 使用 pdb. 前缀访问 perf.db 中的表
       ON ps.timestamp_trace        -- ← 按自省结果替换为 timestamp_trace 或 timeStamp
          BETWEEN fs.ts AND (fs.ts + fs.dur)
WHERE fs.type_desc = 'actural'
  AND fs.depth = 0
GROUP BY fs.id
ORDER BY frame_instructions DESC
LIMIT 30;
```

#### D. 线程维度（优先读 JSON → 保底 SQL）

**第一步：读 `redundant_thread_analysis.json`（优先，覆盖冗余线程）**

```bash
# redundant_thread_analysis.json 已由 ThreadAnalyzer 聚合冗余线程
cat <用例>/report/redundant_thread_analysis.json | python -c "
import json,sys
data=json.load(sys.stdin)
for step_id, step in data.items():
    rs=step.get('redundant_threads_summary',{})
    print(f'=== {step_id} === redundant_threads={rs.get(\"total_redundant_threads\",0)} redundant_instructions={rs.get(\"total_redundant_instructions\",0)}')
    for t in (rs.get('redundant_threads') or [])[:10]:
        print(f'  {t.get(\"thread_name\",\"?\"):30s} type={t.get(\"type\",\"?\"):10s} instr={t.get(\"redundant_instructions\",0):>12}  wait_ratio={t.get(\"waiting_ratio\",0)}')
"
```

**第二步：SQL 保底（仅当需要「全线程指令数分布」且 JSON 不覆盖时）**

> `redundant_thread_analysis.json` 只含**冗余**线程。**全线程**（含主线程）指令数分布仍须 SQL。

先确认目标应用的 `process_id`：

```sql
-- 第一步：列出所有进程，找到目标应用的 process_id
SELECT DISTINCT process_id, thread_name
FROM perf_thread
ORDER BY process_id;
```

再按 `process_id` 过滤各线程指令数：

```sql
-- 目标应用进程各线程指令数（将 <PID> 替换为上方查询得到的实际 process_id）
SELECT
    pt.thread_name,
    SUM(ps.event_count)              AS total_instructions,
    ROUND(SUM(ps.event_count) * 100.0 /
          (SELECT SUM(ps2.event_count)
           FROM perf_sample ps2
           JOIN perf_thread pt2 ON ps2.thread_id = pt2.thread_id
           WHERE pt2.process_id = <PID>), 2) AS pct
FROM perf_sample ps
JOIN perf_thread pt ON ps.thread_id = pt.thread_id
WHERE pt.process_id = <PID>
GROUP BY ps.thread_id
ORDER BY total_instructions DESC
LIMIT 20;
```

#### E. 跨步骤对比（多 step 时执行）

对每个 `stepN` 分别取 §4.3.A 的 JSON 结果（`so_file_load.json` 按 `step_id` 分列）或保底 SQL 结果，汇总表格比较各步骤 `total_instructions`。

### 4.4 静态数据交叉

1. 取 §4.3.A Top-5 热点 SO，在 `opt`/`static` 产物中检索各 SO 的：
   - LTO 是否启用（`-flto`、LTO 标记）
   - 代码段（`.text`）大小
   - Strip 状态（是否有符号表）
2. 将结果填入 §三.3.5 的「动静交叉发现」表。
3. 若某热点 SO 的符号全为 `[unknown]` 或十六进制，**标记为「需 symbol-recovery」**，并在最终报告的「未覆盖/数据不足」中说明。

### 4.5 与自动报告对照

逐条列出：

- **HTML / `report/*.json` 已写明的结论**（热点 SO、帧率数值、冗余线程等）
- **仅从原始侧（`perf_sample`/`perf_callchain`/静态产物）可见的额外发现** → 标为「LLM 挖掘 - 新发现」

**禁止**把 `summary.json` 字段与 HTML 的「字段对齐」当作新发现来源；**也禁止**把 `so_file_load.json` 等 JSON 的已有聚合复述为新发现——新发现须是 JSON/HTML **未直接陈述**的额外洞察。

### 4.6 LLM 推理任务（显式）

对每条证据请模型回答：

1. **分类**：SO级热点 / 符号级热点 / 帧级负载 / 线程争抢 / 动静交叉优化机会
2. **独立性**：是否构成独立优化问题（与其他已知问题无重叠）
3. **可能原因**：若 HTML 未提及，说明可能的代码/架构原因
4. **验证步骤**：一条可执行 SQL 或命令（`sqlite3`/`python`/`rg`）

**禁止**把缺乏数据支撑的猜测写成确定结论；**禁止**从 `summary.json` 复述规则化结论并包装成「新发现」。

### 4.7 落盘

**一份采集数据（同一 `reports_path`）只对应一份 `hapray-analysis-*.md`**；后续补充默认在原文件上更新。  
默认路径：`<PROJECT_ROOT>/reports/hapray-analysis-*.md`（不与 `reports_path` 混淆）。

该 `.md` 须包含：

- **报告元信息**（文末必填，见主 `SKILL.md`）
- **数据范围**（真实路径列表；`summary.json` 单独注明「不参与挖掘」）
- **高指令数热点表**（对应 §三，每条含：SO/符号、指令数、占比、**来源 JSON 或 SQL**）
- **动静交叉优化机会表**（§三.3.5）
- **新发现**（每条：现象、可追溯证据、与 HTML 差异、风险/影响等级、建议验证步骤）
- **未覆盖/数据不足**（诚实列出；含「需 symbol-recovery」的 SO）

8. **单源模式（仅 `trace.db`）**  
   当缺少 perf 与日志时，必须至少完成：
   - 主进程/主线程定位（与 scroll-jank 一致）；  
   - `callstack` Top 耗时与 Top 频次各一组聚合；  
   - 若涉及帧，补充 `frame_slice`（`type_desc=actural`、`depth=0`）统计；  
   - 输出 **「单源结论」** 与 **「不可验证假设」** 分栏；  
   - 在「未覆盖/数据不足」中明确写：缺少 perf/log，无法完成多源交叉。

---

## 五、与其他 Skill 的协作

| 文档 | 关系 |
|------|------|
| [`../SKILL.md`](../SKILL.md) | CLI、契约、`gui-agent` 前置条件、独立 `.md` 命名与落盘规则 |
| [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | **帧与手势**的权威规则与 SQL；帧级指令数与帧结论须保持一致 |
| [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 当热点函数为 `[unknown]`/stripped 时**必须先执行**，再回到本文分析 |
| [`../schemas/hapray-tool-result.md`](../schemas/hapray-tool-result.md) | 定位 `reports_path` 与契约字段 |
| [`../root-cause/comprehensive.md`](../root-cause/comprehensive.md) | 阶段5 根因分析；CLI 的 `signal_extractors` 会独立读取同一原始产物，Agent 做补充深挖时应**优先引用阶段4已挖出的线索**，避免重复 |

### 与阶段5的分工

| 维度 | 阶段4（本 Skill） | 阶段5 root-cause |
|------|------------------|------------------|
| 目标 | 发现线索与假设 | 确认根因 + 源码级定位 |
| 手段 | Agent 读 JSON + 保底 SQL + 数据探索 | CLI 自动多信号提取 + LLM/Agent 推断 |
| 产出 | 高负载热点表 + 新发现 | `root_cause.md` + Agent 源码级补充 |
| 数据源 | 同一原始产物（`report/` JSON + 保底 `perf.db`） | CLI 独立提取（读同一批 `report/*.json`），不依赖阶段4产出 |

**注意**：阶段5 CLI 的 `signal_extractors`（`SoLoadEvidenceExtractor` 读 `so_file_load.json`、`FrameLoadEvidenceExtractor` 读 `trace_frameLoads.json` 等）与本 Skill §四.3 **读同一批 JSON**。本 Skill 改为 JSON 优先后，**阶段4与阶段5的数据源完全对齐**，仅在分析深度和产出格式上不同：本 Skill 侧重**人工发现与验证**，CLI 侧重**自动推断**。Agent 在阶段5做补充深挖时，应引用本阶段的发现而非从零重做。

---

## 六、新发现判定门槛（硬规则）

满足以下全部条件，才可标记为 **「LLM 挖掘 - 新发现」**：

1. **自动报告未明确给出**：HTML 或 `report/*.json`（`so_file_load.json`、`trace_frameLoads.json` 等）中未直接陈述该问题。  
2. **证据可追溯**：至少满足其一：  
   - 双源证据（例如 trace + perf，或 trace + 日志）；  
   - 单源强证据（仅 trace 但具备稳定重复的聚合结果）+ 一条反证说明。  
3. **可复验**：附至少 **1 条命令或 SQL**，可在同一报告根目录复现观察。

若任一不满足，只能标记为 **「候选问题（待验证）」**，不得写成确定结论。

---

## 七、禁止与质量约束

- **禁止**虚构路径、表名、栈名、百分比与指令数。
- **禁止**仅根据行业常识输出「热点清单」而不引用本轮**真实产物**的输出（JSON 或 SQL）。
- **禁止**以 `summary.json` 作为 LLM 高负载挖掘的主线数据源。
- **禁止**对 `report/` 下已有预聚合 JSON（`so_file_load.json` 等，见 §2.4）重复跑 SQL 聚合——**优先读 JSON，SQL 仅保底**（JSON 缺失或口径不匹配时）。
- 「新发现」每条须带：**文件路径 + 查询/命令**可追溯证据（来自原始侧，非 summary 字段复述）；若为推测，标注**「待验证」**并给出验证步骤。
- 若仅有 `trace.db` 无独立 `perf.db`，先检查 `trace.db` 中是否存在 `perf_sample` 表（`sqlite3 trace.db ".tables"`），再决定是否可执行 §四.3 的保底 SQL。
- 若热点符号大量为 `[unknown]`，**不得**假装完成「符号级分析」；应在报告中标注「需 symbol-recovery 后重分析」。

---

## 八、触发词（供主 Skill 索引）

`CPU指令数`、`高负载挖掘`、`LLM挖掘`、`动静交叉`、`perf_sample`、`perf热点`、`SO级指令数`、`符号级热点`、`帧级负载`、`原始trace`、`报告未覆盖`、`未知瓶颈`、`多源交叉`、`主动发现`、`深挖`、`弱信号`、`结论冲突`、`尽可能深入`、`第二源`、`交叉印证`。
