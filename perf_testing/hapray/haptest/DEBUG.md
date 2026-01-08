# HapTest 调试信息说明

## 📁 日志文件位置

HapTest会生成独立的详细日志文件:

```
reports/<timestamp>/HapTest_XXX/logs/haptest.log
```

**日志级别**:
- **控制台**: 只显示INFO及以上级别(简洁输出)
- **日志文件**: 包含所有DEBUG级别信息(完整详情)

**查看日志**:
```bash
# 实时查看日志
tail -f reports/<timestamp>/HapTest_XXX/logs/haptest.log

# Windows
Get-Content reports\<timestamp>\HapTest_XXX\logs\haptest.log -Wait
```

## 📊 日志输出解读

运行HapTest时,会输出详细的调试信息帮助理解测试过程:

### 1. 步骤信息

```
============================================================
Step 1/30
============================================================
```

每一步都会显示当前步数和总步数。

### 2. UI状态信息

```
UI状态: 新状态
可点击元素数: 15
未访问元素数: 15
未访问元素示例: ['登录', '注册', '首页']
```

- **UI状态**: 新状态/已访问
- **可点击元素数**: 当前页面可以点击的UI元素总数
- **未访问元素数**: 还没有点击过的元素数量
- **未访问元素示例**: 前3个未访问元素的文本

### 3. 决策信息

```
决策: 点击 Button "登录"
```

显示策略决定的下一步操作:
- `点击 <类型> "<文本>"` - 点击某个UI元素
- `滑动 up/down` - 滑动屏幕
- `返回` - 返回上一页

### 4. 策略调试信息

深度优先策略的详细信息:

```
[DepthFirst] 未访问元素数: 0, 连续返回次数: 2
[DepthFirst] 决策: 返回 (2/5)
```

- **未访问元素数**: 当前页面未点击的元素数
- **连续返回次数**: 已连续返回的次数(达到上限会停止)

### 5. 状态管理信息

```
[HapTest.State] 解析到 15 个可点击元素
[HapTest.State] 总可点击: 15, 已点击: 3, 未访问: 12
```

- **解析到X个可点击元素**: 从inspector JSON中提取的元素数
- **总可点击/已点击/未访问**: 元素访问统计

## 🔍 常见问题诊断

### Q: 为什么一直输出"返回"?

可能的原因:

1. **可点击元素数为0**
   ```
   可点击元素数: 0
   未访问元素数: 0
   ```
   **解决方法**: 检查inspector JSON文件是否正常生成

2. **Inspector文件不存在**
   ```
   [HapTest.State] Inspector文件不存在: /path/to/inspector_current.json
   ```
   **解决方法**: 确认UI采集功能正常,检查`capture_ui_handler`是否正常工作

3. **所有元素都已访问**
   ```
   未访问元素数: 0
   [DepthFirst] 决策: 返回 (1/5)
   ```
   **解决方法**: 正常行为,会尝试返回到上层页面继续探索

### Q: 如何查看采集的UI数据?

UI数据保存在报告目录中:

```
reports/<timestamp>/HapTest_XXX/ui/step1/
├── screenshot_current_1.png      # 截图
├── element_tree_current_1.txt    # 元素树
└── inspector_current.json        # Inspector数据(包含可点击元素)
```

检查这些文件是否存在和内容是否正常。

### Q: 如何增加调试信息?

**方法1: 查看日志文件** (推荐)

所有详细信息都已保存在日志文件中:
```
reports/<timestamp>/HapTest_XXX/logs/haptest.log
```

**方法2: 临时在控制台显示DEBUG信息**

在测试用例中添加:
```python
import logging

class MyHapTest(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(...)
        
        # 临时在控制台也显示DEBUG信息
        logging.getLogger('HapTest').setLevel(logging.DEBUG)
        logging.getLogger('HapTest.Strategy').setLevel(logging.DEBUG)
        logging.getLogger('HapTest.State').setLevel(logging.DEBUG)
```

## 📈 测试流程图

```
开始
  ↓
启动应用(wait 3s)
  ↓
┌─────────────────────┐
│  采集当前UI状态      │
│  - 截图              │
│  - Element树         │
│  - Inspector JSON    │
└─────────────────────┘
  ↓
┌─────────────────────┐
│  解析可点击元素      │
│  (从Inspector JSON)  │
└─────────────────────┘
  ↓
┌─────────────────────┐
│  状态去重判断        │
│  (基于Element树)     │
└─────────────────────┘
  ↓
┌─────────────────────┐
│  策略决策           │
│  - 有未访问元素?     │
│    → 点击           │
│  - 可以滑动?        │
│    → 滑动           │
│  - 否则             │
│    → 返回           │
└─────────────────────┘
  ↓
┌─────────────────────┐
│  执行操作 + 采集性能 │
│  - 执行动作          │
│  - 采集perf数据      │
│  - 采集trace数据     │
└─────────────────────┘
  ↓
达到最大步数? ─No→ 返回"采集UI状态"
  ↓Yes
生成报告
  ↓
结束
```

## 💡 优化建议

1. **调整最大返回次数**: 在策略初始化时设置
   ```python
   strategy = ExplorationStrategy('depth_first')
   strategy.strategy.max_back_count = 5  # 默认3
   ```

2. **增加等待时间**: 如果UI加载慢,增加等待时间
   ```python
   self.driver.wait(5)  # 改为更长时间
   ```

3. **自定义可点击判断**: 修改`_extract_clickable_recursive`方法
