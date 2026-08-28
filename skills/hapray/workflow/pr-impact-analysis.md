> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **PR-Impact 场景分支**
> 前置文档：[`build.md`](build.md) · [`perf-collect.md`](perf-collect.md) · [`../analysis/README.md`](../analysis/README.md) · [`../root-cause/comprehensive.md`](../root-cause/comprehensive.md) · [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md)

# PR 影响对比分析工作流（PR-Impact）

> **范围**：用户提供一个 PR 或 Git 提交标识（commit hash / branch / PR URL / patch 文件）+ 测试场景描述，需要对**改动前**与**改动后**两份代码分别构建 debug HAP、安装到设备、执行完整的高负载性能分析流水线，最终生成前后对比报告，评估该 PR 对应用负载的影响（优化 / 劣化 / 无变化）。
>
> **核心原则**：两轮测试**必须使用同一条 `PerfLoad_*` 用例脚本**、**同一台设备**、**相同的采集参数**（`--round` 等），确保数据可比性。脚本在「改动前」轮次编写并 `prepare` 验证通过后，改动后轮次直接复用，**禁止**重写。

## 何时触发

| 用户表述 | 是否触发 |
|----------|----------|
| 「这个 PR 对性能有什么影响」「改动前后对比一下」「帮我看看这个提交是优化了还是劣化了」 | **必须** |
| 提供 PR 编号 / commit hash / 分支名 / patch 文件 + 测试场景 | **必须** |
| 仅做单轮性能分析（无前后对比意图） | **跳过**，走标准 Full 流程 |
| 已有两份独立报告，只需对比 | **跳过**本流程，直接进入阶段 6 `comparison` 报告（见 [`../report/analysis-deliverable.md`](../report/analysis-deliverable.md)） |

## 额外输入（§0 之外）

除 §0 标准路径门禁（源码路径 + SO 路径）外，本工作流需要**额外两项输入**，在 §0 完成后追问：

### 必问模板（§0 完成后）

```text
**PR 影响对比分析 — 额外输入 1/2：Git 标识**
请提供要评估的 PR 或 Git 提交标识，接受以下格式之一：
- PR URL（如 https://gitcode.com/xxx/xxx/pull/123）
- commit hash（如 a1b2c3d4）
- 分支名（如 feature/optimize-scroll）
- patch 文件路径（如 /path/to/changes.patch）
→ 回复具体标识

收到后我会继续询问第 2 项（测试场景）。
```

### 必问模板（第 2 项）

```text
**PR 影响对比分析 — 额外输入 2/2：测试场景**
请描述要在两轮测试中执行的测试场景（同一条用例脚本会用于前后两轮）：
- 场景描述（如「首页滑动列表 → 进入播放页 → 后台播放 30s」）
- 关注的性能维度（如 CPU 指令数、空刷帧、滑动流畅度等，默认全量高负载分析）
→ 回复场景描述

汇总确认：
- 源码路径：<§0 已确认>
- SO 路径：<§0 已确认或 build 自动填充>
- Git 标识：<用户提供的 PR/commit/branch/patch>
- 测试场景：<用户描述的场景>

确认无误后，我将开始 PR 影响对比分析流程。
```

### 输入判定

| 用户表述 | 记录字段 | 处理方式 |
|----------|----------|----------|
| PR URL | `pr_ref_type=url` | 通过 `git fetch` + `git merge` 拉取 PR 分支 |
| commit hash | `pr_ref_type=commit` | `git cherry-pick <commit>` 或 `git checkout <commit>` |
| 分支名 | `pr_ref_type=branch` | `git checkout <branch>` 或 `git merge <branch>` |
| patch 文件 | `pr_ref_type=patch` | `git apply <patch>` |
| 测试场景 | `test_scenario` | 用于编写 `PerfLoad_*` 用例脚本 |

## 整体流程

```text
§0 路径门禁 + 额外输入（Git 标识 + 测试场景）
  │
  ├─── Read 阶段文档（build + perf-collect + analysis + root-cause + deliver）
  ├─── ensure-workspace-layout.sh
  │
  ├─── 阶段 A：Git 状态管理（保存当前状态 → 确定 base → checkout base）
  │
  ├─── 阶段 B：改动前轮（Pre Round）
  │    ├─ B1. build debug HAP --install --uninstall（base 代码）
  │    ├─ B2. 编写 PerfLoad_* + prepare 验证（仅首次，后续复用）
  │    ├─ B3. perf 采集 → report/（pre_timestamp）
  │    ├─ B4. [可选] 符号恢复 update --so_dir
  │    ├─ B5. analysis high-load（读 report/）
  │    ├─ B6. root-cause（独立 CLI + Agent 补充）
  │    └─ B7. 交付 pre 报告（hapray-analysis-<date>-<app>-load-pre.md）
  │
  ├─── 阶段 C：应用 PR 改动（checkout/merge/cherry-pick/apply）
  │
  ├─── 阶段 D：改动后轮（Post Round）
  │    ├─ D1. build debug HAP --install --uninstall（PR 改动后代码）
  │    ├─ D2. 复用同一 PerfLoad_*（禁止重写，仅 prepare 确认可行）
  │    ├─ D3. perf 采集 → report/（post_timestamp）
  │    ├─ D4. [可选] 符号恢复 update --so_dir
  │    ├─ D5. analysis high-load（读 report/）
  │    ├─ D6. root-cause（独立 CLI + Agent 补充）
  │    └─ D7. 交付 post 报告（hapray-analysis-<date>-<app>-load-post.md）
  │
  ├─── 阶段 E：对比报告（hapray-analysis-<date>-<app>-load-comparison.md）
  │
  └─── 阶段 F：恢复 Git 原始状态
```

## 阶段 A：Git 状态管理

> **目的**：保存当前工作区状态，确定「改动前」的 base 代码版本，确保两轮测试的 Git 状态清晰可追溯。

### A.1 保存当前状态

```bash
# 记录当前分支和 commit（在 <HarmonyOS源码工程根> 下执行）
cd "<HarmonyOS源码工程根>"
git rev-parse --abbrev-ref HEAD    # 当前分支名 → original_branch
git rev-parse HEAD                 # 当前 commit hash → original_commit
git status --short                 # 工作区状态 → original_status
```

- 若工作区有未提交改动：`git stash push -m "hapray-pr-impact-temp"` 保存
- 记录 `original_branch`、`original_commit`、`original_status` 到会话变量，用于阶段 F 恢复

### A.2 确定 base（改动前）版本

根据用户提供的 Git 标识类型，确定 base 版本：

| `pr_ref_type` | base 版本确定方式 | 改动应用方式（阶段 C） |
|---------------|-------------------|----------------------|
| `url`（PR URL） | `git fetch origin pull/<N>/head:pr-<N>`；base = PR 的 merge-base | `git merge pr-<N>` 或 `git checkout pr-<N>` |
| `commit` | base = `git rev-parse <commit>^`（目标 commit 的父提交） | `git cherry-pick <commit>` |
| `branch` | base = `git merge-base HEAD <branch>` 或当前 HEAD | `git checkout <branch>` 或 `git merge <branch>` |
| `patch` | base = 当前 HEAD | `git apply <patch>` |

```bash
# 示例：commit 类型 — checkout 到父提交作为 base
git checkout <commit>^    # 改动前 = 目标提交的上一版
```

```bash
# 示例：branch 类型 — 当前 HEAD 即为 base（PR 分支的改动尚未合入）
# 无需 checkout，当前状态即为 before
```

### A.3 验证 base 状态

```bash
git log --oneline -3    # 确认当前在 base commit
git status --short       # 确认工作区干净
```

> **禁止**：在未保存原始状态的情况下直接 `git checkout`/`git reset`，否则无法恢复。

## 阶段 B：改动前轮（Pre Round）

> 完整执行 build → collect → analysis → root-cause → deliver 流程，产出 pre 报告。

### B.1 构建 debug HAP（base 代码）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" \
  --build-mode debug \
  --product default \
  --install --uninstall \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 构建成功后读取 `hapray-tool-result.json` 的 `outputs.so_dir`，自动填充 §0 `so_dir`
- `--install --uninstall` 确保旧版本被卸载、新 debug HAP 被安装到设备

### B.2 编写 `PerfLoad_*` 用例脚本（仅首次）

按 [`perf-collect.md`](perf-collect.md) 的完整流程编写用例脚本：

1. 根据 §0 源码路径 + 用户测试场景，分析应用源码确定操作步骤
2. 执行 §7.1.5 UI 坐标映射探测
3. 遵循 `step_verified` 门禁，逐步编写 → 设备执行 → 验证 → 下一步
4. 落盘到 `<PROJECT_ROOT>/testcases/<包名>/PerfLoad_<应用简称>_<编号>.py`
5. `prepare` 完整试跑通过

> **关键**：此脚本将在 Post Round **原样复用**，禁止在 Post Round 重写或修改。编写时须确保脚本不依赖特定代码版本（如硬编码的页面文案在前后两版应一致；若 PR 改动了 UI 文案，脚本应使用坐标或稳定的 id）。

### B.3 采集 perf（产出 `report/`）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 记录 pre 轮的 `reports_path`（`<PROJECT_ROOT>/reports/<pre_timestamp>/`）
- 产出 `report/` 全套分析器数据（`summary.json`、`more_flame_graph.json`、`trace_*.json` 等）

### B.4 [可选] 符号恢复

仅当需要符号级热点或火焰图 stripped 时执行：

```bash
uv run python -m scripts.main update \
  --report_dir <PROJECT_ROOT>/reports/<pre_timestamp> \
  --so_dir "<§0_SO>" \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

> **注意**：两轮测试的符号恢复策略须**保持一致**（要么都做，要么都不做），否则对比不公平。

### B.5 分析（阶段 4）

按 [`analysis/README.md`](../analysis/README.md) 读取 `report/` 做高负载分析。

### B.6 根因（阶段 5）

按 [`root-cause/comprehensive.md`](../root-cause/comprehensive.md) 执行独立 `root-cause` CLI + Agent 补充深挖。

### B.7 交付 pre 报告

按 [`analysis-deliverable.md`](../report/analysis-deliverable.md) 的 **pre 报告结构（10 章）** 落盘：

```
<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<app>-load-pre.md
```

- `report_suffix=pre`
- 数据路径指向 `<PROJECT_ROOT>/reports/<pre_timestamp>/<用例名>/`

## 阶段 C：应用 PR 改动

> **目的**：将用户指定的 PR/commit/branch/patch 改动应用到当前工作区，进入「改动后」状态。

### C.1 应用改动

根据 `pr_ref_type` 执行对应 Git 操作：

```bash
cd "<HarmonyOS源码工程根>"

# commit 类型：cherry-pick 目标提交
git cherry-pick <commit_hash>

# branch 类型：合并 PR 分支
git merge <branch_name>

# url 类型：先 fetch PR 再合并
git fetch origin pull/<N>/head:pr-<N>
git merge pr-<N>

# patch 类型：直接 apply
git apply <patch_file_path>
```

### C.2 验证改动已生效

```bash
git log --oneline -3    # 确认新提交在顶部
git diff HEAD~1 --stat  # 查看改动文件列表
```

- 若 `cherry-pick` / `merge` 出现冲突：**STOP**，提示用户解决冲突后继续
- 若 `git apply` 失败（patch 不匹配）：**STOP**，提示用户检查 patch 文件

### C.3 记录改动信息

记录以下信息用于对比报告：
- PR/commit 标识
- 改动文件列表（`git diff HEAD~1 --name-only`）
- 改动统计（`git diff HEAD~1 --stat`）

## 阶段 D：改动后轮（Post Round）

> **关键约束**：**复用** Pre Round 的 `PerfLoad_*` 脚本，禁止重写。仅重新 build + 采集 + 分析。

### D.1 构建 debug HAP（PR 改动后代码）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main build \
  --project-dir "<HarmonyOS源码工程根>" \
  --build-mode debug \
  --product default \
  --install --uninstall \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- `--uninstall` 确保卸载 pre 版本的 HAP，安装 post 版本
- 构建失败时检查是否因 PR 改动引入编译错误

> **⚠️ build-profile.json5 冲突处理**：Pre 轮的 `devecocli signature generate --force` 会重写 `build-profile.json5`（添加签名配置）。checkout 到 PR 版本后，该文件可能与 PR 改动冲突，导致 JSON5 解析失败。**解决方法**：
> ```bash
> # 在 <HarmonyOS源码工程根> 下执行
> git checkout -- build-profile.json5
> ```
> 重置后 build 的 auto-signing 会重新生成签名配置。

### D.2 复用用例脚本

- **禁止**重写或修改 `PerfLoad_*` 脚本
- 若 PR 改动了 UI（页面结构、控件 id/文案），导致脚本操作失效：
  - 首选：脚本已使用坐标模式（`coordinate-only`），不依赖文案/id → 应仍可用
  - 若确实失效：**STOP**，标注「PR 改动导致 UI 结构变化，前后脚本不可复用」，降级为两份独立分析（非严格对比）
- 可执行一次 `prepare` 确认脚本在新版本上仍可跑通

### D.3 采集 perf（产出 `report/`）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  --round 1 \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

- 记录 post 轮的 `reports_path`（`<PROJECT_ROOT>/reports/<post_timestamp>/`）
- **禁止**覆盖 pre 轮的报告目录（确保 timestamp 不同）

### D.4 [可选] 符号恢复

与 Pre Round **保持一致**的策略：

```bash
uv run python -m scripts.main update \
  --report_dir <PROJECT_ROOT>/reports/<post_timestamp> \
  --so_dir "<§0_SO>" \
  --result-file <PROJECT_ROOT>/hapray-tool-result.json
```

### D.5 分析（阶段 4）

按 [`analysis/README.md`](../analysis/README.md) 读取 post 轮的 `report/` 做高负载分析。

### D.6 根因（阶段 5）

按 [`root-cause/comprehensive.md`](../root-cause/comprehensive.md) 执行独立 `root-cause` CLI + Agent 补充深挖。

### D.7 交付 post 报告

按 [`analysis-deliverable.md`](../report/analysis-deliverable.md) 的 **post 报告结构** 落盘：

```
<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<app>-load-post.md
```

- `report_suffix=post`
- 数据路径指向 `<PROJECT_ROOT>/reports/<post_timestamp>/<用例名>/`
- post 报告须在 §三 每条根因增加「优化效果评估」（✅/⚠️/❌）

### D.8 报告落盘检查（进入阶段 E 前 MUST）

```text
□ 1. Pre 报告已落盘？  → reports/hapray-analysis-<YYYYMMDD>-<app>-load-pre.md
□ 2. Post 报告已落盘？ → reports/hapray-analysis-<YYYYMMDD>-<app>-load-post.md
□ 3. 两份报告均包含完整 10 章结构？
□ 4. Post 报告 §三 每条根因含优化效果评估（✅/⚠️/❌）？
□ 5. root_cause.md 已验收（无 Pending Agent Inference）？
```

> **禁止**在 Pre 和 Post 报告均未落盘时直接写对比报告。3 份报告必须各自独立可读。

## 阶段 E：对比报告

> 按 [`analysis-deliverable.md`](../report/analysis-deliverable.md) 的 **comparison 报告结构（10 章）** 落盘。

```
<PROJECT_ROOT>/reports/hapray-analysis-<YYYYMMDD>-<app>-load-comparison.md
```

### 对比维度

| 维度 | 对比方式 | 判定 |
|------|----------|------|
| 总指令数 | pre vs post 各步骤 | 降幅 > 5% → 优化；增幅 > 5% → 劣化；±5% 内 → 无明显变化 |
| 主线程占比 | pre vs post 各步骤 | 下降 → 优化；上升 → 劣化 |
| 空刷帧数/率 | pre vs post 各步骤 | 减少 → 优化；增加 → 劣化 |
| 离树节点占比 | pre vs post | 下降 → 优化 |
| 组件复用率 | pre vs post | 上升 → 优化 |
| 冗余线程/指令 | pre vs post | 减少 → 优化 |
| IPC QPS | pre vs post 最活跃步骤 | 下降 → 优化 |
| 符号级热点 | pre vs post Top-N 符号指令数 | 下降 → 优化 |
| 帧统计 | pre vs post 平均/最大帧耗时 | 下降 → 优化 |

### 综合结论判定

| 整体表现 | 判定 | 描述 |
|----------|------|------|
| 多数维度明显改善，无关键维度劣化 | **优化** | PR 对性能有正面影响 |
| 多数维度无明显变化（±5%），个别微优/微劣 | **无明显影响** | PR 对性能无显著影响 |
| 存在关键维度劣化（如指令数增加 > 5%、空刷增多） | **劣化** | PR 对性能有负面影响，需评估是否接受 |
| 部分优化 + 部分劣化 | **混合** | 需逐项说明，由用户决策 |

> **对比报告须包含**：PR 标识、改动文件列表、改动统计、两轮数据的 timestamp 路径，便于复现。

## 阶段 F：恢复 Git 原始状态

> **必须执行**：分析完成后恢复到阶段 A.1 保存的原始状态。

```bash
cd "<HarmonyOS源码工程根>"

# 回到原始分支
git checkout <original_branch>

# 若曾 stash，恢复改动
git stash pop    # 若阶段 A.1 执行了 git stash

# 验证恢复
git rev-parse HEAD    # 应等于 original_commit
git status --short    # 应恢复 original_status
```

> **禁止**：遗忘恢复，导致用户工作区停留在 PR 改动状态。阶段 F 完成后须在对话中确认恢复结果。

## 降级与异常

| 情况 | 动作 |
|------|------|
| PR cherry-pick / merge 冲突 | **STOP**，提示用户解决冲突后继续；不跳过冲突强行构建 |
| `git apply` patch 不匹配 | **STOP**，提示检查 patch 文件或改用 branch/commit 方式 |
| Pre 轮构建失败 | 检查源码工程配置；无法构建则终止流程，不进入 Post 轮 |
| Post 轮构建失败 | 检查是否 PR 引入编译错误；标注「Post 轮构建失败，对比报告仅基于 Pre 数据」 |
| Post 轮 `PerfLoad_*` 脚本失效（UI 改动） | 标注「PR 改动导致 UI 变化，前后不可严格对比」；降级为两份独立分析 |
| Post 轮 `perf` 采集失败 | 结合日志修正后重跑；仍失败则标注「Post 采集失败」，对比报告仅基于 Pre 数据 |
| 符号恢复策略不一致 | 对比报告中标注「符号恢复策略不一致，符号级热点对比仅供参考」 |
| Git 恢复失败 | 输出 `original_branch` / `original_commit`，指导用户手动 `git checkout` 恢复 |

## 与标准流程的关系

| 标准流程阶段 | PR-Impact 中的角色 |
|-------------|-------------------|
| §0 路径门禁 | **必须**，额外追加 Git 标识 + 测试场景两项输入 |
| 0.5 build | **必须**，两轮各执行一次（debug HAP + .so + install） |
| 1 setup | 按标准流程（源码轨或二进制轨） |
| 2 perf-collect | **必须**，两轮各执行一次；用例脚本仅首轮编写，次轮复用 |
| 3 gen-perf-report | 按需，两轮策略须一致 |
| 4 analysis | **必须**，两轮各执行一次 |
| 5 root-cause | **必须**，两轮各执行一次 |
| 6 deliver | **必须**，产出 3 份报告（pre + post + comparison） |

## 会话变量（本工作流新增）

| 变量 | 说明 |
|------|------|
| `pr_impact_mode` | `true`：当前处于 PR-Impact 工作流 |
| `pr_ref_type` | `url` / `commit` / `branch` / `patch` |
| `pr_ref_value` | 用户提供的 Git 标识值 |
| `test_scenario` | 用户描述的测试场景 |
| `original_branch` | 阶段 A.1 保存的原始分支名 |
| `original_commit` | 阶段 A.1 保存的原始 commit hash |
| `original_status` | 阶段 A.1 保存的工作区状态 |
| `pre_timestamp` | Pre 轮的 reports 时间戳目录 |
| `post_timestamp` | Post 轮的 reports 时间戳目录 |
| `pr_changed_files` | PR 改动的文件列表（阶段 C.3 记录） |
| `current_round` | `pre` / `post`：当前正在执行的轮次 |
| `report_suffix` | `pre` / `post` / `comparison` |

## 禁止事项

- **禁止**两轮使用不同的 `PerfLoad_*` 脚本（破坏对比基线）
- **禁止**两轮使用不同的设备或不同的 `--round` 参数
- **禁止**两轮符号恢复策略不一致（要么都做要么都不做）
- **禁止**在 Post 轮重写或修改用例脚本（除非 PR 改动了 UI 导致脚本失效）
- **禁止**Post 轮覆盖 Pre 轮的报告目录
- **禁止**遗忘阶段 F 的 Git 状态恢复
- **禁止**在 Git 状态未保存的情况下直接 `git checkout`/`git reset`
- **禁止**跳过 Pre 轮直接做 Post 轮（无基线无法对比）

---
