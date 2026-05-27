# HapRay Agent Skills（独立发布说明）

本目录存放 **可独立分发** 的 Agent Skill：每个子目录是一个完整 skill（至少包含 `SKILL.md`），**不依赖** monorepo 内其他路径即可被 Cursor、OpenCode、Codex 等工具加载。

## 目录约定

```
skills/
├── README.md                 # 本文件
└── <skill-name>/
    ├── SKILL.md              # 必填：YAML frontmatter + 正文
    ├── reference.md          # 可选：参数表、长文档
    ├── examples.md           # 可选：自然语言示例
    ├── hapray-tool-result.md # 可选：hapray-tool-result.json 字段速查（Schema 在仓库 docs/schemas/）
    └── analysis/             # 可选：数据分析子 Skill（多专题 Markdown，由主 SKILL 索引）
        ├── README.md         # 子 Skill 索引表
        └── <topic>.md        # 各专题长文档（如 scroll-jank-trace-analysis.md）
```

- **`<skill-name>`**：小写字母、数字、连字符（如 `hapray`）。
- **`hapray`**：主文件为工作流与 CLI；**`analysis/`** 内为可扩展的数据分析子文档，发布时须 **整目录** 复制。
- **独立发布**时，对外交付物即为 `<skill-name>/` 整个文件夹（或下文所述的归档）。

## HapRay 运行时交付建议（二进制优先 + 源码回退）

对 `hapray` skill，推荐采用 **Release 二进制优先** 的运行方式；当二进制下载失败或二进制不可运行时，必须自动回退到源码方式。  
**真机采集**：有预设则 `perf`；无预设时编写前须 **UI 映射探测**，脚本须**中文步骤注释**（每步做什么、依据何来），再 **`prepare` 通过** 后 `perf`。详见 `skills/hapray/SKILL.md`「真机采集路由」§2。  
该策略应以 **标准 Skill 描述** 方式表达（流程规则），由 AI 按规则自动执行，而不是依赖用户手工改脚本：

- **制品 URL 形态**：仅允许 `…/releases/download/<tag>/<asset_name>` 直链下载（或用户给出的等价整链）；**禁止**打开 GitCode 发布列表/详情页或 `releases/latest` 做「自动查最新」。
- 运行策略：按 `skills/hapray/SKILL.md` §1.0 确定 `tag` 与 `BASE`，再按平台拼候选 `asset_name` 并 **优先用 `curl`** 探测/下载 Release 制品；失败时回退 `git clone` + `uv run python -m scripts.main`
- 分析流程：使用二进制执行采集，基于 `reports_path` 与相关产物做子 Skill 分析并输出报告
- 最小自动化闭环：`直链/锚定 tag -> 平台识别 -> 候选资产名 curl 探测 -> curl 下载 -> 完整性校验 -> 可执行自检 -> 失败则源码回退`
- **镜像**：优先用户直链、`HAPRAY_RELEASES_DOWNLOAD_BASE` 或 `skills/hapray/SKILL.md` §1.0 表内备用根；全程不依赖浏览器打开发布页。

> 说明：`skills/` 目录本身仍可随仓库、独立仓库或 zip 分发；以上建议仅针对 HapRay 工具运行时获取方式。

### `hapray`：`git clone` 后为什么常「全挂」？

**Release 二进制包已含构建产物**，而 **仅从仓库检出源码不包含** `dist/tools/sa-cmd`、`symbol_recovery/.venv`。若 Agent/用户跳过构建直接跑 `perf` / `update` / `perf.data`→DB，会得到「转不了 DB、符号恢复失败、dbtools/负载拆解不可用」等现象。  
这在 **`skills/hapray/SKILL.md`** 的 **[源码工作区硬门禁]**、及 **`skills/hapray/analysis/symbol-recovery-analysis.md` §〇** 中规定为 **MUST**；挂载 skill 时请确保模型能读到 **`description`/§〇/硬门禁**，不要只读到「二进制失败再回退」那一段。

## 在各 Agent 工具中安装

无论通过哪种方式获取 skill（克隆本仓库、独立 skill 仓库、zip），安装原则相同：**整目录复制** `skills/<skill-name>/`（对 `hapray` 须包含 `analysis/` 子目录），目标路径下应出现 `<skill-name>/SKILL.md`。

对 `hapray`：运行时优先 **releases/download 直链**（见 `SKILL.md` §1.0–§1.1）；下载失败或二进制不可运行时回退源码流程。

### Cursor

| 范围 | 路径 | 说明 |
|------|------|------|
| 用户级（推荐） | `~/.cursor/skills/<skill-name>/` | 所有项目可用；Windows 一般为 `%USERPROFILE%\.cursor\skills\` |
| 项目级 | `.cursor/skills/<skill-name>/` | 随仓库共享，适合团队统一版本 |

```bash
# 示例：用户级安装 hapray（Linux/macOS）
mkdir -p ~/.cursor/skills
cp -r skills/hapray ~/.cursor/skills/hapray
```

```powershell
# 示例：用户级安装 hapray（Windows PowerShell）
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills" | Out-Null
Copy-Item -Recurse -Force "skills\hapray" "$env:USERPROFILE\.cursor\skills\hapray"
```

> 勿写入 `~/.cursor/skills-cursor/`：该目录为 Cursor 内置 skill 保留区。

### OpenCode

[OpenCode](https://opencode.ai/) 通过内置 `skill` 工具按需加载 `SKILL.md`。每个 skill 为 **一个子目录 + 其中的 `SKILL.md`**（文件名须全大写）。官方文档：[Agent Skills](https://open-code.ai/en/docs/skills)。

**默认扫描位置**（项目内会从当前工作目录向上遍历至 Git 根目录）：

| 范围 | 路径 |
|------|------|
| 项目 | `.opencode/skills/<skill-name>/SKILL.md` |
| 项目（Claude 兼容） | `.claude/skills/<skill-name>/SKILL.md` |
| 项目（Agents 兼容） | `.agents/skills/<skill-name>/SKILL.md` |
| 全局 | `~/.config/opencode/skills/<skill-name>/SKILL.md` |
| 全局（Claude / Agents 兼容） | `~/.claude/skills/…`、`~/.agents/skills/…` |

**方式 A — 在本仓库内通过 `opencode.json` 加载（当前未启用）**

仓库根 `opencode.json` **默认不包含** `skills.paths`，OpenCode **不会**自动加载本仓库 `skills/hapray/`。若需要，可自行在 `opencode.json` 增加：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": {
    "paths": ["skills"]
  }
}
```

**方式 B — 复制到项目 `.opencode/skills/`（可选）**

适合只拷贝 skill、不带 `opencode.json` 的场景：

```bash
mkdir -p .opencode/skills
cp -r skills/hapray .opencode/skills/hapray
```

```powershell
New-Item -ItemType Directory -Force -Path ".opencode\skills" | Out-Null
Copy-Item -Recurse -Force "skills\hapray" ".opencode\skills\hapray"
```

**方式 C — 全局安装**

```bash
mkdir -p ~/.config/opencode/skills
cp -r skills/hapray ~/.config/opencode/skills/hapray
```

**方式 D — 自定义路径（`opencode.json`）**

在**项目** `opencode.json` 或**全局** `~/.config/opencode/opencode.json` 中增加 `skills.paths`（路径相对于配置文件所在目录，支持 `~`）：

```json
{
  "skills": {
    "paths": ["~/my-skills", "./vendor/agent-skills"]
  }
}
```

每个条目应指向 **包含多个 skill 子目录的根**（即其下存在 `hapray/SKILL.md` 这类结构），而不是单个 `SKILL.md` 文件。

**方式 E — 远程 URL（可选）**

```json
{
  "skills": {
    "urls": ["https://example.com/.well-known/skills/"]
  }
}
```

具体 URL 形态以 [OpenCode 配置 schema](https://opencode.ai/config.json) 为准。

**权限（可选）**：在 `opencode.json` 的 `permission.skill` 中按 skill 名称配置 `allow` / `deny` / `ask`（支持 `internal-*` 等通配符），见 [Permissions](https://open-code.ai/en/docs/permissions)。

**排错**：skill 未出现时检查 — `SKILL.md` 拼写、frontmatter 含 `name` 与 `description`、`name` 与目录名一致（小写+连字符）、多路径下名称不冲突、未被 `deny` 隐藏。

### Codex

复制到 `$CODEX_HOME/skills/<skill-name>/`（未设置时默认为 `~/.codex/skills`）：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -r skills/hapray "${CODEX_HOME:-$HOME/.codex}/skills/hapray"
```

## 独立发布方式

### 1. 随 ArkAnalyzer-HapRay 仓库发布（Skill 分发推荐）

Skill 与主仓库同版本迭代。安装到各 Agent 工具见上文 **[在各 Agent 工具中安装](#在各-agent-工具中安装)**。

### 2. Git 子树拆成独立仓库

在仓库根目录将 `skills/<skill-name>` 推到单独远端，便于只订阅 skill、单独打 tag：

```bash
# 示例：首次将 hapray skill 推到独立仓库（需先创建空远端）
git subtree split -P skills/hapray -b publish-hapray
git push <remote-skill-url> publish-hapray:main
```

之后可在独立仓库上发 Release、附 zip。

### 3. 仅分发归档（zip / Release 附件）

打包时**只包含** `skills/<skill-name>/` 目录内容，解压后目录名应为 `<skill-name>`，且内含 `SKILL.md`。

### 4. 与 `npx skills add` 类工具

若工具支持 **按仓库子路径** 安装 skill，可将远端指向本仓库并指定路径，例如：

`https://gitcode.com/SMAT/ArkAnalyzer-HapRay` + 路径 `skills/hapray`（具体以所用 CLI 文档为准）。

不支持子路径时，用户可先 **sparse clone** 或只用方式 1/2/3。

## 版本与兼容性

- Skill 正文中的 **环境版本**（Node、Python）以主仓库根目录 **`.nvmrc`、`.python-version`、`package.json` 的 `engines`** 为准；Skill 内勿写死易过期的小版本号，可写「见仓库锚点文件」。
- **`hapray/SKILL.md` YAML `version`**：与当前对外 **GitCode Release 锚定 tag**（如 `v1.5.4`）对齐，作为 **默认直链 tag**（不再依赖发布页/latest）；发新版 Release 后须同步改该字段及正文示例直链。非锚定版本由用户提供整链或环境变量 `HAPRAY_RELEASE_TAG`。

## 维护清单（发布前）

- [ ] `SKILL.md` 的 `description` 含足够触发词（HapRay、鸿蒙性能、perf、HAP、SO/LTO 等）。
- [ ] `hapray/SKILL.md` 顶部 `version` 与 GitCode 当前 Release tag 一致；正文 **releases/download** 示例直链已核对（不要求维护「发布页」流程）。
- [ ] 命令与 `README.md`、`docs/使用说明.md` 一致；契约参数见 `docs/工具契约式输入输出方案.md`。
- [ ] 若 CLI 有破坏性变更，同步更新本目录下对应 skill。
