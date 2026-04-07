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

## 独立发布方式

### 1. 随 ArkAnalyzer-HapRay 仓库发布（推荐）

Skill 与主仓库同版本迭代；用户只克隆仓库后，将某一 skill **复制或软链**到本机 Agent skills 目录即可。

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

## 维护清单（发布前）

- [ ] `SKILL.md` 的 `description` 含足够触发词（HapRay、鸿蒙性能、perf、HAP、SO/LTO 等）。
- [ ] 命令与 `README.md`、`docs/使用说明.md` 一致；契约参数见 `docs/工具契约式输入输出方案.md`。
- [ ] 若 CLI 有破坏性变更，同步更新本目录下对应 skill。
