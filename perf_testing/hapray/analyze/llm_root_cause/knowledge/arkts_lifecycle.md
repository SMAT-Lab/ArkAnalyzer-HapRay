---
topic: arkts_lifecycle
priority: 9
applicable: ["empty-frame", "redundant-thread"]
---

# ArkTS 组件生命周期与状态管理要点

> 定位空刷和冗余线程根因时的关键先验知识。

## 1. 组件生命周期（性能分析视角）

```
aboutToAppear()       ← 组件挂载，初始化 State、启动定时器/订阅
  build()             ← 首次渲染，构建虚拟 DOM 树
    onPageShow()      ← 页面进入前台（可见）
      ...正常交互...
    onPageHide()      ← 页面进入后台（不可见）！定时器/动画应在此停止！
  aboutToDisappear()  ← 组件卸载，清理资源
```

### 关键陷阱

- `aboutToAppear` 与 `onPageShow` 不同：路由返回时组件不销毁，`aboutToAppear` 不再触发，只触发 `onPageHide → onPageShow`
- 后台定时器：组件进入 `onPageHide` 后如未清理 `setInterval`，仍在后台产生 State 写入，引发空刷

## 2. 状态装饰器触发重绘的范围

| 装饰器 | 触发重绘范围 | 空刷风险 |
|--------|------------|---------|
| `@State` | 当前组件 | 中（局部） |
| `@Prop` | 当前组件（接收父传值） | 中 |
| `@Link` | 当前组件 + 父组件（双向） | 高 |
| `@Observed` + `@ObjectLink` | 所有引用该对象的组件 | 高 |
| `AppStorage` | 所有绑定该 key 的组件 | **极高** |
| `LocalStorage` | 同一 LocalStorage 实例范围内 | 高 |

### 识别方法

在 `symbol_index.jsonl` 中搜索 `@State`、`@Link`、`AppStorage.Set` 等关键词，结合调用图确认写入触发方。

## 3. build() 函数的重绘开销

每次状态改变后，ArkUI 重新执行 `build()`，与改变的字段相关的子树被标脏重建。以下操作在 `build()` 内代价极高：

- 复杂计算（数组过滤、排序）
- 同步 I/O（文件/数据库读取）
- 创建大对象（`new Date()`、`JSON.parse()` 在循环中）

### 优化策略

```typescript
// 危险：每次重绘都计算
build() {
  ForEach(this.rawData.filter(x => x.visible), ...)
}

// 推荐：缓存计算结果
@State filteredData: DataType[] = []

aboutToAppear() {
  this.filteredData = this.rawData.filter(x => x.visible)
}
```

## 4. 冗余线程常见来源（redundant-thread checker）

- `Worker` 线程：`new worker.Worker(...)` 未在 `aboutToDisappear` 中 `terminate()`
- `TaskPool` 任务：提交后未监控完成，形成任务堆积
- 后台 HTTP 长连接：`http.createHttp()` 创建后未 `destroy()`
- WebSocket 保活：`ws.connect()` 后在页面隐藏时未 `close()`

## 5. 线程唤醒链路

```
业务线程写 @State
  → ArkUI JS Thread 标脏
  → VSync 到来 → UI Thread 执行 build()
  → RenderService 线程收到 drawing command
  → GPU 线程执行渲染
```

若 perf 采样显示 `RenderService` 线程频繁唤醒但 GPU 指令数接近零，即为疑似空刷。
