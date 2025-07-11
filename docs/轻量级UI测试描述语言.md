# 轻量级UI测试描述语言

## 一、业界**主流 UI 测试录制与回放方案总结**

### 1.1 **iOS 平台 (Apple XCUITest)**

**录制工具**：Xcode UI Test Recorder

- **录制方式**：
    - 在 Xcode 中启动录制功能
    - 操作 iOS 模拟器或真机
    - 自动生成 Swift/Objective-C 代码
- **生成脚本示例**：

```swift
let app = XCUIApplication()
app.buttons["Login"].tap()
app.textFields["username"].typeText("testuser")
app.secureTextFields["password"].typeText("password123")
app.buttons["Submit"].tap()
```

### 1.2 **Android 平台 (Google Espresso/UI Automator)**

**录制工具**：Android Studio Test Recorder

- **录制方式**：
    - 在 Android Studio 中启动录制
    - 操作模拟器或真机
    - 生成 Java/Kotlin 测试代码
- **生成脚本示例**：

```java
onView(withId(R.id.login_button)).perform(click());
onView(withId(R.id.username_field)).perform(typeText("testuser"));
onView(withId(R.id.password_field)).perform(typeText("password123"));
onView(withId(R.id.submit_button)).perform(click());
```

### 1.3 鸿蒙平台

**录制工具**：Hypium 插件

- **录制方式**：
    - 在 PyCharm 中启动Hypium插件录制
    - 操作真机
    - 生成 python测试代码
- **生成脚本示例**：

```python
        # 点击text为{专业}的控件
        self.driver.touch(BY.text('专业'))
        self.driver.wait(0.5)
        # 点击type为{Text}并且text为{更多介绍}的控件
        self.driver.touch(BY.type('Text').text('更多介绍'))
        self.driver.wait(0.5)
        # 从(886, 1956)滑动至(914, 879)
        self.driver.slide((886, 1956), (914, 879))
        self.driver.wait(0.5)
        # 从(1001, 823)拖拽至(1021, 839)
        self.driver.drag((1001, 823), (1021, 839))
        self.driver.wait(0.5)
```

### 1.4 总结

UI测试脚本录制均直接生成最终代码，录制的内容仅包含了UI的操作。完整的测试脚本还需要开发者二次加工。对于HapRay而言，一个完整的测试用例定义包含：

1. 基础配置：被测试应用包名、应用名、屏幕大小(可选)
2. 用例执行前置条件：拉起应用，若干UI点击操作
3. 场景化测试步骤：步骤名、步骤序号、采集持续事件，UI操作
4. 测试完成生成测试报告

录制回放仅能解决其中的UI操作部分。

## 二、HapRay UI测试领域描述语言 (HapRay UI Test DSL)

HapRay已有测试用例基于Hypium接口实现的python 用例，这些用例为开发者基于应用重要场景编写。未来希望HapTest综合模糊测试和人工简单配置不同页面的权重来生成HapRay的测试用例。为简化HapTest用例生成，我们定义一种轻量级的领域描述语言（DSL），用于描述HapRay的UI自动化测试用例。该语言采用YAML格式，具有良好的可读性和易于编写的特点，专注于解决移动应用UI自动化测试的需求。

### 2.1 语言核心组件

- **组件选择器（Component Selectors）**：用于精确定位UI元素
    - 基本选择器：text、type、key、id、xpath
    - 复合选择器：组合多个基本选择器
    - 相对选择器：定位元素之间的关系（之前、之后、内部）
- **界面操作（UI Actions）**：模拟用户与界面的交互
    - 点击操作（touch）：普通点击、长按、双击
    - 滑动操作（swipe）：上滑、下滑、左滑、右滑
    - 缩放操作（pinch）：放大、缩小
    - 文本输入（input_text）：在文本框输入内容
    - 按键操作（press_key）：模拟物理按键
- **应用操作（App Operations）**：控制应用生命周期
    - 启动应用（start_app）：启动指定应用
    - 停止应用（stop_app）：停止指定应用
- **控制语句（Control Statements）**：控制测试流程
    - 循环操作（loop）：重复执行特定步骤
    - 等待操作（wait）：等待特定时间
    - 性能采集 (performance): 采集负载相关性能数据

### 2.2 DSL示例

```yaml
config:
  source_screen: [1084, 2412]  # 设计基准分辨率
  app_package: 'com.ss.hm.ugc.aweme' # 应用报名
  app_name: '抖音' # 应用名
  scene_name: 'ResourceUsage_PerformanceDynamic_Douyin_0010' # 测试场景名

test_cases:
	- name: "start"
		steps:
			# 启动应用，等待5s
			- type: "start_app"
			- type: "wait"
				duration: 5
				
			# 浏览视频，上滑5次, 每次等待1s
			- type: "loop"
				count: 5
				steps:
					- type: "swipe",
						direction: "UP"
						
					- type: "wait"
						duration: 1
						
				# 抖音点击“我”，等待 2s
				- type: "touch"
					target:
						text: "我"
				- type: "wait"
					duration: 2
					
				# 抖音“我”页面点击右上角选项，等待2s
				- type: "touch"
          target:
					  pos: [988, 183]
				- type: "wait"
					duration: 2
		
		- name: "点击观看历史"
			perf:
				step: 1           # 步骤
				duration: 10   # perf/trace采集时间10s
			steps:
				- type: "touch"
					target:
						text: "观看历史"
				- type: "wait"
					duration: 2
		
		- name: "观看历史浏览"
			performance:
				step: 2
				duration: 20	# 采集时间20s
			steps:
				# 上滑5次
				- type: "loop"
					count: 5
					steps:
						- type: "swipe",
							direction: "UP"
							
						- type: "wait"
							duration: 1
							
					# 下滑5次
					- type: "loop"
					count: 3
					steps:
						- type: "swipe",
							direction: "DOWN"
							
						- type: "wait"
							duration: 1
```

### 2.3 详细接口定义

### 2.3.1 组件选择器

| 操作 | 参数 | 说明 |
| --- | --- | --- |
| BY.text | text:strpattern: MatchPattern |  |
| BY.key | key:str |  |
| BY.type | type:str |  |
| BY.xpath | path: str |  |

**多属性组合定位控件**

```yaml
# 点击文本为"蓝牙", 类型为"Button", 并且key为"bluetooth_switch"的按钮
driver.touch(BY.text("蓝牙").type("Button").key("bluetooth_switch"))
```

**控件相对位置+属性组合定位控件**

```yaml
# 查找在text属性为"显示通知图标"的控件之后的type属性为"Button"的控件
component = driver.find_component(BY.type("Button").isAfter(BY.text("显示通知图标")))
# 查找在text属性为"账号"的控件之前的type属性为"Image"的控件
component = driver.find_component(BY.type("Image").isBefore(BY.text("账号")))
# 查找在key为"nav_container"内部的类型为"Image"的控件
component = driver.find_component(BY.type("Image").within(BY.key("nav_container")))
# 查找包名为"com.huawei.hmos.settings"的应用内部的text属性为"蓝牙"的控件
component = driver.find_component(BY.text("蓝牙").inWindow("com.huawei.hmos.settings"))
```

### 2.3.2 触摸屏界面基础操作

| 操作 | 参数 | 说明 |
| --- | --- | --- |
| **点击touch** | target:Union[By, UiComponent, tuple]，<br>mode: str = "normal"，<br>scroll_target: Union[By, UiComponent] = None，<br>wait_time: float = 0.1 | target：需要点击的目标，可以为控件(通过By类指定)或者屏幕坐标(通过tuple类型指定，例如(100, 200)， 其中100为x轴坐标，200为y轴坐标), 或者使用find_component找到的控件对象<br>mode：点击模式，目前支持:"normal" 点击"long" 长按（长按后放开）"double" 双击<br>scroll_target：指定可滚动的控件，在该控件中滚动搜索指定的目标控件target。仅在target为By对象时有效<br>wait_time：点击后等待响应的时间，默认0.1s |
| **捏合缩小pinch_in** | area: Union[By, UiComponent, Rect], scale: float = 0.4, direction: str = "diagonal", **kwargs | area: 手势执行的区域<br>scale: 缩放的比例, [0, 1], 值越小表示缩放操作距离越长, 缩小的越多<br>direction: 双指缩放时缩放操作方向, 支持"diagonal" 对角线滑动 "horizontal" 水平滑动<br>kwargs:其他可选滑动配置参数dead_zone_ratio 缩放操作时控件靠近边界不可操作的区域占控件长度/宽度的比例, 默认为0.2, 调节范围为(0, 0.5) |
| **双指放大pinch_out** | area: Union[By, UiComponent, Rect], scale: float = 1.6, direction: str = "diagonal", **kwargs | area: 手势执行的区域<br>scale: 缩放的比例, [0, 1], 值越小表示缩放操作距离越长, 缩小的越多<br>direction: 双指缩放时缩放操作方向, 支持"diagonal" 对角线滑动"horizontal" 水平滑动<br>kwargs:其他可选滑动配置参数dead_zone_ratio 缩放操作时控件靠近边界不可操作的区域占控件长度/宽度的比例, 默认为0.2, 调节范围为(0, 0.5) |
| **滑动swipe** | direction: str,distance: int = 60, area: Union[By, UiComponent] = None, side: str = None, start_point: tuple = None, swipe_time: float = 0.3 | direction：滑动方向，目前支持:  "LEFT" 左滑  "RIGHT" 右滑  "UP" 上滑  "DOWN" 下滑<br>distance： 相对滑动区域总长度的滑动距离，范围为1-100, 表示滑动长度为滑动区域总长度的1%到100%， 默认为60<br>area：通过控件指定的滑动区域<br>side：滑动位置， 指定滑动区域内部(屏幕内部)执行操作的大概位置，支持: UiParam.LEFT 靠左区域 UiParam.RIGHT 靠右区域 UiParam.TOP 靠上区域 UiParam.BOTTOM 靠下区域<br>start_point：滑动起始点, 默认为None, 表示在区域中间位置执行滑动操作, 可以传入滑动起始点坐标，支持使用(0.5, 0.5)这样的比例坐标。当同时传入side和start_point的时候, 仅start_point生效<br>swipe_time：滑动时间(s)， 默认0.3s |
| **输入文本input_text** | component: Union[By, UiComponent], text: str | component：需要输入文本的控件，可以使用By对象，或者使用find_component找到的控件对象<br>text：需要输入的文本 |
| **按键press_key** | key_code: Union[KeyCode, int], key_code2: Union[KeyCode, int] = None, mode="normal" | key_code：需要按下的按键编码<br>key_code2：需要按下的按键编码<br>mode：按键模式, 仅在进行单个按键时支持，支持: UiParam.NORMAL 默认, 按一次 UiParam.LONG 长按 UiParam.DOUBLE 双击 |

### 2.3.3 应用操作

| 操作 | 参数 | 说明 |
| --- | --- | --- |
| **start_app** | package_name: str, page_name: str = None, params: str = "", wait_time: float = 1 | package_name：应用程序包名(bundle name)<br>page_name：应用内页面名称(ability name)<br>params：其他传递给aa命令行参数<br>wait_time：发送启动指令后，等待app启动的时间 |
| **stop_app** | package_name: str, wait_time: float = 0.5 | package_name：应用程序包名(bundle name)<br>wait_time：停止app后延时等待的时间, 单位为秒 |

### 2.3.4 控制语句

| 操作 | 参数 | 说明 |
| --- | --- | --- |
| **wait** | duration: int | 等待（毫秒） |
| **loop** | count: int, steps[] | 循环执行子步骤 |

## **三、UI测试配置规范 (YAML Schema)**

```yaml
# UI 测试配置规范 v1.0
version: 1.0
description: 支持复杂组件选择器的 UI 测试配置规范

# 根对象
type: object
required: [config, test_case]
properties:
  config:
    type: object
    required: [app_package, app_name, scene_name]
    properties:
      source_screen:
        type: array
        description: 设计基准分辨率 [宽度, 高度]
        items:
          type: number
        minItems: 2
        maxItems: 2
      app_package:
        type: string
        description: 应用包名
        minLength: 1
      app_name:
        type: string
        description: 应用显示名称
        minLength: 1
      scene_name:
        type: string
        description: 测试场景标识符
        minLength: 1

  test_case:
    type: object
    description: 测试用例
    required: [steps]
    properties:
      setup:
        type: array
        description: 前置步骤序列
        items:
          $ref: "#/definitions/event"
      cleanup:
        type: array
        description: 清理步骤序列
        items:
          $ref: "#/definitions/event"
      steps:
        type: array
        description: 主步骤序列
        minItems: 1
        items:
          type: object
          required: [name, events]
          properties:
            name:
              type: string
              description: 步骤名称
              minLength: 1
            performance:
              type: object
              required: [duration]
              description: 性能采集配置
              properties:
                duration:
                  type: integer
                  description: 采集持续时间(s)
                  minimum: 1
            events:
              type: array
              description: 事件序列
              minItems: 1
              items:
                $ref: "#/definitions/event"
# 定义
definitions:
  componentSelector:
    type: object
    description: 组件选择器
    properties:
      text:
        type: string
        description: 文本匹配
      key:
        type: string
        description: 键值匹配
      type:
        type: string
        description: 类型匹配
      xpath:
        type: string
        description: XPath 匹配
      relations:
        type: array
        description: 相对位置关系
        items:
          type: object
          properties:
            relation:
              type: string
              enum: [ isAfter, isBefore, within, inWindow ]
            target:
              $ref: "#/definitions/componentSelector"
          required: [ relation, target ]
      pos:
        type: array
        description: 坐标位置 [x, y]
        items:
          type: number
        minItems: 2
        maxItems: 2

  event:
    oneOf:
      - $ref: "#/definitions/touchEvent"
      - $ref: "#/definitions/swipeEvent"
      - $ref: "#/definitions/pinchEvent"
      - $ref: "#/definitions/inputEvent"
      - $ref: "#/definitions/waitEvent"
      - $ref: "#/definitions/loopEvent"
      - $ref: "#/definitions/keyEvent"
      - $ref: "#/definitions/startAppEvent"
      - $ref: "#/definitions/stopAppEvent"

  # 具体事件类型
  touchEvent:
    type: object
    required: [type, target]
    properties:
      type:
        type: string
        const: touch
        description: 点击事件
      target:
        $ref: "#/definitions/componentSelector"
      mode:
        type: string
        description: 点击模式
        enum: [normal, long, double]
        default: normal
      scroll_target:
        $ref: "#/definitions/componentSelector"
        description: 滚动查找的目标组件
      wait_time:
        type: number
        description: 点击后等待时间(s)
        default: 0.1

  swipeEvent:
    type: object
    required: [type, direction]
    properties:
      type:
        type: string
        const: swipe
        description: 滑动事件
      direction:
        type: string
        description: 滑动方向
        enum: [LEFT, RIGHT, UP, DOWN]
      distance:
        type: integer
        description: 滑动距离百分比(1-100)
        minimum: 1
        maximum: 100
        default: 60
      area:
        $ref: "#/definitions/componentSelector"
        description: 滑动区域组件
      side:
        type: string
        description: 滑动起始位置
        enum: [LEFT, RIGHT, TOP, BOTTOM]
      start_point:
        type: array
        description: 滑动起始点坐标 [x, y] 或比例 [0.5, 0.5]
        items:
          type: number
        minItems: 2
        maxItems: 2
      swipe_time:
        type: number
        description: 滑动时间(s)
        default: 0.3

  pinchEvent:
    type: object
    required: [type, operation, area]
    properties:
      type:
        type: string
        const: pinch
        description: 捏合手势事件
      operation:
        type: string
        description: 捏合操作类型
        enum: [in, out]
      area:
        $ref: "#/definitions/componentSelector"
      scale:
        type: number
        description: 缩放比例
        default: 0.4
      direction:
        type: string
        description: 滑动方向
        enum: [diagonal, horizontal]
        default: diagonal
      dead_zone_ratio:
        type: number
        description: 边界死区比例
        minimum: 0
        maximum: 0.5
        default: 0.2

  inputEvent:
    type: object
    required: [type, component, text]
    properties:
      type:
        type: string
        const: input_text
        description: 输入事件
      component:
        $ref: "#/definitions/componentSelector"
        description: 目标输入组件
      text:
        type: string
        description: 输入的文本

  waitEvent:
    type: object
    required: [type, duration]
    properties:
      type:
        type: string
        const: wait
        description: 等待事件
      duration:
        type: integer
        description: 等待时间(s)
        default: 1

  loopEvent:
    type: object
    required: [type, count, events]
    properties:
      type:
        type: string
        const: loop
        description: 循环事件
      count:
        type: integer
        description: 循环次数
        minimum: 1
      events:
        type: array
        description: 循环内的事件序列
        minItems: 1
        items:
          $ref: "#/definitions/event"

  keyEvent:
    type: object
    required: [type, key_code]
    properties:
      type:
        type: string
        const: press_key
        description: 按键事件
      key_code:
        oneOf:
          - type: string
            enum: [BACK, HOME, MENU, ENTER, VOLUME_UP, VOLUME_DOWN, POWER]
          - type: integer
        description: 按键类型
      key_code2:
        oneOf:
          - type: string
            enum: [BACK, HOME, MENU, ENTER, VOLUME_UP, VOLUME_DOWN, POWER]
          - type: integer
        description: 第二个按键(组合键)
      mode:
        type: string
        description: 按键模式
        enum: [normal, long, double]
        default: normal

  startAppEvent:
    type: object
    required: [type]
    properties:
      type:
        type: string
        const: start_app
        description: 启动应用事件
      package_name:
        type: string
        description: 应用包名
      page_name:
        type: string
        description: 应用内页面名称
      params:
        type: string
        description: 启动参数
      wait_time:
        type: number
        description: 等待时间(s)
        default: 1

  stopAppEvent:
    type: object
    required: [type]
    properties:
      type:
        type: string
        const: stop_app
        description: 停止应用事件
      package_name:
        type: string
        description: 应用包名
      wait_time:
        type: number
        description: 等待时间(s)
        default: 0.5

```