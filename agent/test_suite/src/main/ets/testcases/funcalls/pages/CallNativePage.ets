import {add} from 'libtest_suite.so';

@Entry
@Component
struct Index {
  build() {
    Column() {
      Button('call10')
        .width(200)
        .height(60)
        .fontSize(20)
        .margin(20)
        .onClick(() => {
           let a = 0;
           for (let i = 0; i < 10; i++) {
              a = add(a, i);
           }
            console.log('HapRayAgent %d' , a);
        })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}