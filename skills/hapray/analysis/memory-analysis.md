# 内存分析（Native Memory 分配/释放/泄漏 + 一级内存趋势）

> **核心度量**：本文中 **「内存」= Native 堆内存** —— 即 `native_hook` 表中的 malloc/free/mmap/munmap 事件（hiprofiler nativehook 插件采集），以 `heapSize` 正负值表达分配/释放。
> **分析目标**：通过 **未释放内存检测（LIFO 地址匹配）**、**组件分类聚合**、**调用链精化** 与 **一级内存时序（meminfo）** 的交叉，挖掘内存泄漏、超额分配、异常增长等问题。
> **与 high-load 的关系**：high-load 以 `perf_sample.event_count`（CPU 指令数）为主线，本文以 `native_hook`（内存事件）为主线，两者数据源独立、互不依赖，可联合采集（`perf --memory`）。

---

## 一、触发条件与最低完成标准

### 1.1 必须加载的触发条件（满足任一条即强制）

> **默认进入**：当 `perf` 使用 `--memory` 参数采集时，`hapray_report.db` 中 `memory_records` 表有数据 → 强制进入本文。未开 `--memory` 时该表为空，本文**跳过**。

| 类别 | 用户表述或客观信号 | 必须行为 |
|------|--------------------|----------|
| **默认进入** | `--memory` 采集产出 `hapray_report.db` 含 `memory_records` 数据 | 读 `hapray_report.db` + `memory_report.xlsx`，执行 §四 各维度分析 |
| **意图明确** | 含「内存分析」「内存泄漏」「memory leak」「未释放」「native memory」「meminfo」「内存增长」「内存占用」「GC 频繁」等 | 全文流程 + §三 各维度逐项检索 |
| **产物已齐** | `hapray_report.db` 存在且 `memory_records` 表有数据 + `memory_report.xlsx` 存在 | 完整分析；**禁止**只读 HTML 摘要 |
| **产物部分齐** | 仅有 `memory_report.xlsx` 无 `hapray_report.db`，或反之 | 最大化利用已有源，**显式写明**缺失的数据源 |
| **GC 异常信号** | `gc_analyzer` 产物显示 `GCStatus = 'Too many GC'` 或 GC 线程负载 > 15% | 必须执行 §四.6 GC 压力关联分析 |

### 1.2 数据源降级场景

| 场景 | `memory_records` | `gc_analyzer` 产物 | `meminfo/` | 说明 |
|------|------------------|-------------------|-----------|------|
| 联合采集（`perf --memory`） | ✅ 有数据 | ✅ 可用（有 `perf.db` + `trace.db`） | ✅ 有 | 完整内存分析 + GC 关联 |
| 纯内存（`--no-trace --no-perf --memory`） | ✅ 有数据 | ❌ 不可用（无 `perf.db` + `trace.db`） | ✅ 有 | 仅做 memory 主线分析；GC 章节标注「纯内存模式，GC 数据不可用」 |
| 未开 `--memory`（常规 perf） | ❌ 空或不存在 | ✅ 可用（有 `perf.db` + `trace.db`） | ❌ 无 | 本文跳过；GC 可独立分析（不依赖 `--memory`） |

> **建议**：在阶段 4 评估时，若用户未开 `--memory` 但描述了内存相关问题，应提示「建议使用 `--memory` 参数重新采集以启用内存分析」。

### 1.3 最低完成标准（Agent 自检清单）

触发后，深入程度至少达到以下 6 条：

1. **枚举**：列出 `hapray_report.db` 真实路径、`memory_report.xlsx` 路径、`meminfo/` 目录路径、`trace.db` 路径。若某类不存在，写「未找到：已搜索的模式」。
2. **内存概览**：按 **§四.1** 查询 `memory_results` 表，输出每个 step 的 `peak_time` 和 `records_count`。
3. **组件分配**：按 **§四.2** 聚合 `memory_records`，输出按 `componentCategory` 的分配/释放/净内存表。
4. **未释放分析**：读 **§四.3** `memory_report.xlsx` 的 `MemoryUnreleased` sheet，输出峰值时刻和结束时刻的 Top 未释放 callchain。
5. **meminfo 趋势**（有数据时）：按 **§四.5** 查询 `memory_meminfo` 表，输出 smaps/GPU/DMA 时序趋势。
6. **落盘**：独立 `hapray-analysis-*-memory-*.md`，含 [memory-deliverable](../report/memory-deliverable.md) 结构；**禁止**仅在对话中给结论而不落盘（除非用户只要对话）。

---

## 二、数据源与表结构

### 2.1 核心数据库：`hapray_report.db`

位于 `<用例>/report/hapray_report.db`，由 `MemoryAnalyzer` 写入。采用**紧凑存储 + 视图**设计：

| 表/视图 | 作用 | 关键字段 |
|---------|------|----------|
| `memory_results` | step 汇总 | `step_id`、`peak_time`、`records_count` |
| `memory_records` | 明细记录（紧凑存储，字符串 ID 化） | `pid`、`processId`、`tid`、`threadId`、`fileId`、`symbolId`、`eventTypeId`、`addr`、`callchainId`、`heapSize`（正=分配，负=释放）、`relativeTs`、`componentNameId`、`componentCategory`（INTEGER）、`categoryNameId`、`subCategoryNameId` |
| `memory_data_dicts` | 字典表（dictId → value 去重字符串） | `dictId`、`value`、`step_id` |
| `memory_callchains_raw` | 调用链帧原始存储 | `callchainId`、`depth`、`ip`、`symbolId`、`fileId`、`offset`、`symbolOffset`、`vaddr` |
| `memory_callchains` | 视图：联表 data_dicts 展开符号/文件名 | 同上 + `symbol`(TEXT) + `file`(TEXT) |
| `memory_meminfo` | 一级内存（JSON 存储，动态分类） | `timestamp`、`timestamp_epoch`、`data`(JSON) |

**componentCategory 枚举值**（与 TypeScript 枚举一致）：

| 值 | 常量 | 说明 |
|----|------|------|
| 0 | APP_ABC | 应用 ArkTS 字节码（.abc） |
| 1 | APP_SO | 应用 native 库（.so） |
| 2 | APP_LIB | 应用其他库 |
| 3 | OS_Runtime | OS 运行时 |
| 4 | SYS_SDK | 系统库（默认分类） |
| 5 | RN | React Native |
| 6 | Flutter | Flutter |
| 7 | WEB | Web |
| 8 | KMP | Kotlin Multiplatform |
| -1 | UNKNOWN | 未知 |

**heapSize 存储规则**：分配事件（AllocEvent/MmapEvent）为正数，释放事件（FreeEvent/MunmapEvent）为负数。

### 2.2 原始数据库：`trace.db`

位于 `<用例>/htrace/step*/trace.db`，包含 hiprofiler nativehook 原始表：

| 表 | 关键字段 | 用途 |
|----|----------|------|
| `native_hook` | `id`、`callchain_id`、`ipid`、`itid`、`event_type`、`sub_type_id`、`start_ts`、`addr`、`heap_size`、`last_lib_id`、`last_symbol_id` | 原始内存事件 |
| `native_hook_frame` | `callchain_id`、`depth`、`ip`、`symbol_id`、`file_id` | 调用链帧 |
| `data_dict` | `id`、`data` | 符号/文件名映射 |
| `process` / `thread` | `ipid`/`itid`、`pid`/`tid`、`name` | 进程线程信息 |

> 通常无需直接查询 `trace.db`——`hapray_report.db` 已完成数据清洗、分类、ID 字典化。仅在需要验证原始数据时回退。

### 2.3 Excel 报告：`memory_report.xlsx`

位于 `<用例>/report/memory_report.xlsx`，包含 4 个 sheet：

| Sheet | 内容 |
|-------|------|
| `MemoryUnreleased` | 未释放内存明细（peak + end 两时间点），含 callchainId、size、count、pid、process、symbol 等 |
| `Summary_ByCategory` | 按大类汇总未释放量 |
| `Summary_ByCategorySub` | 按大类+小类汇总未释放量 |
| `Meminfo` | 一级内存时序数据（字节转 MB），含 smaps/GPU/DMA 各分类 |

### 2.4 meminfo 目录

位于 `<用例>/meminfo/step*/`，包含设备侧周期采集的文本文件：

| 子目录 | 内容 | 文件格式 |
|--------|------|----------|
| `dynamic_showmap/` | smaps 内存（PSS + SwapPss） | `*.txt`，按 Category 分类 |
| `dynamic_gpuMem/` | GPU 内存 | `*.txt`，按 PID 过滤 |
| `dynamic_process_dmabuff_info/` | DMA 内存 | `*.txt`，按 buf_type 分类 |

### 2.5 GC 分析产物

GC 分析由 `GCAnalyzer` 自动执行（不依赖 `--memory`），产物在 `hapray_report.db` 或 report JSON 中：

| 产物 | 内容 |
|------|------|
| GC 线程负载 | `OS_GC_Thread` 的 `SUM(event_count)` 占应用总指令数比例（阈值 > 15%） |
| GC 调用次数 | FullGC / SharedFullGC / SharedGC / PartialGC 各类型计数 |
| GC 频率 | 调用次数 > 10 且频率 > 1次/s → `Too many GC` |

---

## 三、内存可疑模式（检索维度）

以下各维度的**证据须来自 `memory_records` / `memory_callchains` / `memory_meminfo` / `memory_report.xlsx` 等原始侧**，不得仅凭 HTML 摘要断言。

### 3.1 内存峰值异常

- 峰值时刻（`peak_time`）的净内存显著高于平均水平——尖峰型，通常为某次大对象分配或批量加载。
- 峰值后未回落到基线水平——可能是泄漏或缓存未释放。
- 多步骤间峰值持续上升——阶梯型增长，典型泄漏信号。

### 3.2 未释放内存（泄漏检测）

- **峰值时刻未释放量**大——在内存最高点时，有大量分配未匹配到释放。
- **结束时刻未释放量**大——采集结束时仍有大量未释放，强泄漏信号。
- 同一 callchainId 下多个 (pid, tid) 聚合的未释放 count 高——同一调用路径反复分配未释放。
- 未释放量集中在特定组件（如 APP_SO / APP_ABC）——指向该组件的泄漏点。

### 3.3 组件分类分配集中

- 某组件大类（如 `APP_SO`）的净内存占比异常高（> 50%）——该组件的 native 库是内存消耗主体。
- `APP_ABC` 净内存高——ArkTS 堆内存增长，可能与 JS 对象累积、闭包泄漏有关。
- `SYS_SDK` 分配量大但释放量也大——系统库正常生命周期行为，非泄漏。
- `RN` / `Flutter` / `KMP` 组件分配高——第三方框架内存开销，需结合场景评估。

### 3.4 调用链聚集

- 多个未释放分配指向**同一 callchainId**——同一调用栈反复分配未释放，强泄漏信号。
- 调用链精化后的首个非系统帧指向业务代码——可定位到具体源码位置。
- 调用链深度较深（depth > 10）——调用路径过深可能导致中间层持有引用。

### 3.5 一级内存趋势异常（meminfo）

- smaps 总量持续上升不回落——进程虚拟内存持续增长，可能泄漏。
- GPU 内存突增——大量图片/纹理加载，需结合场景评估是否合理。
- DMA `dma_pixelmap` 类型增长——PixelMap 未释放，图片泄漏信号。
- `.hap` 类别 smaps 占比过高——应用自身内存占比大。
- `AnonPage other(ArkTS)` 增长——ArkTS 堆内存增长。

### 3.6 GC 压力关联

- GC 线程负载 > 15%——内存压力导致频繁 GC。
- GC 频率 > 1次/s 且总次数 > 10——短时间大量 GC，可能内存分配过快或泄漏触发回收。
- GC 高发时段与内存峰值时间重叠——峰值触发 GC 回收。
- FullGC / SharedFullGC 次数多——老年代回收频繁，对象长期存活。

### 3.7 事件类型分布异常

- `AllocEvent` 数量远大于 `FreeEvent`——分配/释放不对称，部分内存未释放。
- `MmapEvent` 的 subEventType 中某类型占比高——特定类型的 mmap 分配集中（如 anonymous、file-backed）。
- `MmapEvent` 净内存大但 `AllocEvent` 正常——大块 mmap 映射未 munmap。

---

## 四、主动挖掘工作流

### 4.1 定位根目录与数据源枚举

从 `hapray-tool-result.json` 或用户给出的目录读取 **`reports_path`**，然后枚举：

```bash
# 检查 hapray_report.db 是否存在且有 memory_records 表
sqlite3 <用例>/report/hapray_report.db ".tables" | grep memory

# 检查 memory_report.xlsx 是否存在
ls -la <用例>/report/memory_report.xlsx

# 检查 meminfo 目录
ls <用例>/meminfo/step*/ 2>/dev/null

# 检查 trace.db 是否有 native_hook 表
sqlite3 <用例>/htrace/step*/trace.db ".tables" | grep native_hook
```

若 `memory_records` 表不存在或为空，标注「未开启 `--memory` 采集，内存分析不可用」，本文跳过。

### 4.2 内存概览

```sql
-- 各 step 的内存概览
SELECT step_id, peak_time, records_count
FROM memory_results
ORDER BY step_id;
```

### 4.3 组件分类分配聚合

```sql
-- 按组件大类聚合分配/释放/净内存
SELECT
    r.componentCategory,
    CASE r.componentCategory
        WHEN 0 THEN 'APP_ABC'
        WHEN 1 THEN 'APP_SO'
        WHEN 2 THEN 'APP_LIB'
        WHEN 3 THEN 'OS_Runtime'
        WHEN 4 THEN 'SYS_SDK'
        WHEN 5 THEN 'RN'
        WHEN 6 THEN 'Flutter'
        WHEN 7 THEN 'WEB'
        WHEN 8 THEN 'KMP'
        ELSE 'UNKNOWN'
    END AS category_name,
    SUM(CASE WHEN r.heapSize > 0 THEN r.heapSize ELSE 0 END) AS total_alloc,
    SUM(CASE WHEN r.heapSize < 0 THEN ABS(r.heapSize) ELSE 0 END) AS total_free,
    SUM(r.heapSize) AS net_mem,
    COUNT(*) AS event_count
FROM memory_records r
WHERE r.step_id = ?    -- 替换为实际 step_id
GROUP BY r.componentCategory
ORDER BY net_mem DESC;
```

### 4.4 进程/线程维度聚合

```sql
-- 按进程+线程聚合净内存
SELECT
    r.pid,
    d_proc.value AS process_name,
    r.tid,
    d_thread.value AS thread_name,
    SUM(CASE WHEN r.heapSize > 0 THEN r.heapSize ELSE 0 END) AS total_alloc,
    SUM(CASE WHEN r.heapSize < 0 THEN ABS(r.heapSize) ELSE 0 END) AS total_free,
    SUM(r.heapSize) AS net_mem,
    COUNT(*) AS event_count
FROM memory_records r
LEFT JOIN memory_data_dicts d_proc
    ON d_proc.dictId = r.processId AND d_proc.step_id = r.step_id
LEFT JOIN memory_data_dicts d_thread
    ON d_thread.dictId = r.threadId AND d_thread.step_id = r.step_id
WHERE r.step_id = ?
GROUP BY r.pid, r.tid
ORDER BY net_mem DESC
LIMIT 20;
```

### 4.5 未释放内存（泄漏检测）

**未释放检测算法**已在 Python 侧实现（`MemoryAggregator.get_unreleased_by_callchain`），采用 **LIFO 地址匹配**：

- 分配事件（heapSize > 0）按地址压栈
- 释放事件（heapSize < 0）按地址 LIFO 弹栈扣减
- 剩余活跃分配按 callchainId 聚合，再按 (pid, tid) 二次聚合

**Agent 读取方式**：直接读 `memory_report.xlsx` 的 `MemoryUnreleased` sheet（已含 peak + end 两时间点的聚合结果）。

```bash
# 用 Python 读取 Excel 的未释放数据
python3 -c "
import pandas as pd
df = pd.read_excel('<用例>/report/memory_report.xlsx', sheet_name='MemoryUnreleased')
# 按 point (peak/end) 分组，取 Top-10 未释放
for point in df['point'].unique():
    sub = df[df['point']==point].nlargest(10, 'size')
    print(f'=== {point} ===')
    for _, r in sub.iterrows():
        print(f'  callchainId={r[\"callchainId\"]:>6}  size={r[\"size\"]:>12}  count={r[\"count\"]:>4}  '
              f'symbol={r.get(\"symbol\",\"?\"):30s}  file={r.get(\"file\",\"?\")}')
"
```

**也可通过 SQL 模拟简化版**（按 callchainId 聚合净 heapSize，仅看分配>释放的调用链）：

```sql
-- 简化版：按 callchainId 聚合净内存（分配 - 释放），仅看净正值的调用链
SELECT
    r.callchainId,
    SUM(r.heapSize) AS net_mem,
    COUNT(*) AS event_count,
    d_file.value AS file_name,
    d_sym.value AS symbol_name
FROM memory_records r
LEFT JOIN memory_data_dicts d_file
    ON d_file.dictId = r.fileId AND d_file.step_id = r.step_id
LEFT JOIN memory_data_dicts d_sym
    ON d_sym.dictId = r.symbolId AND d_sym.step_id = r.step_id
WHERE r.step_id = ? AND r.callchainId IS NOT NULL
GROUP BY r.callchainId
HAVING net_mem > 0
ORDER BY net_mem DESC
LIMIT 20;
```

> **注意**：SQL 简化版不包含 LIFO 地址匹配逻辑，仅按 callchainId 聚合净 heapSize。完整未释放检测以 `memory_report.xlsx` 的 `MemoryUnreleased` sheet 为准。

### 4.6 调用链分析

```sql
-- 查询指定 callchainId 的调用链帧（已展开符号/文件名）
SELECT
    mc.callchainId,
    mc.depth,
    mc.symbol,
    mc.file,
    mc.ip
FROM memory_callchains mc
WHERE mc.step_id = ? AND mc.callchainId = ?
ORDER BY mc.depth;
```

**解读规则**（对应 `CallchainRefiner` 的精化逻辑）：
- `depth` 从大到小遍历（最底层用户代码 → 最顶层系统入口）
- 首个非系统帧（file 不匹配 `callchain_filter` 排除规则）即为**精化后的责任帧**
- 若所有帧均为系统帧，取 depth 最小的有效帧兜底

### 4.7 一级内存趋势（meminfo）

```sql
-- 查询 meminfo 时序数据（JSON 存储）
SELECT
    timestamp,
    timestamp_epoch,
    data
FROM memory_meminfo
WHERE step_id = ?
ORDER BY timestamp_epoch;
```

**JSON 解析**（用 Python 展开）：

```bash
python3 -c "
import json, sqlite3
conn = sqlite3.connect('<用例>/report/hapray_report.db')
rows = conn.execute('SELECT timestamp_epoch, data FROM memory_meminfo WHERE step_id=? ORDER BY timestamp_epoch', (1,)).fetchall()
for ts, data_json in rows:
    d = json.loads(data_json)
    # 打印关键指标（字节转 MB）
    gpu_mb = d.get('gpu', 0) / 1048576
    hap_mb = d.get('.hap', 0) / 1048576
    so_mb = d.get('.so', 0) / 1048576
    dma_pm_mb = d.get('dma_pixelmap', 0) / 1048576
    print(f'ts={ts}  gpu={gpu_mb:.1f}MB  hap={hap_mb:.1f}MB  so={so_mb:.1f}MB  dma_pixelmap={dma_pm_mb:.1f}MB')
conn.close()
"
```

**也可直接读 Excel 的 `Meminfo` sheet**（已转为 MB）：

```bash
python3 -c "
import pandas as pd
df = pd.read_excel('<用例>/report/memory_report.xlsx', sheet_name='Meminfo')
print(df.columns.tolist())
print(df.head(10))
# 计算各列的变化趋势
for col in df.columns:
    if col not in ['step', 'timestamp', 'timestamp_epoch']:
        first = df[col].iloc[0]
        last = df[col].iloc[-1]
        delta = last - first
        print(f'{col:40s}  first={first:.1f}MB  last={last:.1f}MB  delta={delta:+.1f}MB')
"
```

### 4.8 GC 压力关联

> **前置条件**：GC 分析依赖 `perf.db`（GC 线程负载）和 `trace.db`（GC 调用次数/频率）。**纯内存模式**（`--no-trace --no-perf --memory`）下两者均不存在，本节跳过，标注「纯内存模式，GC 数据不可用」。

GC 数据由 `GCAnalyzer` 自动产出（不依赖 `--memory`，但依赖 `perf.db` + `trace.db`），可在 report JSON 或 `hapray_report.db` 中查找：

```sql
-- 从 perf.db 查 GC 线程负载（需替换 <PID> 为应用 process_id）
-- 注意：纯内存模式下 perf.db 不存在，此查询不可用
sqlite3 <用例>/htrace/step*/perf.db "
SELECT
    pt.thread_name,
    SUM(ps.event_count) AS gc_instructions,
    ROUND(SUM(ps.event_count) * 100.0 /
        (SELECT SUM(ps2.event_count) FROM perf_sample ps2
         JOIN perf_thread pt2 ON ps2.thread_id = pt2.thread_id
         WHERE pt2.process_id IN (<PID>)), 2) AS pct
FROM perf_sample ps
JOIN perf_thread pt ON ps.thread_id = pt.thread_id
WHERE pt.thread_name = 'OS_GC_Thread'
  AND pt.process_id IN (<PID>)
GROUP BY pt.thread_id;
"
```

**GC 异常判定**（对应 `GCAnalyzer` 逻辑）：
- GC 线程负载 > 15% → `Too many GC`
- GC 调用次数 > 10 且频率 > 1次/s → `Too many GC`

### 4.9 事件类型分布

```sql
-- 按事件类型聚合
SELECT
    d_evt.value AS event_type,
    d_sub.value AS sub_event_type,
    SUM(CASE WHEN r.heapSize > 0 THEN r.heapSize ELSE 0 END) AS total_alloc,
    SUM(CASE WHEN r.heapSize < 0 THEN ABS(r.heapSize) ELSE 0 END) AS total_free,
    SUM(r.heapSize) AS net_mem,
    COUNT(*) AS event_count
FROM memory_records r
LEFT JOIN memory_data_dicts d_evt
    ON d_evt.dictId = r.eventTypeId AND d_evt.step_id = r.step_id
LEFT JOIN memory_data_dicts d_sub
    ON d_sub.dictId = r.subEventTypeId AND d_sub.step_id = r.step_id
WHERE r.step_id = ?
GROUP BY r.eventTypeId, r.subEventTypeId
ORDER BY net_mem DESC;
```

### 4.10 跨步骤对比

```sql
-- 各步骤净内存对比
SELECT
    r.step_id,
    SUM(CASE WHEN r.heapSize > 0 THEN r.heapSize ELSE 0 END) AS total_alloc,
    SUM(CASE WHEN r.heapSize < 0 THEN ABS(r.heapSize) ELSE 0 END) AS total_free,
    SUM(r.heapSize) AS net_mem,
    COUNT(*) AS event_count,
    mr.peak_time
FROM memory_records r
LEFT JOIN memory_results mr ON mr.step_id = r.step_id
GROUP BY r.step_id
ORDER BY r.step_id;
```

---

## 五、与其他 Skill 的协作

| 文档 | 关系 |
|------|------|
| [`../SKILL.md`](../SKILL.md) | CLI、契约、路由规则 |
| [`high-load-analysis.md`](high-load-analysis.md) | **CPU 指令数**主线；与本文数据源独立，可联合采集（`perf --memory`）后分别分析 |
| [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | 滑动/掉帧分析；内存泄漏可能导致卡顿，两文可交叉 |
| [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 当未释放 callchain 的符号为 `[unknown]` 时，需符号恢复后重分析 |
| [`../workflow/memory-collect.md`](../workflow/memory-collect.md) | 内存采集路由（`--memory` 参数说明） |
| [`../root-cause/comprehensive.md`](../root-cause/comprehensive.md) | 阶段5 根因分析；CLI 的 `MemoryEvidenceExtractor` 从 `memory_records` 提取 Top-N 分配组件；Agent 应参考本文的未释放/meminfo/GC 分析做补充深挖 |
| [`../report/memory-deliverable.md`](../report/memory-deliverable.md) | 阶段6 内存专题交付报告模板 |

### 与 high-load 的分工

| 维度 | high-load（阶段4） | memory（本文） |
|------|-------------------|----------------|
| 主数据源 | `perf_sample`（CPU 指令数） | `native_hook`（内存事件） |
| 数据库 | `perf.db` | `hapray_report.db:memory_*` + `memory_report.xlsx` |
| 核心指标 | `SUM(event_count)` | `SUM(heapSize)`、未释放量、meminfo 趋势 |
| 分析目标 | CPU 热点、优化机会 | 内存泄漏、分配热点、meminfo 趋势、GC 压力 |
| 交付报告 | `hapray-analysis-*-load-*.md` | `hapray-analysis-*-memory-*.md` |
| 联合采集 | `perf`（默认） | `perf --memory`（联合 perf+trace+memory） |

### 与 root-cause 的分工

| 维度 | 本文（阶段4） | root-cause（阶段5） |
|------|--------------|---------------------|
| 目标 | 发现内存线索与假设 | 确认根因 + 源码级定位 |
| 手段 | Agent 读 `hapray_report.db` + Excel + SQL | CLI `MemoryEvidenceExtractor` 自动提取 + LLM/Agent 推断 |
| 产出 | 内存热点表 + 未释放清单 + 新发现 | `root_cause.md` memory 信号 suspect + Agent 源码级补充 |
| 关系 | CLI 的 `MemoryEvidenceExtractor` **仅提取 Top-N 分配组件**；本文的未释放/meminfo/GC 分析为 Agent 补充深挖的输入 |

---

## 六、新发现判定门槛（硬规则）

满足以下全部条件，才可标记为 **「LLM 挖掘 - 新发现」**：

1. **自动报告未明确给出**：HTML 或 `report/*.json` 中未直接陈述该问题。
2. **证据可追溯**：至少满足其一：
   - `memory_report.xlsx` 中的未释放数据 + callchain 证据；
   - `hapray_report.db` SQL 查询结果 + meminfo 时序数据双源印证。
3. **可复验**：附至少 **1 条命令或 SQL**，可在同一报告根目录复现观察。

若任一不满足，只能标记为 **「候选问题（待验证）」**，不得写成确定结论。

---

## 七、禁止与质量约束

- **禁止**虚构路径、表名、callchainId、地址与内存大小。
- **禁止**仅根据 HTML 摘要断言内存泄漏，必须引用 `memory_records` / `memory_report.xlsx` 的真实数据。
- **禁止**在未开 `--memory` 时假装完成内存分析；应标注「未开启 `--memory` 采集，内存分析不可用」。
- **禁止**将 SQL 简化版的 `SUM(heapSize) per callchainId` 等同于完整 LIFO 未释放检测；完整结果以 `memory_report.xlsx` 的 `MemoryUnreleased` sheet 为准。
- 「新发现」每条须带：**文件路径 + 查询/命令**可追溯证据；若为推测，标注**「待验证」**并给出验证步骤。
- 若未释放 callchain 的符号为 `[unknown]` / 十六进制地址，**不得**假装完成调用链分析；应标注「需 symbol-recovery 后重分析」。

---

## 八、触发词（供主 Skill 索引）

`内存分析`、`内存泄漏`、`memory leak`、`内存泄漏检测`、`未释放内存`、`unreleased`、`native memory`、`native_hook`、`meminfo`、`内存增长`、`内存占用`、`内存趋势`、`GC 频繁`、`GC 压力`、`heap`、`malloc`、`分配热点`、`内存超额分配`、`smaps`、`DMA`、`PixelMap 泄漏`、`内存优化`。
