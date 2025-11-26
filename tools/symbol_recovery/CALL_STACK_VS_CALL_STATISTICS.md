# 调用堆栈 vs 调用统计

## 区别说明

### 调用堆栈（Call Stack）✅ 已实现

**定义**：描述函数的调用关系，即函数在调用链中的位置

**包含信息**：
1. **调用者（Callers）**：哪些函数调用了当前函数
2. **被调用者（Callees）**：当前函数调用了哪些有符号的函数

**数据来源**：从 `perf.db` 的 `perf_callchain` 表查询

**实现位置**：
- `_get_call_stack_info()`: 从 perf.db 获取调用堆栈信息
- `_enhance_context_with_call_stack()`: 将调用堆栈信息添加到上下文

**示例**：
```
调用堆栈信息（谁调用了这个函数）:
  1. parseExpression (libquick.so+0x12345)
  2. evaluateExpression (libquick.so+0x67890)

被调用的函数（这个函数调用了哪些有符号的函数）:
  1. nextToken (libquick.so+0x97794)
  2. malloc (libc.so+0x12345)
```

**用途**：
- 了解函数的调用上下文
- 推断函数的使用场景
- 识别函数在调用链中的位置
- 帮助理解函数的功能模块

---

### 调用统计（Call Statistics）✅ 已实现

**定义**：描述函数的调用频率和执行频率，即函数被调用了多少次

**包含信息**：
1. **调用次数（call_count）**：函数被调用的总次数（数值）
2. **指令执行次数（event_count）**：函数内指令的总执行次数（数值）

**数据来源**：从 `perf.db` 的 `perf_sample` 和 `perf_callchain` 表统计

**实现位置**：
- 在 `_get_missing_symbols_from_perf_db()` 中统计
- 在 `analyze_function()` 中传递给 LLM

**示例**：
```
调用次数: 1,234
指令执行次数(event_count): 5,678,901
```

**用途**：
- 识别热点函数（调用次数多的函数）
- 识别性能瓶颈（执行次数多的函数）
- 推断函数的重要性
- 帮助优化分析优先级

---

## 对比表

| 特性 | 调用堆栈（Call Stack） | 调用统计（Call Statistics） |
|------|---------------------|-------------------------|
| **类型** | 关系信息（谁调用了谁） | 数值信息（调用了多少次） |
| **内容** | 调用者列表、被调用者列表 | 调用次数、执行次数 |
| **数据来源** | `perf_callchain` 表（查询调用关系） | `perf_sample` + `perf_callchain`（统计计数） |
| **格式** | 函数名、地址、深度 | 数值（整数） |
| **用途** | 理解调用关系、推断功能 | 识别热点、优化优先级 |
| **已实现** | ✅ 是 | ✅ 是 |

---

## 在 LLM Prompt 中的使用

### 调用堆栈信息
在 `context` 字段中，通过 `_enhance_context_with_call_stack()` 添加：

```
背景信息:
这是一个基于 Chromium Embedded Framework (CEF) 的 Web 核心库（libquick.so），
运行在 HarmonyOS 平台上。

调用堆栈信息（谁调用了这个函数）:
  1. parseExpression (libquick.so+0x12345)
  2. evaluateExpression (libquick.so+0x67890)

被调用的函数（这个函数调用了哪些有符号的函数）:
  1. nextToken (libquick.so+0x97794)
```

### 调用统计信息
在 prompt 的单独字段中显示：

```
函数偏移量: 0xc8a7c
函数范围: 0xc8a7c - 0xc8bcf (大小: 299 字节)
指令数量: 75 条
调用次数: 1,234
指令执行次数(event_count): 5,678,901
```

---

## 总结

- **调用堆栈**：描述"谁调用了谁"（关系信息）
- **调用统计**：描述"调用了多少次"（数值信息）

两者是**互补的**：
- 调用堆栈帮助理解函数的调用上下文和功能模块
- 调用统计帮助识别热点函数和优化优先级

两者都已实现并传递给 LLM，提供更全面的上下文信息。

