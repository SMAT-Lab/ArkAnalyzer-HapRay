/**
 * 资讯卡片节点的统一数据类。
 *
 * 一张卡片的全部 BuilderNode 节点共用同一份实例：
 * - 字段全部打平为第一层属性（@Observed 只监听第一层赋值）；
 * - 交互回调也收进来、随实例换绑——复用换卡时 BuilderNode.update()
 *   传入新实例，节点内 @ObjectLink 重新指向并触发 @Watch，回调自然
 *   指向新卡片（若回调留在组件普通属性上，update 刷不到，会出现
 *   「点赞点到上一张卡」）；
 * - 挂载期间改属性：@Observed 直接驱动节点内视图刷新，无需再调 update。
 */
import { NewsItem } from './NewsModels';

@Observed
export class NewsNodeData {
  // —— 头像节点 ——
  avatarIndex: number = 0;
  // —— 作者节点 ——
  authorName: string = '';
  isFollowed: boolean = false;
  // —— 标题节点 ——
  title: string = '';
  // —— 点赞节点 ——
  isLiked: boolean = false;
  likeCount: number = 0;
  // —— 评论节点 ——
  commentCount: number = 0;
  // —— 收藏节点 ——
  isFavorited: boolean = false;
  favoriteCount: number = 0;
  // —— 转发节点 ——
  shareCount: number = 0;

  // —— 交互回调：由持有该数据的卡片容器（NewsCardView）提供 ——
  onAvatarClick: () => void = () => {
  };
  onFollowClick: (followed: boolean) => void = () => {
  };
  onLikeClick: (liked: boolean) => void = () => {
  };
  onCommentClick: () => void = () => {
  };
  onFavoriteClick: (favorited: boolean) => void = () => {
  };
  onShareClick: () => void = () => {
  };
}

/**
 * 卡片出现时构建一份数据实例（条目数据字段 + 卡片交互回调），
 * 交给该卡片全部 7 个节点共用。
 */
export function makeNewsNodeData(item: NewsItem,
  onAvatarClick: () => void,
  onFollowClick: (followed: boolean) => void,
  onLikeClick: (liked: boolean) => void,
  onCommentClick: () => void,
  onFavoriteClick: (favorited: boolean) => void,
  onShareClick: () => void): NewsNodeData {
  const data = new NewsNodeData();
  data.avatarIndex = item.avatarIndex;
  data.authorName = item.authorName;
  data.isFollowed = item.isFollowed;
  data.title = item.title;
  data.isLiked = item.isLiked;
  data.likeCount = item.likeCount;
  data.commentCount = item.commentCount;
  data.isFavorited = item.isFavorited;
  data.favoriteCount = item.favoriteCount;
  data.shareCount = item.shareCount;
  data.onAvatarClick = onAvatarClick;
  data.onFollowClick = onFollowClick;
  data.onLikeClick = onLikeClick;
  data.onCommentClick = onCommentClick;
  data.onFavoriteClick = onFavoriteClick;
  data.onShareClick = onShareClick;
  return data;
}
