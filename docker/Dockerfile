FROM ubuntu:22.04

# 设置环境变量，避免一些交互式配置问题
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/tools/node-v22.14.0-linux-x64/bin:/tools/sdk-toolchains:/tools/trace_streamer_binary/:${PATH}"

# https://mirrors.huaweicloud.com/mirrorDetail/5ea14ecab05943f36fb75ee7?mirrorName=ubuntu&catalog=os
RUN sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list && \
    sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
    git \
    python3 \
    python3-pip \
    unzip \
    usbutils \
    vim \
    && rm -rf /var/lib/apt/lists/*

COPY HapRayDep/pip.conf /root/.config/pip/pip.conf
COPY HapRayDep/npmrc /root/.npmrc
COPY HapRayDep/hypium-5.0.7.200 /tools/hypium-5.0.7.200
COPY HapRayDep/hypium_perf-5.0.7.200 /tools/hypium_perf-5.0.7.200
COPY HapRayDep/sdk-toolchains /tools/sdk-toolchains
COPY HapRayDep/trace_streamer_binary /tools/trace_streamer_binary
COPY HapRayDep/node-v22.14.0-linux-x64 /tools/node-v22.14.0-linux-x64

RUN cd /tools/hypium-5.0.7.200 && \
    pip install --no-cache-dir xdevice-5.0.7.200.tar.gz && \
    pip install --no-cache-dir xdevice-devicetest-5.0.7.200.tar.gz && \
    pip install --no-cache-dir xdevice-ohos-5.0.7.200.tar.gz && \
    pip install --no-cache-dir hypium-5.0.7.200.tar.gz && \
    rm -rf /tools/hypium-5.0.7.200

RUN cd /tools/hypium_perf-5.0.7.200 && \
    ./install.sh && \
    rm -rf /tools/hypium_perf-5.0.7.200

# 设置工作目录
WORKDIR /workspace

# 默认命令
CMD ["/bin/bash"]

