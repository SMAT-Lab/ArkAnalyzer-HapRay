# Optimization Detector

二进制文件优化级别和LTO（Link-Time Optimization）检测工具。

## 功能特性

- ✅ **优化级别检测**: 检测二进制文件的编译优化级别（O0, O1, O2, O3, Os）
- ✅ **LTO检测**: 检测二进制文件是否使用了LTO优化
- ✅ **批量处理**: 支持批量处理SO文件、AR文件或HAP/HSP/APK/HAR包
- ✅ **多线程处理**: 支持多线程并行处理，提高处理速度
- ✅ **Excel报告**: 生成详细的Excel格式检测报告

## 安装

### 使用 npm 脚本（推荐）

```bash
# 克隆或下载源码
cd optimization_detector_tool

# 安装依赖（自动运行 setup）
npm install

# 或手动运行 setup
npm run setup
```

### 从源码安装

```bash
# 克隆或下载源码
cd optimization_detector_tool

# 安装
pip install .

# 或者使用开发模式
pip install -e .
```

### 依赖项

- Python >= 3.10
- numpy >= 2.0
- pandas >= 2.0.3
- tensorflow >= 2.20.0
- tqdm >= 4.67.1
- pyelftools >= 0.32
- arpy ~= 2.3.0
- joblib >= 1.3.0

所有依赖项会在安装时自动安装。

## 构建和打包

### 使用 npm 脚本

```bash
# 构建 pip 包（wheel 和 tar.gz）
npm run build

# 构建可执行文件（单文件模式）
npm run build:python
# 或
npm run build:onefile

# 构建可执行文件（目录模式，启动更快）
# 会自动压缩为 zip 文件（优化便于分发）
npm run build:onedir

# 单独压缩已构建的 onedir 输出
npm run zip:onedir

# 清理构建文件（包括 zip 文件）
npm run clean
```

### 使用脚本文件

```bash

# 构建可执行文件（单文件模式）
./build.sh

# 构建可执行文件（目录模式）
ONEDIR_MODE=true ./build.sh

# 压缩 onedir 输出为 zip 文件（便于分发）
./zip_onedir.sh
```

## 使用方法

### 命令行工具

安装后会提供 `opt-detector` 命令：

```bash
# 检测单个SO文件
opt-detector -i libexample.so -o report.xlsx

# 检测目录中的所有二进制文件
opt-detector -i /path/to/binaries -o report.xlsx --jobs 4

# 只检测优化级别，不检测LTO
opt-detector -i libexample.so -o report.xlsx --no-lto

# 只检测LTO，不检测优化级别
opt-detector -i libexample.so -o report.xlsx --no-opt

# 使用4个并行工作线程
opt-detector -i /path/to/binaries -o report.xlsx -j 4

# 设置文件分析超时时间（秒）
opt-detector -i libexample.so -o report.xlsx --timeout 300

# 启用详细日志
opt-detector -i libexample.so -o report.xlsx -v

# 保存日志到文件
opt-detector -i libexample.so -o report.xlsx --log-file analysis.log
```

### Python API

```python
from optimization_detector import OptimizationDetector, FileCollector

# 创建文件收集器
collector = FileCollector()
file_infos = collector.collect_binary_files('/path/to/binaries')

# 创建检测器
detector = OptimizationDetector(
    workers=4,           # 并行工作线程数
    timeout=300,         # 超时时间（秒）
    enable_lto=True,     # 启用LTO检测
    enable_opt=True      # 启用优化级别检测
)

# 执行检测
results = detector.detect_optimization(file_infos)

# results 是一个列表，包含 (sheet_name, DataFrame) 元组
for sheet_name, df in results:
    print(f"Sheet: {sheet_name}")
    print(df)

# 清理临时文件
collector.cleanup()
```

## 输出报告

工具会生成Excel格式的报告，包含以下信息：

### 优化级别报告列

- **File**: 文件路径
- **Status**: 检测状态（Successfully Analyzed / Analysis Failed）
- **Optimization Category**: 优化类别（Unoptimized / Low Optimization / Medium Optimization / High Optimization）
- **Optimization Score**: 优化分数（0-100%）
- **O0 Chunks**: O0级别的代码块数量
- **O1 Chunks**: O1级别的代码块数量
- **O2 Chunks**: O2级别的代码块数量
- **O3 Chunks**: O3级别的代码块数量
- **Os Chunks**: Os级别的代码块数量
- **Total Chunks**: 总代码块数量
- **File Size (bytes)**: 文件大小（字节）
- **Size Optimized**: 是否使用大小优化（基于Os比例）
- **LTO Score**: LTO分数（0-1，如果启用LTO检测）
- **LTO Prediction**: LTO预测结果（LTO / No LTO）
- **LTO Model Used**: 使用的LTO模型名称

## LTO检测配置

LTO检测需要额外的特征提取器。如果LTO检测失败，请：

1. 设置 `LTO_DEMO_PATH` 环境变量指向 `lto_demo` 目录：
   ```bash
   export LTO_DEMO_PATH=/path/to/lto_demo/lto_demo
   ```

2. 或在命令行中指定：
   ```bash
   opt-detector -i libexample.so -o report.xlsx --lto-demo-path /path/to/lto_demo/lto_demo
   ```

如果不使用LTO检测，可以使用 `--no-lto` 选项禁用。

## 支持的输入格式

- **SO文件**: `.so` 共享库文件
- **AR文件**: `.a` 静态库文件
- **HAP文件**: `.hap` 鸿蒙应用包
- **HSP文件**: `.hsp` 鸿蒙共享包
- **APK文件**: `.apk` Android应用包
- **HAR文件**: `.har` 鸿蒙静态共享包
- **目录**: 包含上述文件的目录（递归搜索）

## 工作原理

1. **文件收集**: 扫描输入路径，收集所有二进制文件
2. **特征提取**: 从二进制文件的`.text`段提取字节序列特征
3. **模型推理**: 使用训练好的LSTM模型预测每个代码块的优化级别
4. **结果聚合**: 将所有代码块的预测结果聚合成文件级别的优化类别
5. **LTO检测** (可选): 使用SVM/RF模型检测是否使用LTO

## 性能优化

- 使用多线程并行处理多个文件
- 支持结果缓存，避免重复分析
- 支持超时控制，避免卡在问题文件上
- 使用TensorFlow的批处理提高推理速度

## 注意事项

- 首次运行会加载模型文件，可能需要一些时间
- 大文件的处理时间较长，建议使用超时设置
- LTO检测需要额外的特征提取器，如果不需要可以禁用
- 确保有足够的磁盘空间用于临时文件和缓存

## 许可证

Apache License 2.0

## 贡献

欢迎提交Issue和Pull Request！

