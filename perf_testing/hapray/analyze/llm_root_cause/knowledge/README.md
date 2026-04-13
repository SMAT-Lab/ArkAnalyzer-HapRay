# 人工分析经验知识库

这个目录存放人工分析积累的**先验知识**，在构造 LLM Code Review Context 时注入 system prompt，帮助 LLM 更准确地推理根因。

## 设计原则

- 每个文件聚焦一个主题，控制在 300 行以内（避免超出 context window）
- 内容来源：人工分析真实 case 后总结的规律、半成品分析笔记、领域经验
- 文件格式：Markdown，优先用表格和列表，减少大段叙述
- 命名约定：`<主题>_<类型>.md`，如 `empty_frame_patterns.md`、`trace_perf_tables.md`

## 注入机制

`demo.py` 会在运行时自动读取本目录下所有 `*.md` 文件，按文件头的 `priority` 字段（YAML frontmatter）排序后拼接到 system prompt 的"领域知识"区段。

frontmatter 示例：
```yaml
---
topic: empty_frame
priority: 10        # 数字越大越优先注入，超出 token 预算时低优先级文件被截断
applicable: ["empty-frame"]   # 适用的 checker 类型
---
```

不带 frontmatter 的文件默认 priority=5，适用所有 checker。

## 文件列表

| 文件 | 主题 | 优先级 |
|------|------|--------|
| `trace_perf_tables.md` | Trace/Perf 数据库关键表结构和联查链路 | 8 |
| `empty_frame_patterns.md` | 空刷常见代码模式和反模式 | 10 |
| `arkts_lifecycle.md` | ArkTS 组件生命周期与状态管理要点 | 9 |

## 添加新知识

1. 在此目录新建 `*.md` 文件
2. 在文件头写 frontmatter（可选），指定 priority 和 applicable
3. 内容聚焦分析中遇到的真实问题，避免照抄官方文档
4. 在上方表格补充一行记录
