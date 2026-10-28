# 组件复用拓展（extension / 检查默认使用）

主 Skill [`../SKILL.md`](../SKILL.md) §5 信号路由 / §7 约束索引引用。本目录是**组件复用域的拓展资料库**，不是流水线阶段——不占阶段编号、不改变既有六阶段流程。

**与原有组件复用分析的关系**：HapRay 的组件复用分析（`component-reuse` 信号 / `ComponentReusableAnalyzer`，度量 @Reusable / LazyForEach 条目组件复用率）保持原样。本目录把组件复用的检查范围**默认扩展到第二条通道**：`NodeContainer + BuilderNode` 节点随条目反复构建——`component-reuse` 指标反映不出它，需按本目录子文档 §〇 的方法检查。

## 使用方式（检查默认，改造经确认）

- **检查默认使用**：阶段 4 analysis / 阶段 5 root-cause 涉及组件复用、滑动卡顿、构建热点时，**默认**同时检查 @Reusable 与 BuilderNode 两条通道（无需用户点名），检查方法见各子文档 §〇；
- **改造经用户确认**：检查确认适用后，向用户提出改造建议（root-cause **之前**执行为宜——改造属已知模式，不必带进根因分析，且改码后旧根因结论即过时）；用户同意后按子文档执行，改后**复用同一 `PerfLoad_*` 脚本重采**，root-cause 与交付报告基于拓展后数据；
- **用户点名直入**：「把 BuilderNode 改成复用的」等表述且提供 §0 源码路径时，直接取用对应子 Skill，改后走 2 重采 → 4 → 5 → 6；
- **检查不适用**：无 `NodeContainer+BuilderNode` 用法或仅静态挂载一次 → 记录「已检查，不适用」即可，流程照旧。

## 索引

| ID | 文件 | 适用信号 | 内容 |
|----|------|----------|------|
| `buildernode-reuse` | [`buildernode-reuse.md`](buildernode-reuse.md) | `scroll-jank` 构建调用聚集、`cpu-hotspot` build 热点、`NodeContainer+BuilderNode` 随条目反复构建 | 改造为 BuilderNode 复用池：组件树只构建一次、池取池还、`update()` 换数据 |

## 两条复用通道（使用前必读）

| | @Reusable 组件复用（原有分析） | BuilderNode 节点池（本拓展） |
|---|---|---|
| 作用层 | LazyForEach 条目组件 | 条目内部 NodeContainer 节点 |
| 机制 | ArkUI 内建 reuse | 应用层自建池 + `update()` 换数据 |
| HapRay 指标 | `component-reuse` 信号 / `reusability_ratio` | 无内建指标（见子文档的观测与验证方式） |

**注意**：节点池改造前后 `reusability_ratio` 基本不动是正常现象——**不可**用它验证本拓展的效果。

## 新增拓展子 Skill 时

1. 本目录新增 `<id>.md`（主文档：信号对照、改造规则、重采衔接）+ 配套资料子目录 `<id>-references/`；
2. 更新上表与 [`../SKILL.md`](../SKILL.md) §7 约束索引；
3. 执行时在对话中标明 **子 Skill ID + 文件名**。
