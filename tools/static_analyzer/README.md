# HapRay SA

#### 使用说明

## 1. HAP静态分析 (`hapray hap`)
分析HAP/ZIP文件或目录中的框架与资源，支持多种输出格式和并发处理。

### 基本用法
```bash
# 分析单个HAP文件，输出JSON格式
node hapray-sa-cmd.js hapray hap -i app.hap -o ./output

# 分析目录中的所有HAP文件
node hapray-sa-cmd.js hapray hap -i ./hap_files/ -o ./output

# 生成HTML报告
node hapray-sa-cmd.js hapray hap -i app.hap -o ./output -f html

# 生成所有格式的报告（JSON、HTML、Excel）
node hapray-sa-cmd.js hapray hap -i app.hap -o ./output -f all
```

### 参数说明
- `-i, --input <path>`: 分析输入路径（HAP/ZIP文件或目录）【必需】
- `-o, --output <path>`: 输出目录（默认：./output）
- `-f, --format <format>`: 输出格式：json, html, excel, all（默认：all）
- `-j, --jobs <number>`: 并发分析数量，默认为CPU核心数

### 并发处理示例
```bash
# 使用4个并发任务
node hapray-sa-cmd.js hapray hap -i app.hap -o ./output -j 4

# 使用自动并发（CPU核心数）
node hapray-sa-cmd.js hapray hap -i app.hap -o ./output -j auto
```

### 功能特性
- **框架检测**: 自动识别技术栈（React Native、Flutter、Unity等）
- **SO文件分析**: 深度分析原生库及其优化机会
- **资源分析**: 全面扫描JavaScript、图片等资源文件
- **多格式输出**: JSON用于程序化使用，HTML用于可视化报告，Excel用于数据分析
- **Hermes字节码检测**: 专门检测React Native Hermes引擎字节码
- **嵌套压缩包支持**: 递归分析HAP包内的压缩文件

## 2. HAP解压 (`unzip hap`)
```bash
node hapray-sa-cmd.js -p xxx.hap -o output
```

## 3. 负载拆解
```bash
node hapray-sa-cmd.js hapray dbtools -i <input_path>
```

## 4. 负载拆解支持带so符号导入
```bash
node hapray-sa-cmd.js hapray dbtools -i <input_path> -s <so_path>
```



