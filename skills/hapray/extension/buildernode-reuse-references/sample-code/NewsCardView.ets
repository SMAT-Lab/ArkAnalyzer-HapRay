/**
 * 资讯卡片：List 中的一条内容（BuilderNode 复用版）。
 *
 * 树形结构（与叠加层式瀑布流不同，采用常规卡片流布局）：
 * Column(卡片)
 * ├── Row(头部)：NodeContainer(头像节点) + Column{ NodeContainer(作者+关注节点), 发布时间 }
 * ├── NodeContainer(标题节点：长标题折叠展开)
 * ├── Text(正文摘要，普通组件，不经 BuilderNode)
 * ├── Divider
 * └── Row(操作栏，横向均分)：点赞/评论/收藏/转发 4 个 NodeContainer
 *
 * 复用形态：与不复用版的布局、交互完全一致，区别仅在节点供给方式——
 * - 出现时：构建一份统一数据实例（NewsNodeData）共用给 7 个节点，
 *   节点从 NewsNodePools 取（优先复用已卸载的，其次新建）；
 * - 销毁时：节点归还池中等待下一次复用，不 dispose；
 * - 挂载期间点赞/关注/收藏等数据变化：改 item 模型 + 改 uiData 属性，
 *   @Observed 自动刷新节点视图，不再调用 node.update()。
 */
import { NewsItem } from '../model/NewsModels';
import { NewsNodeData, makeNewsNodeData } from '../model/NewsNodeData';
import { ReusableNodeItem } from '../nodecore/ReusableNodePool';
import { NewsNodePools } from '../nodecore/NewsNodePools';
import { showToastSafely } from '../common/UiUtils';

@Component
export struct NewsCardView {
  @ObjectLink item: NewsItem;
  /** 统一数据（@Observed）：本卡片全部 7 个节点共用一份 */
  private uiData: NewsNodeData = new NewsNodeData();
  private avatarNode: ReusableNodeItem | null = null;
  private authorNode: ReusableNodeItem | null = null;
  private titleNode: ReusableNodeItem | null = null;
  private likeNode: ReusableNodeItem | null = null;
  private commentNode: ReusableNodeItem | null = null;
  private favoriteNode: ReusableNodeItem | null = null;
  private shareNode: ReusableNodeItem | null = null;

  aboutToAppear(): void {
    console.info(`[ReuseCard] appear ${this.item.id}`);
    // 构造统一数据（数据字段 + 本卡片交互回调），7 个节点共用同一份
    this.uiData = makeNewsNodeData(this.item,
      () => this.onAvatarClick(),
      (followed: boolean) => this.onFollowClick(followed),
      (liked: boolean) => this.onLikeClick(liked),
      () => this.onCommentClick(),
      (favorited: boolean) => this.onFavoriteClick(favorited),
      () => this.onShareClick());
    // 从复用池获取各节点（可复用时直接复用），重挂载时 update 传入新数据实例
    this.avatarNode = NewsNodePools.avatar.acquire(this.uiData);
    this.authorNode = NewsNodePools.author.acquire(this.uiData);
    this.titleNode = NewsNodePools.title.acquire(this.uiData);
    this.likeNode = NewsNodePools.like.acquire(this.uiData);
    this.commentNode = NewsNodePools.comment.acquire(this.uiData);
    this.favoriteNode = NewsNodePools.favorite.acquire(this.uiData);
    this.shareNode = NewsNodePools.share.acquire(this.uiData);
  }

  aboutToDisappear(): void {
    console.info(`[ReuseCard] disappear ${this.item.id}`);
    // 节点归还复用池（池内先下树，按限额入池或销毁），而不是直接 dispose
    if (this.avatarNode !== null) {
      NewsNodePools.avatar.recycle(this.avatarNode);
    }
    if (this.authorNode !== null) {
      NewsNodePools.author.recycle(this.authorNode);
    }
    if (this.titleNode !== null) {
      NewsNodePools.title.recycle(this.titleNode);
    }
    if (this.likeNode !== null) {
      NewsNodePools.like.recycle(this.likeNode);
    }
    if (this.commentNode !== null) {
      NewsNodePools.comment.recycle(this.commentNode);
    }
    if (this.favoriteNode !== null) {
      NewsNodePools.favorite.recycle(this.favoriteNode);
    }
    if (this.shareNode !== null) {
      NewsNodePools.share.recycle(this.shareNode);
    }
  }

  private onAvatarClick(): void {
    showToastSafely(this.getUIContext(), `进入 @${this.item.authorName} 的主页（演示）`, 220);
  }

  /** 关注/取关：改 item 模型 + 改 uiData 属性，@Observed 自动刷新作者节点 */
  private onFollowClick(followed: boolean): void {
    this.item.isFollowed = followed;
    this.uiData.isFollowed = followed;
  }

  /** 点赞/取消点赞：改 item 模型 + 改 uiData 属性，@Observed 自动刷新点赞节点 */
  private onLikeClick(liked: boolean): void {
    this.item.isLiked = liked;
    this.item.likeCount += liked ? 1 : -1;
    this.uiData.isLiked = liked;
    this.uiData.likeCount += liked ? 1 : -1;
  }

  private onCommentClick(): void {
    showToastSafely(this.getUIContext(), `打开评论区（演示），共 ${this.item.commentCount} 条评论`, 220);
  }

  /** 收藏/取消收藏：改 item 模型 + 改 uiData 属性，@Observed 自动刷新收藏节点 */
  private onFavoriteClick(favorited: boolean): void {
    this.item.isFavorited = favorited;
    this.item.favoriteCount += favorited ? 1 : -1;
    this.uiData.isFavorited = favorited;
    this.uiData.favoriteCount += favorited ? 1 : -1;
  }

  private onShareClick(): void {
    showToastSafely(this.getUIContext(), '打开转发菜单（演示）', 220);
  }

  build() {
    Column({ space: 10 }) {
      // 头部：头像节点 + (作者节点 + 时间)
      Row({ space: 10 }) {
        if (this.avatarNode) {
          NodeContainer(this.avatarNode)
            .width(40)
            .height(40)
        }

        Column({ space: 3 }) {
          if (this.authorNode) {
            NodeContainer(this.authorNode)
              .width('100%')
              .constraintSize({ minHeight: 22 })
          }
          Text(this.item.publishTime)
            .fontSize(11)
            .fontColor('#73FFFFFF')
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .alignItems(VerticalAlign.Center)

      // 标题节点（长标题折叠展开）
      if (this.titleNode) {
        NodeContainer(this.titleNode)
          .width('100%')
          .constraintSize({ minHeight: 46 })
      }

      // 正文摘要：普通组件（不经 BuilderNode）
      Text(this.item.content)
        .fontSize(14)
        .fontColor('#A6FFFFFF')
        .lineHeight(21)
        .maxLines(3)
        .textOverflow({ overflow: TextOverflow.Ellipsis })

      Divider()
        .color('#1FFFFFFF')
        .strokeWidth(1)

      // 操作栏：4 个节点横向均分
      Row() {
        if (this.likeNode) {
          NodeContainer(this.likeNode)
            .layoutWeight(1)
        }
        if (this.commentNode) {
          NodeContainer(this.commentNode)
            .layoutWeight(1)
        }
        if (this.favoriteNode) {
          NodeContainer(this.favoriteNode)
            .layoutWeight(1)
        }
        if (this.shareNode) {
          NodeContainer(this.shareNode)
            .layoutWeight(1)
        }
      }
      .width('100%')
      .alignItems(VerticalAlign.Center)
    }
    .width('100%')
    .padding(14)
    .borderRadius(12)
    .backgroundColor('#FF1C1C20')
    .alignItems(HorizontalAlign.Start)
  }
}
