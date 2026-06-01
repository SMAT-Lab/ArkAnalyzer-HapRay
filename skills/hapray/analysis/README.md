# 数据分析子 Skill（阶段 4）

本目录存放 **基于 HapRay 产物的线索挖掘**（SQL、trace 深挖、动静交叉）。主 Skill [`../SKILL.md`](../SKILL.md) **§9** 要求：`gen-perf-report`（阶段 3）完成后，按本索引**逐一评估**；条件不满足则跳过并写明原因。

> **与阶段 5 分工**：`analysis/` 产出**线索与假设**；仅 [`../root-cause/empty-frame.md`](../root-cause/empty-frame.md) 对**空刷**跑 `root-cause` 流水线。最终合并见 [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md)（阶段 6）。

## 索引

| ID | 文件 | 适用场景 | 摘要 |
|----|------|----------|------|
| `scroll-jank` | [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | 列表/首页 **滑动**、周期性卡顿、掉帧 | `trace.db`、`frame_slice`、`HandleDragUpdate` |
| `high-load` | [`high-load-analysis.md`](high-load-analysis.md) | 高 CPU 指令数、未知瓶颈；**不用** `summary.json` 作主线 | `perf_sample` 聚合 + 静态 SO 交叉 |
| `symbol-recovery` | [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 热点仍为 `libxxx.so+0x…`；update 后仍异常 | SymRecover venv；Radare2 **建议** |

**阶段 5（非本目录）**：空刷根因 → [`../root-cause/empty-frame.md`](../root-cause/empty-frame.md)

## 评估顺序

1. `scroll-jank` → 2. `high-load` → 3. `symbol-recovery`  
（有空刷信号时，阶段 5 在 analysis 之后或并行评估，见主 Skill §9）

## 新增子 Skill 时

1. 在本目录新增 `*.md`（建议 `kebab-case`，专题类用 `*-analysis.md`）。  
2. 更新上表与 [`../SKILL.md`](../SKILL.md) §9。  
3. 执行时在对话中标明 **子 Skill ID + 文件名**。
