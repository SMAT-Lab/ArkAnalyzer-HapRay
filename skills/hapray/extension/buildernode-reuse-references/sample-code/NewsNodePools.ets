/**
 * 资讯卡片节点的复用池注册表。
 * 每类节点一个池实例（全局静态，跨卡片共享），节点数据统一为
 * NewsNodeData，池内持有各节点的 WrappedBuilder。
 */
import { ReusableNodeTypePool } from './ReusableNodePool';
import { avatarNodeBuilder } from '../nodes/AvatarNode';
import { authorNodeBuilder } from '../nodes/AuthorNode';
import { titleNodeBuilder } from '../nodes/TitleNode';
import { likeNodeBuilder } from '../nodes/LikeNode';
import { commentNodeBuilder } from '../nodes/CommentNode';
import { favoriteNodeBuilder } from '../nodes/FavoriteNode';
import { shareNodeBuilder } from '../nodes/ShareNode';

/**
 * 池空闲上限（每类节点）：开发者指定 10。
 * 估算参考：卡片高约 240vp、列表可视区约 720vp → 每屏约 3 条，
 * 「至少两屏条目数」公式给出 6；当前取 10，为快滑突发留足余量。
 * 要调整只改这一个常量即可。
 */
const MAX_FREE_PER_TYPE: number = 10;

export class NewsNodePools {
  /** 作者头像 */
  static readonly avatar: ReusableNodeTypePool =
    new ReusableNodeTypePool(avatarNodeBuilder, 'avatar', MAX_FREE_PER_TYPE);
  /** 作者名 + 关注 */
  static readonly author: ReusableNodeTypePool =
    new ReusableNodeTypePool(authorNodeBuilder, 'author', MAX_FREE_PER_TYPE);
  /** 标题（折叠展开） */
  static readonly title: ReusableNodeTypePool =
    new ReusableNodeTypePool(titleNodeBuilder, 'title', MAX_FREE_PER_TYPE);
  /** 点赞 */
  static readonly like: ReusableNodeTypePool =
    new ReusableNodeTypePool(likeNodeBuilder, 'like', MAX_FREE_PER_TYPE);
  /** 评论 */
  static readonly comment: ReusableNodeTypePool =
    new ReusableNodeTypePool(commentNodeBuilder, 'comment', MAX_FREE_PER_TYPE);
  /** 收藏 */
  static readonly favorite: ReusableNodeTypePool =
    new ReusableNodeTypePool(favoriteNodeBuilder, 'favorite', MAX_FREE_PER_TYPE);
  /** 转发 */
  static readonly share: ReusableNodeTypePool =
    new ReusableNodeTypePool(shareNodeBuilder, 'share', MAX_FREE_PER_TYPE);

  /** 清空全部节点池：销毁所有空闲节点（离开页面时调用，释放内存） */
  static clearAll(): void {
    NewsNodePools.avatar.clear();
    NewsNodePools.author.clear();
    NewsNodePools.title.clear();
    NewsNodePools.like.clear();
    NewsNodePools.comment.clear();
    NewsNodePools.favorite.clear();
    NewsNodePools.share.clear();
  }

  /** 池中待复用节点总数（调试观测） */
  static totalFreeCount(): number {
    return NewsNodePools.avatar.size() + NewsNodePools.author.size() + NewsNodePools.title.size()
      + NewsNodePools.like.size() + NewsNodePools.comment.size() + NewsNodePools.favorite.size()
      + NewsNodePools.share.size();
  }

  /** 累计复用命中总数（所有节点类型，调试观测） */
  static totalReuseHitCount(): number {
    return NewsNodePools.avatar.getReuseHitCount() + NewsNodePools.author.getReuseHitCount()
      + NewsNodePools.title.getReuseHitCount() + NewsNodePools.like.getReuseHitCount()
      + NewsNodePools.comment.getReuseHitCount() + NewsNodePools.favorite.getReuseHitCount()
      + NewsNodePools.share.getReuseHitCount();
  }

  /** 累计新建总数（所有节点类型，调试观测） */
  static totalCreateNewCount(): number {
    return NewsNodePools.avatar.getCreateNewCount() + NewsNodePools.author.getCreateNewCount()
      + NewsNodePools.title.getCreateNewCount() + NewsNodePools.like.getCreateNewCount()
      + NewsNodePools.comment.getCreateNewCount() + NewsNodePools.favorite.getCreateNewCount()
      + NewsNodePools.share.getCreateNewCount();
  }
}
