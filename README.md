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
- [鸿蒙应用覆盖率](docs/鸿蒙应用覆盖率.md) - ArkTs Coverage Analysis
- [so编译优化收益和配置指南](docs/so编译优化收益和配置指南.md) - SO Optimization Detection

## Build
```
npm install
npm run build
```

## Release
```
npm run release
```

## Lint
```
npm run lint
```

## Usage Guide

### Command Line Usage
The tool provides four main commands: `perf` for performance testing, `opt` for optimization detection, `update` for updating existing reports, and `compare` for report comparison.

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
- `--devices <device_serial_numbers...>`: Device serial numbers (e.g., HX1234567890)

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
For more detailed information about Optimization Detection, please refer to [so编译优化收益和配置指南](docs/so编译优化收益和配置指南.md)

#### Update Reports (`update`)
```bash
python -m scripts.main update --report_dir <report_directory> [--so_dir <so_directory>]
```
Options:
- `--report_dir <path>`: Directory containing existing reports to update (required)
- `--so_dir <path>`: Directory containing updated symbolicated .so files (optional)
- `--mode <int>`: Select mode: 0 COMMUNITY, 1 COMPATIBILITY, 2 SIMPLE
- `--perfs <path1> <path2> ...`: Multiple perf data paths (required for SIMPLE mode)
- `--traces <path1> <path2> ...`: Multiple trace file paths (required for SIMPLE mode)
- `--package-name <package_name>`: Application package name (required for SIMPLE mode)
- `--pids <N+>`: Process IDs (optional for SIMPLE mode)
- `--steps <path>`: Path to custom steps.json file (optional for SIMPLE mode)
- `--time-ranges <range1> <range2> ...`: Time range filters in format "startTime-endTime" (nanoseconds), supports multiple ranges (optional)

Example:
```bash
# COMMUNITY mode
# Update existing reports with new symbol files
python -m scripts.main update --report_dir reports/20240605120000 --so_dir updated_symbols

# Update reports without changing symbol files
python -m scripts.main update --report_dir reports/20240605120000

# SIMPLE mode - Multiple files (auto-generate steps.json)
python -m scripts.main update --report_dir reports/20240605120000 --mode 2 --perfs perf1.data perf2.data --traces trace1.htrace trace2.htrace --package-name com.jd.hm.mall --pids 1 2 3

# SIMPLE mode - Multiple files with custom steps.json
python -m scripts.main update --report_dir reports/20240605120000 --mode 2 --perfs perf1.data perf2.data --traces trace1.htrace trace2.htrace --package-name com.jd.hm.mall --steps /path/to/custom_steps.json

# SIMPLE mode with time range filtering
python -m scripts.main update --report_dir reports/20240605120000 --mode 2 --perfs perf.data --traces trace.htrace --package-name com.jd.hm.mall --time-ranges "12835982205508-12843345730507"

```

#### Compare Reports (`compare`)
```bash
python -m scripts.main compare --base_dir <base_report_directory> --compare_dir <compare_report_directory> [--output <output_excel>]
```
Options:
- `--base_dir <path>`: Directory containing baseline reports (required)
- `--compare_dir <path>`: Directory containing reports to compare (required)
- `--output <path>`: Output Excel file path (default: compare_result.xlsx in current dir)

Example:
```bash
# Specify output file
python -m scripts.main compare --base_dir reports/base/ --compare_dir reports/compare/ --output my_compare.xlsx
```

### Guide: Running Release Program on macOS
1. Open Terminal (Applications > Utilities)
2. Grant Execution Permission
```bash
chmod +x /path/to/ArkAnalyzer-HapRay
```
3. Remove Quarantine Attribute
macOS marks downloaded files with a security flag. Remove it with:
```bash
sudo xattr -r -d com.apple.quarantine /path/to/ArkAnalyzer-HapRay
```
Replace /path/to/ArkAnalyzer-HapRay with your actual program path
Enter your administrator password when prompted

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
# Activate the python virtual environment perf_testing/.venv
source activate.sh
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main perf/opt/update [options]
```

### Windows Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install
npm run build
# Command-Line(CMD) Alternative the python virtual environment perf_testing/.venv
activate.bat
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main perf/opt/update [options]
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

## Starting HiSmartPerf Server

To launch the HiSmartPerf web server, execute the appropriate binary for your operating system:

| Operating System | Command                                       |
|------------------|----------------------------------------------|
| Windows          | `third-party/HiSmartPerf_20250109/main.exe`  |
| macOS            | `third-party/HiSmartPerf_20250109/main_darwin`|
| Linux            | `third-party/HiSmartPerf_20250109/main_linux`|

After successful startup, access the analysis interface at:  
`https://localhost:9000/application/`


