# HapTest 日志系统

## ✨ 特性

HapTest现在拥有**双输出**日志系统:

### 📺 控制台输出 (简洁)

只显示关键的INFO级别信息:
```
HapTest日志已保存至: /path/to/logs/haptest.log
应用: 京东
============================================================
开始HapTest自动化测试: 京东
策略: depth_first, 最大步数: 30
============================================================

============================================================
Step 1/30
============================================================
UI状态: 新状态
可点击元素数: 15
未访问元素数: 15
决策: 点击 Button "登录"
```

### 📝 日志文件 (详细)

完整的DEBUG级别日志,包含所有详情:
```
reports/<timestamp>/HapTest_XXX/logs/haptest.log
```

**内容包括**:
- ✅ 所有UI状态解析详情
- ✅ 每个可点击元素的完整信息
- ✅ 策略决策的详细推理过程
- ✅ 状态管理器的内部状态
- ✅ 所有DEBUG级别的调试信息

## 📂 文件结构

```
reports/haptest_com.jd.hm.mall_20251217142024/
└── HapTest_com_jd_hm_mall/
    ├── logs/
    │   └── haptest.log          # 📝 完整调试日志
    ├── hiperf/
    │   └── step1/
    ├── htrace/
    │   └── step1/
    ├── ui/
    │   └── step1/
    │       ├── screenshot_current_1.png
    │       ├── element_tree_current_1.txt
    │       └── inspector_current.json
    └── testInfo.json
```

## 🔍 查看日志

### Windows

```powershell
# 实时查看
Get-Content reports\20251217142024\HapTest_XXX\logs\haptest.log -Wait

# 查看全部
type reports\20251217142024\HapTest_XXX\logs\haptest.log

# 搜索关键词
findstr "点击" reports\20251217142024\HapTest_XXX\logs\haptest.log
```

### Linux/Mac

```bash
# 实时查看
tail -f reports/20251217142024/HapTest_XXX/logs/haptest.log

# 查看全部
cat reports/20251217142024/HapTest_XXX/logs/haptest.log

# 搜索关键词
grep "点击" reports/20251217142024/HapTest_XXX/logs/haptest.log
```

## 📊 日志示例

### 控制台输出 (简洁)

```
14:20:24 - HapTest - INFO - HapTest日志已保存至: C:\...\logs\haptest.log
14:20:24 - HapTest - INFO - 应用: 京东
14:20:24 - HapTest - INFO - ============================================================
14:20:27 - HapTest - INFO - Step 1/30
14:20:27 - HapTest - INFO - UI状态: 新状态
14:20:27 - HapTest - INFO - 可点击元素数: 15
14:20:27 - HapTest - INFO - 未访问元素数: 15
14:20:27 - HapTest - INFO - 决策: 点击 Button "登录"
```

### 日志文件 (详细)

```
14:20:24 - HapTest - INFO - HapTest日志已保存至: C:\...\logs\haptest.log
14:20:24 - HapTest - INFO - 应用: 京东
14:20:27 - HapTest.State - DEBUG - 解析到 15 个可点击元素
14:20:27 - HapTest.State - DEBUG - 总可点击: 15, 已点击: 0, 未访问: 15
14:20:27 - HapTest - DEBUG - 未访问元素示例: ['登录', '注册', '首页']
14:20:27 - HapTest.Strategy - DEBUG - [DepthFirst] 未访问元素数: 15, 连续返回次数: 0
14:20:27 - HapTest.Strategy - DEBUG - [DepthFirst] 决策: 点击 Button "登录"
14:20:27 - HapTest - INFO - 决策: 点击 Button "登录"
```

## ⚙️ 自定义配置

### 在控制台也显示DEBUG信息

如果需要在控制台看到详细信息:

```python
import logging

class MyHapTest(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.your.app',
            app_name='应用名',
            strategy_type='depth_first',
            max_steps=30
        )
        
        # 临时在控制台显示DEBUG
        logging.getLogger('HapTest').setLevel(logging.DEBUG)
        logging.getLogger('HapTest.Strategy').setLevel(logging.DEBUG)
        logging.getLogger('HapTest.State').setLevel(logging.DEBUG)
```

### 只保存文件不输出控制台

```python
# 禁用控制台输出
logging.getLogger('HapTest').handlers = []
```

## 📝 日志内容说明

### HapTest 日志

主要测试流程信息:
- 测试启动/完成
- 每步的UI状态
- 操作决策
- 测试统计

### HapTest.State 日志

UI状态管理信息:
- 可点击元素解析
- 元素访问统计
- 状态去重结果
- 文件解析错误

### HapTest.Strategy 日志

策略决策信息:
- 未访问元素统计
- 连续返回次数
- 决策推理过程
- 停止条件触发

## 🎯 最佳实践

1. **测试时**: 只看控制台简洁输出
2. **调试时**: 查看日志文件详细信息
3. **出问题时**: 搜索日志文件找错误
4. **分析时**: 完整查看日志文件了解全过程

## 💡 提示

- 日志文件使用UTF-8编码,支持中文
- 每次测试生成新的日志文件(覆盖模式)
- 日志文件大小通常在几KB到几MB之间
- 可以用文本编辑器直接打开查看
