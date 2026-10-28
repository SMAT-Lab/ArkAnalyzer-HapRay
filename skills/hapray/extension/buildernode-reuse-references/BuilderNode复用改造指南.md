# BuilderNode 复用改造指南：把「不复用」改成「复用」

面向已经用 `NodeContainer + BuilderNode` 实现了界面、想在滚动场景下消除
反复构建耗时的开发者。文中所有前后代码对照取自一次真实改造
（资讯流 List，每条卡片 7 个节点：头像、作者+关注、标题、点赞、评论、
收藏、转发），改造后编译零告警、行为无回退。

> 配套资料：
> - 同主题 AI 技能 `buildernode-reuse`（`../SKILL.md`，供 ZCode 等工具
>   自动执行本改造，其 `references/` 内含改造后关键代码样本）；
> - 本文代码来源的示例工程见所在仓库的 `sample/` 目录，其 git 历史保留
>   了改造前后的完整对照。

## 1. 为什么改：问题与收益

**问题**：滚动容器（List / Swiper / Grid + LazyForEach）会持续创建、销毁
条目组件。每个条目挂 N 个 `NodeContainer`，条目一出现就要
`new BuilderNode` + `build` 构建整棵组件树，条目滑出缓存区就 `dispose`。
来回滑动时，同一批节点被**反复构建、反复销毁**——构建是毫秒级开销，
节点多、滑动快时直接表现为掉帧、白块。

**收益**：复用池让组件树**只构建一次**。条目销毁时节点不下岗，先从树上
卸下、归还池中；下一个条目出现时从池里取出，`BuilderNode.update()`
换一份数据接着用。构建开销从「每次出现」降为「首次出现」。

**适用条件**：同一类条目内节点种类固定、只是数据不同（同构结构）。
节点结构每条差异巨大、或页面级静态挂载的 BuilderNode，没有复用收益。

---

## 2. 改造总览：三处变化

| 位置 | 改造前（不复用） | 改造后（复用） |
| --- | --- | --- |
| 节点组件 | `@Prop` 接数据 + 回调放普通属性 | `@ObjectLink + @Watch` 接一个 `@Observed` 统一数据类，数据与回调都从 `this.data` 读 |
| 节点供给 | 条目出现时 `new ParamNodeController`（内部 new BuilderNode + build），销毁时 `dispose` | 条目出现时 `pool.acquire(data)`（池优先），销毁时 `pool.recycle(item)`（先下树再入池） |
| 数据刷新 | 交互后 `makeXxxParams` + `node.update(params)` 手动推 | 交互后直接改数据对象属性，`@Observed` 自动刷新 |

改造分六步，顺序不要乱。以下每步都有前后代码对照。

---

## 3. 动手前确认三件事

1. **原地改还是双版本并行**？要留 A/B 对比演示就复制一套 `Reuse*` 文件并行，
   原文件不动；否则原地改（本文示例为原地改）。
2. **池空闲上限**：按业务估算，**至少两屏条目数**——一屏条目数 = 屏高 ÷
   条目高（示例工程卡片约 240vp、可视区约 720vp → 每屏 3 条 → 公式给 6，
   快滑多再留余量，实际取 10）。这个值写在一个常量里，别散落。
3. **要不要调试观测**（命中/新建/空闲计数、事件日志、页面指示条）：
   会侵入 UI 和日志，生产代码默认不加；调优期可加，验收后移除。

---

## 4. 六步改造

### 第 1 步：盘点现有节点

全局搜 `NodeContainer(`、`extends NodeController`、`new BuilderNode`、
`wrapBuilder`，对每个节点记三样东西：参数类字段（数据 + 回调）、视图用了
什么装饰器、谁在什么时机创建/销毁它。顺便记下滚动容器的
`cachedCount` 和一屏条目数（第 3 节问题 2 要用）。

### 第 2 步：建统一数据类

把**所有节点用到的数据字段和交互回调**收进一个 `@Observed` 类，字段全部
打平为第一层属性（`@Observed` 只监听第一层赋值）。一个条目一份实例，
全部节点共用。

```ts
@Observed
export class NewsNodeData {
  avatarIndex: number = 0;
  authorName: string = '';
  isFollowed: boolean = false;
  title: string = '';
  isLiked: boolean = false;
  likeCount: number = 0;
  // ……其余节点用到的字段

  // 交互回调也收进来：随数据实例换绑，见第 6.1 节原理
  onAvatarClick: () => void = () => {};
  onFollowClick: (followed: boolean) => void = () => {};
  onLikeClick: (liked: boolean) => void = () => {};
  // ……
}

export function makeNewsNodeData(item: NewsItem, /* 6 个回调 */): NewsNodeData {
  const data = new NewsNodeData();
  data.avatarIndex = item.avatarIndex;
  data.authorName = item.authorName;
  // ……逐字段赋值
  data.onLikeClick = onLikeClick;
  return data;
}
```

### 第 3 步：改节点组件（@Prop → @ObjectLink + @Watch）

以点赞节点为例。**改造前**（不复用形态）：

```ts
export class LikeParams {
  isLiked: boolean = false;
  likeCount: number = 0;
  onToggleLike: (liked: boolean) => void = () => {};
}

@Component
struct LikeView {
  @Prop isLiked: boolean = false;
  @Prop likeCount: number = 0;
  onToggleLike: (liked: boolean) => void = () => {};   // 普通属性

  build() {
    Row({ space: 5 }) {
      Image(this.isLiked ? $r('app.media.ic_heart_filled_red')
        : $r('app.media.ic_heart_outline_white')).width(22).height(22)
      Text(FormatUtil.formatCount(this.likeCount)).fontSize(12)
    }
    .onClick(() => this.onToggleLike(!this.isLiked))
  }
}

@Builder
function buildLike(params: LikeParams) {
  LikeView({ isLiked: params.isLiked, likeCount: params.likeCount,
    onToggleLike: params.onToggleLike })
}

export function createLikeNode(item, cb): ParamNodeController<LikeParams> {
  return new ParamNodeController<LikeParams>(
    wrapBuilder<[LikeParams]>(buildLike), makeLikeParams(item, cb));
}
```

**改造后**：

```ts
@Component
struct LikeView {
  @ObjectLink @Watch('onDataUpdated') data: NewsNodeData;

  // 换条目重挂载（update 传入新数据实例）时触发；无内部状态则留空
  onDataUpdated(propName: string): void {
  }

  build() {
    Row({ space: 5 }) {
      Image(this.data.isLiked ? $r('app.media.ic_heart_filled_red')
        : $r('app.media.ic_heart_outline_white')).width(22).height(22)
      Text(FormatUtil.formatCount(this.data.likeCount)).fontSize(12)
    }
    .onClick(() => this.data.onLikeClick(!this.data.isLiked))
  }
}

@Builder
function buildLike(data: NewsNodeData) {
  LikeView({ data: data })
}

// 构建器导出给复用池用；wrapBuilder 是全局函数，不要 import
export const likeNodeBuilder: WrappedBuilder<[NewsNodeData]> =
  wrapBuilder<[NewsNodeData]>(buildLike);
```

要点：
- 每类节点删掉自己的 Params 类、`makeXxxParams`、`createXxxNode`，
  只保留一个导出的 builder 常量；
- 有内部状态的节点（如标题折叠态）在 `@Watch` 回调里复位：

```ts
@Component
struct TitleView {
  @ObjectLink @Watch('onDataUpdated') data: NewsNodeData;
  @State expanded: boolean = false;

  onDataUpdated(propName: string): void {
    this.expanded = false;   // 换条目复位展开态，不残留上一条的展开状态
  }
}
```

### 第 4 步：引入池基建

两个类 + 一个注册表，可从参考工程整套复制（只改数据类名）：

- `ReusableNodeItem`（NodeController）：持有 BuilderNode 与当前数据。
  首次 `makeNode` 创建并 build；复用 `makeNode` 走 `update(newData)`；
  回收态 `makeNode` 返回 null（配合 rebuild 实现主动下树，见 6.3）。
- `ReusableNodeTypePool`：每类节点一个池。`acquire` 只取已卸载
  （`getFrameNode().getParent()` 为空）的节点；`recycle` 先下树、
  按上限决定入池或 dispose；`clear` 清空整池。
- 注册表：每类节点一行，上限常量集中定义：

```ts
/**
 * 池空闲上限：开发者指定 10。
 * 估算参考：卡片高约 240vp、列表可视区约 720vp → 每屏约 3 条，
 * 「至少两屏条目数」公式给出 6；当前取 10，为快滑突发留足余量。
 */
const MAX_FREE_PER_TYPE: number = 10;

export class NewsNodePools {
  static readonly avatar: ReusableNodeTypePool =
    new ReusableNodeTypePool(avatarNodeBuilder, 'avatar', MAX_FREE_PER_TYPE);
  static readonly like: ReusableNodeTypePool =
    new ReusableNodeTypePool(likeNodeBuilder, 'like', MAX_FREE_PER_TYPE);
  // ……每类节点一个池

  static clearAll(): void { /* 逐池 clear，页面销毁时调用 */ }
}
```

### 第 5 步：改容器组件（条目/卡片）

**改造前**：

```ts
aboutToAppear(): void {
  this.likeNode = createLikeNode(this.item, (liked) => this.onLikeClick(liked));
  // ……7 个节点逐个 create
}

aboutToDisappear(): void {
  this.likeNode?.dispose();      // 销毁释放
  // ……
}

private onLikeClick(liked: boolean): void {
  this.item.isLiked = liked;
  this.item.likeCount += liked ? 1 : -1;
  this.likeNode?.update(makeLikeParams(this.item, (l) => this.onLikeClick(l)));  // 手动推参数
}
```

**改造后**：

```ts
private uiData: NewsNodeData = new NewsNodeData();

aboutToAppear(): void {
  // 一份数据（字段 + 本卡片回调），7 个节点共用
  this.uiData = makeNewsNodeData(this.item,
    () => this.onAvatarClick(),
    (followed: boolean) => this.onFollowClick(followed),
    (liked: boolean) => this.onLikeClick(liked),
    () => this.onCommentClick(),
    (favorited: boolean) => this.onFavoriteClick(favorited),
    () => this.onShareClick());
  this.likeNode = NewsNodePools.like.acquire(this.uiData);   // 池取
  // ……7 个节点逐个 acquire
}

aboutToDisappear(): void {
  if (this.likeNode !== null) {
    NewsNodePools.like.recycle(this.likeNode);   // 先下树再入池，不 dispose
  }
  // ……7 个节点逐个 recycle（判空）
}

private onLikeClick(liked: boolean): void {
  this.item.isLiked = liked;                 // 数据模型（面板等仍读它）
  this.item.likeCount += liked ? 1 : -1;
  this.uiData.isLiked = liked;               // 改属性 → @Observed 自动刷新
  this.uiData.likeCount += liked ? 1 : -1;
}
```

注意：交互处理里**不要再调用 `node.update()`**——改 `uiData` 属性就够了。

### 第 6 步：页面退出清理

承载页面销毁时清空全部池，节点树不随页面残留：

```ts
// pages/Index.ets
aboutToDisappear(): void {
  NewsNodePools.clearAll();
}
```

---

## 5. 验证清单

改造完按这个清单过一遍（编译只能证明结构对，行为要真机看）：

- [ ] 编译零告警（`hvigorw assembleHap`）；
- [ ] 滚动/来回滚动：每条内容正确——序号、数值、人设组合与条目对得上
      （数据可辨认时直接肉眼校验，不符 = 节点没刷新）；
- [ ] 点赞/收藏/关注：图标与计数即时变化，且**作用在当前条目**；
- [ ] 有内部状态的节点（标题展开态）：展开后滚走再滚回，恢复初始态；
- [ ] 返回上级页面再进入：池从零开始（有日志时可见 clear 事件）；
- [ ] 若加了调试观测：命中随滚动增长、新建稳定后不涨、空闲在上限内波动。

---

## 6. 关键原理：五个「为什么」

理解这五条，改造中的每个设计决定就都有依据了。

### 6.1 为什么必须弃用 @Prop，换成 @ObjectLink + @Watch

`BuilderNode.update()` 只刷新**被装饰变量**（@Prop / @ObjectLink）。
回调函数放在普通属性上时，update 刷不到——复用节点挂到新条目后，
回调仍指向**旧条目**的闭包，点赞会改到上一条数据上。

统一数据类 + `@ObjectLink` 后，回调作为数据实例的字段随实例整体换绑；
且挂载中改属性即刷新（@Observed 第一层监听），交互处理退化为
「改两个对象的属性」，不再手动推参数。

### 6.2 为什么换数据用 update()，不用 BuilderNode.reuse()

`reuse()` / `recycle()` 是向内部自定义组件传递 `aboutToReuse` /
`aboutToRecycle` 事件的通道，服务于 @Reusable 组件复用机制——
**不是给节点池换数据用的**。池的换数据一律走 `update(newData)`：
`@ObjectLink` 重新指向新实例、`@Watch` 触发，语义干净且不依赖
内部组件实现 aboutToReuse。

### 6.3 为什么回收要先「下树」再入池

条目销毁时（aboutToDisappear）节点虽被归还池中，但它可能**还没从
节点树上卸载**（组件树销毁是异步流程）。此时 `acquire` 检查
`getParent()` 会发现它仍挂着——跳过、取不走。表现为：池里数字只涨
不落、复用不命中、内存膨胀。

解法是回收时**主动卸载**：置回收标记后调用 NodeController 的
`rebuild()`，NodeContainer 会重新回调 `makeNode`，对回收态返回 `null`，
组件树当场从容器卸下，之后入池的节点都立即可复用。

### 6.4 为什么池要上限和清理

复用版比不复用版**多占内存**（空闲组件树驻留），不清理就是倒退。
三条清理路径缺一不可：
- 回收时池内空闲已达上限 → 直接 `dispose`（不入池）；
- 入池后超限 → 防御性 dispose 多余节点；
- 承载页面销毁 → `clearAll()` 清空全部池。

上限不是拍脑袋：**至少两屏条目数**（快滑时一批条目先建后毁或先毁后建，
池要缓冲这个突发；池太小会频繁「销毁又重建」，复用率反而下降）。

### 6.5 「创建时做一次」和「数据更新」要分开

与具体数据无关、只需做一次的工作——无限循环动画启动（唱片旋转、
音波均衡器）、监听器注册、资源预取——放在 `aboutToAppear` /
`onAppear`，**不要放进 @Watch**。复用模式下组件实例跨条目保留，
这类准备天然只执行一次（这正是复用收益的一部分）；误放进 @Watch
会导致每次换数据都重复执行（动画重启/叠加、监听器越挂越多）。

判断口径：这段逻辑依赖新数据的值吗？不依赖 → 一次性准备（创建时）；
依赖 → 才放进更新路径（@Watch / 属性）。

---

## 7. 常见坑速查

| 症状 | 原因 | 解法 |
| --- | --- | --- |
| 换条目后点赞改了别的条目 | 回调在普通属性上，update 刷不到 | 统一数据类 + @ObjectLink（6.1） |
| 每次换数据动画重启、监听器重复注册 | 一次性准备放进了 @Watch | 移到 aboutToAppear（6.5） |
| 池空闲数只涨不落、复用不命中 | 回收的节点还没下树 | rebuild → makeNode 返回 null（6.3） |
| 空闲数远超预期 | 快滑突发未命中滞留 | 核对上限估算，必要时调大（6.4） |
| 拿不准要不要用 reuse() 换数据 | 误解其用途 | 一律 update()（6.2） |
| `import { wrapBuilder }` 编译失败 | 它是全局声明 | 删掉 import |
| dispose 后组件树悬空 | 对挂载中的节点 dispose | 只 dispose 池内/已下树节点 |

---

## 8. 参考实现

- **改造后关键代码**：本技能目录 `references/sample-code/`（7 个工程文件
  原样副本，含阅读顺序索引）；
- **完整示例工程与改造前后 git 对照**：所在仓库的 `sample/` 目录——首提交
  为不复用形态，第二个提交为复用改造，
  `git diff HEAD~2 HEAD~1 -- sample/BuilderNodeReuseTest` 即全部改造内容；
- 双版本并列对照（同一推荐流的「不复用版」与「复用版」并存，含结构对比
  文档与对比图）：所在仓库 `sample/BuilderNodeReuse/`（抖音式推荐流，
  Swiper 单列瀑布流形态；其 `docs/复用与不复用版本结构对比.md` 含对比图）。
