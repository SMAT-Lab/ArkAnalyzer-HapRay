# 滑动卡顿场景 Trace 分析方法文档

> 适用场景：分析 HarmonyOS 应用首页（或任意列表页）上下滑动时的周期性卡顿问题，
> 通过 `trace.db` 还原手势序列、卡顿分布及"拉动页面"现象。

---

## 一、数据来源

测试框架采集后会生成以下文件：

```
<report_dir>/<TestCase>/htrace/step1/trace.db
```

`trace.db` 是一个 SQLite 数据库，本文档涉及以下四张表。

### 1.1 `process` — 进程表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT | 进程的内部 ID（`ipid`），用于关联其他表 |
| `pid` | INT | 系统进程号 |
| `name` | TEXT | 进程名，如 `com.jd.hm.mall` |

**用途**：根据 app 包名找到 `ipid`，再定位主线程。

### 1.2 `thread` — 线程表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT | 线程的内部 ID（`itid`），与 `callstack.callid` 对应 |
| `tid` | INT | 系统线程号 |
| `name` | TEXT | 线程名 |
| `ipid` | INT | 所属进程的 `ipid` |
| `is_main_thread` | INT | 1 = 主线程 |

**用途**：找到主线程的 `itid`（即 `callstack` 里的 `callid`）。

### 1.3 `callstack` — Hitrace 事件表

| 字段 | 类型 | 说明 |
|---|---|---|
| `ts` | INT | 事件开始时间戳（纳秒） |
| `dur` | INT | 事件持续时间（纳秒） |
| `callid` | INT | 所属线程的内部 ID（对应 `thread.id`） |
| `name` | TEXT | Hitrace 标记名，如 `H:HandleDragUpdate, mainDelta:-35.000000, ...` |
| `depth` | INT | 调用栈深度 |

**用途**：所有 `hiTraceMeter`/`hiTrace` 打点事件都存在这张表。是本分析最核心的数据来源。

### 1.4 `frame_slice` — 帧渲染记录表

| 字段 | 类型 | 说明 |
|---|---|---|
| `ts` | INT | 帧开始时间戳（纳秒） |
| `dur` | INT | 帧实际耗时（纳秒） |
| `type_desc` | TEXT | `actural`（实际渲染帧）或 `expect`（期望帧，即 vsync 周期） |
| `depth` | INT | 嵌套深度，**0 = 真实的单帧卡顿**，>0 为系统跨帧追踪的级联记录 |
| `vsync` | INT | 对应的 vsync 编号 |
| `ipid` | INT | 所属进程 |

**用途**：统计卡顿帧数量和分布。**分析时只取 `depth=0` 的 `actural` 帧**，其他 depth 是嵌套追踪产生的数值放大，不代表真实单帧时长。

---

## 二、分析步骤

### Step 1：定位主进程和主线程

```sql
-- 找到 app 进程的 ipid
SELECT id AS ipid, pid, name
FROM process
WHERE name = 'com.jd.hm.mall';

-- 找到主线程的 itid（即 callstack 的 callid）
-- 方法一：主线程 tid == pid
SELECT id AS itid, tid, name
FROM thread
WHERE ipid = <ipid> AND tid = <pid>;

-- 方法二：is_main_thread 标志
SELECT id AS itid, tid, name
FROM thread
WHERE ipid = <ipid> AND is_main_thread = 1;
```

> **注意**：`callstack.callid` 对应的是 `thread.id`（内部 itid），不是系统 tid。

---

### Step 2：帧卡顿整体统计

```sql
-- 只统计 depth=0 的真实帧
SELECT
    COUNT(*)                                                        AS total_frames,
    SUM(CASE WHEN dur > 16666666 THEN 1 ELSE 0 END)                AS jank_mild,    -- >16ms (60Hz 超限)
    SUM(CASE WHEN dur > 33333333 THEN 1 ELSE 0 END)                AS jank_severe,  -- >33ms (2帧)
    ROUND(AVG(dur) / 1e6, 2)                                       AS avg_ms,
    ROUND(MAX(dur) / 1e6, 2)                                       AS max_ms
FROM frame_slice
WHERE type_desc = 'actural'
  AND depth = 0;
```

**卡顿分级参考**：

| 等级 | 阈值 | 含义 |
|---|---|---|
| 正常 | ≤16.67ms | 60fps 以内 |
| 轻度卡顿 | 16~33ms | 掉帧 1 帧 |
| 中度卡顿 | 33~66ms | 掉帧 2 帧 |
| 重度卡顿 | 66~100ms | 掉帧 4 帧 |
| 严重卡顿 | >100ms | 明显感知 |

---

### Step 3：提取手势序列

系统在每次触摸事件时会打 `H:DVSyncDelay::SetTouchEvent, touchType:X` 标记：

| touchType | 含义 |
|---|---|
| 2 | 手指按下（DOWN） |
| 3 | 手指移动抬起（UP/MOVE） |
| 4 | 手势结束（惯性滚动结束） |

```sql
-- 获取所有触摸事件，按时间排序
SELECT ts, name
FROM callstack
WHERE callid = <main_itid>
  AND name LIKE 'H:DVSyncDelay::SetTouchEvent%'
ORDER BY ts;
```

**分组规则**：每遇到 `touchType:2`（DOWN）就开始新手势，遇到 `touchType:4` 表示本次手势结束（包含惯性滚动结束）。

---

### Step 4：计算每次手势的滑动方向和距离

`H:HandleDragUpdate, mainDelta:<value>, ..., tag:WaterFlow` 记录了每一帧的实际位移量：
- `mainDelta < 0`：向上滑（内容向上）
- `mainDelta > 0`：向下滑（内容向下）

```sql
-- 在某次手势时间窗口内统计滑动距离
SELECT
    SUM(CAST(SUBSTR(name, INSTR(name,'mainDelta:') + 10,
        INSTR(name, ',', INSTR(name,'mainDelta:')) - INSTR(name,'mainDelta:') - 10) AS REAL))
        AS total_delta,
    COUNT(*) AS drag_events
FROM callstack
WHERE callid = <main_itid>
  AND name LIKE '%HandleDragUpdate%WaterFlow%'
  AND ts BETWEEN <gesture_start_ts> AND <gesture_end_ts>;
```

> **推荐用 Python 做此步骤**，SQL 的字符串提取比较繁琐（见下方完整脚本）。

---

### Step 5：统计每次手势内的卡顿帧数

```sql
SELECT
    COUNT(*)                                              AS total_frames,
    SUM(CASE WHEN dur > 16666666 THEN 1 ELSE 0 END)      AS jank_frames
FROM frame_slice
WHERE type_desc = 'actural'
  AND depth = 0
  AND ts BETWEEN <gesture_start_ts> AND <gesture_end_ts + fling_window>;
```

> `fling_window` 建议设 2000000000（2 秒），覆盖惯性滚动期间的卡顿。

---

### Step 6：识别"隔次卡"和"拉动页面"特征

通过 Step 3–5 的结果，在时序上逐手势对比：

**隔次卡特征**：
- 奇数次手势 jank_frames 低（0~2），偶数次高（8~9）
- 或两者交替，周期为 2

**距离异常特征**：
- 某次上滑 total_delta 骤降为正常值的 10% 以下 → 已滑到顶/被卡顿打断
- 最后一次下滑 total_delta 约为正常值的 50% → 触底后进入 OverScroll/下拉刷新

**拉动页面特征**：
- 最后一次下滑 jank_frames 反而是全程最多 → OverScroll 动画额外开销

---

## 三、完整 Python 分析脚本

```python
import sqlite3
from collections import defaultdict

DB_PATH = "<report_dir>/<TestCase>/htrace/step1/trace.db"
APP_NAME = "com.jd.hm.mall"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ── Step 1: 定位主线程 ──────────────────────────────────────────────
c.execute("SELECT id FROM process WHERE name=?", (APP_NAME,))
ipid = c.fetchone()[0]

c.execute("SELECT id, tid FROM thread WHERE ipid=? AND tid=(SELECT pid FROM process WHERE id=?)",
          (ipid, ipid))
main_itid, main_tid = c.fetchone()
print(f"主线程 itid={main_itid}, tid={main_tid}")

# ── Step 2: 帧卡顿总览 ────────────────────────────────────────────
c.execute("""
    SELECT COUNT(*),
           SUM(CASE WHEN dur>16666666 THEN 1 ELSE 0 END),
           SUM(CASE WHEN dur>33333333 THEN 1 ELSE 0 END),
           ROUND(AVG(dur)/1e6,2), ROUND(MAX(dur)/1e6,2)
    FROM frame_slice
    WHERE type_desc='actural' AND depth=0
""")
total, jank_mild, jank_severe, avg_ms, max_ms = c.fetchone()
print(f"\n帧总数={total}, >16ms={jank_mild}, >33ms={jank_severe}, avg={avg_ms}ms, max={max_ms}ms")

# ── Step 3: 提取手势序列 ──────────────────────────────────────────
c.execute("""
    SELECT ts, name FROM callstack
    WHERE callid=? AND name LIKE 'H:DVSyncDelay::SetTouchEvent%'
    ORDER BY ts
""", (main_itid,))
touches = [(r[0], r[1].split("touchType:")[-1].split("|")[0])
           for r in c.fetchall()]

gestures = []
current = []
for ts, ttype in touches:
    if ttype == "2":          # DOWN = 新手势开始
        if current:
            gestures.append(current)
        current = [(ts, ttype)]
    else:
        current.append((ts, ttype))
if current:
    gestures.append(current)
print(f"\n共检测到 {len(gestures)} 次手势")

# ── Steps 4+5: 逐手势分析 ─────────────────────────────────────────
print(f"\n{'#':>3}  {'方向':>6}  {'距离(px)':>10}  {'时长(ms)':>9}  {'总帧':>6}  {'卡顿帧':>6}")
print("-" * 55)

for i, gesture in enumerate(gestures):
    g_start = gesture[0][0]
    g_end   = gesture[-1][0]

    # 滑动方向与距离
    c.execute("""
        SELECT name FROM callstack
        WHERE callid=? AND name LIKE '%HandleDragUpdate%WaterFlow%'
          AND ts BETWEEN ? AND ?
    """, (main_itid, g_start - 50000000, g_end + 2500000000))
    total_delta = 0
    for (dname,) in c.fetchall():
        try:
            delta = float(dname.split("mainDelta:")[1].split(",")[0])
            total_delta += delta
        except (IndexError, ValueError):
            pass

    direction = "UP↑" if total_delta < 0 else "DOWN↓"
    dur_ms = (g_end - g_start) / 1e6

    # 卡顿帧统计
    c.execute("""
        SELECT COUNT(*), SUM(CASE WHEN dur>16666666 THEN 1 ELSE 0 END)
        FROM frame_slice
        WHERE type_desc='actural' AND depth=0
          AND ts BETWEEN ? AND ?
    """, (g_start, g_end + 2000000000))
    fr = c.fetchone()
    total_frames = fr[0] or 0
    jank_frames  = fr[1] or 0

    flag = ""
    if abs(total_delta) < 300 and i < len(gestures) // 2:
        flag = "← 距离异常短！(触顶)"
    if abs(total_delta) < 1200 and total_delta > 0:
        flag = "← 疑似触顶转拉动刷新"

    print(f"{i+1:>3}  {direction:>6}  {total_delta:>10.0f}  {dur_ms:>9.0f}  "
          f"{total_frames:>6}  {jank_frames:>6}  {flag}")

conn.close()
```

---

## 四、关键诊断规律

### 周期性卡顿（"隔次卡"）判断
- 提取各手势的 `jank_frames`，检查是否呈 **低-高-低-高** 交替模式
- 通常原因：某一状态更新逻辑在奇偶帧间存在不对称代价（如首次进入边界触发全量重绘，次次正常）

### 滑动距离累积不平衡
- 多次上滑合计距离 < 多次下滑合计距离 → 卡顿导致某次上滑被截断
- 具体定位：找 `total_delta` 骤降的手势，查该手势内的最慢 `FlushLayoutTask` 或 `CustomNodeUpdate`

### 触底转拉动识别
- 最后一次下滑：`total_delta` 明显低于前几次 **且** `jank_frames` 最多
- 可进一步查该手势内是否出现 `overScroll` 或 `pullRefresh` 相关 hitrace 标记

---

## 五、常见 Hitrace 标记速查

| 标记 | 含义 |
|---|---|
| `H:DVSyncDelay::SetTouchEvent, touchType:2` | 手指按下 |
| `H:DVSyncDelay::SetTouchEvent, touchType:3` | 手指移动/抬起 |
| `H:DVSyncDelay::SetTouchEvent, touchType:4` | 惯性滚动结束 |
| `H:HandleDragUpdate, mainDelta:<px>, tag:WaterFlow` | WaterFlow 每帧滚动量（负=上滑，正=下滑） |
| `H:Animation start/end and current sceneId=APP_LIST_FLING` | 惯性滚动动画开始/结束 |
| `H:FlushLayoutTask` | ArkUI 布局刷新（max 值是单帧最慢布局） |
| `H:FlushDirtyNodeUpdate` | ArkUI 脏节点重绘 |
| `H:UITaskScheduler::FlushTask` | 一帧的完整 UI 任务（含布局+渲染） |
| `H:CustomNodeUpdate name:<组件名>` | 某个自定义组件被标记为需要更新 |
| `H:CustomNode:OnAppear` / `H:aboutToAppear` | 组件首次出现的生命周期初始化 |
| `H:HandleVisibleAreaChangeEvent_nodeCount:<N>` | N 个节点接受可见性变化回调 |
| `H:HandleOnAreaChangeEvent_nodeCount:<N>` | N 个节点接受 area 变化回调（与 Y 坐标更新直接相关） |
| `H:WalkThroughAncestorForStateListener` | 响应式状态传播遍历祖先节点 |
| `H:APP_LIST_FLING` | 列表惯性滚动期间的性能标记 |
