# HapTest 使用指南

## ✅ 已完成修复

HapTest测试用例现已正确放置在 `hapray/testcases/haptest/` 目录下，可以被正常识别。

## 🚀 两种使用方式

### 方式一: haptest命令 (最简单,推荐)

**无需编写代码**,直接运行:

```bash
# Windows - 激活环境
cd ArkAnalyzer-HapRay\perf_testing
.\.venv\Scripts\activate

# Linux/Mac - 激活环境  
cd ArkAnalyzer-HapRay/perf_testing
source activate.sh

# 运行haptest (以京东为例)
python -m scripts.main haptest \
  --app-package com.jd.hm.mall \
  --app-name "京东" \
  --max-steps 20
```

**优点**: 
- 无需创建测试文件
- 自动生成测试用例
- 命令行直接配置所有参数

### 方式二: 使用预置测试用例

运行预置的京东测试用例:

```bash
# 激活环境后运行
python -m scripts.main perf --run_testcases HapTest_JD
```

**优点**:
- 可以复用配置
- 适合集成到CI/CD
- 可以自定义测试逻辑

## 📁 测试用例位置

**重要**: 测试用例必须放在 **子目录** 中，且需要配套的 **JSON配置文件**:

```
hapray/testcases/
├── haptest/                    # ✅ 正确: 子目录
│   ├── __init__.py
│   ├── HapTest_JD.py          # ✅ Python测试文件
│   └── HapTest_JD.json        # ✅ JSON配置文件(必需!)
├── com.jd.hm.mall/            # 其他京东测试
│   ├── PerfLoad_jingdong_0010.py
│   └── PerfLoad_jingdong_0010.json
└── HapTest_XXX.py             # ❌ 错误: 根目录无法识别
```

**JSON配置文件格式**:

```json
{
    "description": "Test description",
    "environment": [
        {
            "type": "device",
            "label": "phone"
        }
    ],
    "driver": {
        "type": "DeviceTest",
        "py_file": [
            "HapTest_JD.py"
        ]
    },
    "kits": []
}
```

## 📝 创建自定义测试用例

**1. 创建目录和文件**:

```bash
mkdir -p hapray/testcases/haptest
```

**2. 创建Python测试文件** `hapray/testcases/haptest/MyHapTest.py`:

```python
from hapray.haptest import HapTest

class MyHapTest(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.your.app',  # 你的应用包名
            app_name='你的应用',
            strategy_type='depth_first',
            max_steps=30
        )
```

**3. 创建JSON配置文件** `hapray/testcases/haptest/MyHapTest.json`:

```json
{
    "description": "My HapTest automation",
    "environment": [
        {
            "type": "device",
            "label": "phone"
        }
    ],
    "driver": {
        "type": "DeviceTest",
        "py_file": [
            "MyHapTest.py"
        ]
    },
    "kits": []
}
```

**4. 运行测试**:

```bash
python -m scripts.main perf --run_testcases MyHapTest
```

## ⚙️ 参数说明

### haptest命令参数

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `--app-package` | ✅ | 应用包名 | - |
| `--app-name` | ✅ | 应用名称 | - |
| `--strategy` | ❌ | 探索策略 | depth_first |
| `--max-steps` | ❌ | 最大步数 | 30 |
| `--round` | ❌ | 测试轮数 | 1 |
| `--memory` | ❌ | 启用内存分析 | False |
| `--no-trace` | ❌ | 禁用trace | False |

### 策略类型

| 策略 | 特点 | 适用场景 |
|------|------|---------|
| `depth_first` | 深度优先,系统性遍历 | 全面覆盖测试 |
| `breadth_first` | 广度优先,随机选择 | 快速发现问题 |
| `random` | 完全随机操作 | 压力测试 |

## 🎯 完整示例

### 示例1: 测试京东(使用haptest命令)

```bash
python -m scripts.main haptest --app-package com.jd.hm.mall --app-name "京东" --strategy depth_first --max-steps 30 --memory
```

### 示例2: 测试京东(使用测试用例)

```bash
python -m scripts.main perf --run_testcases HapTest_JD
```

### 示例3: 多轮测试高德地图

```bash
python -m scripts.main haptest \
  --app-package com.amap.hmapp \
  --app-name "高德地图" \
  --max-steps 40 \
  --round 3
```

## 📊 输出报告

测试完成后生成:

```
reports/haptest_<app>_<timestamp>/
├── HapTest_XXX/
│   ├── hiperf/          # 性能数据
│   │   ├── step1/perf.data
│   │   └── steps.json
│   ├── htrace/          # trace数据
│   │   └── step1/trace.htrace
│   ├── ui/              # UI数据
│   │   └── step1/
│   │       ├── screenshot_current_1.png
│   │       ├── element_tree_current_1.txt
│   │       └── inspector_current.json
│   ├── logs/            # 📝 日志文件
│   │   └── haptest.log  # HapTest详细日志(包含所有调试信息)
│   └── testInfo.json
└── summary_report.xlsx
```

**重要**: `logs/haptest.log` 包含完整的调试信息:
- 所有UI状态信息
- 策略决策详情
- 元素解析过程
- DEBUG级别日志

控制台只显示关键的INFO级别信息,完整日志请查看该文件。

## ❓ 常见问题

### Q: 提示"Test source or its json does not exist"?

**A**: 每个测试用例需要配套的JSON配置文件:
```bash
# ✅ 正确 - 两个文件都存在
hapray/testcases/haptest/HapTest_JD.py
hapray/testcases/haptest/HapTest_JD.json

# ❌ 错误 - 缺少JSON配置  
hapray/testcases/haptest/HapTest_JD.py  (仅有.py文件)
```

JSON文件内容参考:
```json
{
    "description": "Test description",
    "environment": [{"type": "device", "label": "phone"}],
    "driver": {
        "type": "DeviceTest",
        "py_file": ["HapTest_JD.py"]
    },
    "kits": []
}
```

**注意**: 使用 `haptest` 命令会自动生成JSON配置，无需手动创建。

### Q: 导入错误 "No module named 'hypium'"?

**A**: 需要激活虚拟环境:
```bash
# Windows
activate.bat

# Linux/Mac
source activate.sh
```

### Q: 如何只测试某个应用?

**A**: 使用haptest命令最简单:
```bash
python -m scripts.main haptest \
  --app-package com.your.app \
  --app-name "应用名" \
  --max-steps 20
```
