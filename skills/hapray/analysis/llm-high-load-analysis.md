# LLM 高负载挖掘（CPU 指令数 · 动态 perf + 静态 SO 交叉）

> **核心度量**：本文中 **「负载」= CPU 指令数** —— 即 `perf_sample.event_count` 的聚合值（hiperf 采集事件：`raw-instruction-retired`，每个样本代表一个周期内执行的指令数）。  
> **分析目标**：通过 **动态指令数（perf_sample）** 与 **静态 SO 分析（binary/LTO/符号）** 的交叉，挖掘 **自动报告未写出的** 高指令数热点与优化机会。  
> **与 `summary.json` 的关系**：`summary.json` 是按已知规则汇总的摘要，**禁止**将其作为本 Skill 挖掘的主线数据源；原始侧以 **`perf_sample`、`perf_callchain`、`perf_files`、`callstack`、`frame_slice`** 为准，静态侧以 **SO 二进制分析产物** 为准。

---

## 一、触发条件与最低完成标准

### 1.1 必须加载的触发条件（满足任一条即强制）

| 类别 | 用户表述或客观信号 | 必须行为 |
|------|--------------------|----------|
| **意图明确** | 含「深挖」「高负载挖掘」「LLM 挖掘」「CPU 指令数」「未知瓶颈」「报告没写」「还有没有别的问题」「弱信号」「动静交叉」等 | 全文流程 + §三 各维度逐项检索 |
| **产物已齐** | `reports_path` 下同时存在 `perf.db`（或内嵌 `perf_sample` 的 `trace.db`）与 SO 静态分析产物（`opt`/`static` 输出、`symbol_recovery` 输出等） | 动静交叉；**禁止**只读 HTML 摘要 |
| **产物部分齐** | 仅有 `perf.db`/`trace.db`（无静态产物），或仅有静态分析产物 | 最大化利用已有源，**显式写明**缺失的另一侧 |
| **结论冲突** | 自动报告「正常/无异常」，但用户描述卡顿、发热、帧率低 | 必须从 `perf_sample` 找矛盾证据 |
| **与 scroll-jank 同时需要** | 问题涉及滑动/掉帧，且同时关心 CPU 指令数 | **同时**加载 `scroll-jank` 与本文；帧结论只按 scroll-jank 规则，指令数分析按本文 |

### 1.2 最低完成标准（Agent 自检清单）

触发后，深入程度至少达到以下 6 条：

1. **枚举**：列出 `perf.db`（或含 `perf_sample` 的 `trace.db`）真实路径、SO 静态产物路径、`summary.json`（标注「不参与挖掘」）。若某类不存在，写「未找到：已搜索的模式」。
2. **动态 Top 热点**：对每个 `perf.db` 执行 **§四.3.A**（SO 级）和 **§四.3.B**（符号级）的聚合 SQL，得到 Top-N 热点（`SUM(event_count)` 排序）。
3. **帧级指令数**：若存在 `frame_slice`，执行 **§四.3.C** 的逐帧负载 SQL，输出指令数最高的帧列表。
4. **静态交叉**（有产物时）：将动态热点 SO 与静态分析结论（LTO 状态、代码段大小、符号可见性）对齐，在 **§四.4** 中写出「优化机会」条目。
5. **对照 HTML**：单列「HTML 已写明的结论」vs「仅从 perf_sample/callchain 可见的额外发现」，后者标为「LLM 挖掘 - 新发现」。
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

- `perf.db` 或内嵌 perf 表的 `trace.db` 的**真实绝对路径**（按 `step*` 子目录分列）
- SO 静态分析产物路径（`opt/`、`static-output/`、`symbol_recovery/` 等）
- `perf.data` 原始文件（若存在）
- `summary.json`（列路径并标注「不参与挖掘」）

若某类不存在，写「未找到：已搜索模式 `**/perf.db` 等」。

### 4.3 动态数据：聚合查询

#### A. SO 级热点（优先执行）

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

#### C. 帧级指令数分布（有 `frame_slice` 时执行）

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

#### D. 线程维度（按进程/线程分组）

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

对每个 `stepN/perf.db` 分别执行 A 查询，汇总表格比较各步骤 `total_instructions`。

### 4.4 静态数据交叉

1. 取 §4.3.A Top-5 热点 SO，在 `opt`/`static` 产物中检索各 SO 的：
   - LTO 是否启用（`-flto`、LTO 标记）
   - 代码段（`.text`）大小
   - Strip 状态（是否有符号表）
2. 将结果填入 §三.3.5 的「动静交叉发现」表。
3. 若某热点 SO 的符号全为 `[unknown]` 或十六进制，**标记为「需 symbol-recovery」**，并在最终报告的「未覆盖/数据不足」中说明。

### 4.5 与自动报告对照

逐条列出：

- **HTML 已写明的结论**（热点 SO、帧率数值等）
- **仅从 `perf_sample`/`perf_callchain`/静态产物可见的额外发现** → 标为「LLM 挖掘 - 新发现」

**禁止**把 `summary.json` 字段与 HTML 的「字段对齐」当作新发现来源。

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
- **高指令数热点表**（对应 §三，每条含：SO/符号、指令数、占比、来源 SQL/文件）
- **动静交叉优化机会表**（§三.3.5）
- **新发现**（每条：现象、可追溯证据、与 HTML 差异、风险/影响等级、建议验证步骤）
- **未覆盖/数据不足**（诚实列出；含「需 symbol-recovery」的 SO）

---

## 五、与其他 Skill 的协作

| 文档 | 关系 |
|------|------|
| [`../SKILL.md`](../SKILL.md) | CLI、契约、`gui-agent` 前置条件、独立 `.md` 命名与落盘规则 |
| [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | **帧与手势**的权威规则与 SQL；帧级指令数与帧结论须保持一致 |
| [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 当热点函数为 `[unknown]`/stripped 时**必须先执行**，再回到本文分析 |
| [`../hapray-tool-result.md`](../hapray-tool-result.md) | 定位 `reports_path` 与契约字段 |

---

## 六、禁止与质量约束

- **禁止**虚构路径、表名、栈名、百分比与指令数。
- **禁止**仅根据行业常识输出「热点清单」而不引用本轮**真实产物**的 SQL 输出。
- **禁止**以 `summary.json` 作为 LLM 高负载挖掘的主线数据源。
- 「新发现」每条须带：**文件路径 + 查询**可追溯证据（来自原始侧，非 summary 字段复述）；若为推测，标注**「待验证」**并给出验证步骤。
- 若仅有 `trace.db` 无独立 `perf.db`，先检查 `trace.db` 中是否存在 `perf_sample` 表（`sqlite3 trace.db ".tables"`），再决定是否可执行 §四.3 的 SQL。
- 若热点符号大量为 `[unknown]`，**不得**假装完成「符号级分析」；应在报告中标注「需 symbol-recovery 后重分析」。

---

## 七、触发词（供主 Skill 索引）

`CPU指令数`、`高负载挖掘`、`LLM挖掘`、`动静交叉`、`perf_sample`、`perf热点`、`SO级指令数`、`符号级热点`、`帧级负载`、`原始trace`、`报告未覆盖`、`未知瓶颈`、`多源交叉`、`主动发现`、`深挖`、`弱信号`、`结论冲突`、`尽可能深入`、`第二源`、`交叉印证`。
