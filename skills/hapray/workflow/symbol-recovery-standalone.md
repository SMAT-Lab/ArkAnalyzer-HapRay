> 主 Skill 路由：[`SKILL.md`](../SKILL.md)  
> 与 [`gen-perf-report.md`](gen-perf-report.md)（`update --so_dir`、完整报告目录）互补。  
> 分析细节与参数速查：[`analysis/symbol-recovery-analysis.md`](../analysis/symbol-recovery-analysis.md)

# 轻量符号恢复（三参数 · 无源码 · 纯二进制）

> **适用场景**：用户只提供 **`perf.data` + SO 目录 + `hiperf_report.html`**，**不做**完整 `perf` 采集、**不需要**应用源码/HAP 源码、**不跑** `hapray update`。  
> **推断模式**：默认 **Agent 离线编排**（`--prompt-only` → Agent 写结果 → `--import-llm-results`），**禁止**默认走 `--step2-openai` / 在线 LLM API。  
> **环境**：源码轨 venv **或** Release **`dist/tools/symbol-recovery/symbol-recovery.exe`** 均可；**不依赖** `tools/symbol_recovery` 源码树是否可 import。

---

## 一、与 `update` 集成的区别

| 维度 | 轻量三参数（本文） | `update --so_dir`（见 gen-perf-report） |
|------|-------------------|----------------------------------------|
| 输入 | 3 个文件/目录即可 | 完整 `reports/<ts>/` 报告树 |
| 应用源码 | ❌ 不需要 | ❌ 符号恢复不需要（root-cause 才要） |
| 应用二进制（`.so`） | ✅ `--so-dir` | ✅ `--so_dir` |
| 入口 | `symbol-recovery.exe` / `main.py` | `perf-testing update` |
| Agent 推断 | 对话内 Agent 完成 Step2 | `update` 内编排或 Agent |
| 典型用户 | 只有 perf 原始文件 + 从 HAP 解压的 libs | 已跑完 `perf` 采集 |

---

## 二、三参数映射

| # | 用户提供 | CLI 参数 | 说明 |
|---|----------|----------|------|
| 1 | `perf.data` | `--perf-data` | 热点采样源；工具内自动 `perf.data` → `perf.db`（需 `trace_streamer`） |
| 2 | `…/libs/arm64/`（含 `*.so`） | `--so-dir` | 应用**二进制** SO，非源码；须与采集时**同版本构建** |
| 3 | `hiperf_report.html` | `--html-input` | Step4 生成 `*_with_inferred_symbols.html`；仅要 Excel 时可省略 |

**SO 目录示例**（HAP/HSP 解压或设备拉取）：

```text
<包名>/libs/arm64/*.so
# 例：com.kuaishou.hmapp/libs/arm64/
```

**不需要**：`perf.json`、`perf.db`（事先提供）、`report/`、`testInfo.json`、应用 `.ets/.ts` 源码、`hapray update`。

---

## 三、环境：源码轨 vs 纯二进制（dist）

### 3.1 源码轨（开发/克隆仓）

```text
<REPO_ROOT>/tools/symbol_recovery/.venv/Scripts/symbol-recovery.exe   # Windows
<REPO_ROOT>/tools/symbol_recovery/.venv/bin/symbol-recovery          # Linux/macOS
```

需完成 [`setup-source.md`](setup-source.md) 第 5 步 venv；**不**要求 radare2 硬门禁（建议项）。

### 3.2 纯二进制轨（Release / dist，**无源码**）

```text
<PROJECT_ROOT>/dist/tools/symbol-recovery/symbol-recovery.exe
```

同包内应含（自动发现，无需手工配置 PATH）：

| 组件 | 典型路径 |
|------|----------|
| `trace_streamer` | `dist/tools/bin/trace_streamer_windows.exe`（或平台对应名） |
| 捆绑 `r2`（建议） | `dist/tools/bin/r2/` |

**分体安装**时设置其一：

- `HAPRAY_SYMBOL_RECOVERY_ROOT` → 含 `symbol-recovery.exe` 的目录  
- `HAPRAY_SYMBOL_RECOVERY_EXE` → exe 绝对路径  

详见 [`setup-binary.md` §5](setup-binary.md)。

**验证**（日志模块名为 `symbol_recovery.__main__` 表示 PyInstaller 打包 exe）：

```powershell
.\dist\tools\symbol-recovery\symbol-recovery.exe --help
```

---

## 四、Agent 离线闭环（推荐，禁止默认在线 LLM）

> **禁止**：无故 `--step2-openai`、`--symbol-recovery-llm-mode`；LLM 探活失败时必须降级 Agent 并同次完成回填。

### Step 1 — 导出任务

```powershell
$EXE = "<PROJECT_ROOT>\dist\tools\symbol-recovery\symbol-recovery.exe"
$WORK = "<PROJECT_ROOT>\reports\<场景目录>"   # 三参数可同目录，如 reports/testsymbol

& $EXE `
  --perf-data "$WORK\perf.data" `
  --so-dir "$WORK\<包名>\libs\arm64" `
  --html-input "$WORK\hiperf_report.html" `
  --output-dir "$WORK\output" `
  --top-n 50 `
  --stat-method event_count `
  --prompt-only
```

产出：`output/symbol_recovery_llm_tasks.json`、`output/perf.db`、`output/event_count_top50_analysis.xlsx`（骨架）。

### Step 2 — Agent 推断（对话内）

读取 `symbol_recovery_llm_tasks.json`，逐条分析 `prompt`（反汇编/反编译/字符串），写入：

`output/symbol_recovery_external_results.json`

**结果 JSON 约束**（与 [`symbol-recovery-analysis.md`](../analysis/symbol-recovery-analysis.md) 一致）：

- 必填：`function_id`、`functionality`（中文）、`function_name`（语义英文）、`performance_analysis`（中文）、`confidence`
- `function_name` **禁止**含偏移后缀（`_0x1a2b`、`+0x…` 等）
- 顶层：JSON 数组 `[...]` 或 `{"functions":[...]}`

任务数 ≤30：Agent 对话内逐批处理；较多时可 `--step2-split` / `--step2-merge`（仍由 Agent 推断，**不要**切在线 LLM）。

### Step 3 — 回填 + Step4 火焰图

```powershell
& $EXE `
  --skip-step1 `
  --perf-data "$WORK\perf.data" `
  --perf-db "$WORK\output\perf.db" `
  --so-dir "$WORK\<包名>\libs\arm64" `
  --html-input "$WORK\hiperf_report.html" `
  --output-dir "$WORK\output" `
  --top-n 50 `
  --stat-method event_count `
  --import-llm-results "$WORK\output\symbol_recovery_external_results.json"
```

日志应出现：`Imported external LLM results: applied=N, unmatched=0`，并完成 Step4 符号替换。

### Step 3 补充（可选）

若需写回独立 `perf.json`（三参数模式通常**无**该文件，可跳过）：

```powershell
& $EXE `
  --apply-excel-to-perf-json `
  --symbol-mapping-excel "$WORK\output\event_count_top50_analysis.xlsx" `
  --perf-json "$WORK\output\perf.json"
```

---

## 五、交付验收（四件套）

| 产物 | 路径 |
|------|------|
| `symbol_recovery_llm_tasks.json` | `<output-dir>/` |
| `symbol_recovery_external_results.json` | `<output-dir>/` |
| `event_count_top{N}_analysis.xlsx` | `<output-dir>/` |
| `hiperf_report_with_inferred_symbols.html` | 与 `--html-input` **同目录** |

**成功标准**：

- `external_results` 条数 = `--top-n`（或 tasks 条数）
- `replacements` / Excel 中**无** `auto_recovered_*` 占位
- 增强火焰图可打开且 stripped 地址已替换为推断名

仅有 `llm_tasks`、无 `external_results` → **未完成**，不得声称符号恢复成功。

---

## 六、已验证用例（工作区内）

目录：`reports/testsymbol/`

| 输入 | 路径 |
|------|------|
| perf.data | `reports/testsymbol/perf.data` |
| SO | `reports/testsymbol/com.kuaishou.hmapp/libs/arm64/`（119 个 `.so`） |
| HTML | `reports/testsymbol/hiperf_report.html` |

| 测试项 | 结果 |
|--------|------|
| 源码 venv `symbol-recovery.exe` + Agent | ✅ top-50 闭环 |
| **仅** `dist/tools/symbol-recovery/symbol-recovery.exe` + Agent | ✅ top-20 闭环（无源码 venv） |
| 无应用源码 | ✅ |
| 无 `update` / 无完整 report 树 | ✅ |

---

## 七、常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 未找到 `trace_streamer` | dist 不完整或 exe 与 `dist/tools/bin` 未同包 | 补全 Release 或把 `trace_streamer` 放入 `dist/tools/bin/` |
| SO 反汇编失败 / 偏移不对 | SO 与 perf 采集**版本不一致** | 换与采集同版本的 HAP/libs |
| Step4 跳过 | 未传 `--html-input` | 补上 HTML 或单独 `--only-step4` |
| `applied=0` | `function_id` 与 tasks 不对齐 | 修正 `external_results.json` |
| 想用 `update` | 只有 3 个文件、无 report 树 | **改走本文档**，不要硬跑 `update` |

---

## 八、Agent 执行清单

1. 确认三参数路径存在；SO 为 `libs/arm64` 且含热点对应 `.so`  
2. 选择 exe：优先 `<PROJECT_ROOT>/dist/tools/symbol-recovery/symbol-recovery.exe`（用户仅二进制包时）；开发仓可用 venv 入口  
3. **不要**设置在线 LLM；跑 `--prompt-only` 并 **Await 完成**  
4. 读取 tasks → 写 `symbol_recovery_external_results.json`（校验命名规范）  
5. `--import-llm-results` 一次回填；检查四件套与 `applied=N`  
6. 交付路径告知用户：`hiperf_report_with_inferred_symbols.html` + Excel  

**禁止**：在三参数场景下默认 `update`；`import` 完成后再次手动跑 `symbol-recovery` 重复分析；用 `--step2-openai` 替代 Agent 且用户明确要求仅 Agent 时。
