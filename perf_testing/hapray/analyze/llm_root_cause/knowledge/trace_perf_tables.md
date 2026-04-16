# Trace / Perf 关键表提炼（空刷定位用）

> 摘自 [docs/des_table.md](../../docs/des_table.md)，只保留 `standalone_tools/llm_root_cause` 当前做空刷根因定位、`/proc` 用户态符号补充、trace/perf 对齐时最需要的表。

## 1. 先记住这几个关键区别

- `process.id` 是 TraceStreamer 内部进程 ID，其他表通常通过 `ipid` 引用它。
- `thread.id` 是 TraceStreamer 内部线程 ID，其他表通常通过 `itid` 引用它。
- `callstack` 是 **trace 侧** 的调用栈/异步调用表。
- `perf_callchain` 是 **perf 侧** 的采样调用链表。
- `frame_slice.callstack_id` 指向的是 trace 侧 `callstack`，**不是** perf 侧 `perf_callchain`。
- `perf_sample.timestamp_trace` 是 perf 同步到 trace 时间轴后的时间戳，是 trace/perf 联动时最关键的锚点之一。

## 2. 这次 POC 最关心的定位链路

### Trace 侧

1. 从空刷检测结果拿到重点帧、线程、`vsync`、时间范围。
2. 在 `frame_slice` 中找到对应帧，读取：
   - `ipid`
   - `itid`
   - `callstack_id`
   - `vsync`
   - `dur`
3. 通过 `process` / `thread` 还原真实进程名、线程名。
4. 如需 trace 侧调用栈，再用 `callstack_id` 去看 `callstack`。

### Perf 侧

1. 用对齐后的时间戳查 `perf_sample.timestamp_trace`。
2. 从 `perf_sample` 取到对应的 `callchain_id`、`thread_id`、`event_type_id`。
3. 用 `callchain_id` 查 `perf_callchain`，拿到逐层调用链。
4. 用 `file_id` 去 `perf_files` 取 `path` / `symbol`，补出 `/proc/.../entry.hap`、`.so`、业务符号等信息。
5. 用 `perf_thread` / `perf_report` 还原线程和事件类型上下文。

这条链路正是后面要做的：**从空刷帧 -> 对齐 perf 采样 -> 回捞 `/proc` 用户态 file/symbol -> 缩小到反编译源码/控件范围。**

## 3. 关键表说明

### 3.1 `process`

**用途**
- 记录进程相关数据。

**当前最有用字段**
- `id`：数据库内部重新定义的进程 ID。
- `ipid`：TS 内部进程 ID。
- `pid`：真实进程号。
- `name`：进程名。
- `start_ts`：开始时间。

**我们怎么用**
- 主要把 `frame_slice.ipid`、`thread.ipid` 还原成真实进程名。
- 文档特别强调：`process.id` 在其他表中通常作为 `ipid` 使用。

---

### 3.2 `thread`

**用途**
- 记录线程相关数据。

**当前最有用字段**
- `id`：唯一标识。
- `itid`：TS 内部线程 ID。
- `tid`：真实线程号。
- `name`：线程名。
- `ipid`：所属进程，关联 `process.id`。
- `is_main_thread`：是否主线程。

**我们怎么用**
- 主要把 `frame_slice.itid` 还原成真实线程名、判断是不是主线程。
- 文档特别强调：`thread.id` 在其他表中通常作为 `itid` 使用。

---

### 3.3 `frame_slice`

**用途**
- 记录应用和 RenderService 的帧渲染数据，以及它们之间的关联关系。

**当前最有用字段**
- `ts`：数据上报时间戳。
- `vsync`：标识一组渲染帧的 ID。
- `ipid`：所属进程内部 ID，关联 `process.id`。
- `itid`：所属线程内部 ID，关联 `thread.id`。
- `callstack_id`：该帧对应的 trace 侧调用栈行。
- `dur`：帧渲染时长。
- `src`：被哪一帧触发。
- `dst`：对应的渲染帧行。
- `type` / `type_desc`：实际帧还是期望帧。
- `flag`：是否卡帧、是否无须绘制、是否 RS/App 起止异常。

**我们怎么用**
- 它是 empty-frame / frame 问题的 trace 侧主入口表。
- 一旦拿到重点帧，就可以从这里继续走：
  - `ipid -> process`
  - `itid -> thread`
  - `callstack_id -> callstack`
- 对后续把“空刷帧”落到“哪个线程/哪个调用链/哪个页面”非常关键。

---

### 3.4 `callstack`

**用途**
- 记录 trace 侧调用堆栈和异步调用信息。

**当前最有用字段**
- `id`：唯一标识。
- `ts`：事件时间戳。
- `dur`：调用时长。
- `callid`：调用者 ID，文档举例里可对应线程表中的 ID。
- `name`：调用名称。
- `depth`：调用深度。
- `parent_id`：父调用 ID。
- `argsetid`：参数列表，关联 `args.id`。
- `cookie` / `child_callid`：异步调用关联字段。

**我们怎么用**
- 它用于解释 `frame_slice.callstack_id` 对应的 trace 侧调用栈。
- 如果要分析某一帧在 trace 视角下是由什么调度/消息/异步链路触发的，要看这张表。
- 这张表和 perf 里的 `perf_callchain` 不是同一个概念。

---

### 3.5 `perf_thread`

**用途**
- 记录 Hiperf 采集到的进程/线程数据。

**当前最有用字段**
- `thread_id`：线程号。
- `process_id`：进程号。
- `thread_name`：线程名。

**我们怎么用**
- 把 `perf_sample.thread_id` 还原成线程名。
- 也可以按 `process_id` 过滤，只保留目标应用进程的采样。

---

### 3.6 `perf_sample`

**用途**
- 记录 Hiperf 的采样信息。

**当前最有用字段**
- `callchain_id`：关联 `perf_callchain.callchain_id`。
- `timestamp`：未做时钟同步的时间戳。
- `timestamp_trace`：同步到 trace 时间轴后的时间戳。
- `thread_id`：线程号。
- `event_count`：采样统计值。
- `event_type_id`：事件类型，关联 `perf_report.id`。
- `cpu_id`：CPU 核编号。
- `thread_state`：线程状态。

**我们怎么用**
- 这是 perf 侧与 trace 侧时间对齐的入口表。
- 后续需要围绕 `timestamp_trace` 找到某个空刷帧附近的 perf 采样，再顺着 `callchain_id` 展开调用链。

---

### 3.7 `perf_callchain`

**用途**
- 记录 Hiperf 采样的调用链信息。

**当前最有用字段**
- `callchain_id`：一组调用链的标识。
- `depth`：调用深度。
- `ip`：函数 IP。
- `vaddr_in_file`：函数在文件中的虚拟地址。
- `file_id`：关联文件。
- `symbol_id`：符号 ID。
- `name`：函数名。

**我们怎么用**
- 它是把某条 perf sample 展开成逐层调用链的关键表。
- 我们后面想补的 `/proc/...` 用户态证据，核心就来自这里再去关联 `perf_files`。
- 当调用链里出现 `/proc/.../entry.hap`、业务 `.so`、ArkTS 编码符号时，可以直接显著提升源码/控件定位能力。

---

### 3.8 `perf_files`

**用途**
- 记录 Hiperf 采集到的函数符号表和文件路径。

**当前最有用字段**
- `file_id`：文件编号。
- `serial_id`：同一文件中的函数编号。
- `symbol`：函数名。
- `path`：文件路径。

**我们怎么用**
- 它是恢复用户态文件路径和符号名的关键表。
- 重点看：
  - `/proc/.../entry.hap`
  - 应用私有 `.so`
  - ArkTS/业务函数符号
- 这张表能把“callchain 只有地址/模糊函数”的信息，提升成“具体文件/具体业务符号”的信息。

---

### 3.9 `perf_report`

**用途**
- 记录 Hiperf 采集配置。

**当前最有用字段**
- `id`：唯一标识。
- `report_type`：类型，文档中包括 `config_name`、`workload`、`cmdline`。
- `report_value`：对应值。

**我们怎么用**
- 主要用于把 `perf_sample.event_type_id` 还原成具体事件类型。
- 如果后面要区分不同 perf event 对空刷证据的含义，这张表会用到。

## 4. 表关系速记

### Trace 侧

- `process.id` <- `thread.ipid`
- `process.id` <- `frame_slice.ipid`
- `thread.id` <- `frame_slice.itid`
- `callstack.id / 行号` <- `frame_slice.callstack_id`

### Perf 侧

- `perf_thread.thread_id` <- `perf_sample.thread_id`
- `perf_report.id` <- `perf_sample.event_type_id`
- `perf_callchain.callchain_id` <- `perf_sample.callchain_id`
- `perf_files.file_id` <- `perf_callchain.file_id`

## 5. 对我们后续实现最重要的 SQL 入口

> 下面保留文档里最有用的查询方向。真正落地时，先以当前数据库实际 schema 为准。

### 5.1 已知同步后的时间戳，先找 perf sample

```sql
select * from perf_sample where timestamp_trace = 28463134340470;
```

### 5.2 已知同步后的时间戳，继续展开调用链

```sql
select * from perf_sample where timestamp_trace = 28463134340470;
-- 再取出结果里的 callchain_id，去 perf_callchain 查整条调用链
```

### 5.3 已知调用链里的 file_id，取文件路径和符号

```sql
select * from perf_files where file_id = ?;
```

### 5.4 已知进程，找该进程下所有线程

```sql
select thread.*
from thread, process
where process.pid = 123 and thread.ipid = process.id;
```

### 5.5 已知进程，找其 perf 采样

```sql
select A.*
from perf_sample as A, perf_thread as B
where B.process_id = 7863 and A.thread_id = B.thread_id;
```

## 6. 当前文档里的一个重要注意点

`docs/des_table.md` 的 perf 关系图说明和后面的详细表结构之间，存在一处需要注意的不一致：

- 前面的 perf 关系说明/示例里，`perf_sample` 和 `perf_callchain` 有时按 `sample_id` 关联来描述。
- 但后面的详细表结构里，`perf_sample` 给出的关键关联字段是 `callchain_id`，`perf_callchain` 也明确有 `callchain_id`。

**因此后续写 SQL 或代码时，不要只凭文档前半段的示意图硬编码，先以当前实际数据库 schema 为准。**

## 7. 这份提炼对空刷定位的直接价值

对当前 empty-frame POC 来说，这几张表已经足够支撑下一步增强：

1. 从 `frame_slice` 把空刷帧落到具体 app 线程。
2. 从 `perf_sample.timestamp_trace` 对齐 perf 采样。
3. 从 `perf_callchain + perf_files` 回捞 `/proc` 用户态文件和符号。
4. 把 `/proc/.../entry.hap`、业务 `.so`、ArkTS 符号映射到反编译源码范围。
5. 最终把输出从“泛化页面猜测”收敛到“更短的可疑源码/控件列表”。
