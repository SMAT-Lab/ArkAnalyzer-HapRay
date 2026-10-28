/**
 * 节点项：点赞按钮（卡片底部操作栏）。
 * 复用形态：数据来自统一数据类 NewsNodeData（@Observed），经
 * @ObjectLink + @Watch 接入——属性变更自动刷新；换卡重挂载时
 * update() 传入新数据实例，@ObjectLink 重新指向并触发 @Watch，
 * 回调随之换绑到新卡片。节点由复用池创建并跨卡片复用。
 */
import { NewsNodeData } from '../model/NewsNodeData';
import { FormatUtil } from '../common/FormatUtil';

@Component
struct LikeView {
  @ObjectLink @Watch('onDataUpdated') data: NewsNodeData;

  // 换卡重挂载（update 传入新数据实例）时触发；本节点无内部状态，无需复位
  onDataUpdated(propName: string): void {
  }

  build() {
    Row({ space: 5 }) {
      Image(this.data.isLiked ? $r('app.media.ic_heart_filled_red') : $r('app.media.ic_heart_outline_white'))
        .width(22)
        .height(22)
      Text(FormatUtil.formatCount(this.data.likeCount))
        .fontSize(12)
        .fontColor(this.data.isLiked ? '#FE2C55' : '#B3FFFFFF')
        .maxLines(1)
    }
    .alignItems(VerticalAlign.Center)
    .onClick(() => {
      this.data.onLikeClick(!this.data.isLiked);
    })
  }
}

@Builder
function buildLike(data: NewsNodeData) {
  LikeView({ data: data })
}

/** 点赞节点构建器（复用池使用）；wrapBuilder 是全局函数，不要 import */
export const likeNodeBuilder: WrappedBuilder<[NewsNodeData]> =
  wrapBuilder<[NewsNodeData]>(buildLike);
