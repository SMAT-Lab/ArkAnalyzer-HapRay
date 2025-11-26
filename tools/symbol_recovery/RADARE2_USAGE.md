# Radare2 使用指南

## 目录
1. [安装](#安装)
2. [基本使用](#基本使用)
3. [Dump SO 文件](#dump-so-文件)
4. [Python 接口 (r2pipe)](#python-接口-r2pipe)
5. [常用命令速查](#常用命令速查)

---

## 安装

### macOS
```bash
brew install radare2
```

### Linux
```bash
# Ubuntu/Debian
sudo apt-get install radare2

# CentOS/RHEL
sudo yum install radare2
```

### Python 接口
```bash
pip install r2pipe
```

---

## 基本使用

### 1. 打开 SO 文件

#### 命令行方式
```bash
# 基本打开（交互模式）
r2 libquick.so

# 自动分析并打开（非交互模式）
r2 -A libquick.so

# 快速分析（推荐，比 -A 快）
r2 -AA libquick.so
```

#### Python 方式（r2pipe）
```python
import r2pipe

# 打开文件
r2 = r2pipe.open('libquick.so', flags=['-2'])

# 执行分析
r2.cmd('aa')  # 快速分析（推荐）
# 或
r2.cmd('aaa')  # 完整分析（较慢）

# 关闭
r2.quit()
```

---

## Dump SO 文件

### 1. 导出原始二进制数据

#### 导出整个文件
```bash
# 命令行
r2 -c "wtf dump_libquick.bin" libquick.so

# Python
r2 = r2pipe.open('libquick.so')
r2.cmd('wtf dump_libquick.bin')
r2.quit()
```

#### 导出指定地址范围
```bash
# 导出 0x10000 到 0x20000 的数据
r2 -c "s 0x10000; wtf dump_segment.bin 0x10000" libquick.so
```

### 2. 导出反汇编代码

#### 导出所有函数的反汇编
```bash
# 命令行（JSON 格式）
r2 -A -c "aflj" libquick.so > functions.json

# 导出所有函数的反汇编文本
r2 -A -c "afl~fcn" libquick.so | while read func; do
    r2 -c "pdf @$func" libquick.so >> disasm.txt
done
```

#### Python 方式
```python
import r2pipe
import json

r2 = r2pipe.open('libquick.so')
r2.cmd('aa')  # 快速分析

# 获取所有函数列表
functions_json = r2.cmd('aflj')
functions = json.loads(functions_json)

# 导出每个函数的反汇编
with open('disasm.txt', 'w') as f:
    for func in functions:
        func_addr = func.get('offset', 0)
        disasm = r2.cmd(f'pdf @{func_addr}')
        f.write(f'\n=== Function at 0x{func_addr:x} ===\n')
        f.write(disasm)
        f.write('\n')

r2.quit()
```

### 3. 导出反编译代码

#### 安装反编译插件
```bash
# r2dec（推荐，轻量快速）
r2pm install r2dec

# r2ghidra（高质量，需要 Java）
r2pm install r2ghidra
```

#### 导出反编译代码
```bash
# 命令行 - 单个函数
r2 -A -c "s @0xc8a7c; pdg" libquick.so > func_decompiled.c

# 命令行 - 所有函数
r2 -A -c "afl~fcn" libquick.so | while read func; do
    r2 -c "s @$func; pdg" libquick.so >> all_decompiled.c
done
```

#### Python 方式
```python
import r2pipe

r2 = r2pipe.open('libquick.so')
r2.cmd('aa')

# 尝试不同的反编译器（按优先级）
decompilers = [
    ('pdd', 'r2dec'),
    ('pdg', 'r2ghidra'),
    ('pdq', 'pdq')
]

func_addr = 0xc8a7c
r2.cmd(f's @{func_addr}')

decompiled = None
for cmd, name in decompilers:
    try:
        decompiled = r2.cmd(cmd)
        if decompiled and 'WARNING' not in decompiled[:100]:
            print(f'使用 {name} 反编译成功')
            break
    except:
        continue

if decompiled:
    with open('decompiled.c', 'w') as f:
        f.write(decompiled)

r2.quit()
```

### 4. 导出字符串

```bash
# 命令行
r2 -c "iz" libquick.so > strings.txt

# JSON 格式
r2 -c "izj" libquick.so > strings.json
```

```python
import r2pipe
import json

r2 = r2pipe.open('libquick.so')
strings_json = r2.cmd('izj')
strings = json.loads(strings_json)

for s in strings:
    print(f"0x{s['vaddr']:x}: {s['string']}")

r2.quit()
```

### 5. 导出符号表

```bash
# 命令行
r2 -c "isj" libquick.so > symbols.json

# 导出函数符号
r2 -c "aflj" libquick.so > functions.json
```

```python
import r2pipe
import json

r2 = r2pipe.open('libquick.so')
r2.cmd('aa')

# 获取所有函数（JSON）
functions = json.loads(r2.cmd('aflj'))

# 获取符号表
symbols = json.loads(r2.cmd('isj'))

r2.quit()
```

### 6. 导出段信息

```bash
# 命令行
r2 -c "iSj" libquick.so > sections.json
```

```python
import r2pipe
import json

r2 = r2pipe.open('libquick.so')
sections = json.loads(r2.cmd('iSj'))

for sec in sections:
    print(f"{sec['name']}: 0x{sec['vaddr']:x} - 0x{sec['vaddr'] + sec['vsize']:x}")

r2.quit()
```

---

## Python 接口 (r2pipe)

### 基本用法

```python
import r2pipe
import json

# 打开文件
r2 = r2pipe.open('libquick.so', flags=['-2'])

# 执行分析
r2.cmd('aa')  # 快速分析（推荐，比 aaa 快 10 倍+）

# 执行命令并获取结果
result = r2.cmd('aflj')  # 返回字符串
functions = json.loads(result)  # 解析 JSON

# 执行命令并获取 JSON（自动解析）
functions = r2.cmdj('aflj')  # 直接返回 Python 对象

# 跳转到地址
r2.cmd('s @0xc8a7c')

# 获取当前地址
current_addr = r2.cmd('s')

# 关闭
r2.quit()
```

### 项目中的实际使用示例

参考 `core/analyzers/r2_analyzer.py`：

```python
from pathlib import Path
import r2pipe

class R2FunctionAnalyzer:
    def __init__(self, so_file: Path):
        self.so_file = so_file
        self.r2 = None
    
    def _open_r2(self, analyze_all=False):
        """打开 radare2 实例"""
        if self.r2 is None:
            self.r2 = r2pipe.open(str(self.so_file), flags=['-2'])
            if analyze_all:
                self.r2.cmd('aaa')  # 完整分析
            else:
                self.r2.cmd('aa')   # 快速分析（推荐）
    
    def find_function_by_offset(self, offset: int):
        """根据偏移量查找函数"""
        self._open_r2(analyze_all=False)
        
        # 获取所有函数（JSON）
        functions_json = self.r2.cmd('aflj')
        functions = json.loads(functions_json)
        
        # 查找包含该偏移量的函数
        for func in functions:
            minbound = func.get('minbound', func.get('offset', 0))
            maxbound = func.get('maxbound', func.get('offset', 0) + func.get('size', 0))
            if minbound <= offset < maxbound:
                return func
        return None
    
    def disassemble_function(self, offset: int):
        """反汇编函数"""
        self._open_r2()
        disasm_json = self.r2.cmd(f'pdfj @{offset}')
        return json.loads(disasm_json)
    
    def decompile_function(self, offset: int):
        """反编译函数"""
        self._open_r2()
        self.r2.cmd(f's @{offset}')
        
        # 按优先级尝试不同反编译器
        for cmd in ['pdd', 'pdg', 'pdq']:
            try:
                decompiled = self.r2.cmd(cmd)
                if decompiled and 'WARNING' not in decompiled[:100]:
                    return decompiled
            except:
                continue
        return None
```

---

## 常用命令速查

### 分析命令
- `aa` - 快速分析（推荐，分析基本块和函数）
- `aaa` - 完整分析（较慢，分析所有内容）
- `afl` - 列出所有函数
- `aflj` - 列出所有函数（JSON 格式）
- `afij` - 获取当前函数信息（JSON）
- `af @0xADDR` - 分析指定地址的函数

### 反汇编命令
- `pd` - 反汇编当前地址
- `pdf` - 反汇编当前函数
- `pdfj` - 反汇编当前函数（JSON）
- `pdf @0xADDR` - 反汇编指定地址的函数
- `pd 100` - 反汇编 100 条指令

### 反编译命令
- `pdd` - r2dec 反编译
- `pdg` - r2ghidra 反编译
- `pdq` - pdq 反编译

### 字符串命令
- `iz` - 列出所有字符串
- `izj` - 列出所有字符串（JSON）
- `iz @0xADDR` - 列出指定地址的字符串

### 符号命令
- `is` - 列出符号
- `isj` - 列出符号（JSON）
- `afl` - 列出函数符号

### 段/节命令
- `iS` - 列出段
- `iSj` - 列出段（JSON）
- `S` - 段操作

### 交叉引用命令
- `axt` - 列出交叉引用（xrefs to）
- `axtj` - 列出交叉引用（JSON）
- `axt @0xADDR` - 列出指向指定地址的引用
- `axf` - 列出交叉引用（xrefs from）
- `axfj` - 列出交叉引用（JSON）
- `axfj @0xADDR` - 列出从指定地址的引用

### 导航命令
- `s 0xADDR` - 跳转到地址
- `s @0xADDR` - 跳转到地址（函数模式）
- `s` - 显示当前地址
- `s+` - 下一个地址
- `s-` - 上一个地址

### 导出命令
- `wtf filename` - 写入文件（导出二进制）
- `wtf filename 0x1000` - 导出指定大小的数据
- `wtf filename @0xADDR 0x1000` - 从指定地址导出

### 搜索命令
- `/ STRING` - 搜索字符串
- `/x 41 42 43` - 搜索十六进制
- `/a` - 搜索汇编指令

---

## 完整 Dump 示例

### 导出 SO 文件的完整信息

```python
#!/usr/bin/env python3
"""完整导出 SO 文件的所有信息"""

import r2pipe
import json
from pathlib import Path

def dump_so_file(so_file: str, output_dir: str):
    """导出 SO 文件的所有信息"""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    
    r2 = r2pipe.open(so_file, flags=['-2'])
    r2.cmd('aa')  # 快速分析
    
    # 1. 导出二进制
    print("导出二进制...")
    r2.cmd(f'wtf {output / "dump.bin"}')
    
    # 2. 导出函数列表
    print("导出函数列表...")
    functions = r2.cmdj('aflj')
    with open(output / 'functions.json', 'w') as f:
        json.dump(functions, f, indent=2)
    
    # 3. 导出所有函数的反汇编
    print("导出反汇编...")
    with open(output / 'disasm.txt', 'w') as f:
        for func in functions:
            addr = func.get('offset', 0)
            name = func.get('name', f'fcn.{addr:x}')
            disasm = r2.cmd(f'pdf @{addr}')
            f.write(f'\n{"="*80}\n')
            f.write(f'Function: {name} @ 0x{addr:x}\n')
            f.write(f'{"="*80}\n')
            f.write(disasm)
            f.write('\n')
    
    # 4. 导出反编译代码
    print("导出反编译代码...")
    with open(output / 'decompiled.c', 'w') as f:
        for func in functions:
            addr = func.get('offset', 0)
            name = func.get('name', f'fcn.{addr:x}')
            r2.cmd(f's @{addr}')
            
            # 尝试反编译
            decompiled = None
            for cmd in ['pdd', 'pdg', 'pdq']:
                try:
                    decompiled = r2.cmd(cmd)
                    if decompiled and 'WARNING' not in decompiled[:100]:
                        break
                except:
                    continue
            
            if decompiled:
                f.write(f'\n/* Function: {name} @ 0x{addr:x} */\n')
                f.write(decompiled)
                f.write('\n')
    
    # 5. 导出字符串
    print("导出字符串...")
    strings = r2.cmdj('izj')
    with open(output / 'strings.json', 'w') as f:
        json.dump(strings, f, indent=2)
    
    # 6. 导出符号表
    print("导出符号表...")
    symbols = r2.cmdj('isj')
    with open(output / 'symbols.json', 'w') as f:
        json.dump(symbols, f, indent=2)
    
    # 7. 导出段信息
    print("导出段信息...")
    sections = r2.cmdj('iSj')
    with open(output / 'sections.json', 'w') as f:
        json.dump(sections, f, indent=2)
    
    r2.quit()
    print(f"✅ 导出完成，输出目录: {output}")

if __name__ == '__main__':
    dump_so_file('libquick.so', 'dump_output')
```

### 使用示例

```bash
# 运行脚本
python dump_so.py

# 输出目录结构
dump_output/
├── dump.bin          # 原始二进制
├── functions.json     # 函数列表
├── disasm.txt         # 反汇编代码
├── decompiled.c       # 反编译代码
├── strings.json       # 字符串
├── symbols.json       # 符号表
└── sections.json      # 段信息
```

---

## 注意事项

1. **性能优化**：
   - 使用 `aa` 而不是 `aaa`（快 10 倍+）
   - 复用 r2pipe 实例，避免重复初始化
   - 使用 JSON 格式（`j` 后缀）提高解析效率

2. **反编译器选择**：
   - `pdd` (r2dec)：轻量快速，适合批量分析
   - `pdg` (r2ghidra)：高质量，类型推断准确，但需要 Java
   - `pdq`：快速反编译器，作为备选

3. **地址格式**：
   - `0xADDR` - 十六进制地址
   - `@0xADDR` - 函数模式地址
   - `s @0xADDR` - 跳转到函数地址

4. **错误处理**：
   - 反编译器可能失败，需要按优先级尝试多个
   - 某些命令可能返回空结果，需要检查

---

## 参考资源

- [Radare2 官方文档](https://radare.gitbooks.io/radare2book/)
- [r2pipe Python API](https://r2wiki.readthedocs.io/en/latest/tools/r2pipe-python/)
- [Radare2 命令参考](https://book.rada.re/basic_commands/intro.html)

