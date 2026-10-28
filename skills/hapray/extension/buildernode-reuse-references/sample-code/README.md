# sample-code：改造后的关键代码样本

以下 7 个文件取自一次**真实改造后的完整资讯流工程**（HarmonyOS，API 26，
List + LazyForEach 卡片流，每卡片 7 个 BuilderNode 节点），是技能模式代码
（`../pattern-code.md`）的工程实照。文件为原样复制：import 路径沿用了原工程
的相对结构，仅供阅读，不参与编译。

## 阅读顺序与每个文件演示什么

| 顺序 | 文件 | 演示内容 |
| --- | --- | --- |
| 1 | `NewsNodeData.ets` | 统一数据类（@Observed，字段打平 + 回调随实例）与工厂函数 |
| 2 | `ReusableNodePool.ets` | 池基建：`ReusableNodeItem`（首次 build / 复用 update / 回收态返回 null / takeDown / dispose）+ `ReusableNodeTypePool`（acquire 只取已下树 / recycle 先下树再按限额入池 / clear） |
| 3 | `NewsNodePools.ets` | 池注册表：每类节点一个池、上限常量（含估算说明）、clearAll、统计汇总 |
| 4 | `LikeNode.ets` | 典型节点：`@ObjectLink + @Watch` 接统一数据类，回调经 `this.data.onXxx` 调用 |
| 5 | `TitleNode.ets` | 带内部状态的节点：`@Watch` 里复位标题展开态 |
| 6 | `NewsCardView.ets` | 容器接线：一份数据 7 次 `acquire`、销毁 7 次 `recycle`（判空）、交互只改 item + uiData 属性 |
| 7 | `Index.ets` | 页面：`aboutToDisappear` 时 `clearAll()`；含调试观测（统计指示条 + 定时器去抖与清理） |

## 验证锚点（改造样本用的数据设计，可借鉴）

原工程的 mock 数据固定人设、固定顺序：标题带【第 N 条】序号，数值为固定公式
（点赞 `200+N×89`、评论 `10+N×7`、收藏 `30+N×13`、转发 `5+N×3`），
部分人设为长标题验证折叠展开。滚动时画面与条目不符 = 节点未刷新。

## 池健康度观察（原工程调试观测的行为基线）

- 命中：每次滚过一张卡 +7，只增不减——复用生效；
- 新建：首屏约 4 张卡 × 7 = 28，稳定后基本不再增长；
- 空闲：稳态小幅波动，快滑突发时可逼近上限（每类上限 × 节点类数）；
  持续增大并逼近/超过上限 = 复用未命中（常见原因：回收时未先下树）。

事件日志：hilog 过滤 `NodePool` / `ReuseCard` 可看到 hit / new / recycle /
dispose-on-recycle / clear 完整事件流。

> 注：统计指示与事件日志是**调试观测设施**（本样本为演示目的保留全套）；
> 生产改造按技能第 0 步与开发者确认的结果决定去留，默认不加。
