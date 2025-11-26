# HAP 文件地址解析工具使用说明

## 问题背景

在性能分析中，perf 数据可能包含来自 HAP 文件的地址，格式如：
- `entry.hap@0x5adaa0440e`

这些地址是 HAP 文件（ZIP 格式）内的偏移量，而不是解压后 SO 文件内的偏移量。需要将这些地址转换为对应的 SO 文件内的实际偏移量。

## 工具功能

`hap_address_resolver.py` 工具可以：
1. 解压 HAP 文件，提取所有 SO 文件
2. 根据 HAP 文件内的偏移量找到对应的 SO 文件
3. 计算 SO 文件内的实际偏移量
4. 可选：使用 radare2 分析找到的函数

## 使用方法

### 基本用法

```bash
# 解析单个地址
python3 hap_address_resolver.py entry.hap entry.hap@0x5adaa0440e

# 解析并分析函数
python3 hap_address_resolver.py entry.hap entry.hap@0x5adaa0440e --analyze
```

### 批量解析

```bash
# 从文件读取地址列表
python3 hap_address_resolver.py entry.hap --addresses addresses.txt
```

地址列表文件格式（每行一个地址）：
```
entry.hap@0x5adaa0440e
entry.hap@0x5adaa0570e
entry.hap@0x5adab7ebd9
```

## 工作原理

### 1. HAP 文件结构

HAP 文件是 ZIP 格式，包含：
- `libs/arm64-v8a/*.so` - SO 文件
- `config.json` - 配置文件
- 其他资源文件

### 2. 地址解析流程

```
HAP 文件内偏移量 (0x5adaa0440e)
    ↓
查找 ZIP 文件结构
    ↓
找到包含该偏移量的 SO 文件
    ↓
计算 SO 文件内的偏移量
    ↓
解压 SO 文件（如果需要）
    ↓
返回 SO 文件路径和偏移量
```

### 3. 注意事项

- **压缩文件**: 如果 SO 文件在 ZIP 中是压缩的，需要先解压
- **内存映射**: 运行时 HAP 文件会被映射到内存，地址可能与文件偏移量不同
- **ZIP 格式**: ZIP 文件格式复杂，工具会尝试自动处理

## 集成到符号恢复流程

### 方法 1: 预处理地址

在分析前，先将 HAP 地址转换为 SO 文件地址：

```python
from hap_address_resolver import HapAddressResolver

resolver = HapAddressResolver('entry.hap')
result = resolver.resolve_address('entry.hap@0x5adaa0440e')

if result:
    so_file = result['so_path']
    so_offset = result['so_offset']
    # 使用 so_file 和 so_offset 进行分析
```

### 方法 2: 修改 perf_converter.py

在 `perf_converter.py` 中添加 HAP 地址处理：

```python
def process_address(self, address_str):
    """处理地址字符串"""
    if '@' in address_str and address_str.endswith('.hap'):
        # HAP 文件地址
        resolver = HapAddressResolver(self.hap_file)
        result = resolver.resolve_address(address_str)
        if result:
            return f"{result['so_name']}+0x{result['so_offset']:x}"
    else:
        # 普通 SO 文件地址
        return address_str
```

## 限制和已知问题

1. **内存映射地址**: 如果地址是运行时内存映射地址，而不是文件偏移量，需要额外的转换
2. **压缩文件**: 压缩的 SO 文件需要先解压，可能影响性能
3. **ZIP 格式变体**: 某些 ZIP 格式变体可能不被支持

## 替代方案

### 方案 1: 直接解压 HAP 文件

如果 HAP 文件不大，可以直接解压所有 SO 文件：

```bash
# 解压 HAP 文件
unzip entry.hap -d extracted/

# 使用解压后的 SO 文件进行分析
python3 dump_and_find_function.py extracted/libs/arm64-v8a/libquick.so 0xc8a7c
```

### 方案 2: 使用项目中的 HAP 解析器

项目中的 `tools/static_analyzer` 已经有 HAP 解析功能，可以复用：

```typescript
// TypeScript 版本
import { Hap } from './core/hap/hap_parser';
const hap = await Hap.loadFromHap('entry.hap');
await hap.extract('output_dir');
```

### 方案 3: 运行时地址转换

如果地址是运行时内存映射地址，需要：
1. 获取进程的内存映射信息（/proc/{pid}/maps）
2. 找到 HAP 文件的内存映射区域
3. 计算文件偏移量

## 示例

### 示例 1: 解析单个地址

```bash
$ python3 hap_address_resolver.py entry.hap entry.hap@0x5adaa0440e

正在解压 HAP 文件: entry.hap
临时目录: /tmp/hap_extract_xxxxx
  找到 SO 文件: libquick.so (1123456 字节)
  找到 SO 文件: libxwebcore.so (2345678 字节)

解析地址: entry.hap@0x5adaa0440e
  HAP 文件: entry.hap
  HAP 偏移量: 0x5adaa0440e (390937088014)

查找 HAP 偏移量 0x5adaa0440e 对应的 SO 文件...
  ZIP 文件大小: 5000000 字节
  Central Directory 偏移: 0x4c0000
  文件数量: 15
  ✅ 找到 SO 文件: libquick.so
     ZIP 数据范围: 0x5adaa00000 - 0x5adab00000
     SO 文件路径: /tmp/hap_extract_xxxxx/libs_arm64-v8a_libquick.so
     SO 文件内偏移: 0x440e

================================================================================
解析总结: 1/1 成功
================================================================================

entry.hap@0x5adaa0440e
  -> libquick.so @ 0x440e
     文件: /tmp/hap_extract_xxxxx/libs_arm64-v8a_libquick.so
```

### 示例 2: 解析并分析函数

```bash
$ python3 hap_address_resolver.py entry.hap entry.hap@0x5adaa0440e --analyze

... (解析过程) ...

使用 radare2 分析函数...
  函数名: fcn.0000440e
  函数范围: 0x440e - 0x4500
  函数大小: 242 字节
```

## 故障排除

### 问题 1: 无法找到对应的 SO 文件

**原因**: 
- 偏移量不在任何 SO 文件的范围内
- ZIP 文件格式不标准

**解决**:
- 检查偏移量是否正确
- 尝试直接解压 HAP 文件查看结构

### 问题 2: 偏移量计算错误

**原因**:
- SO 文件在 ZIP 中是压缩的
- ZIP 文件格式变体

**解决**:
- 工具会自动解压文件
- 检查解压后的文件是否正确

### 问题 3: 内存映射地址

**原因**:
- 地址是运行时内存映射地址，不是文件偏移量

**解决**:
- 需要获取进程的内存映射信息
- 计算文件偏移量 = 内存地址 - 映射基址

## 相关工具

- `dump_and_find_function.py` - 根据偏移量查找函数
- `verify_excel_offsets.py` - 验证 Excel 中的偏移量
- `verify_function_finding.py` - 验证函数查找准确性

## 参考

- [ZIP 文件格式规范](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)
- [HAP 文件格式](https://developer.harmonyos.com/cn/docs/documentation/doc-guides/basic-concepts-overview-0000000000031907)

