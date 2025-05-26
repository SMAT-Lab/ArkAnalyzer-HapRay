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

## Release
```
npm run release
```

## Usage Guide

### Dependencies
- pip > 23.0.1
- Python 3.9 ~ 3.12
- [Command Line Tools for HarmonyOS](https://developer.huawei.com/consumer/cn/download/) > 5.0.5

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
    git-lfs \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev

# Add Command Line Tools for HarmonyOS to PATH
# export command_line_tools=[Command Line Tools for HarmonyOS] directory
export PATH=$PATH:$command_line_tools/tool/node/bin:$command_line_tools/sdk/default/openharmony/toolchains
```
### MacOS Dependencies
```bash
brew install git git-lfs python@3.12

# Add Command Line Tools for HarmonyOS to PATH
# export command_line_tools=[Command Line Tools for HarmonyOS] directory
export PATH=$PATH:$command_line_tools/tool/node/bin:$command_line_tools/sdk/default/openharmony/toolchains
```

### Mac & Linux Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install

# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
source .venv/bin/activate
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main
```

### Windows Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install

# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
# Command-Line(CMD) Alternative the python virtual environment
.venv\Scripts\activate.bat
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main
```