import { TestRunner, TestSuite } from '../common/TestRunner';

@Entry
@Component
struct Index {
  private testRunner: TestRunner = TestRunner.getInstance();
  @State availableTestSuites: Array<TestSuite> = [];
  @State isInitializing: boolean = true;

  aboutToAppear() {
    this.loadAvailableTestSuites();
  }

  async loadAvailableTestSuites() {
    if (this.isInitializing) {
      this.availableTestSuites = await this.testRunner.getAvailableTestSuites();
      this.isInitializing = false;
    }
  }

  build() {
    NavDestination() {
      Column({ space: 10 }) {
        Text($r('app.string.LoadTestcases_label'))
          .width('100%')
        List({ space: 10 }) {
          ForEach(this.availableTestSuites, (item: TestSuite) => {
            ListItem() {
              Column() {
                Text(item.name)
                  .fontSize(24)
                  .fontColor(Color.Black)
                  .maxLines(3)
                  .lineHeight(22)
                  .opacity(0.9)
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
                  .width('100%')
                List() {
                  ForEach(item.testCases, (testcase: string) => {
                    ListItem() {
                      Text(testcase)
                        .margin({ left: 24 })
                    }
                  })
                }
              }.width('100%')
            }.margin({ top: 12, left: 16, right: 16 })
            .borderRadius(12)
          }, (item: TestSuite) => item.name)
        }.width('100%')
      }
      .width('100%')
      .margin({ left: 24 })
      .backgroundColor(Color.White)
    }.backgroundColor(0xF1F3F5)
    .title($r('app.string.app_name'))
  }
}