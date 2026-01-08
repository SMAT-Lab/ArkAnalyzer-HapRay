# HapTest 快速开始指南

## 📦 安装与配置

### 1. 安装依赖

```bash
# Windows
cd ArkAnalyzer-HapRay/perf_testing
activate.bat

# Linux/Mac
cd ArkAnalyzer-HapRay/perf_testing
source activate.sh
```

### 2. 确认设备连接

```bash
hdc list targets
```

## 🚀 使用方式

### 方式一: haptest命令 (推荐)

**无需编写代码**,直接通过命令行运行:

```bash
# 基础示例 - 测试京东应用
python -m scripts.main haptest \
  --app-package com.jd.hm.mall \
  --app-name "京东" \
  --max-steps 20

# 完整参数示例
python -m scripts.main haptest \
  --app-package com.jd.hm.mall \
  --app-name "京东" \
  --strategy depth_first \
  --max-steps 50 \
  --round 3 \
  --memory
```

### 方式二: 编写测试用例

如需集成到测试框架或自定义逻辑:

```bash
# 运行预置的京东测试
python -m scripts.main perf --run_testcases HapTest_JD
```

## 📊 输出报告

测试完成后,会在 `reports/haptest_<app>_<timestamp>/` 目录生成:

```
reports/haptest_com.jd.hm.mall_20251216223000/
├── HapTest_com_jd_hm_mall/
│   ├── hiperf/          # 性能数据
│   │   ├── step1/
│   │   │   ├── perf.data
│   │   │   └── perf.json
│   │   └── steps.json
│   ├── htrace/          # trace数据
│   │   └── step1/
│   │       └── trace.htrace
│   ├── ui/              # UI数据
│   │   └── step1/
│   │       ├── screenshot_start_1.png
│   │       ├── element_tree_start_1.txt
│   │       └── inspector_start.json
│   └── testInfo.json
└── summary_report.xlsx  # 性能汇总报告
```

## ⚙️ 参数说明

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `--app-package` | ✅ | 应用包名 | - |
| `--app-name` | ✅ | 应用名称 | - |
| `--strategy` | ❌ | 探索策略(depth_first/breadth_first/random) | depth_first |
| `--max-steps` | ❌ | 最大探索步数 | 30 |
| `--round` | ❌ | 测试轮数 | 1 |
| `--devices` | ❌ | 设备序列号 | 自动检测 |
| `--trace` | ❌ | 启用trace采集 | True |
| `--no-trace` | ❌ | 禁用trace采集 | - |
| `--memory` | ❌ | 启用内存分析 | False |
| `--no-perf` | ❌ | 禁用perf采集 | False |

## 🎯 策略说明

| 策略 | 特点 | 适用场景 |
|------|------|---------|
| `depth_first` | 深度优先,系统性遍历 | 全面覆盖测试 |
| `breadth_first` | 广度优先,随机选择 | 快速发现问题 |
| `random` | 完全随机操作 | 压力测试 |

## 💡 常见问题

### Q: 提示找不到测试用例?
A: 确保已激活虚拟环境: `activate.bat` (Windows) 或 `source activate.sh` (Mac/Linux)

### Q: 如何测试其他应用?
A: 修改 `--app-package` 和 `--app-name` 参数为目标应用

### Q: 如何自定义探索逻辑?
A: 参考 `hapray/haptest/strategy.py` 创建自定义策略类

## 📝 示例

### 测试京东应用(深度优先,30步)
```bash
python -m scripts.main haptest \
  --app-package com.jd.hm.mall \
  --app-name "京东" \
  --strategy depth_first \
  --max-steps 30
```

### 测试高德地图(随机探索,采集内存数据)
```bash
python -m scripts.main haptest \
  --app-package com.amap.hmapp \
  --app-name "高德地图" \
  --strategy random \
  --max-steps 50 \
  --memory
```

### 多轮测试(3轮)
```bash
python -m scripts.main haptest \
  --app-package com.kuaishou.hmapp \
  --app-name "快手" \
  --max-steps 40 \
  --round 3
```
