/**
 * 资讯流主页面（BuilderNode 复用版）。
 *
 * 结构：标题栏 + List（LazyForEach 懒加载）——滚动时 List 持续创建/销毁
 * 条目组件，每个条目（NewsCardView）携带 7 个 NodeContainer 节点。
 * 复用形态下节点来自 NewsNodePools 复用池：条目销毁时节点归还池中，
 * 条目再次出现时直接复用（BuilderNode.update 换数据），滚动中不再
 * 反复 new BuilderNode + build。滚动到底部自动加载下一批。
 *
 * 顶部常驻池统计指示条（调试观测设施，验收后可整体移除）：
 * - 命中：从池中取走已回收节点完成复用的累计次数（每次滚动过一张卡 +7）；
 * - 新建：池空时新建节点的累计次数（首屏约 4 张卡 × 7 = 28，稳定后应基本不再涨）；
 * - 空闲：池中等待复用的节点数，稳态小幅波动，快滑突发时可逼近上限 70
 *   （每类上限 10 × 7 类）；持续增大并逼近/超过上限说明复用未命中。
 */
import { NewsItem } from '../model/NewsModels';
import { NewsDataSource } from '../datasource/NewsDataSource';
import { NewsCardView } from '../views/NewsCardView';
import { NewsNodePools } from '../nodecore/NewsNodePools';

/** 首屏加载的条数 */
const INITIAL_COUNT: number = 15;
/** 统计刷新延迟（毫秒）：等待离屏卡片完成回收后再统计 */
const POOL_STATS_DELAY_MS: number = 600;

@Entry
@Component
struct Index {
  private dataSource: NewsDataSource = new NewsDataSource(INITIAL_COUNT);
  @State loadingMore: boolean = false;
  @State poolStats: string = '节点复用：命中 0 · 新建 0 · 空闲 0';
  private statsTimer: number = -1;

  aboutToDisappear(): void {
    // 离开页面清空全部节点池，销毁空闲节点释放内存
    //（挂载中的节点随卡片组件树一起销毁）
    if (this.statsTimer >= 0) {
      clearTimeout(this.statsTimer);
      this.statsTimer = -1;
    }
    NewsNodePools.clearAll();
  }

  private tryLoadMore(): void {
    if (this.loadingMore) {
      return;
    }
    this.loadingMore = true;
    this.dataSource.loadMore(() => {
      this.loadingMore = false;
      this.refreshPoolStats();
    });
  }

  /** 刷新复用池统计（延迟到离屏卡片回收完成后，去抖只保留最后一个定时器） */
  private refreshPoolStats(): void {
    if (this.statsTimer >= 0) {
      clearTimeout(this.statsTimer);
      this.statsTimer = -1;
    }
    this.statsTimer = setTimeout(() => {
      this.statsTimer = -1;
      this.poolStats = `节点复用：命中 ${NewsNodePools.totalReuseHitCount()}` +
        ` · 新建 ${NewsNodePools.totalCreateNewCount()}` +
        ` · 空闲 ${NewsNodePools.totalFreeCount()}`;
    }, POOL_STATS_DELAY_MS);
  }

  build() {
    Stack() {
      Column() {
        // 标题栏
        Text('资讯推荐')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor(Color.White)
          .width('100%')
          .height(56)
          .textAlign(TextAlign.Center)

        // 资讯列表
        List({ space: 10 }) {
          LazyForEach(this.dataSource, (item: NewsItem) => {
            ListItem() {
              NewsCardView({ item: item })
            }
          }, (item: NewsItem) => item.id)
        }
        .width('100%')
        .layoutWeight(1)
        .padding({ left: 12, right: 12, bottom: 12 })
        .cachedCount(1)
        .scrollBar(BarState.Off)
        .edgeEffect(EdgeEffect.Spring)
        .onScrollIndex(() => {
          this.refreshPoolStats();
        })
        .onScrollStop(() => {
          this.refreshPoolStats();
        })
        .onReachEnd(() => {
          this.tryLoadMore();
        })

        // 底部加载提示
        if (this.loadingMore) {
          Row({ space: 8 }) {
            LoadingProgress()
              .width(18)
              .height(18)
              .color('#99FFFFFF')
            Text('正在加载更多…')
              .fontSize(13)
              .fontColor('#99FFFFFF')
          }
          .width('100%')
          .height(44)
          .justifyContent(FlexAlign.Center)
        }
      }
      .width('100%')
      .height('100%')

      // 复用池状态指示条（调试观测设施）
      Text(this.poolStats)
        .fontSize(12)
        .fontColor('#E6FFFFFF')
        .padding({ left: 14, right: 14, top: 6, bottom: 6 })
        .borderRadius(14)
        .backgroundColor('#66000000')
        .position({ x: '50%', y: 64 })
        .markAnchor({ x: '50%' })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#FF101014')
  }
}
