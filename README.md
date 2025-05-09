# ArkAnalyzer-HapRay
Code-oriented Performance Analysis for OpenHarmony Apps

## build

```
npm install
npm run build
```

----

## Mac & Linux 使用指导

### Ubuntu 系统下的系统基础依赖安装

```bash
# 可选配置 ubuntu-22.04 mirror 源加速配置
sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list
sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list
[setup.sh](setup.sh)
# 可选配置 ubuntu-24.04 mirror 源加速配置
sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list.d/ubuntu.sources
sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list.d/ubuntu.sources

apt-get update && \
apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    unzip
```

### Mac & Linux 安装使用

```bash
# 初始化环境，仅需要执行一次
git clone https://github.com/SMAT-Lab/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
./setup.sh

# 每次运行测试前执行（需要先切换到 ArkAnalyzer-HapRay 目录）
source .venv/bin/activate
cd perf_testing
# 根据需要配置 config.yaml 测试用例，不要跑的用例，可以删除或在开头用`#`注释掉
python main.py
```
