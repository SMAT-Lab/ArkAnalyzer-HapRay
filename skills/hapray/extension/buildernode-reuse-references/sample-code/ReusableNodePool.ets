/**
 * BuilderNode 复用基础设施。
 *
 * 与不复用形态（每次挂载 new BuilderNode + build、卸载即 dispose）相对：
 * - ReusableNodeItem：NodeController 的复用版包装，BuilderNode 只创建一次；
 *   再次挂载时通过 BuilderNode.update() 把新的统一数据实例（NewsNodeData）
 *   传入视图，@ObjectLink 重新指向新对象并触发 @Watch；
 *   回收时主动 rebuild() 触发 makeNode 返回 null，让 NodeContainer 先把
 *   旧组件树卸下（下树），保证归还池的节点立即可复用；
 * - ReusableNodeTypePool：按节点类型缓存节点项，卡片出现时 acquire
 *   （优先复用已卸载的），卡片销毁时 recycle（先下树再归还，不 dispose）。
 *
 * 注意：BuilderNode.reuse()/recycle() 接口用于向内部自定义组件传递
 * aboutToReuse/aboutToRecycle 事件（@Reusable 组件复用机制），不是给
 * 节点池换数据用的，此处换数据一律走 update()。
 */
import { BuilderNode, FrameNode, NodeController, UIContext } from '@kit.ArkUI';
import { LinkedList } from '@kit.ArkTS';
import { NewsNodeData } from '../model/NewsNodeData';

/**
 * 可复用节点项。数据统一为 NewsNodeData（@Observed），与节点构建器
 * （WrappedBuilder<[NewsNodeData]>）一一配套。
 * 生命周期：
 * 1. 首次 makeNode：创建 BuilderNode 并按数据构建组件树；
 * 2. 从池中取出再次挂载：组件树保留，BuilderNode.update(newData) 把新数据
 *    实例传入视图，@ObjectLink 重新指向新对象并触发 @Watch；
 * 3. 挂载期间数据属性变化：@Observed 直接驱动视图刷新，无需本类参与；
 * 4. 回收：置回收态并主动 rebuild()，makeNode 返回 null，NodeContainer 卸下组件树。
 */
export class ReusableNodeItem extends NodeController {
  private readonly wrappedBuilder: WrappedBuilder<[NewsNodeData]>;
  /** 当前数据实例：换卡时替换为新实例，挂载时经 update() 传入视图（@ObjectLink + @Watch） */
  private currentData: NewsNodeData;
  private builderNode: BuilderNode<[NewsNodeData]> | null = null;
  /** 回收态：makeNode 返回 null，用于卸下组件树 */
  private recycled: boolean = false;

  constructor(wrappedBuilder: WrappedBuilder<[NewsNodeData]>, data: NewsNodeData) {
    super();
    this.wrappedBuilder = wrappedBuilder;
    this.currentData = data;
  }

  makeNode(context: UIContext): FrameNode | null {
    if (this.recycled) {
      // 回收态：返回 null 让绑定的 NodeContainer 卸下组件树（下树）
      return null;
    }
    if (this.builderNode === null) {
      // 首次使用：创建并构建组件树
      this.builderNode = new BuilderNode<[NewsNodeData]>(context);
      try {
        this.builderNode.build(this.wrappedBuilder, this.currentData);
      } catch (err) {
        console.error(`build node failed: ${JSON.stringify(err)}`);
      }
    } else {
      // 复用挂载：组件树保留，用 update 把新数据实例传入视图（@ObjectLink + @Watch）
      try {
        this.builderNode.update(this.currentData);
      } catch (err) {
        console.error(`update node failed: ${JSON.stringify(err)}`);
      }
    }
    return this.builderNode.getFrameNode();
  }

  /** 从池中取出、尚未挂载时设置新一轮数据（挂载时经 update() 传入视图） */
  prepare(data: NewsNodeData): void {
    this.currentData = data;
    this.recycled = false;
  }

  /** 是否仍挂在节点树上（只有已卸载的节点才能被复用） */
  isAttached(): boolean {
    const parent: FrameNode | null | undefined = this.builderNode?.getFrameNode()?.getParent();
    return parent !== null && parent !== undefined;
  }

  /**
   * 回收：置回收态并主动 rebuild()，触发绑定的 NodeContainer 重新回调
   * makeNode（返回 null），先把旧组件树卸下，再归还池中等待复用。
   * 不先下树的话，「已回收但还挂在树上」的节点会被 acquire 的
   * isAttached() 判定跳过、取不走，池失效并持续膨胀。
   */
  takeDown(): void {
    this.recycled = true;
    try {
      this.rebuild();
    } catch (err) {
      // NodeContainer 可能已随卡片销毁，rebuild 无效时由容器销毁完成下树
      console.info(`rebuild on recycle skipped: ${JSON.stringify(err)}`);
    }
  }

  /**
   * 直接销毁：与后端实体节点解绑并释放，不再进入复用池。
   * 用于池已满时的回收、池超限清理与整池清理。
   */
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

/**
 * 池空闲上限的兜底默认值。
 * 上限应按业务估算：至少保留「两屏条目数」的空闲节点——
 * 一屏条目数 = 屏高 / 条目高，每类上限 ≥ 2 × 一屏条目数；
 * 快速连滑/长 fling 的场景再酌情加余量。
 * 此默认值 2 仅是「一屏 1 条」容器的下限，勿在未估算的情况下直接依赖。
 */
const DEFAULT_MAX_FREE_COUNT: number = 2;

/**
 * 单一节点类型的复用池。
 * 每种节点类型（头像、作者、标题、点赞……）各建一个池实例，持有该节点
 * 的 WrappedBuilder<[NewsNodeData]>；节点数据统一为 NewsNodeData。
 */
export class ReusableNodeTypePool {
  private readonly wrappedBuilder: WrappedBuilder<[NewsNodeData]>;
  private readonly poolName: string;
  /**
   * 池内空闲节点数上限（按业务估算或开发者指定，至少两屏条目数）：
   * 超过即销毁，不再入池。池太小会在快滑的创建/销毁突发下频繁
   * 「销毁又重建」，复用率下降；池太大则空闲组件树长期驻留内存。
   */
  private readonly maxFreeCount: number;
  private readonly freeItems: LinkedList<ReusableNodeItem> = new LinkedList();
  /** 统计：从池中复用的次数（调试观测） */
  private reuseHitCount: number = 0;
  /** 统计：池空新建的次数（调试观测） */
  private createNewCount: number = 0;

  constructor(wrappedBuilder: WrappedBuilder<[NewsNodeData]>, poolName: string = 'node',
    maxFreeCount: number = DEFAULT_MAX_FREE_COUNT) {
    this.wrappedBuilder = wrappedBuilder;
    this.poolName = poolName;
    this.maxFreeCount = maxFreeCount > 0 ? maxFreeCount : DEFAULT_MAX_FREE_COUNT;
  }

  /**
   * 取一个可用节点：优先复用池中已卸载的节点项，没有可复用的才新建。
   */
  acquire(data: NewsNodeData): ReusableNodeItem {
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

  /**
   * 卡片销毁时归还节点：先主动下树（rebuild + makeNode 返回 null），再入池。
   * 池内空闲已达上限时本节点多余，直接销毁不入池；入池后若超出限额，
   * 防御性地销毁多余节点。
   */
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

  /** 清空池：销毁全部空闲节点（页面销毁时调用，释放内存） */
  clear(): void {
    let disposedCount: number = 0;
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

  /** 池中待复用的节点数（含极少数尚未完成卸载、暂不可用的） */
  size(): number {
    return this.freeItems.length;
  }

  /** 累计复用命中次数（调试观测） */
  getReuseHitCount(): number {
    return this.reuseHitCount;
  }

  /** 累计新建次数（调试观测） */
  getCreateNewCount(): number {
    return this.createNewCount;
  }
}
