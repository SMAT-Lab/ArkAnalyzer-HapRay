# Docker 镜像（HapRay 工具链）

基于 Ubuntu 22.04，内置与仓库 **`.nvmrc`** 一致的 Node（Linux x64）、**uv**、**Rust（rustup stable）** 及与 CI 一致的 **Tauri Linux 系统库**（GTK/WebKit 等），以及 pip/npm 国内镜像配置。**`trace_streamer_binary` 等随仓库提供的工具不打包进镜像**，请在运行容器时挂载本机仓库目录，使用 **`dist/tools/`**（由 `npm run prebuild` 等生成）或 **`third-party/`** 中的路径。

构建上下文为仓库根目录 **`my-dev/`**（即 `docker` 的上一级）。

## 构建镜像

在 **`my-dev/docker/`** 下执行：

```bash
./build.sh
```

脚本会 **`docker pull ubuntu:22.04`** 并 **`docker build`**，生成 **`hapray:latest`**（Node 版本从 **`.nvmrc`** 读取并传入 `--build-arg`）。

在 **`my-dev/`** 根目录手动构建：

```bash
docker pull ubuntu:22.04
docker build \
  --build-arg NODE_VERSION="$(tr -d ' \r\n' < .nvmrc)" \
  --build-arg NODE_DIST_DIR="node-v$(tr -d ' \r\n' < .nvmrc)-linux-x64" \
  -t hapray \
  -f docker/Dockerfile \
  .
```

### 构建加速说明

- **`./build.sh`** 已设置 **`DOCKER_BUILDKIT=1`**。Dockerfile 使用 **BuildKit 缓存**（`--mount=type=cache`）缓存 **apt** 与 **cargo registry/git**，**同一台机器上重复 `docker build`** 时，未变更层会命中缓存，显著减少重复下载。
- **ARM64（如 Apple Silicon 默认构建 `linux/arm64`）** 时，系统源原为 **`ports.ubuntu.com`**（海外），镜像内已改为 **华为云 `ubuntu-ports`**，首次 **`apt-get install`** 会快很多。
- 若目标运行环境是 **x86_64 Linux** 且希望与 Dockerfile 中 **Node linux-x64** 一致，可显式指定平台（在 Intel/AMD 机器上构建通常更快）：  
  **`docker build --platform linux/amd64 ...`**（在 ARM Mac 上会走 QEMU 模拟，可能更慢，更适合在 **x86 CI** 上构建镜像）。
- 网络仍慢时：换时段、代理，或在公司内网 **registry 镜像** 旁路加速。

## 运行容器

进入交互式 shell（工作目录 **`/workspace`**）：

```bash
docker run --rm -it --privileged hapray bash
```

将本机 **`my-dev`** 挂到 **`/workspace`**，在容器内使用仓库里的 **`node_modules`**、**`dist/tools/trace_streamer_binary`** 等（需先在宿主机执行 **`npm install`**、**`npm run prebuild`** 等）：

```bash
docker run --rm -it --privileged \
  -v /绝对路径/my-dev:/workspace \
  hapray bash
```

在 **`my-dev/docker`** 目录下可写为：

```bash
docker run --rm -it --privileged \
  -v "$(cd .. && pwd):/workspace" \
  hapray bash
```

### 关于 `--privileged`

连接 USB 或部分设备调试时可能需要；纯命令行与网络场景可酌情去掉。

### 使用宿主机上的 `hdc`（容器外已安装的命令）

镜像内默认**不带** HarmonyOS **Command Line Tools** 里的 **`hdc`**。若希望**沿用宿主机已安装的 `hdc`**，本质是：把宿主机上 **`hdc` 可执行文件及其依赖库**挂进容器，并保证设备连接方式可用。

1. **挂载 SDK / 工具链目录（推荐）**  
   在宿主机找到 **`hdc` 所在目录**（通常在 **命令行工具** 安装路径下，与同级的 **`lib`** 等目录并列）。将整个上层目录挂到容器内固定路径，例如：

   ```bash
   # 将 /宿主机/SDK根目录 换成你本机真实路径（含 hdc 与依赖库）
   docker run --rm -it --privileged \
     -v "$(cd .. && pwd):/workspace" \
     -v /宿主机/SDK根目录:/opt/ohos-sdk:ro \
     hapray bash
   ```

   进入容器后：

   ```bash
   export PATH="/opt/ohos-sdk/实际包含hdc的bin路径:$PATH"
   # 若报找不到 .so，再按实际路径设置，例如：
   # export LD_LIBRARY_PATH="/opt/ohos-sdk/某lib路径:${LD_LIBRARY_PATH}"
   hdc list targets
   ```

   具体子路径以你本机 **SDK 目录结构**为准（不同版本、安装位置不一致）。

2. **USB 设备**  
   真机通过 USB 连接时，除 **`--privileged`** 外，有时还需映射 **`/dev/bus/usb`** 等，视 Docker 版本与系统而定；若仍无法识别设备，可在**宿主机**先执行 **`hdc list targets`** 确认主机侧正常，再排查容器内 **`PATH` / `LD_LIBRARY_PATH`** 与挂载是否完整。

3. **仅使用网络链路的 hdc**  
   若设备与 **`hdc`** 通过 **TCP** 等方式访问，在 **Linux** 上可尝试 **`--network host`**，使容器与宿主机网络栈一致，减少端口转发问题（**macOS Docker Desktop 上 `--network host` 行为与 Linux 不同**，需以实际环境为准）。

4. **替代做法**  
   在**宿主机**执行 **`hdc`**，容器内通过脚本、CI 或 **挂载共享目录** 交换文件与结果，避免在容器内直接跑 **`hdc`**。

## 镜像内环境说明

- **`PATH`** 包含：**Node**（`/tools/node-v…-linux-x64/bin`）、**cargo/rustc**（`/root/.cargo/bin`）、**uv**（`/root/.local/bin`）。
- **`rustc` / `cargo`**：由 **rustup** 安装 **stable**，可在容器内执行 **`cargo build`**（如 **`desktop/src-tauri`**）。
- **Rust 国内源**：镜像内已设置 **`RUSTUP_DIST_SERVER` / `RUSTUP_UPDATE_ROOT`** 指向中科大 **`rust-static`**，并在 **`/root/.cargo/config.toml`** 中将 **crates.io** 替换为 **USTC sparse** 索引，以加速 **`rustup`** 与 **`cargo`** 拉取。若需改用 **rsproxy**，可在本机 **`docker build`** 前用 **`ENV`** 覆盖或自行修改 Dockerfile 中上述变量与 **`config.toml`**。
- **`trace_streamer`**、**`sa-cmd`** 等请依赖挂载后的 **`/workspace/dist/tools/...`**，与宿主机仓库一致。

## 分发给他人使用

他人机器需已安装 **Docker**（Linux 上通常同时装 **Docker Engine**；macOS/Windows 可用 **Docker Desktop**）。常见两种方式：

### 方式一：导出文件（适合内网/U 盘/网盘）

在你本机导出镜像为压缩包：

```bash
docker save hapray:latest | gzip > hapray-image.tar.gz
```

对方导入：

```bash
gunzip -c hapray-image.tar.gz | docker load
```

导入后本地会出现 **`hapray:latest`**，按上文 **`docker run ...`** 使用即可。若导出时用了别的标签，对方 **`docker images`** 里看到的仓库名/标签以实际为准。

### 方式二：镜像仓库（适合团队长期维护）

推送到 **Docker Hub**、**Harbor**、**阿里云 ACR**、**GitHub Container Registry (ghcr.io)** 等，他人 **`docker pull`** 即可。

示例（将 **`你的命名空间/镜像名`**、**`标签`** 换成实际值）：

```bash
docker tag hapray:latest 你的命名空间/hapray:1.5.1
docker login
docker push 你的命名空间/hapray:1.5.1
```

对方：

```bash
docker pull 你的命名空间/hapray:1.5.1
docker run --rm -it --privileged 你的命名空间/hapray:1.5.1 bash
```

私有仓库需对方 **`docker login`** 到有权限的 registry。镜像体积较大时，建议配合仓库的**版本标签**与**变更说明**，便于追溯。

## 常用命令

```bash
docker images hapray
docker rmi hapray:latest
```
