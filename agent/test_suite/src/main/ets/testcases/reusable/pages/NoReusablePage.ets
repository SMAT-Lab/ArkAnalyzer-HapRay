/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { ItemData } from "./ItemData";
import { ItemDataSource } from "./ItemDataSource";
import { genMockItemData } from "./MockData";

@Entry
@Component
struct NoReusablePage {
  private dataSource: ItemDataSource = new ItemDataSource();

  aboutToAppear(): void {
    this.dataSource.pushArray(genMockItemData(1000));
  }

  build() {
    NavDestination() {
      Column() {
        List() {
          LazyForEach(this.dataSource, (item: ItemData) => {
            // layout the component, and set reuse id (or no set with using name as default id)
            ItemView({ title: item.title, from: item.from, tail: item.tail })
          }, (item: ItemData) => item.id.toString())
        }
        .expandSafeArea([SafeAreaType.SYSTEM], [SafeAreaEdge.BOTTOM])
        .cachedCount(1)
        .width('100%')
        .height('100%')
      }
      .width('100%')
      .height('100%')
    }
    .backgroundColor(0xF1F3F5)
    .title('NoResuable')
  }
}

@Component
struct ItemView {
  @State title: string | Resource = '';
  @State from: string | Resource = '';
  @State tail: string | Resource = '';

  build() {
    Column() {
      Text(this.title)
        .fontSize(16)
        .fontWeight(FontWeight.Medium)
        .fontColor(Color.Black)
        .maxLines(3)
        .lineHeight(22)
        .opacity(0.9)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .width('100%')
      Row() {
        Text(this.from)
          .fontSize(12)
          .fontWeight(FontWeight.Regular)
          .fontColor(0x0A59F7)
        Text(this.tail)
          .fontSize(12)
          .opacity(0.4)
          .fontWeight(FontWeight.Regular)
          .margin({ left: 6 })
          .width('100%')
      }
      .margin({ top: 12 })
    }
    .padding({
      top: 16,
      bottom: 12,
      left: 16,
      right: 16
    })
    .margin({ top: 12, left: 16, right: 16 })
    .borderRadius(12)
    .backgroundColor(Color.White)
  }
}
