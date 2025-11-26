# HAP 文件地址解析指南

## 问题背景

在性能分析中，perf 数据可能包含来自 HAP 文件的地址，格式如：
- `entry.hap@0x5adaa0440e`

这些地址需要转换为对应的 SO 文件内的偏移量，才能进行符号恢复。

## 目录结构

解压后的 HAP 文件通常有以下结构：
```
com.ss.hm.ugc.aweme/
├── entry.zip          # 原始 HAP/ZIP 文件
├── entry/             # 解压后的文件
│   └── libs/
│       └── arm64-v8a/  # SO 文件目录
│           ├── libquick.so
│           ├── libxwebcore.so
│           └── ...
└── decrypt/           # 解密后的文件（如 ABC 文件）
```

## 地址类型

HAP 文件中的地址可能有两种类型：

### 1. ZIP 文件内偏移量（文件偏移量）

- **特征**: 地址小于 ZIP 文件大小
- **示例**: `entry.hap@0x1000000`（如果 ZIP 文件 > 16MB）
- **处理**: 直接在 ZIP 文件中查找对应的 SO 文件

### 2. 内存映射地址（运行时地址）

- **特征**: 地址远大于 ZIP 文件大小（如 `0x5adaa0440e`）
- **示例**: `entry.hap@0x5adaa0440e`
- **处理**: 需要从 `/proc/{pid}/maps` 获取内存映射信息

## 工具使用

### 工具 1: `resolve_hap_address.py` - 基础解析工具

适用于 ZIP 文件内偏移量：

```bash
python3 resolve_hap_address.py entry.zip entry.hap@0x1000000 \
  --extracted-dir ./data/com.ss.hm.ugc.aweme \
  --analyze
```

### 工具 2: `resolve_hap_address_smart.py` - 智能解析工具

自动判断地址类型，支持内存映射地址：

```bash
# 自动判断地址类型
python3 resolve_hap_address_smart.py entry.zip entry.hap@0x5adaa0440e \
  --extracted-dir ./data/com.ss.hm.ugc.aweme

# 使用 maps 文件解析内存地址
python3 resolve_hap_address_smart.py entry.zip entry.hap@0x5adaa0440e \
  --extracted-dir ./data/com.ss.hm.ugc.aweme \
  --maps /proc/12345/maps \
  --analyze
```

## 处理流程

### 场景 1: 有 ZIP 文件和解压目录

```bash
# 1. 解析地址
python3 resolve_hap_address_smart.py \
  /path/to/entry.zip \
  entry.hap@0x5adaa0440e \
  --extracted-dir /path/to/com.ss.hm.ugc.aweme

# 2. 如果成功，会输出：
#    SO 文件: libquick.so
#    SO 文件内偏移: 0xc8a7c
#    解压后的文件: /path/to/entry/libs/arm64-v8a/libquick.so

# 3. 使用解压后的 SO 文件进行分析
python3 dump_and_find_function.py \
  /path/to/entry/libs/arm64-v8a/libquick.so \
  0xc8a7c
```

### 场景 2: 有内存映射信息

如果地址是内存映射地址，需要获取进程的内存映射信息：

```bash
# 1. 获取进程的 maps 文件（在设备上）
adb shell "cat /proc/{pid}/maps" > maps.txt

# 2. 使用 maps 文件解析
python3 resolve_hap_address_smart.py \
  entry.zip \
  entry.hap@0x5adaa0440e \
  --extracted-dir ./data/com.ss.hm.ugc.aweme \
  --maps maps.txt \
  --analyze
```

### 场景 3: 直接使用解压后的 SO 文件

如果已经知道对应的 SO 文件，可以直接使用：

```bash
# 直接分析 SO 文件
python3 dump_and_find_function.py \
  /path/to/entry/libs/arm64-v8a/libquick.so \
  0xc8a7c
```

## 集成到符号恢复流程

### 方法 1: 预处理地址

在 `perf_converter.py` 中添加 HAP 地址处理：

```python
from resolve_hap_address_smart import resolve_hap_address_smart

def process_hap_address(self, address_str: str):
    """处理 HAP 文件地址"""
    if '@' in address_str and '.hap' in address_str:
        result = resolve_hap_address_smart(
            hap_file=self.hap_file,
            address_str=address_str,
            extracted_dir=self.extracted_dir,
            maps_file=self.maps_file
        )
        if result and result.get('so_file_path'):
            # 转换为标准格式
            so_name = result['so_name']
            so_offset = result['so_offset']
            return f"{so_name}+0x{so_offset:x}"
    return address_str
```

### 方法 2: 批量处理

从 Excel 或 perf 数据中批量处理 HAP 地址：

```python
import pandas as pd
from resolve_hap_address_smart import resolve_hap_address_smart

def process_excel_hap_addresses(excel_file: str, hap_file: str, extracted_dir: str):
    """处理 Excel 中的 HAP 地址"""
    df = pd.read_excel(excel_file)
    
    for idx, row in df.iterrows():
        address = row.get('地址', '')
        if '@' in address and '.hap' in address:
            result = resolve_hap_address_smart(
                hap_file=Path(hap_file),
                address_str=address,
                extracted_dir=Path(extracted_dir)
            )
            if result:
                # 更新 Excel 中的地址
                df.at[idx, 'SO文件'] = result['so_name']
                df.at[idx, '偏移量'] = f"0x{result['so_offset']:x}"
    
    return df
```

## 常见问题

### Q1: 地址超出 ZIP 文件大小

**原因**: 地址是内存映射地址，不是文件偏移量

**解决**:
1. 提供 `/proc/{pid}/maps` 文件
2. 或者，如果知道对应的 SO 文件，直接使用解压后的文件

### Q2: 找不到对应的 SO 文件

**原因**:
- ZIP 文件结构不标准
- 地址计算错误
- SO 文件在 ZIP 中是压缩的

**解决**:
1. 检查 ZIP 文件是否完整
2. 尝试直接解压所有 SO 文件
3. 检查地址是否正确

### Q3: 如何获取 maps 文件

**方法 1**: 从设备获取
```bash
adb shell "cat /proc/{pid}/maps" > maps.txt
```

**方法 2**: 从 perf 数据中提取
```bash
# perf 数据可能包含内存映射信息
perf script --input perf.data | grep maps
```

**方法 3**: 运行时获取
```python
# 在应用运行时获取
import subprocess
maps = subprocess.check_output(['cat', f'/proc/{pid}/maps']).decode()
```

## 示例

### 示例 1: 解析文件偏移量

```bash
$ python3 resolve_hap_address_smart.py \
    entry.zip \
    entry.hap@0x1000000 \
    --extracted-dir ./data/com.ss.hm.ugc.aweme

================================================================================
智能解析地址: entry.hap@0x1000000
================================================================================
地址: 0x1000000 (16777216)
ZIP 文件大小: 231729764 字节 (0xdcee64)

地址可能是 ZIP 文件内偏移量
正在分析 ZIP 文件: entry.zip
查找偏移量: 0x1000000 (16777216)
  ✅ 找到: libquick.so
     ZIP 数据范围: 0x1000000 - 0x2000000
     SO 文件内偏移: 0x0

解析结果
================================================================================
地址类型: zip_offset
SO 文件: libquick.so
SO 文件内偏移: 0x0
解压后的文件: ./data/com.ss.hm.ugc.aweme/entry/libs/arm64-v8a/libquick.so
```

### 示例 2: 解析内存映射地址

```bash
$ python3 resolve_hap_address_smart.py \
    entry.zip \
    entry.hap@0x5adaa0440e \
    --extracted-dir ./data/com.ss.hm.ugc.aweme \
    --maps maps.txt

================================================================================
智能解析地址: entry.hap@0x5adaa0440e
================================================================================
地址: 0x5adaa0440e (390214992910)
ZIP 文件大小: 231729764 字节 (0xdcee64)

地址可能是内存映射地址（超出文件大小）
使用 maps 文件: maps.txt
解析内存地址: 0x5adaa0440e
✅ 找到内存映射:
   范围: 0x5adaa00000 - 0x5adab00000
   文件偏移: 0x0
   路径: /data/storage/el1/bundle/entry.hap
   计算的文件偏移: 0x440e

正在分析 ZIP 文件: entry.zip
查找偏移量: 0x440e (17422)
  ✅ 找到: libquick.so
     SO 文件内偏移: 0x440e

解析结果
================================================================================
地址类型: hap_zip
SO 文件: libquick.so
SO 文件内偏移: 0x440e
解压后的文件: ./data/com.ss.hm.ugc.aweme/entry/libs/arm64-v8a/libquick.so
```

## 相关工具

- `resolve_hap_address.py` - 基础 HAP 地址解析工具
- `resolve_hap_address_smart.py` - 智能 HAP 地址解析工具（推荐）
- `dump_and_find_function.py` - 根据偏移量查找函数
- `verify_excel_offsets.py` - 验证 Excel 中的偏移量

## 总结

1. **文件偏移量**: 直接使用 `resolve_hap_address.py` 或 `resolve_hap_address_smart.py`
2. **内存映射地址**: 使用 `resolve_hap_address_smart.py` 并提供 maps 文件
3. **已知 SO 文件**: 直接使用 `dump_and_find_function.py` 分析解压后的 SO 文件

