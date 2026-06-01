> 主 Skill 路由：[`SKILL.md`](../SKILL.md) 阶段 6  
> 前置：阶段 3 [`gen-perf-report`](../workflow/gen-perf-report.md) 产出工具报告；阶段 4 [`analysis/`](../analysis/README.md) 线索；阶段 5 [`root-cause/empty-frame`](../root-cause/empty-frame.md) 的 `root_cause.md`（若有空刷）。

# Agent 分析交付报告（analysis-deliverable）

与 HapRay 自动报告（`hapray_report.html` / `root_cause.md`）区分：本文档规范 **Agent 写给用户的独立 Markdown**，默认路径：

`reports/hapray-analysis-<YYYYMMDD>-<topic>.md`（`<PROJECT_ROOT>` 下）

---

## 阶段 6 门禁（MUST，写交付报告前）

| 条件 | 动作 |
|------|------|
| 存在 `trace_emptyFrame.json` 且未 `--no-root-cause` | **必须先完成阶段 5**；Read `<用例>/report/root_cause.md` |
| `root_cause.md` 含 `Pending Agent Inference` | **禁止**写阶段 6；先按 [`empty-frame.md`](../root-cause/empty-frame.md) §0.3 完成 Agent 闭环 |
| `root_cause.md` 为正式根因报告 | 在交付报告中 **全文内嵌**（见下文 §空刷根因章节），不得仅摘要表格 + 外链 |
| 用户 §0 跳过源码 / 无空刷 | 可省略空刷根因章节，在「未覆盖项」说明 |

```text
阶段 5 验收通过 → Read root_cause.md → 阶段 6 落盘（内嵌全文）
```

---

## 报告结构（必须章节）

1. **路由决策** — 场景（ReadOnly / SIMPLE / Full）、运行轨、触发的子 Skill  
2. **执行轨迹** — 关键 CLI、跳过项及原因  
3. **关键证据** — 数据路径、指标摘录、SQL/图表要点（引用阶段 4 analysis 线索）  
4. **空刷根因分析** — **当且仅当**存在正式 `root_cause.md` 时 **MUST**；见下文专节规范  
5. **结论分级** — 高/中/低置信；区分「工具报告已写」vs「Agent 新发现」  
6. **优化建议** — 可执行项；空刷修复与 §4 根因嫌疑一一对应，**禁止**与内嵌根因矛盾  
7. **未覆盖项** — 缺失数据、未跑的子 Skill、待用户补充  

文末注明 Skill 版本：主 Skill frontmatter `version`（当前 `1.5.5`）。

---

## §空刷根因章节（`root_cause.md` 合入规范）

**位置**：建议作为 **§3.x**（关键证据子节）或独立 **§4**；标题示例：

```markdown
### 3.6 空刷根因分析（`root_cause.md` 全文）

> 来源：`<用例>/report/root_cause.md`
```

**内容要求（MUST）**：

1. **Read** 磁盘上的 `root_cause.md`（禁止凭记忆缩写）  
2. **内嵌全部正文**：Executive Summary、Top Suspects（含代码片段与修复建议）、Caveats、需要补充的数据  
3. 可调整标题层级（`#` → `####`）以适配交付报告大纲，**不得删节**嫌疑条目或代码块  
4. 文首保留一行来源路径；**禁止**用「见 root_cause.md」替代正文  

**禁止**：

- 仅写 5 行摘要表 + 外链  
- 阶段 5 未完成却声称根因已分析  
- 内嵌内容与 `root_cause.md` 不一致（若需补充 Agent 解读，写在结论分级，不覆盖根因正文）

---

## 会话变量表（每阶段更新）

| 变量 | 说明 |
|------|------|
| `workspace_layout_done` | 已执行 `ensure-workspace-layout.sh`（macOS 报告重定向） |
| `path_prompt_done` | §0 路径门禁完成 |
| `skill_read_done` | 已 Read 主 SKILL + 当前阶段文档 |
| `path_prompt_state` | `waiting_source` / `waiting_so` / `waiting_confirm` / `done` |
| `app_packages_dir_user` | 空刷根因输入 → `--app-packages-dir`（见 [`root-cause/empty-frame.md`](../root-cause/empty-frame.md)） |
| `so_dir_user` | 符号恢复 SO → `--so_dir` |
| `collection_mode` | `predefined` / `agent-authored` / `gui-agent` |
| `ui_mapping_mode` | `id` / `text` / `coordinate-only` |
| `prepare_passed` | `true` / `false` |
| `root_cause_ready` | `true`：正式 `root_cause.md` 且无 Pending；阶段 6 前置条件 |

---

## 合并来源

| 阶段 | 写入交付报告的内容 |
|------|-------------------|
| 3 gen-perf-report | `hapray_report.html` 摘要、增强火焰图结论 |
| 4 analysis | scroll-jank / high-load / symbol-recovery 的「新发现」 |
| 5 root-cause | **`root_cause.md` 全文内嵌**至 §空刷根因章节（有空刷时）；产物索引可保留外链 |

**禁止**：无证据的伪分析；仅复述 HTML 而无阶段 4 挖掘；有空刷却未内嵌 `root_cause.md` 全文；有空刷却未引用 `root_cause.md` 却声称完成根因分析。

---

## 验收清单（落盘前自检）

- [ ] `reports/hapray-analysis-*.md` 含必须章节 1–7（无空刷时可省略 §4）  
- [ ] 有空刷时：交付报告 **包含** `root_cause.md` 全部 Top Suspects 与代码片段  
- [ ] 交付报告中 **无**「Pending Agent Inference」  
- [ ] 结论分级 / 优化建议与内嵌根因一致  
- [ ] 产物索引列出 `root_cause.md` 路径，并注明全文已在 §x 合入  

---
