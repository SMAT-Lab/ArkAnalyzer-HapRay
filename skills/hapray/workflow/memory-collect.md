> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 2**（内存采集分支）

# 内存采集路由（`--memory`）

> **范围**：需要分析 Native 内存分配/释放/泄漏时，在 `perf` 采集阶段附加 `--memory` 参数。与 [`perf-collect.md`](perf-collect.md) 的常规采集流程互补，不替代。
> **前置**：完成 §0 路径门禁 + Read 本文件 + [`../analysis/memory-analysis.md`](../analysis/memory-analysis.md)。
>
> **与 perf-collect.md 的关系**：用例编写、`prepare` 试跑、`perf` 执行的完整流程在 [`perf-collect.md`](perf-collect.md) 中定义，本文**仅补充** `--memory` 相关的参数、采集模式、产物差异和用例编写要点。无论是否使用 `--memory`，用例编写和 prepare 流程完全相同——`--memory` 只是 `perf` 命令的一个附加参数。

---

## 一、何时需要内存采集

| 场景 | 说明 |
|------|------|
| 用户提及「内存泄漏」「内存增长」「内存占用」「memory leak」 | **必须**附加 `--memory` |
| 用户提及「GC 频繁」「内存压力」 | **必须**附加 `--memory`（GC 分析本身不依赖 `--memory`，但完整内存分析需要） |
| 用户要求分析 PixelMap/DMA/图片内存 | **必须**附加 `--memory`（meminfo 周期采集含 DMA 分类） |
| 用户仅关心 CPU 指令数/卡顿 | **不需要** `--memory`，走常规 perf-collect |
| 用户同时关心 CPU + 内存 | `perf --memory`（联合采集，一次产出两套数据） |

---

## 二、采集模式

### 2.1 联合采集（推荐，默认）

```bash
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --round 1 \
  --memory \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 同时采集 perf（CPU 指令数）+ trace（帧/调度）+ memory（native_hook + meminfo）
- 产出：`perf.db` + `trace.db` + `trace.htrace`(含 native_hook) + `meminfo/` + `hapray_report.db`(memory_* 表)
- 高负载分析和内存分析共享同一 `reports_path`，分别进入各自子 Skill

### 2.2 纯内存采集（仅内存，无 perf/trace）

```bash
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --round 1 \
  --memory --no-trace --no-perf \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 仅采集 memory（native_hook + meminfo），跳过 perf 和 trace
- 产出：`trace.htrace`(含 native_hook) + `meminfo/` + `hapray_report.db`(memory_* 表)
- 适用于：仅需内存分析、perf/trace 采集开销过大、或设备性能受限

> **注意**：纯内存模式下 high-load 分析不可用（无 `perf_sample` 数据），GC 分析降级（GC 线程负载依赖 `perf.db`，但 GC 调用次数/频率依赖 `trace.db`，纯内存模式无 `trace.db`）。

### 2.3 含堆快照采集

```bash
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<用例名>" --round 1 \
  --memory --snapshot \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 在 `--memory` 基础上，每个 step 结束时通过 `hidumper-jsheap` 采集 ArkTS 堆快照
- 快照存储在设备 `memory_leak` 目录，采集完成后传回 `<用例>/memory_leak/`
- 适用于：ArkTS 堆对象泄漏排查、JS 引擎内存分析

---

## 三、CLI 参数说明

| 参数 | 说明 | 配置项 |
|------|------|--------|
| `--memory` | 启用 hiprofiler nativehook 插件（malloc/free/mmap/munmap + 调用链） | `memory.enable = True` |
| `--snapshot` | 启用 ArkTS 堆快照（每 step 结束时采集） | `memory.snapshot_enable = True` |
| `--no-trace` | 禁用 trace 采集 | `trace.enable = False` |
| `--no-perf` | 禁用 perf 采集 | `hiperf.enable = False` |

**非法组合**：`--no-trace --no-perf` 且**未** `--memory` → 全部禁用，CLI 拒绝执行。

### 3.1 config.yaml 内存配置

```yaml
memory:
  enable: False          # 通过 --memory 命令行参数控制
  max_stack_depth: 100   # Native Memory 采集的最大调用栈深度
  interval_seconds: 2    # Level1 Memory (meminfo) 采集的间隔时间（秒）
  snapshot_enable: False # Snapshot 采集开关（通过 --snapshot 控制）
```

- `max_stack_depth`：nativehook 调用栈深度上限，默认 100。增大可捕获更深层调用链，但增加开销。
- `interval_seconds`：meminfo 周期采集间隔，默认 2 秒。减小可提高时序精度，但增加设备 I/O。

---

## 四、底层采集机制

### 4.1 nativehook 插件

`hiprofiler_cmd` 使用 `nativehook` 插件采集 Native 堆内存事件：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `sample_interval` | 5000 (μs) | 采样间隔 |
| `max_stack_depth` | 100 | 最大栈深度 |
| `malloc_free_matching_interval` | 10 | malloc/free 匹配间隔 |
| `offline_symbolization` | true | 离线符号化 |
| `fp_unwind` | true | 帧指针回栈 |
| `callframe_compress` | true | 调用帧压缩 |
| `record_accurately` | true | 精确记录 |

采集的内存事件类型：
- **AllocEvent**：malloc 分配
- **FreeEvent**：free 释放
- **MmapEvent**：mmap 映射（含 subType：anonymous/file-backed 等）
- **MunmapEvent**：munmap 解除映射

### 4.2 meminfo 周期采集

后台线程按 `interval_seconds`（默认 2s）周期采集一级内存数据：

| 子目录 | 设备命令 | 内容 |
|--------|----------|------|
| `dynamic_showmap/` | showmap | smaps 内存（PSS + SwapPss，按 Category 分类） |
| `dynamic_gpuMem/` | GPU 内存查询 | 应用进程 GPU 内存（按 PID 过滤，KB×4×1024 转字节） |
| `dynamic_process_dmabuff_info/` | dmabuf 查询 | DMA 内存（按 buf_type 分类：pixelmap/NULL/hw-video-decoder 等） |

### 4.3 堆快照（`--snapshot`）

每个 step 结束时，通过 `hidumper-jsheap` 采集 ArkTS 堆快照，存储在设备 `memory_leak` 目录。

---

## 五、产物说明

```
reports/<timestamp>/<用例>/
├── htrace/step*/
│   └── trace.htrace              # 含 native_hook 数据（→ 转换为 trace.db）
├── htrace/step*/
│   └── trace.db                  # native_hook / native_hook_frame / data_dict / process / thread
├── meminfo/step*/
│   ├── dynamic_showmap/          # smaps 文本文件
│   ├── dynamic_gpuMem/           # GPU 内存文本文件
│   └── dynamic_process_dmabuff_info/  # DMA 内存文本文件
├── memory_leak/                  # 堆快照（仅 --snapshot 时）
├── report/
│   ├── hapray_report.db          # memory_results / memory_records / memory_callchains / memory_data_dicts / memory_meminfo
│   ├── memory_report.xlsx        # MemoryUnreleased / Summary_ByCategory / Summary_ByCategorySub / Meminfo
│   └── memory_comparison.xlsx    # 对比报告（仅 --use-refined-lib-symbol 时）
└── ...                           # 其他常规产物（perf.db 等，联合采集时存在）
```

---

## 六、用例编写要点（内存场景）

### 6.1 采集时长

内存泄漏通常需要**较长时间**才能体现趋势。建议：

| 场景 | 建议 step 时长 | 说明 |
|------|----------------|------|
| 快速内存概览 | ≥ 15s | 捕获基本分配/释放模式 |
| 泄漏排查 | ≥ 60s | 需足够时间观察未释放趋势 |
| meminfo 趋势分析 | ≥ 30s | interval=2s 时至少 15 个采样点 |
| 重复操作泄漏 | 每次操作 ≥ 10s | 重复 3-5 次相同操作，观察内存是否线性增长 |

### 6.2 操作设计

- **重复操作**：设计可重复的页面切换/列表滚动操作，若每次操作后内存不回落，是泄漏信号
- **避免快速退出**：内存场景用例应保持应用前台运行较长时间，避免 `stop_app` 在采集中途
- **场景覆盖**：覆盖用户关心的主路径，特别是涉及图片加载、列表渲染、页面跳转的场景

### 6.3 与常规用例的区别

| 维度 | 常规 high-load 用例 | 内存专项用例 |
|------|---------------------|-------------|
| step 时长 | 5-15s（关注瞬时 CPU 峰值） | 15-60s（关注内存趋势） |
| 操作重点 | 触发高 CPU 负载的操作 | 触发内存分配的操作（图片加载、列表渲染） |
| 重复性 | 单次操作即可 | 建议重复 3-5 次相同操作 |
| 退应用 | `teardown()` 自动 `stop_app` | 采集期间保持前台；`teardown()` 退出即可 |

---

## 七、采集后门禁与路由

### 7.1 采集完成检查

```bash
# 检查 hapray_report.db 是否有 memory_records 表且有数据
sqlite3 <用例>/report/hapray_report.db "SELECT COUNT(*) FROM memory_records"
# 返回 > 0 → 内存分析可用
# 返回 0 或表不存在 → 内存分析不可用（检查 --memory 是否启用、nativehook 是否运行）
```

### 7.2 路由

采集完成并验证 `memory_records` 有数据后：

```
perf --memory 完成
  ├─ memory_records 有数据 → 进入 analysis/memory-analysis.md（内存分析主线）
  ├─ 同时有 perf.db → 同时进入 analysis/high-load-analysis.md（高负载分析主线）
  └─ memory_records 为空 → 标注「内存采集失败」，检查 hiprofiler_cmd 日志
```

### 7.3 数据源降级

`MemoryAnalyzerCore` 支持双路径降级：

| 数据源 | 条件 | 精度 |
|--------|------|------|
| `native_hook` 表（明细） | 优先检查，有数据时使用 | 最高：含完整事件、地址、调用链、线程信息 |
| `native_hook_statistic` 表（统计） | `native_hook` 无数据时降级 | 降低：缺时间精度、线程信息、地址信息 |

若降级到统计模式，`hapray_report.db` 中 `memory_records` 的 `data_source` 字段为 `native_hook_statistic`，Agent 应在报告中标注「使用统计数据，精度降低」。
