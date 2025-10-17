import {add} from 'libtest_suite.so';

@Entry
@Component
struct Index {
  @State
  default_value: number = add(0, 1)

  build() {
    Column() {
      Button('call10')
        .width(200)
        .height(60)
        .fontSize(20)
        .margin(20)
        .onClick(() => {
           for (let i = 0; i < 10; i++) {
              this.default_value += add(0, 1);
           }
            console.log('HapRayAgent %d' , this.default_value);
        })
      Text(`${this.default_value}`)
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}