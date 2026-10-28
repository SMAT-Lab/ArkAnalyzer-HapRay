# BuilderNode 复用池改造（组件复用拓展 · extension 子 Skill）

> **路由**：主 Skill [`../SKILL.md`](../SKILL.md) §5 信号路由 / §7 约束索引；索引见 [`README.md`](README.md)。
> **定位**：**组件复用域的拓展**——覆盖 `component-reuse` 信号检测不到的 BuilderNode 节点池通道。**检查默认使用**（组件复用相关分析默认检查本通道，见 §〇）；**改造经用户确认**后执行。
> **资料**：通用化模式代码、人工改造指南、真实改造样本全套随包分发，见 [`buildernode-reuse-references/`](buildernode-reuse-references/)。源码路径直接用 §0 已确认的值，不重复询问。

## 〇、进入判定与信号对照

| 信号（分析/根因产物） | 与本拓展的关系 |
|---|---|
| `cpu-hotspot`：条目组件 `build` / `BuilderNode` 相关热点 | **直接适用**——反复构建即改造目标 |
| `scroll-jank`：滑动周期性卡顿 + 构建调用聚集 | **直接适用** |
| `component-reuse`（`trace_componentReuse.json` 低复用率） | **间接参考**——见下方「两条复用通道」 |

**默认检查（无需用户点名）**：组件复用相关分析/根因中，除 @Reusable 通道外，**默认**对 §0 源码执行本通道检查：

```
grep: NodeContainer( / extends NodeController / new BuilderNode / wrapBuilder / .dispose()
```

判定两点：① 条目组件生命周期内（`aboutToAppear`/`aboutToDisappear` 或 `makeNode`/`dispose`）是否反复 `new BuilderNode` + `build`；② 滚动容器（List / Swiper / Grid + LazyForEach）内同类条目节点结构是否同构、只是数据不同。无 `NodeContainer+BuilderNode` 用法或仅静态挂载一次 → 记录「已检查，不适用」。

**无源码边界（第三方应用）**：无 §0 源码时本通道检查不可用——`NodeContainer`/`BuilderNode` 在 trace 侧无事件命名，`component-reuse` 指标亦不覆盖（其 `details` 仅含 CustomNode:Build 计数）；报告中注明「BuilderNode 通道未检查（无源码）」即可，勿用 @Reusable 指标推断本通道状态。

**改造时机（root-cause 之前，经用户确认）**：检查确认适用后向用户提出改造建议；改造消除的是**有既定模式**的构建耗时问题，不必带进根因分析，且改码后旧根因结论即过时。改造后复用脚本重采（见[§三](#三拓展后重采与根因衔接hapray-集成)），root-cause 基于拓展后数据。

**两条复用通道（关键区分，勿混淆）**：

- **@Reusable 组件复用**：ArkUI 内建机制，作用于 LazyForEach **条目组件**层；CLI `component-reuse` 信号度量的就是它（trace 特征 `H:CustomNode:BuildItem` vs `H:CustomNode:BuildRecycle`）。
- **BuilderNode 节点池**（本拓展）：应用层自建池，NodeController 层 `acquire/recycle` + `update()` 换数据；改造的是**条目内部的节点供给**，条目组件本身的创建/销毁不变。
- 因此 `reusability_ratio` **不能**作为本改造的效果指标（改造前后该值基本不动是正常现象）；效果验证走 [§三](#三拓展后重采与根因衔接hapray-集成) 的重采复评与前后对比。

**适用前提**：滚动容器（List / Swiper / Grid + LazyForEach）内，同类条目**节点结构同构、只是数据不同**，节点挂载数量 ≥ 数个。
**不适用**：节点结构每条差异巨大；BuilderNode 仅页面级静态挂载一次（无反复构建即无复用收益）。

## 一、核心设计规则（每条对应真机踩过的坑）

1. **复用挂载用 `BuilderNode.update(newData)`，不要用 `reuse()`/`recycle()`。**
   `reuse/recycle` 是向内部自定义组件传递 `aboutToReuse/aboutToRecycle` 事件的
   通道（服务于 @Reusable 组件复用机制），不是给节点池换数据用的。
2. **被包裹的组件用「统一数据类 + `@ObjectLink` + `@Watch`」，不要用 `@Prop`。**
   `update()` 只刷新被装饰变量，普通属性不会刷新——参数里的回调函数是普通属性，
   用 @Prop 时换卡后节点仍持有旧容器的回调（点赞会打到上一张卡上）。
   改成 @Observed 统一数据类后：挂载中改属性 → @ObjectLink 自动刷新，容器侧
   无需手动调 update；换卡传新实例 → @ObjectLink 重指向 + @Watch 触发（用于
   复位内部状态，如文案展开态），回调随新实例自然换绑。
   数据类字段必须**打平为第一层属性**（@Observed 只监听第一层）。
3. **一次性准备放在生命周期钩子，不要放进 @Watch/更新路径；落点按工作性质选。**
   与具体数据无关、组件实例生命周期内只需做一次的工作，复用模式下实例跨
   条目保留、天然只执行一次（这正是复用收益的一部分）；误放进 @Watch 则
   每次换数据重复执行（重复注册、动画重启/叠加）。落点分两类：
   - **逻辑类 → `aboutToAppear`（创建时）**：事件/服务订阅、监听器注册、
     耗时对象初始化、数据结构预取。订阅随实例走：换数据不重订，实例销毁
     （复用模式下即 dispose，归还池不触发）才退订；
   - **显示类 → `onAppear`（首次显示时）**：无限循环动画启动等渲染相关
     工作（唱片旋转、音波均衡器）。复用模式下动画随组件实例持续运行，
     节点重挂载会再次触发 onAppear——必须加启动守卫（只允许首次启动
     一次）：重复 animateTo 会把仍在运行的无限动画从中途打断，新一轮
     区间被拉长，表现为动画速度时快时慢（真机验证过的坑）。
   @Watch 里只放与数据相关的复位逻辑（如文案展开态）。判断口径：这段逻辑
   依赖新数据的值吗？不依赖 → 一次性准备（按性质选钩子）；依赖 → 才放进
   更新路径。
4. **回收时先下树再入池**：置回收标记后主动调用 NodeController 的 `rebuild()`，
   让 NodeContainer 重新回调 `makeNode`，`makeNode` 对回收态返回 `null`。
   不这样做的话，「已回收但还没从树上卸载」的节点会被 acquire 的 getParent()
   判定跳过、取不走，池失效并持续膨胀。
5. **池按节点类型分池**（一类节点一个池、一个 builder），acquire 只取
   `getFrameNode().getParent()` 为空的已卸载节点。
6. **池必须有清理策略；空闲上限先询问开发者，不要自行拍定**：
   - 每类节点空闲上限 ≥ **两屏条目数**：一屏条目数 = 屏高 / 条目高
     （垂直 Swiper 单列 = 1 条 → 上限 2；List/Grid 一屏约 N 条 → 上限 2N，
     N 向上取整），快速连滑/长 fling 多的场景再酌情加余量；
   - 依据：快速滑动时一批条目会「先创建后销毁」（或反之），池要能缓冲这个
     突发；池太小会频繁「销毁又重建」，复用率下降——这正是要避免的；
   - 改造前向开发者确认上限取值，给出两个选项：a) **由 AI 按业务估算**
     （推荐，附估算过程）；b) **开发者指定数值**。开发者未表态时先采用
     估算值并告知「如需调整改这一个常量即可」；
   - 回收时池内空闲已达上限 → 直接 `dispose`，不再入池；入池后超限 →
     防御性 dispose 多余节点；承载页面销毁（aboutToDisappear）→ `clearAll()`。
7. **`wrapBuilder` 是全局声明的函数，不要 import**（import 会编译失败）。
8. **只 dispose 已下树的节点**：对挂载中的节点 dispose 会让组件树悬空。
   dispose 后置 `builderNode = null`，此后即使误触发 makeNode 也只会返回 null。

## 二、改造流程

### 第 0 步：确认改造方式、池上限与调试观测（问用户三件事）

1. **原地改造**还是**并行双版本**（保留原实现作 A/B 对比）。用户提到
   「对比/演示/两版」时选并行：复制容器组件与页面为 Reuse* 版本，原文件不动。
2. **池空闲上限取值**（规则 6）：AI 估算 or 开发者指定。
3. **是否需要调试观测产物**（命中/新建/空闲计数器、`[NodePool]`/`[ReuseCard]`
   事件日志、页面内指示条）：**默认不加**，开发者明确要才加。

### 第 1 步～第 5 步（按资料执行）

```
grep: NodeContainer( / extends NodeController / new BuilderNode / wrapBuilder / .dispose()
```

1. 盘点现有用法（只读）：参数类字段、视图装饰器、创建/销毁点、update() 调用点、
   cachedCount 与一屏条目数（供上限估算）；
2. 建统一数据类（@Observed，字段打平 + 回调随实例）→ [`references/pattern-code.md`](buildernode-reuse-references/pattern-code.md) 第 1 节；
3. 改节点组件（@Prop → `@ObjectLink + @Watch`）→ 第 2 节；
4. 建池基建（`ReusableNodeItem` + `ReusableNodeTypePool` + 池注册表）→ 第 3 节，可直接复用（改包名与数据类名）；
5. 改容器组件（`aboutToAppear` 逐类 acquire / `aboutToDisappear` 逐类 recycle /
   交互只改数据属性不调 update / 承载页面 `clearAll()`）→ 第 4 节。

## 三、拓展后重采与根因衔接（HapRay 集成）

改造完成后**不直接进入根因分析**，按以下顺序衔接：

1. **编译**：用户工程构建命令零告警；
2. **行为清单**：来回滑动内容正确；交互回调打到当前容器；内部状态（展开态等）
   换容器后复位；一次性准备（动画/注册类）只在节点新建时执行；返回上级页面
   再进入，池从零开始。内容刷新校验优先**数据锚点法**（mock 可辨认数据：
   序号/固定公式，画面与条目序号不符 = 未刷新）；
3. **重采**：复用拓展前**同一 `PerfLoad_*` 脚本**与同一设备重新采集（阶段 2）；
4. **阶段 4 复评**：确认构建类热点（`cpu-hotspot` / `scroll-jank` 构建调用聚集）
   已消除或显著下降；
5. **进入阶段 5 root-cause**：基于**拓展后数据**做多信号综合根因分析——聚焦
   拓展后仍存在的未知问题；
6. **阶段 6 报告**：反映拓展后状态；收益对比引用前后两轮产物
   （pre = 拓展前 / post = 拓展后），关注指标：CPU 指令数（高负载主线）、
   卡顿帧/掉帧率（scroll-jank）、GC 次数；正式收益量化可走
   [`../workflow/pr-impact-analysis.md`](../workflow/pr-impact-analysis.md) 双轮流程；
7. **池健康观测**（仅当第 0 步启用观测设施）：hilog 过滤 `NodePool` / `ReuseCard`
   看 hit / new / recycle / dispose / clear 事件流；健康基线：命中只增不减、
   新建稳定后基本不涨、空闲在上限内小幅波动——空闲持续增大逼近上限 =
   复用未命中（常见原因：回收未先下树）。

## 四、常见坑速查

| 症状 | 原因 | 规则 |
| --- | --- | --- |
| 换卡后点赞改了别的卡的数据 | 回调是普通属性，update 刷不到 | 规则 2（@ObjectLink） |
| 每次换数据动画重启/叠加、监听器重复注册 | 一次性准备被放进了 @Watch/更新路径 | 规则 3 |
| 池里数字只涨不落、复用不命中 | 回收的节点还挂在树上 | 规则 4（rebuild→null 下树） |
| 空闲数远超预期（如 3 倍） | 快滑突发下未命中的节点滞留 | 规则 6（上限+清理） |
| 语义疑惑：要不要用 reuse() | 误把 @Reusable 事件通道当换数接口 | 规则 1（update()） |
| import wrapBuilder 编译失败 | 它是全局声明 | 规则 7 |

## 五、参考资料（buildernode-reuse-references/）

- [`pattern-code.md`](buildernode-reuse-references/pattern-code.md)：通用化模式代码四件套（数据类 / 池基建 / 节点 / 容器接线），先读它再动手；
- [`BuilderNode复用改造指南.md`](buildernode-reuse-references/BuilderNode复用改造指南.md)：面向开发者的分步改造手册（含前后代码对照与原理说明）；
- [`sample-code/`](buildernode-reuse-references/sample-code/README.md)：一次真实改造后的 7 个关键工程文件原样副本（数据类、池基建、池注册表、典型节点、带内部状态的节点、容器接线、页面清理与观测），附阅读顺序索引。
