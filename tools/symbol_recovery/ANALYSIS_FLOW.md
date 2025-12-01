# 符号恢复工具 - 完整分析流程说明

## 整体流程概览

```
perf.data 
  ↓
perf.db (SQLite)
  ↓
提取缺失符号地址 (libquick.so+0xc8a7c)
  ↓
函数定位与切分 (radare2)
  ↓
反汇编/反编译 (radare2)
  ↓
提取上下文信息 (字符串、调用函数、调用堆栈)
  ↓
构建 LLM Prompt
  ↓
LLM 分析推断函数名
```

## 详细流程说明

### 1. 函数定位 (Function Location)

**输入**: `libquick.so+0xc8a7c` (从 perf.db 中提取的缺失符号地址)

**步骤**:
1. 解析地址，提取偏移量: `0xc8a7c`
2. 打开 SO 文件，使用 radare2 分析
3. 使用 `aflj` 获取所有函数列表（JSON 格式）
4. 查找包含该偏移量的函数：
   ```python
   # 检查条件：minbound <= offset < maxbound
   # 注意：radare2 不同版本可能使用不同字段名（aflj 使用 minbound/maxbound，afij 使用 minaddr/maxaddr）
   for func in functions:
       minbound = func.get('minbound', func.get('minaddr', func.get('offset', 0)))
       maxbound = func.get('maxbound', func.get('maxaddr', func.get('offset', 0) + func.get('size', 0)))
       if minbound <= 0xc8a7c < maxbound:
           # 找到匹配的函数
   ```
5. 如果没找到，使用 `af @0xc8a7c` 只分析该地址的函数

**输出**: 函数信息字典
```python
{
    'name': 'fcn.000c8a7c',  # 函数名（如果没有符号）
    'offset': 0xc8a7c,       # 函数起始地址
    'size': 299,              # 函数大小（字节）
    'minbound': 0xc8a7c,      # 函数最小边界
    'maxbound': 0xc8a8cf,     # 函数最大边界
    'nargs': 0,               # 参数数量
    'nbbs': 5,                # 基本块数量
}
```

### 2. 函数切分 (Function Boundary Detection)

**方法**: 使用 radare2 的 `afij` 命令获取函数详细信息

**关键逻辑**:
- 使用 `minbound` 和 `maxbound` 精确确定函数边界
- 如果函数大小 > 100KB，认为不合理，跳过
- 如果找不到，使用默认大小 2000 字节

**示例**:
```python
# radare2 命令
func_info = r2.cmd('afij @0xc8a7c')
# 返回 JSON:
{
    "offset": 0xc8a7c,
    "size": 299,
    "minbound": 0xc8a7c,
    "maxbound": 0xc8a8cf,
    "name": "fcn.000c8a7c"
}
```

### 3. 反汇编 (Disassembly)

**方法**: 使用 radare2 的 `pdfj` 命令（JSON 格式反汇编）

**命令**: `pdfj @0xc8a7c`

**输出示例**:
```json
[
  {
    "ops": [
      {"offset": 0xc8a7c, "opcode": "pacibsp"},
      {"offset": 0xc8a80, "opcode": "stp x29, x30, [sp, #-0x10]!"},
      {"offset": 0xc8a84, "opcode": "mov x29, sp"},
      {"offset": 0xc8a88, "opcode": "sub sp, sp, #0x20"},
      ...
    ]
  }
]
```

**转换为文本格式**:
```python
instructions = [
    "0xc8a7c: pacibsp",
    "0xc8a80: stp x29, x30, [sp, #-0x10]!",
    "0xc8a84: mov x29, sp",
    "0xc8a88: sub sp, sp, #0x20",
    ...
]
```

### 4. 反编译 (Decompilation)

**方法**: 按优先级尝试不同的反编译插件

**插件优先级**:
1. `pdd` (r2dec) - 优先使用
2. `pdg` (r2ghidra) - Ghidra 反编译器
3. `pdq` (pdq) - 快速反编译器

**命令**: 
```python
r2.cmd('s @0xc8a7c')  # 跳转到函数位置
decompiled = r2.cmd('pdg')  # 反编译
```

**输出示例**:
```c
void fcn.000c8a7c(int64_t arg1, int64_t arg2) {
    int64_t var_10;
    int64_t var_18;
    
    pacibsp();
    var_10 = arg1;
    var_18 = arg2;
    
    // 主要逻辑...
    if (var_10 != 0) {
        // ...
    }
    
    return;
}
```

**长度限制**:
- 函数 < 200 字节: 最多 500 行
- 函数 < 500 字节: 最多 1500 行
- 函数 >= 500 字节: 最多 5000 行

**过滤**: 移除所有 `//WARNING` 开头的行

### 5. 字符串常量提取 (String Extraction)

**方法**: 分析反汇编指令中的字符串引用

**ARM64 字符串引用模式**:
1. `adrp + add` 指令对:
   ```
   adrp x0, #0x1234000    ; 设置页基址
   add x0, x0, #0x567     ; 加上页内偏移
   ```
2. `adr` 指令:
   ```
   adr x0, #0x1234        ; 直接加载地址
   ```
3. `ldr` 指令中的立即数:
   ```
   ldr x0, [x1, #0x1234]  ; 从基址+偏移加载
   ```

**提取流程**:
```python
# 1. 查找 .rodata 或 .data 段
rodata_section = elf_file.get_section_by_name('.rodata')

# 2. 分析指令，查找字符串引用
for inst in instructions:
    if inst.mnemonic == 'adrp':
        page_base = parse_adrp(inst)  # 解析页基址
        adrp_registers[reg] = page_base
    elif inst.mnemonic == 'add':
        full_addr = parse_add(inst, adrp_registers)  # 计算完整地址
        if addr_in_rodata_section(full_addr):
            string_addresses.add(full_addr)

# 3. 从找到的地址提取字符串
for str_addr in string_addresses:
    string = extract_string_at_address(rodata_section, str_addr)
    strings.append(string)
```

**输出示例**:
```python
strings = [
    "parseBinaryExpression",
    "unparenthesized unary expression",
    ...
]
```

### 6. 调用函数提取 (Called Functions Extraction)

**方法**: 使用 radare2 的 `axtj` 命令查找交叉引用

**命令**: `axtj @0xc8a7c`

**输出示例**:
```json
[
  {
    "type": "CALL",
    "from": 0xc8a90,
    "to": 0x97794,
    "opcode": "bl sym.imp.nextToken"
  },
  {
    "type": "CALL",
    "from": 0xc8aa0,
    "to": 0xc1bcc,
    "opcode": "bl fcn.000c1bcc"
  }
]
```

**提取函数名**:
```python
for xref in xrefs:
    if 'CALL' in xref['type']:
        target_addr = xref['to']
        # 查找该地址对应的函数名
        func_name = r2.cmd(f'fdj @{target_addr}')
        called_functions.append(func_name)
```

**输出示例**:
```python
called_functions = [
    "sym.imp.nextToken",
    "fcn.000c1bcc",
    "fcn.000c8a60",
    ...
]
```

### 7. 调用堆栈信息 (Call Stack Information)

**方法**: 从 perf.db 查询调用链

**查询调用者** (depth 更小的函数):
```sql
SELECT DISTINCT pc2.file_id, pc2.name, pc2.depth, pc2.symbol_id
FROM perf_callchain pc1
JOIN perf_sample ps ON pc1.callchain_id = ps.callchain_id
JOIN perf_callchain pc2 ON ps.callchain_id = pc2.callchain_id
WHERE pc1.file_id = ? AND pc1.name = ? AND pc1.symbol_id = -1
  AND pc2.depth < pc1.depth
  AND pc2.symbol_id != -1
ORDER BY pc2.depth DESC
LIMIT 10
```

**查询被调用者** (depth 更大的函数):
```sql
SELECT DISTINCT pc2.file_id, pc2.name, pc2.depth, pc2.symbol_id
FROM perf_callchain pc1
JOIN perf_sample ps ON pc1.callchain_id = ps.callchain_id
JOIN perf_callchain pc2 ON ps.callchain_id = pc2.callchain_id
WHERE pc1.file_id = ? AND pc1.name = ? AND pc1.symbol_id = -1
  AND pc2.depth > pc1.depth
  AND pc2.symbol_id != -1
ORDER BY pc2.depth ASC
LIMIT 10
```

**输出示例**:
```python
call_stack_info = {
    'callers': [
        {
            'file_path': '/path/to/libquick.so',
            'address': 'libquick.so+0x12345',
            'symbol_name': 'parseExpression',
            'depth': 2
        }
    ],
    'callees': [
        {
            'file_path': '/path/to/libquick.so',
            'address': 'libquick.so+0x97794',
            'symbol_name': 'nextToken',
            'depth': 4
        }
    ]
}
```

### 8. 性能分析上下文 (Performance Analysis Context)

**新增功能**：针对高指令数负载的热点函数，提供性能分析指导

**性能瓶颈因素**：
- 循环和迭代（特别是嵌套循环、大循环次数）
- 内存操作（大量内存拷贝、频繁的内存分配/释放）
- 字符串处理（字符串拼接、解析、格式化）
- 算法复杂度（O(n²)、O(n³) 等高复杂度算法）
- 系统调用和 I/O 操作（文件读写、网络操作）
- 递归调用（深度递归可能导致栈溢出或高指令数）
- 异常处理（频繁的异常捕获和处理）
- 锁和同步操作（频繁的加锁/解锁、条件等待）
- 数据结构和算法选择不当（低效的数据结构使用）

**函数元信息**：
- 函数边界：起始地址（minbound）、结束地址（maxbound）、大小
- 复杂度指标：基本块数量（nbbs）、控制流边（edges）、参数数量（nargs）、局部变量数量（nlocals）
- SO 文件信息：文件路径、库名称

### 9. Prompt 构建 (Prompt Construction)

**完整示例**:

```python
# 输入数据
function_data = {
    'function_id': 'func_1',
    'offset': 'libquick.so+0xc8a7c',
    'instructions': [
        "0xc8a7c: pacibsp",
        "0xc8a80: stp x29, x30, [sp, #-0x10]!",
        ...
    ],
    'decompiled': """
        void fcn.000c8a7c(int64_t arg1, int64_t arg2) {
            // 函数逻辑...
        }
    """,
    'strings': [
        "parseBinaryExpression",
        "unparenthesized unary expression"
    ],
    'called_functions': [
        "sym.imp.nextToken",
        "fcn.000c1bcc"
    ],
    'symbol_name': None
}

# 上下文信息
context = """
这是一个基于 Chromium Embedded Framework (CEF) 的 Web 核心库（libquick.so），
运行在 HarmonyOS 平台上。该库负责网页渲染、网络请求、DOM 操作等核心功能。

调用堆栈信息（谁调用了这个函数）:
  1. parseExpression (libquick.so+0x12345)
  2. evaluateStatement (libquick.so+0x23456)

被调用的函数（这个函数调用了哪些有符号的函数）:
  1. nextToken (libquick.so+0x97794)
  2. emitError (libquick.so+0x88888)
"""
```

**生成的 Prompt**:

```
请分析以下多个 ARM64 反汇编函数，推断每个函数的功能和可能的函数名。

⚠️ 重要提示：这是一个性能分析场景，这些函数被识别为高指令数负载的热点函数。
请重点关注可能导致性能问题的因素，包括但不限于：
  - 循环和迭代（特别是嵌套循环、大循环次数）
  - 内存操作（大量内存拷贝、频繁的内存分配/释放）
  - 字符串处理（字符串拼接、解析、格式化）
  - 算法复杂度（O(n²)、O(n³) 等高复杂度算法）
  - 系统调用和 I/O 操作（文件读写、网络操作）
  - 递归调用（深度递归可能导致栈溢出或高指令数）
  - 异常处理（频繁的异常捕获和处理）
  - 锁和同步操作（频繁的加锁/解锁、条件等待）
  - 数据结构和算法选择不当（低效的数据结构使用）

请分别提供以下信息：
  1. 功能描述：函数的主要功能是什么（不要包含性能分析）
  2. 负载问题识别与优化建议：
     - 是否存在明显的性能瓶颈（如上述因素）
     - 为什么这个函数可能导致高指令数负载
     - 可能的优化建议（如果有）

背景信息:
这是一个基于 Chromium Embedded Framework (CEF) 的 Web 核心库（libquick.so），
运行在 HarmonyOS 平台上。该库负责网页渲染、网络请求、DOM 操作等核心功能。

调用堆栈信息（谁调用了这个函数）:
  1. parseExpression (libquick.so+0x12345)
  2. evaluateStatement (libquick.so+0x23456)

被调用的函数（这个函数调用了哪些有符号的函数）:
  1. nextToken (libquick.so+0x97794)
  2. emitError (libquick.so+0x88888)

================================================================================
函数 1 (ID: func_1)
================================================================================
函数偏移量: libquick.so+0xc8a7c

反编译代码（伪 C 代码）:
  void fcn.000c8a7c(int64_t arg1, int64_t arg2) {
      int64_t var_10;
      int64_t var_18;
      
      pacibsp();
      var_10 = arg1;
      var_18 = arg2;
      
      if (var_10 != 0) {
          // 主要逻辑...
      }
      
      return;
  }

附近的字符串常量:
  - parseBinaryExpression
  - unparenthesized unary expression

调用的函数:
  - sym.imp.nextToken
  - fcn.000c1bcc

================================================================================
请按以下 JSON 格式返回分析结果:
{
  "functions": [
    {
      "function_id": "func_1",
      "functionality": "详细的功能描述（中文，50-200字，仅描述功能，不包含性能分析）",
      "function_name": "推断的函数名（英文，遵循常见命名规范）",
      "performance_analysis": "负载问题识别与优化建议（中文，100-300字）：是否存在性能瓶颈、为什么导致高指令数负载、可能的优化建议",
      "confidence": "高/中/低",
      "reasoning": "推理过程（中文，说明为什么这样推断）"
    },
    ...
  ]
}

注意:
1. 返回一个 JSON 对象，包含 'functions' 数组
2. 每个函数的结果必须包含 'function_id' 字段，对应输入中的函数 ID
3. 如果符号表中已有函数名，优先使用符号名（如果是 C++ 名称修饰，请还原）
4. 函数名应该遵循常见的命名规范（如驼峰命名、下划线命名）
5. 功能描述应该具体，但请控制在 150 字以内，避免过长导致 JSON 格式问题
6. 推理过程请控制在 200 字以内，简洁明了即可
7. 置信度评估标准：
   - '高'：能看到完整的函数逻辑，包括函数序言、主要业务逻辑、函数调用、返回值等，且功能明确
   - '中'：能看到部分函数逻辑，能推断出大致功能，但可能缺少一些细节
   - '低'：只能看到函数片段（如只有函数结尾），无法确定完整功能
8. 如果反汇编代码从函数开始（有 pacibsp 或 stp x29, x30），且能看到主要逻辑，置信度应该设为'高'或'中'
9. 如果无法确定，confidence 设为'低'，function_name 可以为 null
10. 重要：确保 JSON 格式完整，所有字符串字段必须正确闭合引号，不要截断
```

## 完整示例：从地址到 Prompt

### 输入
- **地址**: `libquick.so+0xc8a7c`
- **文件路径**: `/proc/37655/root/data/storage/el1/bundle/libs/arm64/libquick.so`
- **调用次数**: 26948
- **指令数(event_count)**: 39968913393

### 步骤 1: 函数定位
```python
# 解析地址
vaddr = 0xc8a7c

# 使用 radare2 查找函数
r2 = r2pipe.open('libquick.so')
r2.cmd('aa')  # 快速分析
func_info = r2.cmd('afij @0xc8a7c')
# 返回: {"offset": 0xc8a7c, "size": 299, "minbound": 0xc8a7c, "maxbound": 0xc8a8cf}
```

### 步骤 2: 反汇编
```python
# 反汇编函数
instructions_json = r2.cmd('pdfj @0xc8a7c')
instructions = [
    "0xc8a7c: pacibsp",
    "0xc8a80: stp x29, x30, [sp, #-0x10]!",
    "0xc8a84: mov x29, sp",
    "0xc8a88: sub sp, sp, #0x20",
    # ... 共 299 字节，约 75 条指令
]
```

### 步骤 3: 反编译
```python
# 反编译函数
r2.cmd('s @0xc8a7c')
decompiled = r2.cmd('pdg')
# 返回伪 C 代码（约 200 行，已过滤 warning）
```

### 步骤 4: 提取字符串
```python
# 分析指令中的字符串引用
# 找到 adrp+add 指令对指向 .rodata 段的地址
# 提取字符串
strings = [
    "parseBinaryExpression",
    "unparenthesized unary expression can't appear on the left-hand side of '**'"
]
```

### 步骤 5: 提取调用函数
```python
# 使用 axtj 查找交叉引用
xrefs = r2.cmd('axtj @0xc8a7c')
called_functions = [
    "sym.imp.nextToken",
    "fcn.000c1bcc",
    "fcn.000c8a60"
]
```

### 步骤 6: 获取调用堆栈
```python
# 从 perf.db 查询
call_stack_info = {
    'callers': [
        {'symbol_name': 'parseExpression', 'file_path': '...', 'address': '...'}
    ],
    'callees': [
        {'symbol_name': 'nextToken', 'file_path': '...', 'address': '...'}
    ]
}
```

### 步骤 7: 构建 Prompt
```python
# 整合所有信息
prompt = build_batch_prompt(
    functions_data=[{
        'function_id': 'func_1',
        'offset': 'libquick.so+0xc8a7c',
        'decompiled': decompiled,  # 优先使用反编译代码
        'strings': strings,
        'called_functions': called_functions
    }],
    context=enhanced_context  # 包含调用堆栈信息
)
```

### 步骤 8: LLM 分析
```python
# 发送到 LLM
response = llm.analyze(prompt)
# 返回:
{
    "functions": [{
        "function_id": "func_1",
        "function_name": "parseBinaryExpression",
        "functionality": "实现表达式解析器中的一元/二元运算解析与指令生成...",
        "performance_analysis": "存在明显的性能瓶颈：1) 深度递归调用导致栈开销；2) 大量字符串比较和解析操作；3) 频繁的内存分配。优化建议：使用迭代替代递归，缓存字符串比较结果，预分配内存池。",
        "confidence": "高",
        "reasoning": "大量基于优先级的分支、递归调用、遇到 token 调用 nextToken..."
    }]
}
```

## 关键优化点

1. **函数边界检测**: 使用 `minbound` 和 `maxbound` 精确确定函数范围
2. **反编译优先**: 如果有反编译代码，优先使用，不显示反汇编代码
3. **字符串精准提取**: 通过分析指令中的字符串引用，而不是简单扫描内存，自动过滤错误消息和调试信息
4. **调用堆栈信息**: 从 perf.db 获取真实的调用关系，提供更多上下文
5. **性能分析**: 针对高指令数负载的热点函数，自动识别性能瓶颈并提供优化建议
6. **上下文信息增强**: 提取函数元信息（边界、复杂度指标）和调用堆栈，提升 LLM 分析质量
7. **批量分析**: 一次分析多个函数，提高效率
8. **长度限制**: 根据函数大小动态调整反编译代码长度，避免包含函数边界外的代码


