# 模式代码四件套

以下代码提炼自一次真实改造（已编译验证），命名做了通用化：`NodeData` 对应
`sample-code/NewsNodeData.ets` 中的 `NewsNodeData`，`NodePools` 对应
`sample-code/NewsNodePools.ets`。落地时按业务域重命名即可，结构与 API
保持一致；工程实照见同目录 `sample-code/`（含阅读顺序索引）。

## 1. 统一数据类（@Observed）

一个滚动条目（卡片）内全部 BuilderNode 节点共用**一份**数据实例。
字段必须打平为第一层属性（@Observed 只监听第一层赋值）；
回调也放进来，随实例换绑。

```ts
// model/NodeData.ets
import { BusinessItem } from './BusinessModels'; // 条目数据模型（你原有的模型）

@Observed
export class NodeData {
  // —— 展示数据：按你的节点需要打平 ——
  avatarIndex: number = 0;
  title: string = '';
  subtitle: string = '';
  isLiked: boolean = false;
  likeCount: number = 0;
  // ...其余节点用到的字段

  // —— 交互回调：由持有该数据的容器组件提供 ——
  onAvatarClick: () => void = () => {};
  onToggleLike: (liked: boolean) => void = () => {};
  onOpenPanel: () => void = () => {};
}

/** 条目出现时构建一份数据实例（数据字段 + 容器回调） */
export function makeNodeData(item: BusinessItem,
  onAvatarClick: () => void,
  onToggleLike: (liked: boolean) => void,
  onOpenPanel: () => void): NodeData {
  const data = new NodeData();
  data.avatarIndex = item.avatarIndex;
  data.title = item.title;
  data.subtitle = item.subtitle;
  data.isLiked = item.isLiked;
  data.likeCount = item.likeCount;
  data.onAvatarClick = onAvatarClick;
  data.onToggleLike = onToggleLike;
  data.onOpenPanel = onOpenPanel;
  return data;
}
```

## 2. 节点组件（@ObjectLink + @Watch）

替换原来的 @Prop 字段与普通回调属性；数据与回调一律经 `this.data.xxx` 读取。

```ts
// feednodes/LikeButtonNode.ets
import { ParamNodeController } from '../nodecore/ParamNodeController';
import { NodeData } from '../model/NodeData';

@Component
struct LikeButtonView {
  @ObjectLink @Watch('onDataUpdated') data: NodeData;

  // 换条目重挂载（update 传入新数据实例）时触发；用于复位内部状态
  onDataUpdated(propName: string): void {
    // 本节点无内部状态则留空；有（如展开态）则在此复位
  }

  build() {
    Column({ space: 5 }) {
      // 图标/文案全部读 this.data
      Text(`${this.data.likeCount}`)
        .fontSize(13)
        .fontColor(Color.White)
    }
    .alignItems(HorizontalAlign.Center)
    .onClick(() => {
      this.data.onToggleLike(!this.data.isLiked); // 回调随实例换绑
    })
  }
}

@Builder
function buildLikeButton(data: NodeData) {
  LikeButtonView({ data: data })
}

// 构建器导出给「普通创建」与「复用池」共用；wrapBuilder 是全局函数，不要 import
export const likeButtonNodeBuilder: WrappedBuilder<[NodeData]> =
  wrapBuilder<[NodeData]>(buildLikeButton);

/** 不复用版的创建入口（若做并行双版本则保留） */
export function createLikeButtonNode(data: NodeData): ParamNodeController {
  return new ParamNodeController(likeButtonNodeBuilder, data);
}
```

注意：不读任何数据的节点（纯装饰性，如旋转唱片）可以不加 @ObjectLink，
普通属性接收数据类即可。

### 带一次性准备的节点（两类落点）

与具体数据无关、实例级只需做一次的工作，放生命周期钩子，**不要放进
@Watch/更新路径**。复用模式下组件实例跨条目保留，这类准备天然只执行一次
（这正是复用收益的一部分）；若放进 @Watch，每次换数据都会重复执行
（重复注册、动画重启/叠加、监听器越挂越多）。落点按工作性质分两类。

**逻辑类 → `aboutToAppear`（创建时）**：订阅/注册/耗时初始化。
订阅随实例走：换数据不重订，实例销毁（复用模式下即 dispose，归还池不
触发）才退订。订阅类示例（同一作者出现在多条目时，任一条目关注/取关，
其余条目同步按钮状态）：

```ts
@Component
struct AuthorAvatarView {
  @ObjectLink @Watch('onDataUpdated') data: NodeData;

  /** 实例级订阅回调：事件到达时改 @Observed 数据属性，自动刷新 */
  private readonly onFollowChanged: (authorName: string, followed: boolean) => void =
    (authorName: string, followed: boolean) => {
      if (this.data.authorName === authorName) {
        this.data.isFollowed = followed;   // @Observed 属性变更自动刷新
      }
    };

  aboutToAppear(): void {
    // 一次性准备（逻辑类，创建时）：订阅一次，换数据不重订
    FollowBus.subscribe(this.onFollowChanged);
  }

  aboutToDisappear(): void {
    // 实例销毁时退订（复用模式下归还池不触发，dispose 时触发）
    FollowBus.unsubscribe(this.onFollowChanged);
  }

  // 换条目更新数据时触发：订阅随实例走，无需处理
  onDataUpdated(propName: string): void {
  }

  build() { /* 头像 + 关注按钮，读 this.data */ }
}
```

（FollowBus 为任意事件总线/服务注册表的替身，按业务替换。）

**显示类 → `onAppear`（首次显示时）**：动画启动等渲染相关工作。
复用模式下动画随实例持续运行，节点重挂载会再次触发 onAppear，须加启动
守卫防止重复启动（重复 animateTo 会打断运行中的无限动画，导致速度异常）。
示例（音波均衡器，三根音波条时长错开、无限往复）：

```ts
@Component
struct MusicInfoView {
  @ObjectLink @Watch('onDataUpdated') data: NodeData;
  /** 音波条高度：由显示时启动的无限动画驱动，与具体数据无关 */
  @State barHeight1: number = 5;
  @State barHeight2: number = 10;
  /** 启动守卫：动画随实例持续运行，重挂载触发的 onAppear 不得重复启动 */
  private equalizerStarted: boolean = false;

  // 数据更新路径：均衡器动画与「音乐是哪首」无关，无需任何重复准备
  onDataUpdated(propName: string): void {
  }

  /** 启动均衡动画（三根音波条时长错开、无限往复），只允许调用一次 */
  private startEqualizer(): void {
    this.getUIContext().animateTo({
      duration: 520,
      iterations: -1,
      curve: Curve.EaseInOut,
      playMode: PlayMode.Reverse,
    }, () => {
      this.barHeight1 = 12;
    });
    // ...其余音波条同理，目标固定、时长错开
  }

  build() {
    Row({ space: 6 }) {
      Row({ space: 2 }) {
        Column().width(2).height(this.barHeight1).backgroundColor('#E6FFFFFF')
        Column().width(2).height(this.barHeight2).backgroundColor('#E6FFFFFF')
      }.alignItems(VerticalAlign.Bottom)
      .onAppear(() => {
        if (this.equalizerStarted) {
          return;   // 守卫：重挂载不重复启动，避免打断运行中的动画
        }
        this.equalizerStarted = true;
        this.startEqualizer();
      })
      Text(`音乐：${this.data.musicName}`)   // 数据驱动的部分照常读 this.data
        .fontSize(14).fontColor(Color.White)
    }
  }
}
```

判断口径：这段逻辑依赖新数据的值吗？
不依赖 → 一次性准备（逻辑类 `aboutToAppear` / 显示类 `onAppear`）；
依赖 → 才放进 `@Watch`（数据响应）。

## 3. 池基建（可直接复用）

```ts
// nodecore/ReusableNodePool.ets
import { BuilderNode, FrameNode, NodeController, UIContext } from '@kit.ArkUI';
import { LinkedList } from '@kit.ArkTS';
import { NodeData } from '../model/NodeData';

/**
 * 可复用节点项：BuilderNode 只创建一次。
 * - 首次 makeNode：创建 BuilderNode 并 build；
 * - 复用 makeNode：BuilderNode.update(newData)，组件树保留，
 *   @ObjectLink 重指向新数据并触发 @Watch；
 * - 回收态 makeNode：返回 null（配合 rebuild() 实现主动下树）。
 * 不要用 BuilderNode.reuse()/recycle()——那是 @Reusable 的事件传递通道。
 */
export class ReusableNodeItem extends NodeController {
  private readonly wrappedBuilder: WrappedBuilder<[NodeData]>;
  private currentData: NodeData;
  private builderNode: BuilderNode<[NodeData]> | null = null;
  private recycled: boolean = false;

  constructor(wrappedBuilder: WrappedBuilder<[NodeData]>, data: NodeData) {
    super();
    this.wrappedBuilder = wrappedBuilder;
    this.currentData = data;
  }

  makeNode(context: UIContext): FrameNode | null {
    if (this.recycled) {
      return null; // 回收态：让 NodeContainer 卸下组件树
    }
    if (this.builderNode === null) {
      this.builderNode = new BuilderNode<[NodeData]>(context);
      try {
        this.builderNode.build(this.wrappedBuilder, this.currentData);
      } catch (err) {
        console.error(`build node failed: ${JSON.stringify(err)}`);
      }
    } else {
      try {
        this.builderNode.update(this.currentData); // 复用换数据
      } catch (err) {
        console.error(`update node failed: ${JSON.stringify(err)}`);
      }
    }
    return this.builderNode.getFrameNode();
  }

  /** 池取出后、挂载前设置新数据 */
  prepare(data: NodeData): void {
    this.currentData = data;
    this.recycled = false;
  }

  /** 是否仍挂在节点树上（只有已卸载的节点才能被复用） */
  isAttached(): boolean {
    const parent: FrameNode | null | undefined = this.builderNode?.getFrameNode()?.getParent();
    return parent !== null && parent !== undefined;
  }

  /** 回收：主动 rebuild 触发 makeNode 返回 null，先把旧组件树卸下 */
  takeDown(): void {
    this.recycled = true;
    try {
      this.rebuild();
    } catch (err) {
      // NodeContainer 可能已随容器销毁，此时由容器销毁完成下树
      console.info(`rebuild on recycle skipped: ${JSON.stringify(err)}`);
    }
  }

  /** 直接销毁：与后端实体节点解绑释放，不再入池 */
  dispose(): void {
    this.recycled = true;
    try {
      this.builderNode?.dispose();
    } catch (err) {
      console.error(`dispose node failed: ${JSON.stringify(err)}`);
    }
    this.builderNode = null;
  }
}

/** 单一节点类型的复用池 */
export class ReusableNodeTypePool {
  private readonly wrappedBuilder: WrappedBuilder<[NodeData]>;
  private readonly poolName: string;
  /**
   * 空闲上限（按业务估算，至少两屏条目数）：达到即销毁，不再入池。
   * 池太小会在快滑的创建/销毁突发下频繁「销毁又重建」，复用率下降；
   * 池太大则空闲组件树长期驻留内存。
   */
  private readonly maxFreeCount: number;
  private readonly freeItems: LinkedList<ReusableNodeItem> = new LinkedList();
  // —— 以下为调试观测（计数与事件日志），默认不加：见本节末尾说明 ——
  private reuseHitCount: number = 0;
  private createNewCount: number = 0;

  // 兜底默认 2 仅为「一屏 1 条」容器的下限，务必按业务显式传入估算值
  constructor(wrappedBuilder: WrappedBuilder<[NodeData]>, poolName: string = 'node',
    maxFreeCount: number = 2) {
    this.wrappedBuilder = wrappedBuilder;
    this.poolName = poolName;
    this.maxFreeCount = maxFreeCount > 0 ? maxFreeCount : 2;
  }

  /** 取节点：优先复用已卸载的，没有才新建 */
  acquire(data: NodeData): ReusableNodeItem {
    try {
      for (let i = 0; i < this.freeItems.length; i++) {
        const item = this.freeItems.get(i);
        if (item !== undefined && !item.isAttached()) {
          this.freeItems.removeByIndex(i);
          item.prepare(data);
          this.reuseHitCount++;
          console.info(`[NodePool:${this.poolName}] hit, free=${this.freeItems.length}`);
          return item;
        }
      }
    } catch (err) {
      console.error(`acquire node failed: ${JSON.stringify(err)}`);
    }
    this.createNewCount++;
    console.info(`[NodePool:${this.poolName}] new, free=${this.freeItems.length}`);
    return new ReusableNodeItem(this.wrappedBuilder, data);
  }

  /** 归还：先下树，池满直接销毁，池空入池（超限防御性销毁） */
  recycle(item: ReusableNodeItem): void {
    item.takeDown();
    try {
      if (this.freeItems.length >= this.maxFreeCount) {
        item.dispose();
        console.info(`[NodePool:${this.poolName}] dispose-on-recycle, free=${this.freeItems.length}`);
        return;
      }
      this.freeItems.add(item);
      while (this.freeItems.length > this.maxFreeCount) {
        const overflow = this.freeItems.get(0);
        if (overflow === undefined) {
          break;
        }
        this.freeItems.removeByIndex(0);
        overflow.dispose();
      }
      console.info(`[NodePool:${this.poolName}] recycle, free=${this.freeItems.length}`);
    } catch (err) {
      console.error(`recycle node failed: ${JSON.stringify(err)}`);
    }
  }

  /** 清空池：销毁全部空闲节点（页面销毁时调用） */
  clear(): void {
    let disposedCount = 0;
    try {
      while (this.freeItems.length > 0) {
        const item = this.freeItems.get(0);
        if (item === undefined) {
          break;
        }
        this.freeItems.removeByIndex(0);
        item.dispose();
        disposedCount++;
      }
      if (disposedCount > 0) {
        console.info(`[NodePool:${this.poolName}] clear, disposed=${disposedCount}`);
      }
    } catch (err) {
      console.error(`clear pool failed: ${JSON.stringify(err)}`);
    }
  }

  size(): number {
    return this.freeItems.length;
  }

  getReuseHitCount(): number {
    return this.reuseHitCount;
  }

  getCreateNewCount(): number {
    return this.createNewCount;
  }
}
```

池注册表（每类节点一行）：

```ts
// nodecore/NodePools.ets
import { ReusableNodeTypePool } from './ReusableNodePool';
import { likeButtonNodeBuilder } from '../feednodes/LikeButtonNode';
// ...其余节点构建器

/**
 * 池空闲上限：取值需与开发者确认（AI 估算 or 开发者指定）。
 * 估算口径（至少两屏条目数）：一屏条目数 = 屏高 / 条目高。
 * 垂直 Swiper 单列 = 1 条 → 上限 2；List/Grid 一屏约 N 条 → 上限 2N
 * （N 向上取整），快滑多的场景再加余量。
 */
const MAX_FREE_PER_TYPE: number = 2; // 本例：开发者认可 AI 估算（Swiper 单列，两屏 = 2）

export class NodePools {
  static readonly like: ReusableNodeTypePool =
    new ReusableNodeTypePool(likeButtonNodeBuilder, 'like', MAX_FREE_PER_TYPE);
  // static readonly avatar: ... 每类节点一个池，同样传入 MAX_FREE_PER_TYPE

  /** 离开承载页面时清空全部池 */
  static clearAll(): void {
    NodePools.like.clear();
    // ...
  }

  // 调试观测（默认不加）：totalFreeCount / totalReuseHitCount /
  // totalCreateNewCount 汇总统计，供页面内「命中/新建/空闲」指示条使用
}
```

**调试观测的去留**：上面池代码中的 `reuseHitCount/createNewCount` 计数、
`acquire/recycle/clear` 里的 `console.info` 事件日志、注册表的汇总统计，以及
页面内的「命中 X · 新建 Y · 空闲 Z」指示条，都是**调试设施**——仅当开发者在
改造前明确要求时才保留（对比演示、排查复用率）；生产改造默认整体删除，
不影响任何复用逻辑。`sample-code/` 中的示例为演示目的保留了全套。

## 4. 容器组件接线（卡片/条目）

```ts
// views/ReuseItemCard.ets（复用版容器；并行双版本时复制原容器后只改节点供给）
import { NodeData, makeNodeData } from '../model/NodeData';
import { ReusableNodeItem } from '../nodecore/ReusableNodePool';
import { NodePools } from '../nodecore/NodePools';

@Component
export struct ReuseItemCard {
  @ObjectLink item: BusinessItem;
  /** 统一数据：本条目全部节点共用一份 */
  private uiData: NodeData = new NodeData();
  private likeNode: ReusableNodeItem | null = null;
  // ...其余节点字段

  aboutToAppear(): void {
    // 一份数据 + 全部回调，交给所有节点
    this.uiData = makeNodeData(this.item,
      () => this.onAvatarClick(),
      (liked: boolean) => this.onLikeClick(liked),
      () => this.onOpenPanel());
    this.likeNode = NodePools.like.acquire(this.uiData);
    // ...其余 acquire
  }

  aboutToDisappear(): void {
    // 归还池（内部先下树、按限额决定入池或销毁），不 dispose
    if (this.likeNode !== null) {
      NodePools.like.recycle(this.likeNode);
    }
    // ...其余 recycle
  }

  /** 交互：改模型（供面板等消费）+ 改 uiData 属性（@Observed 自动刷新节点）。
      不要再调用 node.update()。 */
  private onLikeClick(liked: boolean): void {
    this.item.isLiked = liked;
    this.item.likeCount += liked ? 1 : -1;
    this.uiData.isLiked = liked;
    this.uiData.likeCount += liked ? 1 : -1;
  }
  // ...其余回调
}
```

承载页面退出时整池清理：

```ts
// pages/ReusePage.ets
aboutToDisappear(): void {
  // 离开页面清空全部池，销毁空闲节点释放内存
  NodePools.clearAll();
}
```

## 不复用版基座（并行双版本时保留/对照）

```ts
// nodecore/ParamNodeController.ets —— 每次挂载新建、销毁 dispose 的原始形态
export class ParamNodeController extends NodeController {
  private builderNode: BuilderNode<[NodeData]> | null = null;
  private readonly wrappedBuilder: WrappedBuilder<[NodeData]>;
  private currentData: NodeData;

  constructor(wrappedBuilder: WrappedBuilder<[NodeData]>, data: NodeData) {
    super();
    this.wrappedBuilder = wrappedBuilder;
    this.currentData = data;
  }

  makeNode(context: UIContext): FrameNode | null {
    this.builderNode = new BuilderNode<[NodeData]>(context);
    this.builderNode.build(this.wrappedBuilder, this.currentData);
    return this.builderNode.getFrameNode();
  }

  update(data: NodeData): void {
    this.currentData = data;
    if (this.builderNode !== null) {
      this.builderNode.update(data);
    }
  }

  dispose(): void {
    if (this.builderNode !== null) {
      this.builderNode.dispose();
      this.builderNode = null;
    }
  }
}
```
