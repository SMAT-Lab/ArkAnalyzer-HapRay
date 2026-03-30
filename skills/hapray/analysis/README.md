# 数据分析子 Skill（可扩展）

本目录存放 **与 HapRay 产物结合的分析知识**，按主题拆成独立 Markdown，便于主 Skill `../SKILL.md` 引用、Agent **按需加载**（用户问题涉及某类分析时再读对应文件）。

## 索引

| ID | 文件 | 适用场景 | 摘要 |
|----|------|----------|------|
| `scroll-jank` | [`scroll-jank-trace-analysis.md`](scroll-jank-trace-analysis.md) | 列表/首页 **上下滑动**、周期性卡顿、掉帧、从 `trace.db` 还原手势与 jank | `frame_slice`（`depth=0` 真实帧）、`callstack` 手势与 `HandleDragUpdate`、SQL/Python 脚本、Hitrace 标记速查 |

## 新增子 Skill 时

1. 在本目录新增 `*.md`（建议 `kebab-case` 命名）。
2. 在上表增加一行 **ID / 文件 / 适用场景 / 摘要**。
3. 在 **`../SKILL.md`** 的「数据分析子 Skill 索引」表中同步一行，并在 `description` 或「何时使用」中补充触发词（若需要）。

主 Skill **不写**与各子文档重复的长篇步骤；规则与 SQL 以子文档为唯一详述来源。
