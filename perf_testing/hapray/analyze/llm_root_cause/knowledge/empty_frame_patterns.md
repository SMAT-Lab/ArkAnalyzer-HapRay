---
topic: empty_frame
priority: 10
applicable: ["empty-frame"]
---

# 空刷根因常见代码模式

> 人工分析积累的规律总结，帮助 LLM 快速锁定嫌疑代码。

## 1. 高风险触发场景（按频率排序）

| 场景 | 典型代码特征 | 影响机制 |
|------|------------|---------|
| ForEach 数据源高频变更 | `@State items: T[]` 在定时器/网络回调中整体替换 | 触发全量 diff，导致无变化但仍重绘 |
| 无效 State 写入 | `this.flag = this.flag`、值相同但仍赋值 | ArkUI 无法去重，每次赋值均标脏 |
| 定时器驱动重绘 | `setInterval(() => { this.updateTime() }, 16)` | 16ms 一次 VSync，必然触发空刷 |
| 全局 AppStorage 滥用 | 不相关组件监听同一 key | 单个 key 变化导致所有订阅者重绘 |
| 父组件状态下传子组件 | `@Prop count` 在父组件频繁变更 | 子组件被动重绘，即使自身无变化 |
| 动画未及时停止 | `animateTo()` 循环或条件未正确退出 | 持续驱动 VSync，帧率超出需要 |

## 2. 触发链路特征

```
VSync 回调
  └── UIAbility.onForeground / aboutToAppear
        └── 状态写入（@State / @Observed / AppStorage）
              └── 标脏 → 下一帧重绘
                    └── build() 执行 → 实际无 UI 变化 → 空刷
```

关键判断：**状态写入是否真正改变了 UI 可见内容**。若写入值与上次相同，或所写字段未被任何 `@Builder/@Component` 引用，即为潜在空刷源。

## 3. CallStack 特征识别

空刷帧的 perf 采样调用栈通常包含：

- `FlushTask` / `FlushDirtyNodeTask` — ArkUI 内部脏节点刷新
- `RSRenderThread::Run` — RenderService 渲染线程被唤醒
- `VSyncReceiver::Callback` — VSync 回调，但 draw call 数为零
- `EventHandler::Run` 中无业务逻辑帧 — 空循环消耗

若上述符号高频出现但 `draw_call_count=0`，高度怀疑空刷。

## 4. ForEach 专项

### 4.1 数据源设计要点

```typescript
// 危险：整体替换触发全量 diff
this.items = newItems.map(item => ({ ...item }))

// 推荐：增量更新，利用 keyGenerator 精确追踪
ForEach(this.items, item => { ... }, item => item.id)
```

### 4.2 keyGenerator 缺失

未提供第三个参数（keyGenerator）时，ArkUI 按下标匹配，数据顺序变化即触发全量重建。

### 4.3 LazyForEach 的触发条件

`LazyForEach` 依赖 `IDataSource` 接口，只有调用 `notifyDataAdd / notifyDataChange` 才精确触发，否则等同 `ForEach`。

## 5. 快速排除清单

- [ ] 嫌疑函数的写入字段是否出现在任何 `build()` 的渲染树中？
- [ ] `@State` 字段是否为对象引用，每次都 new 一个新对象？
- [ ] 是否有 `setInterval / setTimeout` 在前台持续运行？
- [ ] 是否存在对 `AppStorage.Set()` / `LocalStorage.Set()` 的频繁调用？
- [ ] 动画是否在页面不可见时仍在执行？
