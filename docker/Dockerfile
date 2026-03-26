# syntax=docker/dockerfile:1
# 与 .nvmrc / package.json engines / uv 一致；业务工具请通过挂载仓库使用，不打入镜像。

ARG NODE_VERSION=24.14.1
ARG NODE_DIST_DIR=node-v24.14.1-linux-x64

FROM ubuntu:22.04

ARG NODE_VERSION
ARG NODE_DIST_DIR

LABEL org.opencontainers.image.title="HapRay"
LABEL org.opencontainers.image.description="ArkAnalyzer-HapRay toolchain: Node, uv, Rust (stable)"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# rustup / rustc 下载走中科大镜像，避免 static.rust-lang.org 超时或 SSL 中断
ENV RUSTUP_DIST_SERVER=https://mirrors.ustc.edu.cn/rust-static \
    RUSTUP_UPDATE_ROOT=https://mirrors.ustc.edu.cn/rust-static/rustup

# amd64 走 archive/security；arm64 走 ports.ubuntu.com，须改为华为云 ubuntu-ports。BuildKit 缓存加速重复 apt。
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list; \
      sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list; \
      sed -i "s@http://ports.ubuntu.com/ubuntu-ports@http://mirrors.huaweicloud.com/ubuntu-ports@g" /etc/apt/sources.list; \
      sed -i "s@https://ports.ubuntu.com/ubuntu-ports@http://mirrors.huaweicloud.com/ubuntu-ports@g" /etc/apt/sources.list; \
    fi; \
    if [ -d /etc/apt/sources.list.d ]; then \
      find /etc/apt/sources.list.d -name "*.list" -type f -exec sed -i \
        -e "s@http://ports.ubuntu.com/ubuntu-ports@http://mirrors.huaweicloud.com/ubuntu-ports@g" \
        -e "s@https://ports.ubuntu.com/ubuntu-ports@http://mirrors.huaweicloud.com/ubuntu-ports@g" \
        {} \; ; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    unzip \
    usbutils \
    vim \
    wget \
    file \
    build-essential \
    pkg-config \
    libssl-dev \
    libgtk-3-dev \
    libwebkit2gtk-4.1-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    libxdo-dev \
    ; \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cargo/registry,sharing=locked \
    --mount=type=cache,target=/root/.cargo/git,sharing=locked \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable \
    && /root/.cargo/bin/rustc --version \
    && /root/.cargo/bin/cargo --version

# cargo 依赖 crates.io 走中科大 sparse 索引（容器内 cargo build 时生效）
RUN mkdir -p /root/.cargo && \
    printf '%s\n' \
    '[source.crates-io]' \
    'replace-with = "ustc"' \
    '' \
    '[source.ustc]' \
    'registry = "sparse+https://mirrors.ustc.edu.cn/crates.io-index/"' \
    > /root/.cargo/config.toml

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

RUN mkdir -p /root/.config/pip && \
    printf '%s\n' '[global]' \
        'index-url = https://mirrors.huaweicloud.com/repository/pypi/simple' \
        'trusted-host = mirrors.huaweicloud.com' \
        > /root/.config/pip/pip.conf && \
    printf '%s\n' 'registry=https://registry.npmmirror.com' > /root/.npmrc

RUN mkdir -p /tools && \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz && \
    tar -xJf /tmp/node.tar.xz -C /tools && \
    rm -f /tmp/node.tar.xz && \
    test -x "/tools/${NODE_DIST_DIR}/bin/node"

ENV PATH="/tools/${NODE_DIST_DIR}/bin:/root/.cargo/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /workspace

CMD ["/bin/bash"]
