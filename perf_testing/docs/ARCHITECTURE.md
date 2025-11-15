# Callchain Refiner 架构设计

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     MemoryAnalyzer                              │
│  (use_refined_lib_symbol=True, export_comparison=True)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MemoryAnalyzerCore                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. 加载数据 (MemoryDataLoader)                           │   │
│  │    - 查询 native_hook 事件                               │   │
│  │    - 查询进程、线程信息                                  │   │
│  │    - 查询 data_dict（符号和文件名）                      │   │
│  │    - 查询所有 callchain 帧                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 2. 生成记录 (MemoryRecordGenerator)                      │   │
│  │    - 遍历每个事件                                        │   │
│  │    - 获取原始 last_lib_id 和 last_symbol_id             │   │
│  │    - 如果启用 refined 模式：                             │   │
│  │      * 调用 CallchainRefiner 精化                        │   │
│  │      * 使用精化后的值                                    │   │
│  │    - 分类和统计                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3. 导出报告 (MemoryComparisonExporter)                   │   │
│  │    - 如果启用 export_comparison：                        │   │
│  │      * 生成对比 Excel                                    │   │
│  │      * 展示原始值 vs refined 值                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Callchain Refiner 工作流程

```
输入：callchain_id, data_dict
  │
  ▼
┌─────────────────────────────────────────┐
│ 1. 查询 Callchain 帧                    │
│    query_callchain_by_id(callchain_id)  │
│    返回：[frame0, frame1, frame2, ...]  │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ 2. 按 depth 排序                        │
│    从 depth=0 开始                      │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ 3. 遍历每个帧                           │
│    for frame in sorted_frames:          │
└─────────────────────────────────────────┘
  │
  ├─ frame0: symbol_id=1, file_id=2
  │  ├─ 查询: symbol="malloc", file="libc.so"
  │  ├─ 检查: should_exclude("malloc", "libc.so")?
  │  ├─ 结果: YES (系统符号 + 系统库)
  │  └─ 继续下一帧
  │
  ├─ frame1: symbol_id=3, file_id=4
  │  ├─ 查询: symbol="app_alloc", file="libapp.so"
  │  ├─ 检查: should_exclude("app_alloc", "libapp.so")?
  │  ├─ 结果: NO (应用符号 + 应用库)
  │  └─ 返回: (file_id=4, symbol_id=3, "libapp.so", "app_alloc")
  │
  └─ 如果所有帧都被排除，返回 (None, None, None, None)
```

## 排除规则匹配流程

```
输入：symbol, lib_path
  │
  ▼
┌─────────────────────────────────────────┐
│ 检查系统符号规则                        │
│ patterns: [malloc, free, pthread_*, ...] │
└─────────────────────────────────────────┘
  │
  ├─ 匹配? YES → 排除
  │
  └─ 匹配? NO
      │
      ▼
    ┌─────────────────────────────────────────┐
    │ 检查计算类符号规则                      │
    │ patterns: [std::, __gnu_cxx::, ...]     │
    └─────────────────────────────────────────┘
      │
      ├─ 匹配? YES → 排除
      │
      └─ 匹配? NO
          │
          ▼
        ┌─────────────────────────────────────────┐
        │ 检查系统库规则                          │
        │ patterns: [libc.so, libm.so, ...]       │
        └─────────────────────────────────────────┘
          │
          ├─ 匹配? YES → 排除
          │
          └─ 匹配? NO → 保留
```

## 数据流向

```
trace.db
  │
  ├─ native_hook 表
  │  └─ 包含: id, callchain_id, last_lib_id, last_symbol_id, ...
  │
  ├─ native_hook_frame 表
  │  └─ 包含: callchain_id, depth, symbol_id, file_id, ...
  │
  └─ data_dict 表
     └─ 包含: id, data (符号或文件名)

MemoryDataLoader
  │
  ├─ 查询 native_hook 事件
  ├─ 查询 native_hook_frame (所有 callchain)
  └─ 查询 data_dict

MemoryRecordGenerator
  │
  ├─ 原始模式：使用 last_lib_id, last_symbol_id
  │
  └─ Refined 模式：
     ├─ 对每个事件的 callchain_id
     ├─ 调用 CallchainRefiner.refine_callchain()
     └─ 使用精化后的 lib_id, symbol_id

输出记录
  │
  ├─ 标准报告 (memory_report.xlsx)
  │  └─ 使用 refined 值
  │
  └─ 对比报告 (memory_comparison.xlsx)
     └─ 展示原始值 vs refined 值
```

## 缓存机制

```
MemoryRecordGenerator
  │
  ├─ callchain_cache: dict[int, list[dict]]
  │  │
  │  ├─ 首次查询 callchain_id=123
  │  │  ├─ 数据库查询
  │  │  ├─ 缓存结果
  │  │  └─ 返回结果
  │  │
  │  └─ 再次查询 callchain_id=123
  │     ├─ 检查缓存
  │     ├─ 缓存命中
  │     └─ 直接返回（无数据库查询）
  │
  └─ 性能优化：避免重复查询相同的 callchain
```

## 模块依赖关系

```
MemoryAnalyzer
  │
  └─ MemoryAnalyzerCore
      │
      ├─ MemoryDataLoader
      │  └─ SQLite 数据库
      │
      ├─ MemoryClassifier
      │  └─ 分类规则配置
      │
      ├─ MemoryRecordGenerator
      │  │
      │  ├─ MemoryClassifier
      │  │
      │  └─ CallchainRefiner
      │     │
      │     ├─ CallchainFilterConfig
      │     │
      │     └─ MemoryDataLoader
      │
      └─ MemoryComparisonExporter
         └─ pandas, xlsxwriter
```

## 配置流向

```
MemoryAnalyzer.__init__()
  │
  ├─ use_refined_lib_symbol: bool
  │  └─ 传递给 MemoryAnalyzerCore
  │     └─ 传递给 MemoryRecordGenerator
  │        └─ 控制是否使用 refined 值
  │
  └─ export_comparison: bool
     └─ 传递给 MemoryAnalyzerCore
        └─ 控制是否导出对比 Excel
```

## 性能考虑

```
数据库查询
  │
  ├─ 首次分析
  │  ├─ 查询所有 native_hook 事件: O(n)
  │  ├─ 查询所有 callchain 帧: O(m)
  │  └─ 查询 data_dict: O(k)
  │
  └─ Refined 模式
     ├─ 每个事件查询 callchain: O(n * p)
     │  其中 p = 平均 callchain 长度
     │
     └─ 缓存优化: O(unique_callchains * p)
        其中 unique_callchains << n
```

