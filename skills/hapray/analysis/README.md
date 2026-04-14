# 数据分析子 Skill（可扩展）

本目录存放 **与 HapRay 产物结合的分析知识**，按主题拆成独立 Markdown。主 Skill `../SKILL.md` 要求：**在 `perf_testing` 采集落盘后，数据分析时默认按本索引顺序逐一评估各子 Skill 并深入分析，条件不满足再跳过并写明原因**；对 `trace.db`/报告做 **深入分析**，而非仅浏览自动 HTML（详见主 Skill「数据分析默认流程（逐一子 Skill）」与「采集产物 → 应触发的子 Skill」表）。

## 索引

| ID | 文件 | 适用场景 | 摘要 |
|----|------|----------|------|
| `scroll-jank` | [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | 列表/首页 **上下滑动**、周期性卡顿、掉帧、从 `trace.db` 还原手势与 jank | `frame_slice`（`depth=0` 真实帧）、`callstack` 手势与 `HandleDragUpdate`、SQL/Python 脚本、Hitrace 标记速查 |
| `high-load` | [`high-load-analysis.md`](high-load-analysis.md) | **已采集** perf/trace/log 等数据时，基于 **原始侧** 挖掘未知问题；**不用** `summary.json` 规则化摘要作主线 | 高负载特征、`trace.db`+`hiperf`+日志、可选与 HTML 对照、独立 `.md`「新发现」；**禁止**用 summary 替代原始挖掘 |
| `symbol-recovery` | [`symbol-recovery-analysis.md`](symbol-recovery-analysis.md) | 报告或 **`perf.data`** 中热点为 **`libxxx.so+0x…`** / strip 后无可读符号、需还原函数名以定位瓶颈 | **SymRecover**（`tools/symbol_recovery`）、Radare2/r2dec、LLM 辅助；KMP/stripped SO、热点语义化 |
| `empty-frame` | [`empty-frame-root-cause.md`](empty-frame-root-cause.md) | **空刷根因定位**、VSync 持续驱动无效刷新、列表/容器重建、Web/Hybrid 持续刷新、代码级修复建议 | 端到端流程（反编译→索引→证据提取→LLM）、核心模块说明、三路证据汇聚（/proc + UI dump + perf.db）、当前缺口与优化方向、运行命令与输出报告结构 |

## 新增子 Skill 时

1. 在本目录新增 `*.md`（建议 `kebab-case`；专题分析类与现有文件一致，使用 **`*-analysis.md`** 后缀，如 `scroll-jank-trace-analysis.md`、`high-load-analysis.md`、`symbol-recovery-analysis.md`）。
2. 在上表增加一行 **ID / 文件 / 适用场景 / 摘要**。
3. 在 **`../SKILL.md`** 的「数据分析子 Skill 索引」表中同步一行，并在 `description` 或「何时使用」中补充触发词（若需要）。

主 Skill **不写**与各子文档重复的长篇步骤；规则与 SQL 以子文档为唯一详述来源。执行时 Agent 须在对话中 **标明当前子 Skill ID 与文件名**（见主 Skill「执行过程输出」）。
