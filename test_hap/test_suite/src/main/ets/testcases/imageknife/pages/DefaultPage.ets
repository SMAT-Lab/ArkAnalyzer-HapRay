import { DownSamplingStrategy, ImageKnifeComponent, ImageKnifeOption, ImageInfo } from '@ohos/imageknifepro';
import { ImageCacheUtil } from './ImageCacheUtil';
import common from '@ohos.app.ability.common';


@Component
struct ImageItemComponent {
  @Prop imageUrl: string = '';
  @Prop imageIndex: number = 0;
  @Link cacheMap: Map<string, string>;
  @State imageOption: ImageKnifeOption = {
    loadSrc: this.cacheMap.get(this.imageUrl) || this.imageUrl,
    objectFit: ImageFit.Cover,
    onLoadListener: {
      onLoadStart: (imageInfo: ImageInfo) => {
        console.info(`Image ${this.imageIndex} load start`);
      },
      onLoadSuccess: (imageInfo: ImageInfo) => {
        console.info(`Image ${this.imageIndex} load success`);
        // 图片加载成功后，如果还未缓存，则下载并缓存
        if (!this.cacheMap.has(this.imageUrl)) {
          ImageCacheUtil.downloadAndCache(this.imageUrl).then((cachePath: string) => {
            this.cacheMap.set(this.imageUrl, cachePath);
            console.info(`图片 ${this.imageIndex} 下载并缓存成功`);
          }).catch((err: Error) => {
            console.error(`图片 ${this.imageIndex} 下载失败`, err);
          });
        }
      },
      onLoadFailed: (err: string, imageInfo: ImageInfo) => {
        console.error(`Image ${this.imageIndex} load failed: ${err}`);
      }
    },
    downSampling: DownSamplingStrategy.DEFAULT
  };

  aboutToAppear() {
  }

  build() {
    ImageKnifeComponent({
      imageKnifeOption: this.imageOption
    })
      .width('100%')
      .aspectRatio(1)
      .borderRadius(8)
  }
}

@Entry
@Component
struct Index {
  @State message: string = 'Hello World';
  @State imageList: string[] = [
    "https://picsum.photos/600/800?random=1",
    "https://picsum.photos/600/800?random=2",
    "https://picsum.photos/600/800?random=3",
    "https://picsum.photos/600/800?random=4",
    "https://picsum.photos/600/800?random=5",
    "https://picsum.photos/600/800?random=6",
    "https://picsum.photos/600/800?random=7",
    "https://picsum.photos/600/800?random=8",
    "https://picsum.photos/600/800?random=9",
    "https://picsum.photos/600/800?random=10",
    "https://picsum.photos/600/800?random=11",
    "https://picsum.photos/600/800?random=12",
    "https://picsum.photos/600/800?random=13",
    "https://picsum.photos/600/800?random=14",
    "https://picsum.photos/600/800?random=15",
    "https://picsum.photos/600/800?random=16",
    "https://picsum.photos/600/800?random=17",
    "https://picsum.photos/600/800?random=18",
    "https://picsum.photos/600/800?random=19",
    "https://picsum.photos/600/800?random=20",
    "https://picsum.photos/600/800?random=21",
    "https://picsum.photos/600/800?random=22",
    "https://picsum.photos/600/800?random=23",
    "https://picsum.photos/600/800?random=24"
  ];
  // 存储图片URL和缓存路径的映射
  @State imageCacheMap: Map<string, string> = new Map();

  aboutToAppear() {
    // 获取上下文并初始化缓存目录
    const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
    ImageCacheUtil.initCacheDir(context).then(() => {
      console.info('图片缓存目录初始化完成');
      // 预加载所有图片到缓存
      this.preloadImages();
    }).catch((err: Error) => {
      console.error('图片缓存目录初始化失败', err);
    });
  }

  /**
   * 预加载所有图片到缓存
   */
  async preloadImages(): Promise<void> {
    for (let url of this.imageList) {
      try {
        // 检查是否已缓存
        const cachedPath: string | null = await ImageCacheUtil.getCachedImagePath(url);
        if (cachedPath) {
          // 已缓存，直接使用
          this.imageCacheMap.set(url, cachedPath);
          console.info(`图片已缓存: ${url}`);
        } else {
          // 未缓存，异步下载
          ImageCacheUtil.downloadAndCache(url).then((cachePath: string) => {
            this.imageCacheMap.set(url, cachePath);
            console.info(`图片下载并缓存成功: ${url}`);
          }).catch((err: Error) => {
            console.error(`图片下载失败: ${url}`, err);
            // 下载失败时，仍然使用原始URL
            this.imageCacheMap.set(url, url);
          });
        }
      } catch (error) {
        console.error(`预加载图片失败: ${url}`, error);
        // 出错时使用原始URL
        this.imageCacheMap.set(url, url);
      }
    }
  }

  /**
   * 获取图片路径（优先使用缓存）
   */
  getImagePath(url: string): string {
    return this.imageCacheMap.get(url) || url;
  }

  build() {
    RelativeContainer() {
      Column() {
        Text('图片浏览')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
          .margin({ top: 20, bottom: 20 })
          .width('100%')
          .textAlign(TextAlign.Center)

        Scroll() {
          // 使用Grid布局实现每行3张图片
          Grid() {
            ForEach(this.imageList, (item: string, index: number) => {
              GridItem() {
                ImageItemComponent({
                  imageUrl: item,
                  imageIndex: index,
                  cacheMap: this.imageCacheMap
                })
              }
            }, (item: string, index: number) => `${item}_${index}`)
          }
          .columnsTemplate('1fr 1fr 1fr')
          .rowsGap(12)
          .columnsGap(12)
          .width('100%')
          .padding({
            left: 16,
            right: 16,
            top: 0,
            bottom: 16
          })
        }
        .width('100%')
        .layoutWeight(1)
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#FFFFFF')
    }
    .height('100%')
    .width('100%')
  }
}

