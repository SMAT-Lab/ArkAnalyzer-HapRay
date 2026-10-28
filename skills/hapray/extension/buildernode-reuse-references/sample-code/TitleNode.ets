/**
 * 节点项：资讯标题（长标题默认两行折叠，可展开/收起）。
 * 复用形态：数据来自统一数据类 NewsNodeData（@Observed），经
 * @ObjectLink + @Watch 接入；换卡重挂载时 update() 传入新数据实例，
 * @Watch 中复位展开态——新卡片从折叠开始，不残留上一张卡的展开状态。
 */
import { NewsNodeData } from '../model/NewsNodeData';

const FOLD_THRESHOLD: number = 30;
const COLLAPSED_MAX_LINES: number = 2;

@Component
struct TitleView {
  @ObjectLink @Watch('onDataUpdated') data: NewsNodeData;
  @State expanded: boolean = false;

  // 换卡重挂载（update 传入新数据实例）时触发：复位标题展开态
  onDataUpdated(propName: string): void {
    this.expanded = false;
  }

  private isLongTitle(): boolean {
    return this.data.title.length > FOLD_THRESHOLD;
  }

  build() {
    Column({ space: 4 }) {
      Text(this.data.title)
        .fontSize(16)
        .fontWeight(FontWeight.Medium)
        .fontColor(Color.White)
        .lineHeight(23)
        .maxLines(this.expanded ? 20 : COLLAPSED_MAX_LINES)
        .textOverflow({ overflow: TextOverflow.Ellipsis })

      if (this.isLongTitle()) {
        Text(this.expanded ? '收起' : '展开')
          .fontSize(12)
          .fontColor('#7FB3FF')
          .onClick(() => {
            this.expanded = !this.expanded;
          })
      }
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }
}

@Builder
function buildTitle(data: NewsNodeData) {
  TitleView({ data: data })
}

/** 标题节点构建器（复用池使用）；wrapBuilder 是全局函数，不要 import */
export const titleNodeBuilder: WrappedBuilder<[NewsNodeData]> =
  wrapBuilder<[NewsNodeData]>(buildTitle);
