> 主 Skill 路由：[`SKILL.md`](../SKILL.md) **阶段 2**

# 真机采集路由（§7）

> **范围**：真机场景下需要「跑脚本/UI 操作并采 perf+trace」时（`perf` 全流程等）。**SIMPLE 模式**（已有 `perf.data` + `trace.htrace`）直接 `update`，不适用本节。  
> **阅读顺序**：环境门禁见 **§2–§6**；本章内小节使用 §7.x 局部编号（如 §7.1.5 UI 映射、§7.2 亮屏保活），勿与全局 §1/§2 混淆。

### 决策顺序（严格执行，禁止跳步）

| 优先级 | 条件 | 执行动作 | 记录字段 |
|:------:|------|----------|----------|
| **1** | `testcases/<包名>/` 下存在 `PerfLoad_*.py` 或 `PerfLoad_*.yaml`（或 `--run_testcases` 能匹配） | `perf --run_testcases "<用例名>" --apps <包名> …` | `collection_mode=predefined` |
| **2** | 上一步**无**匹配用例，且用户**未**明确要求 `gui-agent` / 「AI 探索」 | **按本应用编写** `PerfLoad_*` → **`prepare` 完整试跑**（须通过）→ `perf --run_testcases`（见下节） | `collection_mode=agent-authored` |
| **3** | 用户**明确**要求 `gui-agent` / 「AI 探索 UI」/ 「无脚本让模型点手机」 | `gui-agent --apps <包名> [--scenes "…"] …`（需 `GLM_API_KEY`） | `collection_mode=gui-agent` |
| **禁止默认** | 无预设用例、用户未要求 gui-agent | ❌ **不得**默认 `gui-agent`；❌ **不得** `perf --manual` / `PerfLoad_Manual`（仅 `sleep(30)`） | — |

**包名**须通过 `hdc shell bm dump -a` 等设备查询确认，禁止臆造。

### 发现预设用例（进入 `perf` 前 MUST）

1. **首选（对用户可见）**：`<PROJECT_ROOT>/testcases/<包名>/`  
2. **源码轨备选**：`<REPO_ROOT>/perf_testing/hapray/testcases/<包名>/`  
3. **二进制轨运行时**：Release 包 `_internal/hapray/testcases/<包名>/` — **须**由 `<SKILL_DIR>/scripts/sync-testcases-to-runtime.sh` 从 `<PROJECT_ROOT>/testcases/` 同步，**禁止**只在包内改脚本而不落盘工作区。
2. 收集 `PerfLoad_*`（`.py` / `.yaml`），在执行轨迹写明：`predefined_cases=[...]`。  
3. 多个用例：用户指定 > 默认选与场景最相关的一条（须说明理由）。  
4. `--run_testcases` 在磁盘上匹配失败 → 视为「无预设用例」→ 走优先级 **2**（写脚本），**不是** gui-agent。

> **预设用例惯例**：`setup()` 已清场；`process()` 首步 `start_app()` 再进业务；文案一般**不写**「冷启动专测」；采集中避免 `swipe_to_home` 等退应用操作；`teardown()` 负责退出。

### 无预设用例时：Agent 按目标应用编写 `PerfLoad_*`（优先级 2，默认路径）

**禁止**因「没有现成脚本」就直接 `gui-agent`。

#### 核心原则（MUST）

| 原则 | 说明 |
|------|------|
| **禁止照搬他案用例** | 不得把其他 `testcases/<其他包名>/` 里的包名、坐标、Tab 文案、页面顺序、Ability 名原样套到当前应用。那些文件**仅**可参考 `PerfTestCase` 的**类结构**与 `execute_performance_step` 用法，**不是**可复制的业务步骤。 |
| **必须结合本应用** | 若 §0 提供且目录含**应用源码**：步骤须来自**源码分析** + 用户场景；否则来自包名、用户场景、本机 UI（截图/控件树/hdc），及 `wm size` 等。 |
| **长等待保持亮屏** | 步骤间隔/ `sleep` / `wait` 过长须 `wake_up_display()` 或分段唤醒；**息屏、黑屏挂机跑完**视为无效（`prepare` 不得判通过）。 |
| **步骤宜精** | 覆盖用户关心的**一条主路径**即可，避免无依据的多 Tab、十几次子点击或「全功能遍历」；步数由**本应用真实交互**决定，不机械套用其他 app 的步数。 |
| **UI 映射探测** | **编写脚本前**须检查 Inspector 组件 `id` 映射；若可点击节点 **ID 全空** → 必须用**纯坐标**操作（见 §7.1.5），**禁止**依赖 `touch_by_id` / 无依据的 `touch_by_text`。 |
| **步骤注释可读** | 脚本内**多写中文注释**：说明每步在做什么、点哪个控件、坐标/文案依据；**禁止**无注释的裸坐标或裸 `sleep`。 |
| **`prepare` 硬门禁** | 编写后必须用 **`prepare` 完整跑通**用例；逐步操作须成功、运行流畅，**禁止**未通过就 `perf`。 |
| **应用启停（与框架一致）** | `PerfTestCase.setup()` 已 `stop_app()` + 回桌面；`process()` **开头须 `start_app()`**（打开目标 app 再进入业务步骤）；`teardown()` 已 `stop_app()`，用例结束**会退出应用**。自写脚本**勿重复**在 `setup`/`teardown` 里改退出逻辑。 |
| **勿写「冷启动」专测** | **禁止**把用例做成冷启动**专项**（如 `reboot_device()`、步骤名/描述写「冷启动场景」、仅 `start_app`+回桌面采一条冷启 trace），除非用户**明确要求**冷启动压测。这与「首步 `start_app` 打开应用」**不是一回事**。 |
| **采集中勿中途退应用（自写）** | 在 `execute_performance_step` **执行期间**须保持目标 app 前台：禁止 `stop_app()`、Home/`swipe_to_home`、`swipe_to_back`（若会退出应用）、切其他包；仅应用内 Tab/页面/控件导航。 |

#### 脚本生命周期（预设与自写共用，见 `perf_testcase.py`）

| 阶段 | 框架行为 | Agent 编写要求 |
|------|----------|----------------|
| `setup()` | `stop_app()` → 亮屏 → `swipe_to_home()` | 一般**不要**覆盖；用例从「未打开目标 app」开始 |
| `process()` 开头 | — | **须** `start_app(...)`（或等价打开本应用 Ability），再写业务步骤 |
| `execute_performance_step` 内 | 采集 perf+trace | **保持应用内**操作，勿中途退应用（见上表） |
| `teardown()` | `stop_app()` + 生成报告 | **须**保留；用例跑完**必须**退出应用，自写脚本**禁止**在末步再 `stop_app` 代替 teardown |

#### 流程

```text
确认包名与场景 → [有应用源码? 分析源码定步骤 : 收集 UI 依据]
  → UI 坐标映射探测（§7.1.5）
  → 逐步编写 PerfLoad_*（每步循环：写操作 → 设备执行 → 验证证据 → step_verified → 下一步）
  → 所有 step_verified=true → 落盘完整脚本
  → prepare 完整试跑（失败则改脚本再 prepare）→ 通过 → perf → 读 report/ 高负载分析
```

#### 1) 编写前路由：源码优先 vs 无源码（MUST）

§0 已确认的 **root-cause 输入目录**（`app_packages_dir_user` / `--app-packages-dir` / `HAPRAY_APP_PACKAGES_DIR`）按下列规则分支；**未提供或用户跳过**则走 **B 无源码**。

| 分支 | 判定（满足其一即视为「有应用源码」） | 编写依据 |
|------|--------------------------------------|----------|
| **A 有源码** | 目录下存在可分析的**应用源码/解析树**：含足够 `*.ts` / `*.ets`、`source-analysis/` + `index/`、`src/main/ets/`、`source-analysis/index/symbol_index.jsonl` 等（与 `detect_root_cause_input_kind` → `source` 一致，见 `perf_testing/hapray/core/common/device_app_packages.py`） | **必须先阅读、分析该目录源码**，再编写用例；步骤、页面名、按钮文案、Ability 名须能从源码中找到依据 |
| **B 无源码** | 用户跳过 root-cause 路径；或目录仅 `*.hap`、或无上述源码特征 | 沿用下文 **「无源码时的 UI 依据」**，禁止假装读过源码 |

**A 有源码 — Agent 必须做的分析（再写脚本）**

1. 定位源码根：优先 `source-analysis/`、`src/main/ets/`，或用户给定树中 `.ts` 最集中的目录。  
2. 结合用户场景，在源码中查找：**入口 Ability**、路由/页面（`@Entry`、`router`、`pages`）、目标页的 **按钮/Tab 文案**（`Text('…')`、`Resource`、常量字符串）、关键交互（播放、列表、跳转）。  
3. 完成 **§7.1.5 UI 映射探测** 后，将步骤映射为脚本操作：有稳定 `id`/文案时用 `touch_by_id` / `touch_by_text`；**ID 全空**时仅用 **坐标**（`touch_by_coordinates` + `source_screen_*`），**禁止**臆造 id 或盲用文案。  
4. 轨迹记录：`script_authored_from=source`、`source_paths=[...]`、`ui_mapping_mode=`、`app_specific_rationale=`。

**B 无源码 — 编写前（MUST）**

1. **包名**：`hdc list targets`；`hdc shell bm dump -n <包名>` 确认 `app_package`。  
2. **场景**：向用户确认要压测的**一条**主路径。  
3. **本应用 UI 依据**（至少其一，否则勿编造大量坐标）：用户说明、设备截图、UI 树/无障碍、hdc 真机观察。  
4. **入口 Ability**：用 `bm dump` / 源码核对 `start_app(page_name=...)` 的 Ability；`prepare`/`perf` 会走完整 `setup`→`process`，**无需**人工先把 app 停在前台。  
5. 完成 **§7.1.5 UI 映射探测**（无源码时**强制**；探测时可 `start_app` 后 dump 各屏 Inspector）。  
6. 轨迹记录：`script_authored_from=ui-only`、`ui_mapping_mode=`。

#### 7.1.5) UI 坐标映射探测（编写脚本前 MUST）

> **目的**：Hypium 的 `find_component(BY.id/BY.text)` 依赖 Inspector 里**可映射**的组件属性。若 **所有（或目标路径上全部）可点击节点的 `attributes.id` 为空**，则 id/文案映射**不可靠**，脚本须改为**纯坐标**点击（`UIEventWrapper.touch_by_coordinates` + `CoordinateAdapter`，见 `ui_event_wrapper.py` / `coordinate_adapter.py`）。**禁止**在映射失败时仍写 `touch_by_id` / 猜测 `touch_by_text` 并指望 `prepare` 碰运气。

**何时做**：在落盘 `PerfLoad_*.py` **之前**，对**待测主路径上的每一屏**（至少：首页、关键 Tab/入口、压测核心页）各探测一次。

**采集 Inspector（真机前台须为目标 app 对应页面）**：

```bash
# 源码轨；输出须在 <PROJECT_ROOT>/reports/（macOS 先 ensure-workspace-layout）
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main ui \
  -o <PROJECT_ROOT>/reports/_ui_probe_<包名> \
  [--device <设备序列号>]
```

在输出目录下查找 `ui/step*/inspector*.json`（或 `inspector_page_*.json`，以 `capture_ui.py` 落盘为准）。**同时**记录采集坐标时的屏幕分辨率（供 `source_screen_width` / `source_screen_height`）：

```bash
hdc shell hidumper -s RenderService -a screen
# 解析 render size / render resolution= WxH
```

**解析与判定**（结构同 `haptest/state_manager.py` 中 Inspector：`attributes.id`、`text`、`clickable`、`bounds`）：

1. 递归遍历 JSON，统计 **`clickable=='true'`** 且 `bounds` 有效的节点。  
2. 记 `clickable_total`、`id_non_empty`（`id` 非空字符串）、`text_non_empty`。  
3. **判定**（写入轨迹 `ui_mapping_mode`）：

| 条件 | `ui_mapping_mode` | 脚本操作要求 |
|------|-------------------|--------------|
| `clickable_total > 0` 且 `id_non_empty == 0` | **`coordinate-only`** | **必须**用 `touch_by_coordinates(x, y)`；坐标来自该屏 Inspector `bounds` **中心点**或同分辨率截图标注；**禁止**主路径使用 `touch_by_id`；**禁止**无探测依据的 `touch_by_text` |
| `id_non_empty > 0` 且目标控件有稳定 `id` | `id`（可辅以 `text`） | 可用 `touch_by_id`；文案仍须在 Inspector/源码中可核对 |
| 有稳定可见 `text`、无 `id` | `text` | 可用 `touch_by_text`；**须在 `prepare` 日志中确认无** `touch_by_text not found` |
| Inspector 拉取失败或 `clickable_total == 0` | — | **STOP**：先解决 dump/前台 app，**禁止**编造坐标写脚本 |

**`coordinate-only` 脚本要求（MUST）**：

1. 在 `setup()`（或首次点击前）设置 **`self.source_screen_width` / `self.source_screen_height`** 为**采集该组坐标时**的屏幕宽高（与 hidumper 一致），否则 `convert_coordinate` 无法跨分辨率适配。  
2. 每个点击使用 **`touch_by_coordinates`**，坐标与探测时**同一分辨率**下从 `bounds` 解析的中心点一一对应。  
3. 滑动可继续用 `swipes_*` / `driver.swipe`；长等待仍须 §7.2 亮屏保活。  
4. 轨迹：`ui_probe_paths=[...]`、`clickable_total=`、`id_non_empty=`、`ui_mapping_mode=coordinate-only`。

示例（从 bounds 取中心并点击）：

```python
import re

def _bounds_center(bounds_str: str) -> tuple[int, int]:
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not m:
        raise ValueError(f'bad bounds: {bounds_str}')
    l, t, r, b = map(int, m.groups())
    return (l + r) // 2, (t + b) // 2

def setup(self):
    super().setup()
    self.source_screen_width = 1216   # 替换为探测时记录的值
    self.source_screen_height = 2688

def _tap_bounds_center(self, bounds_str: str, wait_seconds: float = 2):
    x, y = self._bounds_center(bounds_str)
    self.touch_by_coordinates(x, y, wait_seconds)
```

#### 2) 编写与落盘

- **路径（MUST）**：`<PROJECT_ROOT>/testcases/<包名>/PerfLoad_<应用简称>_<四位编号>.py` + 同名 `.json`  
- **二进制轨**：落盘后执行 `sync-testcases-to-runtime.sh`，再 `prepare`/`perf`  
- 源码轨若同时维护 `<REPO_ROOT>/perf_testing/hapray/testcases/`，以 `<PROJECT_ROOT>/testcases/` 为 Agent **权威副本**，或 `cp` 保持同步
- 继承 `hapray.core.perf_testcase.PerfTestCase`；实现 `app_package` / `app_name`；`process()` 内用 `execute_performance_step('<本应用场景描述>', <秒数>, step_fn)`。  
- **脚本边界（MUST，无预设自写用例）**：  
  - **`process()` 开头须 `start_app()`**：`setup()` 已杀进程并回桌面，首步负责打开目标 app（与预设用例一致）。  
  - **采集中勿中途退应用**：`execute_performance_step` 内禁止 `stop_app`、Home/`swipe_to_home`、会退出应用的 `swipe_to_back`、切其他包。  
  - **结束由 `teardown()` 退出**：勿在业务末步再写 `stop_app`；框架会在用例结束时退出应用。  
  - **勿做冷启动专测**：除非用户明确要求，禁止 `reboot_device`、步骤名「冷启动」、仅采冷启一条路径。  
- 控件操作：**先按 §7.1.5 的 `ui_mapping_mode` 选型**——`coordinate-only` → 仅 `touch_by_coordinates`（+ `source_screen_*`）；`id`/`text` 模式才用 `touch_by_id` / `touch_by_text`；有源码时文案/路由仍须与源码或 Inspector 一致。
- **逐步验证硬门禁（SKILL.md 状态机强制）**：自写脚本时，每步 UI 操作必须遵循 `step_verified` 门禁（见 SKILL.md 状态机）。**结构性规则**：
  - **写一步 → 执行一步 → 输出验证证据 → 确认生效 → 才能写下一步**。这不是建议，是硬门禁。
  - 验证证据必须输出到对话中（Inspector dump 结果、截图描述、真机观察结论），作为 `step_verified[N]=true` 的依据。
  - 验证失败时必须**立即修正**该步参数并重新验证，禁止跳过继续写下一步。
  - 所有步骤验证通过后，才能落盘完整脚本文件。
  - **`prepare` 是最终完整性验证，不是首次验证操作是否生效的环节。**
  - **⛔ 绝对禁止**：一次性写完全部步骤后再验证；凭源码猜测坐标/手势参数不经设备验证就落盘脚本。违反此条等价于 `path_prompt_done=false` 时执行 Shell。
- **长等待须保持亮屏（MUST）**：perf 采集期间息屏会导致 trace/操作无效。脚本中凡 **单次 `time.sleep` / `driver.wait` ≥ 5 秒**，或 `execute_performance_step` 内连续等待较长时，须避免长时间黑屏：
  - 等待前调用：`self.driver.wake_up_display()`
  - 等待 **≥ 15 秒** 时：拆成多段 sleep（建议每 **≤ 10 秒** 一段），**每段前** `self.driver.wake_up_display()`，或封装为本用例内的 `_wait_keep_screen_on(seconds)`（内部循环 wake + sleep）
  - **禁止** 在性能步骤内出现数十秒无任何亮屏保活的 `sleep`
- 示例（长等待）：

```python
def _wait_keep_screen_on(self, seconds: float, chunk: float = 10):
    remaining = seconds
    while remaining > 0:
        self.driver.wake_up_display()
        time.sleep(min(chunk, remaining))
        remaining -= chunk
```

- 在对话/轨迹中说明：`app_specific_rationale=`、`screen_keep_alive=…`（哪些等待做了亮屏处理）。

**步骤注释（MUST，便于人工审阅与后续改脚本）**

Agent 编写的 `PerfLoad_*.py` 须让**不读源码的人也能看懂每一步意图**，注释用**简体中文**（与业务场景一致即可）。

| 位置 | 必须写清的内容 |
|------|----------------|
| **文件头** | 模块 docstring：应用名、包名、压测场景（用户原话摘要）、`ui_mapping_mode`、坐标采集分辨率（若 `coordinate-only`） |
| **`process()`** | 用注释块列出**步骤总览**（Step1…StepN 各一句） |
| **每个 `execute_performance_step`** | 步骤函数**上方** 2～5 行注释：本步目标、预期界面、与上一步关系 |
| **每次 UI 操作前** | 单行注释：**做什么**（如「进入播放页 Tab」）+ **依据**（源码文案 / Inspector bounds / 截图点位） |
| **坐标与等待** | 裸数字旁注释含义，例如 `# 中心 (608,1344)，来自 inspector 首页「播放」bounds`；`sleep` 注明「等列表加载 / 等播放稳定」 |
| **辅助方法** | `_wait_keep_screen_on`、`_tap_bounds_center` 等须有 docstring 说明用途 |

**禁止**：连续多行 `touch_by_coordinates` / `sleep` 无任何说明；仅用晦涩变量名代替注释；注释与实际操作不一致（改代码须同步改注释）。

**结构示例**（节选，Agent 须按本应用扩写）：

```python
"""
PerfLoad 用例：<应用中文名>（<包名>）
场景：<用户场景，如「首页进入播放并后台播放 30s」>
ui_mapping_mode: coordinate-only | text | id
坐标基准分辨率: 1216x2688（与 §7.1.5 探测一致）
"""


class PerfLoadExample0001(PerfTestCase):
    """<应用> — <一条主路径压测>"""

    def process(self):
        # setup() 已 stop_app + swipe_to_home；此处打开应用（非「冷启动专测」场景）
        self.start_app(page_name='EntryAbility')
        self.driver.wait(3)

        # --- 步骤总览 ---
        # Step1: 应用内点击底部「发现」Tab
        # Step2: 播放第一首，保持前台采集 N 秒（teardown 会自动 stop_app）

        self.execute_performance_step('进入发现 Tab', 5, self._step_open_discover)
        self.execute_performance_step('打开播放并保持采集', 15, self._step_play_first)

    def _step_open_discover(self):
        # 应用内 Tab 切换（勿 swipe_to_home / stop_app）
        self.touch_by_text('发现', wait_seconds=2)
        time.sleep(2)  # 等列表骨架渲染

    def _step_play_first(self):
        # 点击列表第一项播放按钮 — 坐标来自 inspector_page_1.json 可点击节点中心
        self.touch_by_coordinates(608, 1200, wait_seconds=2)  # bounds [..][..] @ 探测目录
        self._wait_keep_screen_on(25)  # 播放稳定期，perf 主要采集窗口；分段亮屏
```

#### 3) `prepare` 完整试跑（硬门禁，未通过禁止 `perf`）

> **说明**：落盘后必须用 **`prepare`** 在真机上**完整执行**该 `PerfLoad_*` 一次（与 xDevice 跑用例路径一致，见 `prepare_action.py`）。**禁止**未跑 `prepare` 就 `perf`；**禁止**把「日志无异常但息屏/卡住/操作未生效」判为通过。

**前置**（每次 `prepare` 前）：

1. 确认设备在线；用例会先走 `setup()`（杀进程、回桌面），再在 `process()` 里 `start_app`，**无需**人工预先打开 app。  
2. 命令确认包名：

```bash
hdc list targets
hdc shell bm dump -n <包名>
```

**执行**（源码轨；二进制轨在 `<RUNTIME_ROOT>` 用等价 `perf-testing`，**先** `sync-testcases-to-runtime.sh`）：

```bash
# macOS 二进制轨：ensure-workspace-layout 后 reports 落在 <PROJECT_ROOT>/reports/
cd <REPO_ROOT>/perf_testing   # 源码轨
uv run python -m scripts.main prepare \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  [--device <设备序列号>]
```

**通过标准**（须**全部**满足；缺一即 `prepare_passed=false`，**禁止** `perf`）：

| 类别 | 要求 |
|------|------|
| **命令结果** | 进程 **exit code = 0**；日志含 `✅ Test case completed: PerfLoad_...`；**无** `❌ Test case failed`、无未处理 Traceback |
| **逐步操作成功** | 通读 `prepare` 全程日志：不得存在 `touch_by_text not found`、关键 `Error`/`Exception`/`ConnectedError`；每个点击/滑动应对应**有效 UI 反馈**（不能靠空 `sleep` 混过）。**采集步骤中途**不得 `stop_app`/回桌面/切应用；`process()` 开头应有 `start_app`。若 §7.1.5 为 `coordinate-only`，不得出现未转换坐标或错分辨率导致的连续误点 |
| **完整跑完** | 所有 `execute_performance_step` 均执行完毕；总耗时与脚本设计量级相符（**禁止**某步卡死拖到超时仍算过） |
| **流畅、非假跑** | 试跑过程中（Agent **须**目视真机或结合试跑中截图）：**目标 app 保持前台**；**屏幕保持亮屏**（脚本须已按 §7.2 做 `wake_up_display` / `_wait_keep_screen_on`）；界面随步骤**连续变化**，非长时间静止/锁屏/停在桌面 |
| **场景达成** | 与用户约定的一条主路径在试跑中**实际走完**（非仅启动后休眠结束） |

**不算通过（MUST 判失败）**：

- 仅因 `sleep` 耗时而结束，但中途**息屏**、**回到桌面/退出目标 app**（采集步骤内误 `swipe_to_home`/`stop_app`）、或停在启动页/弹窗未处理。  
- `process()` **未** `start_app` 即采 perf，或做成冷启动专测（`reboot_device`、仅冷启一条路径）而用户未要求。  
- 日志大量 `touch_by_text not found` 或点击无效仍继续。  
- 应用 ANR、明显卡顿无响应、用例挂起需人工干预才结束。  
- `prepare` 报错或 exit code 非 0。

**失败时**：根据日志 + 真机现象修正**本应用**脚本（勿抄他案）→ **重新 `prepare`**，直至满足上表 → **禁止**带缺陷脚本进入 `perf`。

**轨迹记录**：`prepare_attempts=`、`prepare_log_notes=`、`prepare_passed=true|false`。

> **补充**：编写**前**可用 `hdc` 探路（查 Ability、截图、文案），但**不可替代** `prepare` 完整试跑。

#### 4) `prepare` 通过后执行 `perf`（产出 `report/`）

```bash
cd <REPO_ROOT>/perf_testing
uv run python -m scripts.main perf \
  --run_testcases "PerfLoad_<应用简称>_<编号>" \
  --apps <包名> \
  --round 1 \
  -o ./reports
```

- `perf` 仍失败：结合 `prepare` / `perf` 日志修正脚本后，须重跑 `prepare` 通过再 `perf`。  
- 随后**读 `<用例>/report/`** 进入阶段4 高负载分析（**默认不跑 `update`**；符号恢复按需）。`collection_mode=agent-authored`。

> **⛔ 禁止重复执行 `perf`**：`perf` 执行成功并产出 `report/` 后，**绝对禁止**再次执行同一用例的 `perf` 命令。重复执行会覆盖已有报告、浪费采集时间，且在用户看来是严重失误。执行 `perf` 前 **MUST** 先检查 `reports/<timestamp>/<用例>/report/summary.json` 是否已存在；若存在则直接进入阶段4 读报告，不得重跑。

> **二进制轨**：用例写在 `<PROJECT_ROOT>/testcases/` → `sync-testcases-to-runtime.sh` → `prepare` 通过 → `perf`（产出 `report/`）→ 读 `report/` 高负载分析。**禁止**默认 `gui-agent`；符号恢复按需 `update -r <PROJECT_ROOT>/reports/<timestamp> --so_dir ...`。

### `gui-agent` 触发条件（仅优先级 3）

- **仅当**用户在同一会话中**明确要求** `gui-agent`、AI 探索、或拒绝/无法编写 `PerfLoad_*` 脚本时。  
- 缺 `GLM_API_KEY`：**STOP** 并提示配置；**不得**改用 `perf --manual` 或编造未落盘的用例名。  
- `gui-agent` 完成后同样**读 `report/`** 进入高负载分析（符号恢复按需）。

### `perf --manual`（30 秒）— 仅显式请求

- 对应用例 `testcases/manual/PerfLoad_Manual.py`。  
- **仅当**用户明确说「手动测试 / 手动 30 秒 / `--manual`」时使用。  
- **禁止**作为无预设脚本、不想写脚本、或 `gui-agent` 失败的自动兜底。

### 采集后（与模式无关）

- `perf` 或 `gui-agent` 产出报告目录后，**直接读 `<用例>/report/`**（已含 `summary.json`、`more_flame_graph.json`、全部 `trace_*.json`、`redundant_thread_analysis.json`、`ui_animate.json` 等）进入 **阶段4 高负载分析**（见 [analysis/README.md](../analysis/README.md)）。**默认不跑 `update`**。
- **符号恢复（阶段3，按需）**：仅当需要符号级热点或火焰图为 stripped 地址时，执行 `update --so_dir`（见 [gen-perf-report.md](gen-perf-report.md)）。
- **root-cause（阶段5，独立）**：多信号综合根因走独立 `root-cause` CLI（默认 `--checker comprehensive`）+ Agent 补充深挖，携带 §0 的 `--source-dir`（见 [comprehensive.md](../root-cause/comprehensive.md)）。

---
