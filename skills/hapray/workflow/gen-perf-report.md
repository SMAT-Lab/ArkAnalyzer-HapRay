> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 3（可选符号恢复）**（CLI 为 `update --so_dir`）  
> 产出：增强火焰图 `hiperf_report_with_inferred_symbols.html`、符号级热点；**仅在需要符号级定位时执行**。  
> 多信号综合 root-cause → [`root-cause/comprehensive.md`](../root-cause/comprehensive.md)（独立阶段5，不在本文档展开）。

# 可选符号恢复（gen-perf-report，阶段 3）

> **何时执行（仅按需）**：①用户明确要符号恢复 / 符号级热点；②阶段4 high-load 发现火焰图热点为 stripped 地址（`libxxx.so+0x..`），需符号才能继续符号级分析。  
> **默认不执行**：`perf` 已产出 `report/` 全套分析器数据（含 `more_flame_graph.json`）；SO级/帧级/线程级高负载分析**不依赖**本阶段。无 SO 路径或用户跳过时，符号级热点标注「建议符号恢复」即可，**不要**为此默认跑 `update`。

> **报告根目录（MUST）**：`<PROJECT_ROOT>/reports/<timestamp>/`（macOS 须先 [`ensure-workspace-layout.sh`](../scripts/ensure-workspace-layout.sh)）。`--report_dir` / `-r` 指向该 `<timestamp>` 目录，**禁止**使用工作区外的 `~/ArkAnalyzer-HapRay/reports/`。

### 3.1 SO 路径（§0 确认后写入 update）

符号恢复须在 **§0 必问模板** 中索取 **SO 路径**（第 2 项）。第 1 项源码/HAP 路径属 **阶段 5 root-cause** → [`root-cause/comprehensive.md`](../root-cause/comprehensive.md)。

| 用途 | 用户需提供 | CLI | 环境变量 |
|------|------------|-----|----------|
| 符号恢复（strip `.so`） | 含 `*.so` 的文件夹（如 `libs/arm64`） | `--so_dir <路径>` | `HAPRAY_SO_DIR` |

**路径决策**（与 `update_action.py` 一致）：

1. **用户已提供** → 直接使用，**不再** `hdc file recv` 拉 SO。  
2. **用户未提供** → 尝试设备拉取 → `.symbol_recovery_libs/<包名>/`。  
3. **拉取失败** → **跳过符号恢复**；继续 report 其余分析，并写明跳过原因。

> 必问话术以 **§0 必问模板** 为准。

**update 命令（符号恢复自动执行，禁止重复）**：

```bash
uv run python -m scripts.main update \
  --report_dir <PROJECT_ROOT>/reports/<timestamp> \
  --so_dir "<§0_SO>" \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

> **⚠️ 关键警告**：
> - `update --so_dir` 会**自动触发完整符号恢复流程**（Step1导出 → Step2推断 → Step3导入 → Step4生成增强火焰图）
> - **执行一次即可，等待完成，禁止重复执行**
> - 如果超时进入后台，使用 `AwaitShell` 等待完成，**不要**手动再次执行 `symbol-recovery.exe`
> - 重复执行会导致同一批函数被多次分析，浪费时间和资源

---

### 3.2 符号恢复解决什么（仅符号级）

| 步骤 | 产出 | 火焰图符号状态 |
|------|------|----------------|
| `perf` 采集 | `more_flame_graph.json`、`hiperf_report.html`、原始火焰图 | ❌ strip 的 SO 仅有地址（`libxxx.so+0x1234`） |
| `update --so_dir` 符号恢复 | `hiperf_report_with_inferred_symbols.html` | ✅ 显示推断函数名 |

符号恢复**只影响符号级**：未做时 SO 级、帧级、线程级、IPC、空刷等分析**照常**（数据均在 `report/`）。仅当需要把 stripped 地址映射到函数名时才执行本阶段。采集见 [perf-collect.md](perf-collect.md)；高负载分析见 [analysis/high-load-analysis.md](../analysis/high-load-analysis.md)。

### 3.3 update 命令关键参数（符号恢复）

```bash
uv run python -m scripts.main update \
  --report_dir <REPORT_DIR>              # 必填：perf 输出目录（含 hiperf/）
  --so_dir <SO_DIR>                      # 推荐：本地 .so（提供则跳过设备拉取）
  --symbol-recovery-llm-mode             # 可选：先走在线 LLM（默认 Agent）
  --symbol-recovery-no-llm               # 仅当用户明确跳过符号恢复
```

**符号恢复（默认 Agent）**：

- **默认**：`agent_mode=true`（tasks → Agent 推断 → import → 增强火焰图）
- **在线 LLM**：`--symbol-recovery-llm-mode` 或 `HAPRAY_SYMBOL_RECOVERY_LLM_MODE=1`；失败回退 Agent
- ❌ **禁止**无故 `--symbol-recovery-no-llm`

**设备侧 SO 拉取**（仅未提供 `--so_dir` 时；易失败）：

| 内容 | 落盘路径 |
|------|----------|
| `.so` / `libs` | `<PROJECT_ROOT>/reports/<timestamp>/.symbol_recovery_libs/<包名>/` |

包名确认（`perf` 前）→ [perf-collect.md](perf-collect.md)，禁止臆造。

### 3.4 符号恢复交付验收（必须检查）

| 产物 | 路径 |
|------|------|
| `symbol_recovery_llm_tasks.json` | `.symbol_recovery/<step>/` |
| `symbol_recovery_external_results.json` | 同上 |
| `symbol_recovery_replacements.json` | `hiperf/<step>/` |
| `hiperf_report_with_inferred_symbols.html` | `hiperf/<step>/` **（火焰图最终交付）** |

**验收流程**：
1. `update --so_dir` 命令启动后，符号恢复自动在后台执行
2. 使用 `AwaitShell` 等待任务完成（通常5-15分钟，热点函数多时可能更长）
3. 检查上述4个产物是否存在
4. ✅ 产物齐全 → 符号恢复完成，**禁止**再执行任何符号恢复相关命令
5. ❌ 产物缺失 → 见 **§3.5** 重跑，**禁止**直接手动调用 `symbol-recovery.exe`

> **🚨 禁止行为**：`update` 执行期间或完成后，**禁止**手动执行 `symbol-recovery.exe --step3-import` 或类似命令，这会导致重复分析。

### 3.5 符号恢复：默认 Agent；LLM 仅按需

| 场景 | 自动行为 | 必须产出 |
|------|----------|----------|
| **默认** | **Agent 模式** | tasks → 推断 → external_results → 增强火焰图 |
| `--symbol-recovery-llm-mode` 且探活通过 | 先在线 LLM | 成功则增强火焰图；失败回退 Agent |
| LLM 失败 | **同次切换 Agent** | 同上 |
| Agent 也失败 | 标记失败并给重试命令 | 不得伪称完成 |

**🚨 LLM 失败时的强制修复**：

1. 检测 `auto_recovered_*` 或 LLM 错误 → 判定失败  
2. **删除**错误产物：`.symbol_recovery/<step>/event_count_topN_analysis.xlsx`、`call_count_topN_analysis.xlsx`、含错结果的 `symbol_recovery_external_results.json`  
3. 清理后重跑 Agent：`--prompt-only` → Agent 推断 → `--import-llm-results`  
4. 验证 `symbol_recovery_replacements.json` **无** `auto_recovered_*`  

**禁止**：LLM 失败直接结束；不清理就切 Agent；仅导出 tasks 即声称完成。

---
