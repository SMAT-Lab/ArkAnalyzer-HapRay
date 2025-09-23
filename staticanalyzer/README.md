# HAP Static Analyzer

[![npm version](https://badge.fury.io/js/hapray-staticanalyzer.svg)](https://badge.fury.io/js/hapray-staticanalyzer)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)

HAP Static Analyzer 是一个专业的 HAP (HarmonyOS Application Package) 包静态分析工具，提供深度的技术栈识别、SO 文件分析和资源文件检测功能。该工具支持多种输出格式，具备强大的错误处理和内存管理机制，是 HarmonyOS 应用开发和逆向分析的重要工具。

## ✨ 核心特性

- 🔍 **智能框架识别**: 基于 SO 文件模式匹配识别 React Native、Flutter、Hermes、KMP、CMP、Lynx、Qt、Unity 等主流框架
- 📊 **多格式输出**: 支持 JSON、HTML、Excel 三种输出格式，满足不同场景需求
- 🚀 **高性能分析**: 并行处理架构，内存优化，支持大型 HAP 包分析
- 🛡️ **健壮错误处理**: 完善的错误分类和恢复机制，确保分析过程稳定可靠
- 🔧 **灵活配置**: 支持自定义框架模式和文件类型检测规则
- 📦 **递归解析**: 支持嵌套压缩包的递归分析
- 🎯 **精确检测**: 基于魔术字节和文件扩展名的双重文件类型检测

## 🏗️ 架构设计

### 核心组件结构

```
staticanalyzer/
├── src/                          # 源代码目录
│   ├── analyzers/               # 分析器模块
│   │   ├── so-analyzer.ts       # SO文件分析器 - 框架识别核心
│   │   └── resource-analyzer.ts # 资源文件分析器 - 支持递归解析
│   ├── config/                  # 配置管理模块
│   │   ├── framework-patterns.ts # 框架模式配置加载器
│   │   ├── magic-numbers.ts     # 文件类型魔术字配置
│   │   └── types-config.ts      # 动态类型配置生成器
│   ├── formatters/              # 输出格式化器
│   │   ├── json-formatter.ts    # JSON格式输出
│   │   ├── html-formatter.ts    # HTML报告生成
│   │   ├── excel-formatter.ts   # Excel表格输出
│   │   └── index.ts             # 格式化器统一接口
│   ├── utils/                   # 工具模块
│   │   ├── file-utils.ts        # 文件操作工具
│   │   ├── logger.ts            # 日志系统
│   │   └── zip-adapter.ts       # ZIP处理适配器
│   ├── types/                   # 类型定义模块
│   │   └── zip-types.ts         # ZIP相关类型定义
│   ├── errors/                  # 错误处理模块
│   │   └── index.ts             # 错误类型和工厂函数
│   ├── hap-static-analyzer.ts   # 主分析器类
│   ├── cli.ts                   # 命令行接口
│   ├── index.ts                 # 库入口和便捷函数
│   └── types.ts                 # 核心类型定义
├── res/                         # 配置资源文件
│   ├── framework-patterns.json  # 框架识别模式配置
│   └── magic-numbers.json       # 文件类型识别配置
├── lib/                         # TypeScript编译输出
├── test/                        # 测试套件
│   ├── unit/                    # 单元测试
│   └── create-test-hap.js       # 测试HAP包生成器
└── demo/                        # 演示和示例
```



## 🔧 核心功能详解

### 1. SO文件分析引擎

#### 框架识别算法
- **模式匹配**: 基于正则表达式的 SO 文件名模式识别
- **支持框架**:
  - **React Native**: `libreact_*.so`, `librnoh*.so`
  - **Flutter**: `libflutter.so`
  - **Hermes**: `libhermes.so` (JavaScript引擎)
  - **KMP**: `libkn.so` (Kotlin Multiplatform)
  - **CMP**: `libskikobridge.so` (Compose Multiplatform)
  - **Lynx**: `liblynx*.so`
  - **Qt**: `libQt*.so`
  - **Unity**: `libunity.so`, `libil2cpp.so`
- **系统库识别**: 自动识别系统级共享库，避免误报
- **架构支持**: 专注于 `arm64-v8a` 和 `arm64` 架构，确保分析准确性

#### 内存管理与性能优化
- **流式处理**: 直接从 ZIP 流读取，避免完整解压到磁盘
- **内存监控**: 实时监控内存使用，防止大文件导致的内存溢出
- **错误恢复**: 单个文件分析失败不影响整体流程

### 2. 资源文件分析引擎

#### 文件类型检测机制
- **双重检测**: 魔术字节 + 文件扩展名的组合检测
- **支持格式**:
  - **代码文件**: JavaScript (.js/.mjs/.jsx), JSON, XML/HTML
  - **图像文件**: PNG, JPEG, WebP
  - **压缩文件**: ZIP, JAR, WAR
  - **字节码**: Hermes Bytecode (.hbc/.jsbundle), WebAssembly (.wasm)
  - **库文件**: SO (ELF格式)

#### 高级分析功能
- **JavaScript压缩检测**: 自动识别压缩/混淆的 JS 文件
- **递归压缩包解析**: 支持嵌套 ZIP 文件的深度解析（可配置深度）
- **Hermes字节码识别**: 专门针对 React Native 的 Hermes 引擎字节码
- **MIME类型推断**: 基于文件内容和扩展名推断 MIME 类型

### 3. 多格式输出系统

#### JSON 格式 (默认)
- **结构化数据**: 完整的分析结果，便于程序化处理
- **嵌套信息**: 包含详细的文件层次和属性信息

#### HTML 报告
- **可视化展示**: 美观的网页报告，支持交互式浏览
- **图表统计**: 框架分布、文件类型统计图表
- **搜索过滤**: 支持文件名和类型的快速搜索

#### Excel 表格
- **表格化数据**: 适合数据分析和批量处理
- **多工作表**: 分别展示 SO 文件、资源文件、统计信息
- **条件格式**: 自动高亮重要信息


### 命令行使用

```bash
# 基本分析 - 输出JSON格式
hapray-static -i app.hap -o ./output

# 详细输出模式
hapray-static -i app.hap -o ./output -v

# 指定输出格式
hapray-static -i app.hap -o ./output -f json    # JSON格式
hapray-static -i app.hap -o ./output -f html    # HTML报告
hapray-static -i app.hap -o ./output -f excel   # Excel表格
hapray-static -i app.hap -o ./output -f all 

# 完整参数示例
hapray-static -i app.hap -o ./analysis-results -f html -v
```

#### 命令行参数说明

| 参数 | 简写 | 描述 | 默认值 |
|------|------|------|--------|
| `--input` | `-i` | HAP包文件路径 | 必需 |
| `--output` | `-o` | 输出目录路径 | 必需 |
| `--format` | `-f` | 输出格式 (json/html/excel) | `json` |
| `--verbose` | `-v` | 详细输出模式 | `false` |
| `--help` | `-h` | 显示帮助信息 | - |


## ⚙️ 配置系统

### 框架模式配置 (framework-patterns.json)

框架识别的核心配置文件，定义了各种技术栈的 SO 文件匹配模式：

```json
{
  "frameworks": {
    "RN": {
      "name": "React Native",
      "description": "React Native framework",
      "patterns": [
        "libreact_.*.so",      // React Native 核心库
        "librnoh.so",          // React Native OpenHarmony
        "librnoh_.*.so"        // RNOH 相关库
      ]
    },
    "Flutter": {
      "name": "Flutter",
      "description": "Flutter framework",
      "patterns": [
        "libflutter.so"        // Flutter 引擎
      ]
    },
    "Hermes": {
      "name": "Hermes",
      "description": "Hermes JavaScript engine",
      "patterns": [
        "libhermes.so"         // Hermes JS 引擎
      ]
    },
    "Unity": {
      "name": "Unity",
      "description": "Unity game engine",
      "patterns": [
        "libunity.so",         // Unity 引擎
        "libil2cpp.so"         // IL2CPP 运行时
      ]
    }
  },
  "systemLibraries": [
    "libc.so",               // C 标准库
    "libm.so",               // 数学库
    "libdl.so",              // 动态链接库
    "liblog.so",             // 日志库
    "libnative_*.so",        // 原生库
    "libace_*.so",           // ACE 框架库
    "libhilog_*.so"          // HiLog 日志库
  ]
}
```

### 文件类型配置 (magic-numbers.json)

文件类型检测的配置文件，包含魔术字节、扩展名和 MIME 类型映射：

```json
{
  "magicNumbers": [
    {
      "type": "ZIP",
      "signature": [80, 75],           // "PK" ZIP 文件头
      "offset": 0,
      "description": "ZIP archive"
    },
    {
      "type": "HERMES_BYTECODE",
      "signature": [194, 31, 240, 159], // Hermes 字节码标识
      "offset": 0,
      "description": "Hermes bytecode file (.hbc/.jsbundle)"
    },
    {
      "type": "SO",
      "signature": [127, 69, 76, 70],   // ELF 文件头
      "offset": 0,
      "description": "ELF executable/shared object"
    },
    {
      "type": "WASM",
      "signature": [0, 97, 115, 109],   // WebAssembly 魔术字节
      "offset": 0,
      "description": "WebAssembly binary module"
    }
  ],
  "fileExtensions": {
    "js": "JS",
    "mjs": "JS",
    "jsx": "JS",
    "json": "JSON",
    "so": "SO",
    "hbc": "HERMES_BYTECODE",
    "jsbundle": "HERMES_BYTECODE",
    "wasm": "WASM"
  },
  "mimeTypes": {
    ".js": "application/javascript",
    ".json": "application/json",
    ".so": "application/x-sharedlib",
    ".hbc": "application/octet-stream",
    ".wasm": "application/wasm"
  }
}
```

### 自定义配置

您可以通过修改配置文件来扩展框架识别能力：

#### 添加新框架支持

1. 在 `framework-patterns.json` 中添加框架配置
2. 在代码中更新 `FrameworkType` 枚举
3. 重新编译项目

#### 添加新文件类型

1. 在 `magic-numbers.json` 中添加魔术字节配置
2. 更新文件扩展名映射
3. 在代码中添加对应的 `FileType` 枚举值


**SO 分析流水线**:
- 架构目录过滤 (`libs/arm64-v8a/`, `libs/arm64/`)
- ELF 文件头验证
- 框架模式匹配算法
- 系统库识别与分类
- 内存使用监控

**资源分析流水线**:
- 文件类型检测 (魔术字节 + 扩展名)
- JavaScript 压缩检测算法
- 递归压缩包解析 (最大深度限制)
- Hermes 字节码识别
- 文件统计信息收集

#### 第三阶段：智能框架识别

```typescript
// 框架识别核心算法
class FrameworkDetector {
    detectFrameworks(soFiles: SoFileInfo[]): FrameworkTypeKey[] {
        const detectedFrameworks = new Set<FrameworkTypeKey>();

        for (const soFile of soFiles) {
            for (const [framework, config] of this.frameworkPatterns) {
                for (const pattern of config.patterns) {
                    if (this.matchPattern(soFile.fileName, pattern)) {
                        detectedFrameworks.add(framework);
                        soFile.frameworks.push(framework);
                    }
                }
            }
        }

        return Array.from(detectedFrameworks);
    }

    private matchPattern(fileName: string, pattern: string): boolean {
        // 支持正则表达式和通配符匹配
        const regex = new RegExp(pattern.replace(/\*/g, '.*'));
        return regex.test(fileName);
    }
}
```

## 🛠️ 开发指南

### 环境要求

- **Node.js**: >= 16.0.0
- **TypeScript**: >= 5.0.0
- **npm**: >= 8.0.0

### 项目构建

```bash
# 安装依赖
npm install

# 编译 TypeScript
npm run build

# 运行测试套件
npm test

# 代码质量检查
npm run lint

# 修复代码格式问题
npm run lint:fix

# 构建 Webpack 包
npm run build:webpack
```

### 开发脚本

```bash
# 开发模式 - 监听文件变化自动编译
npm run dev

# 运行演示
npm run demo                    # JSON 格式演示
npm run demo:html              # HTML 格式演示
npm run demo:excel             # Excel 格式演示
npm run demo:all               # 所有格式演示

# 创建测试 HAP 包
npm run create-test-hap

# 运行特定测试
npm run test:cli               # CLI 测试
```


## 🚨 错误处理与故障排除

### 常见错误类型

#### 1. HAP 文件错误
```typescript
HapFileError: HAP file not found: /path/to/app.hap
```
**解决方案**: 检查文件路径是否正确，确保文件存在且可读

#### 2. ZIP 解析错误
```typescript
ZipParsingError: Invalid ZIP file format
```
**解决方案**: 确认文件是有效的 HAP/ZIP 格式，检查文件是否损坏

#### 3. 内存不足错误
```typescript
OutOfMemoryError: Analysis failed due to memory constraints
```
**解决方案**:
- 增加 Node.js 内存限制: `node --max-old-space-size=4096`
- 分批处理大型 HAP 文件
- 关闭其他占用内存的应用

#### 4. 文件大小限制错误
```typescript
FileSizeLimitError: File size exceeds maximum limit
```
**解决方案**: 调整文件大小限制配置或使用流式处理
