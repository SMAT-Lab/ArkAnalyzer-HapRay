# 数据分析子 Skill（阶段 4 analysis / high-load 主线）

本目录存放 **基于 HapRay 产物的线索挖掘**（SQL、trace 深挖、动静交叉）。主 Skill [`../SKILL.md`](../SKILL.md) **§5** 要求：`perf` 完成后**直接读 `<用例>/report/`**（**默认不跑 `update`**），按本索引**逐一评估**；条件不满足则跳过并写明原因。**high-load 为阶段4主线。**

> **与阶段 5 分工**：`analysis/` 产出**线索与假设**（含高负载热点）；[`../root-cause/comprehensive.md`](../root-cause/comprehensive.md)（阶段5，独立 CLI 多信号综合 + Agent 补充深挖）做**根因确认与源码级定位**。最终合并见 [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md)（阶段 6）。
>
> **符号恢复（可选阶段3）**：当 high-load 发现热点为 stripped 地址（`libxxx.so+0x..`）需符号级时，才触发 `update --so_dir`（见 [`../workflow/gen-perf-report.md`](../workflow/gen-perf-report.md)）；否则标注「建议符号恢复」，SO级/帧级/线程级照常分析。

## 索引

| ID | 文件 | 适用场景 | 摘要 |
|----|------|----------|------|
| `high-load` | [`high-load-analysis.md`](high-load-analysis.md) | **阶段4主线**：高 CPU 指令数、未知瓶颈；**不用** `summary.json` 作主线 | `perf_sample` 聚合 + 静态 SO 交叉 |
| `scroll-jank` | [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | 列表/首页 **滑动**、周期性卡顿、掉帧 | `trace.db`、`frame_slice`、`HandleDragUpdate` |
| `symbol-recovery` | [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 热点仍为 `libxxx.so+0x…`；触发可选阶段3 `update --so_dir` | SymRecover venv；Radare2 **建议** |

**阶段 5（非本目录）**：多信号综合 root-cause（CLI + Agent 补充深挖）→ [`../root-cause/comprehensive.md`](../root-cause/comprehensive.md)

## 评估顺序

1. `high-load`（主线）→ 2. `scroll-jank`（涉及滑动/掉帧时）→ 3. `symbol-recovery`（需符号级时触发可选阶段3）  
（阶段5 多信号综合 root-cause 在 high-load 之后，借源码逐类定位，见主 Skill §6）

## 新增子 Skill 时

1. 在本目录新增 `*.md`（建议 `kebab-case`，专题类用 `*-analysis.md`）。  
2. 更新上表与 [`../SKILL.md`](../SKILL.md) §9。  
3. 执行时在对话中标明 **子 Skill ID + 文件名**。
