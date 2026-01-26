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

import { ItemData } from './ItemData';

export class ItemDataSource implements IDataSource {
  private listeners: DataChangeListener[] = [];
  private originDataArray: ItemData[] = [];

  public totalCount(): number {
    return this.originDataArray.length;
  }

  public getData(index: number): ItemData {
    return this.originDataArray[index];
  }

  registerDataChangeListener(listener: DataChangeListener): void {
    if (this.listeners.indexOf(listener) < 0) {
      this.listeners.push(listener);
    }
  }

  unregisterDataChangeListener(listener: DataChangeListener): void {
    const pos = this.listeners.indexOf(listener);
    if (pos >= 0) {
      this.listeners.splice(pos, 1);
    }
  }

  notifyDataReload(): void {
    this.listeners.forEach(listener => {
      listener.onDataReloaded();
    });
  }

  notifyDataAdd(index: number): void {
    this.listeners.forEach(listener => {
      listener.onDataAdd(index);
    });
  }

  notifyDataChange(index: number): void {
    this.listeners.forEach(listener => {
      listener.onDataChange(index);
    });
  }

  notifyDataDelete(index: number): void {
    this.listeners.forEach(listener => {
      listener.onDataDelete(index);
    });
  }

  notifyDataMove(from: number, to: number): void {
    this.listeners.forEach(listener => {
      listener.onDataMove(from, to);
    });
  }

  notifyDatasetChange(operations: DataOperation[]): void {
    this.listeners.forEach(listener => {
      listener.onDatasetChange(operations);
    });
  }

  public pushArray(newData: ItemData[]): void {
    this.originDataArray.push(...newData);
    this.notifyDataReload();
  }

  public addItems(items: ItemData[]) {
    this.originDataArray.push(...items);
    this.notifyDataReload();
  }

  public add1stItem(item: ItemData): void {
    this.originDataArray.splice(0, 0, item);
    this.notifyDataAdd(0);
  }

  public addLastItem(item: ItemData): void {
    this.originDataArray.splice(this.originDataArray.length, 0, item);
    this.notifyDataAdd(this.originDataArray.length - 1);
  }

  public addItem(index: number, item: ItemData): void {
    this.originDataArray.splice(index, 0, item);
    this.notifyDataAdd(index);
  }

  public delete1stItem(): void {
    this.originDataArray.splice(0, 1);
    this.notifyDataDelete(0);
  }

  public delete2ndItem(): void {
    this.originDataArray.splice(1, 1);
    this.notifyDataDelete(1);
  }

  public deleteLastItem(): void {
    this.originDataArray.splice(-1, 1);
    this.notifyDataDelete(this.originDataArray.length);
  }

  public reload() {
    this.originDataArray.splice(1, 1);
    this.originDataArray.splice(3, 2);
    this.reload();
  }
}