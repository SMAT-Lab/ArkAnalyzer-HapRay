# ArkAnalyzer-HapRay
Code-oriented Performance Analysis for OpenHarmony Apps

## Introduction
ArkAnalyzer-HapRay is a tool designed for performance analysis of OpenHarmony applications. It provides detailed insights into app performance, helping developers optimize their applications for better user experience.

## Documentation
For more detailed information, please refer to the following documents:
- [使用前准备](docs/使用说明.md) - Pre-Use Preparation
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

### Command Line Usage
The tool provides three main commands: `perf` for performance testing, `opt` for optimization detection, and `update` for updating existing reports.

#### Performance Testing (`perf`)
```bash
python -m scripts.main perf [options]
```
Options:
- `--run_testcases <regex_patterns...>`: Run test cases matching specified regex patterns
- `--so_dir <directory>`: Directory containing symbolicated .so files
- `--circles`: Sample CPU cycles instead of default events
- `--round <N>`: Number of test rounds to execute (default: 5)
- `--no-trace`: Disable trace capturing

Requirements:
- hdc and node must be in PATH (from Command Line Tools for HarmonyOS) 
  
Example:
```bash
# Run specific test cases with symbol files
python -m scripts.main perf --run_testcases .*_xhs_.* .*_jingdong_0010 --so_dir debug_symbols

# Run specific test cases sample CPU cycles
python -m scripts.main perf --run_testcases .*_xhs_.* .*_jingdong_0010 --circles
```

#### Optimization Detection (`opt`)
```bash
python -m scripts.main opt -i <input> -o <output> [options]
```
Options:
- `-i/--input <path>`: Directory/file containing binaries (.hap/.hsp/.so/.a)
- `-o/--output <path>`: Output report path (default: binary_analysis_report.xlsx)
- `-j/--jobs <N>`: Number of parallel jobs (default: 1)
- `-r/--report_dir <path>`: Directory containing reports to analye invoked symbols (optional)

Example:
```bash
# Analyze binaries with 4 parallel jobs
python -m scripts.main opt -i build_output/ -o optimization_report.xlsx -j4
# Analyze binaries and analye invoked symbols
python -m scripts.main opt -i build_output/ -o optimization_report.xlsx -r existing_reports/
```

#### Update Reports (`update`)
```bash
python -m scripts.main update --report_dir <report_directory> [--so_dir <so_directory>]
```
Options:
- `--report_dir <path>`: Directory containing existing reports to update (required)
- `--so_dir <path>`: Directory containing updated symbolicated .so files (optional)

Example:
```bash
# Update existing reports with new symbol files
python -m scripts.main update --report_dir reports/20240605120000 --so_dir updated_symbols

# Update reports without changing symbol files
python -m scripts.main update --report_dir reports/20240605120000
```

### Dependencies
- pip > 23.0.1
- Python 3.9 ~ 3.12, 
- [Command Line Tools for HarmonyOS](https://developer.huawei.com/consumer/cn/download/) > 5.0.5

> ⚠️ Please make sure that the default `python` command in your terminal points to a valid Python interpreter in the 3.9 ~ 3.12 range.
> You can verify this by running:
> ```bash
> python --version
> ```

> ⚠️ When using `pip` to install dependencies, please ensure that your Python package source is reachable from your network.  
> We recommend configuring a mirror (e.g., Tsinghua or Huawei Cloud) if needed.

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
brew install git git-lfs python@3.11

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
npm run build
# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
source .venv/bin/activate
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main perf/opt/update [options]
# Run pylint
tox -e lint
```

### Windows Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install
npm run build
# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
# Command-Line(CMD) Alternative the python virtual environment
.venv\Scripts\activate.bat
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main perf/opt/update [options]
# Run pylint
tox -e lint
```

## Detailed Explanation of the config.yaml configuration File in perf_testing:

### 1.Preset testcases
```yaml
run_testcases:
 - .*_xhs_.* # Run all test cases of xhs
```

### 2.After setting the so_dir parameter, the import with the symbol so can be supported. This address is the storage path of the.so files in the debug package or the release package
```yaml
so_dir: xxx
```

### 3. Custom Performance Load Source Identification (kind configuration)

```yaml
kind:
  - 
    name: '' # Category name Category name (e.g., Lynx)
    files:
      - xx # File classification regular expressions
    threads:
      - xx # Thread classification regular expressions
```
Explanation:

The `kind` configuration allows you to define custom categories for performance load sources. Each entry in the `kind` list should have:
- `name`: A descriptive name for the category (e.g., KMP, Lynx)
- `files`: A list of regular expressions to match file paths associated with this category
- `threads`: Additionally, you can optionally specify `threads` to match thread names.

Example:
```yaml
kind:
  - 
    name: RN
    files: 
      - /proc/.*librncore\.so$
    threads:
      - "RN.*Worker"
      - "ReactNative.*"
```

### 4.If both config.yaml is configured and parameters are passed in the command line, with the parameters passed in the command line being the main one, the two parameters can be merged:
```
  Use case 1 is passed through the command line, and use case 2 is configured in the configuration file. Eventually, both use cases will be executed.
```

## About Flame diagram

### start HiSmartPerf server:

#### third-party/HiSmartPerf_20250109/main.exe
#### third-party/HiSmartPerf_20250109/main_darwin
#### third-party/HiSmartPerf_20250109/main_linux


