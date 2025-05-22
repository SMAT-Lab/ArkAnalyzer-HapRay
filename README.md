# ArkAnalyzer-HapRay
Code-oriented Performance Analysis for OpenHarmony Apps

## Introduction
ArkAnalyzer-HapRay is a tool designed for performance analysis of OpenHarmony applications. It provides detailed insights into app performance, helping developers optimize their applications for better user experience.

## Documentation
For more detailed information, please refer to the following documents:
- [使用说明](docs/使用说明.md) - Usage Guide
- [工具介绍](docs/工具介绍.md) - Tool Introduction
- [收益测试分析](docs/收益测试分析.md) - Performance Test Analysis
- [用例执行预置条件](docs/用例执行预置条件.md) - Test Case Prerequisites

## Build
```
npm install
npm run build
```

## Usage Guide

### Dependencies
- pip > 23.0.1
- Python > 3.10

### Ubuntu System Dependencies
```bash
# Optional: Configure ubuntu-22.04 mirror for faster downloads
sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list
sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list

# Optional: Configure ubuntu-24.04 mirror for faster downloads
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

### Mac & Linux Installation
```bash
# Initialize environment (only needed once)
git clone https://github.com/SMAT-Lab/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
./setup.sh

# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
source .venv/bin/activate
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main
```
