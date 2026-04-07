# HapTest - 自动化UI探索测试工具

HapTest是基于HapRay框架实现的策略驱动自动化测试工具,能够自动探索应用UI并采集性能数据。

## 架构设计

```
haptest/
├── __init__.py              # 模块入口
├── state_manager.py         # UI状态管理和去重
├── strategy.py              # 探索策略引擎
└── haptest_case.py          # HapTest主类
```

## 核心组件

### 1. StateManager (状态管理器)

负责UI状态的去重和历史记录:

- **UIState**: 封装UI状态(截图、viewTree、inspector)
- **状态哈希**: 基于element tree计算唯一标识
- **历史记录**: 追踪已访问状态和执行的操作
- **统计信息**: 提供测试覆盖度统计

### 2. ExplorationStrategy (探索策略)

提供4种探索策略:

- **DepthFirstStrategy**: 深度优先,优先探索新控件
- **BreadthFirstStrategy**: 广度优先,随机选择控件
- **RandomStrategy**: 随机探索,完全随机操作
- **LLMStrategy**: 基于大模型的智能探索,使用视觉语言模型分析UI并决策

### 3. HapTest (主测试类)

继承自`PerfTestCase`,自动完成:

- UI状态捕获(截图+viewTree)
- 策略决策
- 操作执行
- 性能数据采集

## 快速开始

### 前置要求

1. 已安装HarmonyOS Command Line Tools
2. 设备已连接: `hdc list targets`
3. 目标应用已安装在设备上

### 🚀 方式一: haptest命令 (推荐)

最简单的使用方式,无需编写代码:

```bash
# 激活虚拟环境 (Windows)
cd ArkAnalyzer-HapRay\perf_testing
.\.venv\Scripts\activate

# 连接设备
hdc tconn 192.168.31.204:5555  

# 或 (Linux/Mac)
source activate.sh

# 运行haptest (以京东为例)
python -m scripts.main haptest --app-package com.jd.hm.mall --app-name "京东" --strategy depth_first --max-steps 20

python -m scripts.main haptest --app-package com.taobao.taobao4hmos --app-name "淘宝" --strategy llm --max-steps 10

python -m scripts.main haptest --app-package com.xunmeng.pinduoduo.hos --app-name "pdd" --ability-name EntryAbility --strategy llm --max-steps 10

python -m scripts.main haptest --app-package com.example.deephierarchy --app-name "DH" --ability-name EntryAbility --strategy depth_first --max-steps 20 

python -m scripts.main haptest --app-package com.example.areudead --app-name "AUD" --ability-name EntryAbility --strategy llm --max-steps 20 

python -m scripts.main haptest --app-package com.huawei.hmos.files --app-name "FILE" --ability-name EntryAbility --strategy llm --max-steps 20 


# 完整参数示例
python -m scripts.main haptest \
  --app-package com.jd.hm.mall \
  --app-name "京东" \
  --strategy depth_first \
  --max-steps 50 \
  --round 3 \
  --devices HX1234567890 \
  --trace \
  --memory
```

#### 命令参数说明

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `--app-package` | ✅ | 应用包名 | - |
| `--app-name` | ✅ | 应用名称 | - |
| `--strategy` | ❌ | 探索策略 | depth_first |
| `--max-steps` | ❌ | 最大探索步数 | 30 |
| `--round` | ❌ | 测试轮数 | 1 |
| `--devices` | ❌ | 设备序列号 | 自动检测 |
| `--trace` | ❌ | 启用trace采集 | True |
| `--no-trace` | ❌ | 禁用trace采集 | - |
| `--memory` | ❌ | 启用内存分析 | False |
| `--no-perf` | ❌ | 禁用perf采集 | False |

### 📝 方式二: 编写测试用例 (高级)

如需自定义逻辑或集成到测试框架,可创建测试用例:

**1. 创建测试文件** `hapray/testcases/MyHapTest.py`:

```python
from hapray.haptest import HapTest

class MyHapTest(HapTest):
    def __init__(self, controllers):
        super().__init__(
            tag='MyHapTest',
            configs=controllers,
            app_package='com.jd.hm.mall',  # 修改为你的应用包名
            app_name='京东',                # 修改为你的应用名
            strategy_type='depth_first',
            max_steps=50
        )
```

**2. 运行测试**:

```bash
# 激活环境后运行
python -m scripts.main perf --run_testcases MyHapTest
```

**注意**: 如果遇到导入错误,确保:
1. 已激活虚拟环境 (`activate.bat` 或 `source activate.sh`)
2. 测试文件位于 `hapray/testcases/` 目录下

### 策略选择

| 策略类型 | 特点 | 适用场景 |
|---------|------|---------|
| `depth_first` | 深度优先探索,系统性遍历 | 需要全面覆盖的场景 |
| `breadth_first` | 广度优先,随机探索 | 快速发现问题 |
| `random` | 完全随机 | 压力测试、模糊测试 |
| `llm` | 基于大模型的智能决策 | 需要智能化探索,优先深度遍历 |

#### LLM策略使用

使用LLM策略需要配置环境变量:

```bash
# 创建 .env 文件
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

# 运行测试
python -m scripts.main haptest \n  --app-package com.example.app \n  --app-name "示例应用" \n  --strategy llm \n  --max-steps 30
```

详细配置请参考 `LLM_STRATEGY_GUIDE.md`

## 输出数据

HapTest会自动生成完整的测试报告:

```
report_path/
├── hiperf/
│   ├── step1/
│   │   ├── perf.data         # CPU性能数据
│   │   ├── perf.json         # 解析后的性能指标
│   │   └── pids.json         # 进程信息
│   ├── step2/
│   └── steps.json            # 所有步骤描述
├── htrace/
│   ├── step1/
│   │   └── trace.htrace      # trace数据(含内存)
│   └── step2/
├── ui/
│   ├── step1/
│   │   ├── screenshot_start_1.png    # 操作前截图
│   │   ├── element_tree_start_1.txt  # 操作前viewTree
│   │   ├── inspector_start.json      # 操作前inspector
│   │   ├── screenshot_end_1.png      # 操作后截图
│   │   └── element_tree_end_1.txt    # 操作后viewTree
│   └── step2/
└── testInfo.json             # 测试元数据
```

## 扩展开发

### 自定义策略

```python
from hapray.haptest.strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def decide_next_action(self, ui_state, state_mgr):
        # 自定义决策逻辑
        return ('click', target)
```

### 自定义状态哈希

```python
from hapray.haptest.state_manager import UIState

class MyUIState(UIState):
    def _compute_hash(self):
        # 自定义哈希算法
        return custom_hash_function()
```

## 技术特点

1. **零侵入**: 完全基于HapRay框架,无需修改底层代码
2. **自动采集**: 每步操作自动采集UI+性能数据
3. **智能去重**: 基于UI结构的状态去重机制
4. **策略可插拔**: 支持多种探索策略,可自由扩展
5. **完整链路**: 形成带性能数据的执行路径

## 注意事项

1. 确保设备已连接并通过`hdc list targets`可见
2. 目标应用需要已安装在设备上
3. 首次运行会自动安装测试依赖
4. 性能数据采集需要root权限或调试版本应用

## 示例

参考 `testcases/HapTest_Example.py` 查看完整示例。
