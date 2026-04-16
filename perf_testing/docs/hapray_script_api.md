# HapRay 性能测试脚本 API 文档

## 一、脚本模板

### 1.1 基础性能测试模板（PerfLoad）

```python
from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_<应用名>_<序号>(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.example.app'
        self._app_name = '应用中文名'
        # 原始采集设备的屏幕尺寸
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        # === 前置准备（不采集数据）===
        self.driver.swipe_to_home()
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # === 定义步骤 ===
        def step1():
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        # === 执行性能采集步骤 ===
        self.execute_performance_step('应用名-场景描述-step1步骤描述', 30, step1)
```

### 1.2 含文本/坐标点击的复杂模板

```python
import time

from hypium import BY
from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_<应用名>_<序号>(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'com.example.app'
        self._app_name = '应用名'
        self.source_screen_width = 1084
        self.source_screen_height = 2412

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        # 启动并导航到目标页面
        self.start_app()
        self.touch_by_text('某个文本', 2)

        def step1():
            self.swipes_up(5, 1)
            self.swipes_down(5, 1)

        def step2():
            self.touch_by_coordinates(500, 1000, 2)
            self.driver.touch(BY.text('确认'))
            self.driver.wait(3)

        self.execute_performance_step('场景-step1描述', 30, step1)
        self.execute_performance_step('场景-step2描述', 20, step2)
```

---

## 二、核心 API 参考

### 2.1 PerfTestCase 基类

**文件**: `hapray/core/perf_testcase.py`

继承自 `TestCase` + `UIEventWrapper`，是所有性能测试用例的基类。

| API | 签名 | 说明 |
|-----|------|------|
| `execute_performance_step` | `(step_name: str, duration: int, action: callable, *args, sample_all_processes: bool = None)` | **核心方法**。执行测试步骤并同步采集性能数据。`step_name` 为步骤描述，`duration` 为采集时长(秒)，`action` 为要执行的函数 |
| `setup` | `()` | 测试前初始化：获取 bundle 信息、创建报告目录、停止应用、回到桌面 |
| `teardown` | `()` | 测试后清理：停止应用、生成报告 |
| `process` | `()` | **必须重写**。测试用例主逻辑入口 |
| `report_path` | `property -> str` | 测试报告输出路径 |
| `app_package` | `property -> str` | **必须实现**。被测应用的包名 |
| `app_name` | `property -> str` | **必须实现**。被测应用的中文名 |
| `set_device_redundant_mode` | `()` | 开启设备冗余模式（设置 hdc 参数） |
| `reboot_device` | `()` | 重启设备并等待恢复（最长 180s） |
| `get_app_process_id` | `() -> int` | 获取应用当前进程 PID |

### 2.2 UIEventWrapper - UI 操作封装

**文件**: `hapray/core/ui_event_wrapper.py`

#### 应用生命周期

| API | 签名 | 说明 |
|-----|------|------|
| `start_app` | `(package_name=None, page_name=None, params='', wait_time=5)` | 启动应用。默认启动 `self.app_package` |
| `stop_app` | `(package_name=None, wait_time=0.5)` | 停止应用。桌面应用(`com.ohos.sceneboard`)不会被停止 |

#### 点击操作

| API | 签名 | 说明 |
|-----|------|------|
| `touch_by_text` | `(text: str, wait_seconds=2) -> bool` | 通过文本查找并点击元素，返回是否成功 |
| `touch_by_id` | `(component_id: str, wait_seconds=2) -> bool` | 通过组件 ID 查找并点击 |
| `touch_by_key` | `(key: str, wait_seconds=2) -> bool` | 通过 key 查找并点击 |
| `touch_by_coordinates` | `(x, y, wait_seconds=2) -> bool` | 通过坐标点击（自动适配屏幕分辨率） |

#### 滑动操作

| API | 签名 | 说明 |
|-----|------|------|
| `swipes_up` | `(swip_num: int, sleep: int, timeout=300)` | 向上滑动 N 次，每次间隔 sleep 秒 |
| `swipes_down` | `(swip_num: int, sleep: int, timeout=300)` | 向下滑动 N 次 |
| `swipes_left` | `(swip_num: int, sleep: int, timeout=300)` | 向左滑动 N 次 |
| `swipes_right` | `(swip_num: int, sleep: int, timeout=300)` | 向右滑动 N 次 |

#### 导航操作

| API | 签名 | 说明 |
|-----|------|------|
| `swipe_to_back` | `(sleep: int = 0)` | 返回上一页 |
| `swipe_to_home` | `(sleep: int = 0)` | 回到桌面 |

#### 辅助方法

| API | 签名 | 说明 |
|-----|------|------|
| `find_by_text_up` | `(text: str, try_times=3) -> bool` | 边向上滑动边查找文本，最多尝试 try_times 次 |
| `convert_coordinate` | `(x, y) -> tuple` | 将原始坐标转换为当前设备坐标（自动适配不同屏幕） |

### 2.3 UiDriver 原生驱动（self.driver）

Hypium 框架提供的 `UiDriver`，通过 `self.driver` 访问。

| API | 签名 | 说明 |
|-----|------|------|
| `start_app` | `(pkg, page=None, params='', wait_time=5)` | 启动应用 |
| `stop_app` | `(pkg, wait_time=0.5)` | 停止应用 |
| `touch` | `(component)` | 点击组件（需先用 `BY` 定位） |
| `wait` | `(seconds)` | 等待指定秒数 |
| `swipe_to_home` | `(sleep=0)` | 回桌面 |
| `swipe_to_back` | `()` | 返回 |
| `wake_up_display` | `()` | 唤醒屏幕 |
| `find_component` | `(by)` | 查找组件（返回 None 或组件对象） |
| `input_text` | `(component_or_text, text)` | 输入文本（也可用 `BY.type('TextInput')` 定位输入框） |
| `shell` | `(cmd, timeout=300)` | 在设备上执行 shell 命令 |

### 2.4 BY 定位器（from hypium import BY）

| API | 说明 | 示例 |
|-----|------|------|
| `BY.text(text)` | 按文本匹配 | `self.driver.touch(BY.text('确认'))` |
| `BY.id(id)` | 按组件 ID 匹配 | `self.driver.touch(BY.id('btn_ok'))` |
| `BY.type(type)` | 按组件类型匹配 | `self.driver.touch(BY.type('Button'))` |
| `BY.key(key)` | 按 key 匹配 | `self.driver.touch(BY.key('key_name'))` |

---

## 三、命名规范

| 规范 | 说明 |
|------|------|
| 文件名 | `{类型}_{应用拼音}_{序号}.py`，如 `PerfLoad_jingdong_0010.py` |
| 类名 | 与文件名一致，如 `PerfLoad_jingdong_0010` |
| 测试类型前缀 | `PerfLoad_` (性能负载), `MemLoad_` (内存负载), `ResourceUsage_PerformanceDynamic_` (资源使用动态分析) |
| 目录名 | 应用包名，如 `com.jd.hm.mall/` |
| TAG | `self.TAG = self.__class__.__name__`，固定写法 |

---

## 四、编写要点

### 4.1 process() 结构

```
process()
├── 前置准备（不采集数据）
│   ├── swipe_to_home()
│   ├── start_app()
│   ├── touch_by_text / touch_by_coordinates（导航到目标页面）
│   └── wait / time.sleep
├── 定义 step 函数（多个 def stepN():）
│   └── 每个 step 内写具体的 UI 操作
└── 调用 execute_performance_step()（可多次调用）
    └── 参数: (场景描述, 采集秒数, step函数)
```

### 4.2 关键注意事项

1. **前置导航操作放在 `execute_performance_step` 之外** —— 只有在 `execute_performance_step` 内的操作才会被采集性能数据
2. **屏幕适配** —— 设置 `source_screen_width/height` 为原始采集设备尺寸，`touch_by_coordinates` 会自动转换坐标
3. **坐标 vs 文本** —— 优先使用 `touch_by_text`（更稳定），坐标点击用于文本不可定位的场景
4. **`sample_all_processes=True`** —— 在 MemLoad 类型脚本中传给 `execute_performance_step`，表示采集全部进程数据
5. **返回值检查** —— `touch_by_text/touch_by_id` 返回 `bool`，可用于 fallback 逻辑（找不到时用坐标点击）

### 4.3 输出目录结构

```
report_path/
├── hiperf/              # CPU 性能数据 (perf.data, perf.json)
│   └── steps.json       # 步骤元数据
├── htrace/              # 内存/追踪数据 (trace.htrace)
└── testInfo.json        # 测试元信息（应用名、版本、设备、时间）
```
