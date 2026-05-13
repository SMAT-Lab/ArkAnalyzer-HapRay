# HapRay Agent Skills（独立发布说明）

本目录存放 **可独立分发** 的 Agent Skill：每个子目录是一个完整 skill（至少包含 `SKILL.md`），**不依赖** monorepo 内其他路径即可被 Cursor / Codex 等工具加载。

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
该策略应以 **标准 Skill 描述** 方式表达（流程规则），由 AI 按规则自动执行，而不是依赖用户手工改脚本：

- 发布地址：`https://gitcode.com/SMAT/ArkAnalyzer-HapRay/releases`
- 运行策略：先下载**最新发布版本**并按平台选择对应二进制包（Windows / Linux Ubuntu 22.04/24.04 x64 / macOS Intel / macOS Apple Silicon）；失败时回退 `git clone` + `uv run python -m scripts.main`
- 分析流程：使用二进制执行采集，基于 `reports_path` 与相关产物做子 Skill 分析并输出报告
- 最小自动化闭环：`确定最新 tag -> 平台识别 -> 资产名匹配 -> 下载 -> 完整性校验 -> 可执行自检 -> 失败则源码回退`
- **GitCode 不可达时**：优先使用用户直链、环境变量 `HAPRAY_RELEASES_DOWNLOAD_BASE` 或 `skills/hapray/SKILL.md` §1.0 表内备用根拼接 `releases/download/<tag>/<asset>`，见该节；不得依赖必须打开 GitCode 网页。

> 说明：`skills/` 目录本身仍可随仓库、独立仓库或 zip 分发；以上建议仅针对 HapRay 工具运行时获取方式。

### `hapray`：`git clone` 后为什么常「全挂」？

**Release 二进制包已含构建产物**，而 **仅从仓库检出源码不包含** `dist/tools/sa-cmd`、`symbol_recovery/.venv`。若 Agent/用户跳过构建直接跑 `perf` / `update` / `perf.data`→DB，会得到「转不了 DB、符号恢复失败、dbtools/负载拆解不可用」等现象。  
这在 **`skills/hapray/SKILL.md`** 的 **[源码工作区硬门禁]**、及 **`skills/hapray/analysis/symbol-recovery-analysis.md` §〇** 中规定为 **MUST**；挂载 skill 时请确保模型能读到 **`description`/§〇/硬门禁**，不要只读到「二进制失败再回退」那一段。

## 独立发布方式

### 1. 随 ArkAnalyzer-HapRay 仓库发布（Skill 分发推荐）

Skill 与主仓库同版本迭代；用户获取 skill 后，将某一 skill **复制或软链**到本机 Agent skills 目录即可。

- 对 `hapray`：运行时优先从 Release 下载对应平台的最新二进制包；若下载失败或二进制不可运行，自动回退到源码下载并执行原有流程。

- **Cursor（用户目录）**：复制到 `~/.cursor/skills/<skill-name>/`。
- **Codex**：复制到 `$CODEX_HOME/skills/<skill-name>/`（默认 `~/.codex/skills`）。

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
- **`hapray/SKILL.md` YAML `version`**：与当前对外 **GitCode Release 锚定 tag**（如 `v1.5.4`）对齐，用于「不可解析 latest」时的直链回退；发新版 Release 后须同步改该字段及正文示例直链。

## 维护清单（发布前）

- [ ] `SKILL.md` 的 `description` 含足够触发词（HapRay、鸿蒙性能、perf、HAP、SO/LTO 等）。
- [ ] `hapray/SKILL.md` 顶部 `version` 与 GitCode 当前 Release tag 一致；下载示例 URL 已核对。
- [ ] 命令与 `README.md`、`docs/使用说明.md` 一致；契约参数见 `docs/工具契约式输入输出方案.md`。
- [ ] 若 CLI 有破坏性变更，同步更新本目录下对应 skill。
