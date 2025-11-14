# 工具箱目录

本目录包含各种开发工具和独立工具包。

## 工具列表

### optimization_detector_tool

二进制文件优化级别和LTO检测工具。

**功能**：
- 检测二进制文件的编译优化级别（O0, O1, O2, O3, Os）
- 检测二进制文件是否使用了LTO优化
- 支持批量处理SO文件、AR文件或HAP/HSP/APK包
- 生成详细的Excel格式检测报告

**位置**：`tools/optimization_detector_tool/`

**快速开始**：
```bash
# 进入工具目录
cd tools/optimization_detector_tool

# 查看帮助
./dist/opt-detector/opt-detector --help

# 使用示例
./dist/opt-detector/opt-detector -i /path/to/lib.so -o report.xlsx
```

**详细文档**：
- [README.md](optimization_detector_tool/README.md) - 使用说明
- [INSTALL.md](optimization_detector_tool/INSTALL.md) - 安装指南
- [BUILD_EXE.md](optimization_detector_tool/BUILD_EXE.md) - 打包指南
- [OPTIMIZATION.md](optimization_detector_tool/OPTIMIZATION.md) - 性能优化说明

## 添加新工具

要添加新工具到此目录：

1. 在 `tools/` 目录下创建工具目录
2. 添加工具代码和文档
3. 更新本 README.md 文件，添加工具说明

## 目录结构

```
tools/
├── README.md                    # 本文件
└── optimization_detector_tool/  # 优化检测器工具
    ├── README.md
    ├── INSTALL.md
    ├── build_exe.sh
    └── ...
```

