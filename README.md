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
- [HAP静态分析器](staticanalyzer/README.md) - HAP Static Analysis Tool

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
The tool provides eight main commands: `perf` for performance testing, `opt` for optimization detection, `static` for HAP static analysis, `update` for updating existing reports, `compare` for report comparison, `prepare` for simplified test execution, `hilog` for hilog analysis, and `gui-agent` for AI-powered phone automation.

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
- `--no-perf`: Disable perf capturing (for memory-only mode)
- `--memory`: Enable Memory profiling using hiprofiler nativehook plugin
- `--snapshot`: Enable ArkTs heap snapshot collection
- `--devices <device_serial_numbers...>`: Device serial numbers (e.g., HX1234567890)
- `--manual`: Enable manual testing mode with interactive 30-second performance data collection
- `--app`: Target application bundle name for manual testing (performance data will be collected for 30 seconds)

Requirements:
- hdc and node must be in PATH (from Command Line Tools for HarmonyOS)

Example:
```bash
# Run specific test cases with symbol files
python -m scripts.main perf --run_testcases ".*_xhs_.*" ".*_jingdong_0010" --so_dir debug_symbols

# Run specific test cases sample CPU cycles
python -m scripts.main perf --run_testcases ".*_xhs_.*" ".*_jingdong_0010" --circles

# Run manual testing
python -m scripts.main perf --manual --app your_app_bundle_name

# Memory profiling (memory only)
python -m scripts.main perf --run_testcases ".*_xhs_.*" --memory --no-trace --no-perf

# Mixed collection: perf + trace + memory
python -m scripts.main perf --run_testcases ".*_xhs_.*" --memory

# Mixed collection: perf + memory (no trace)
python -m scripts.main perf --run_testcases ".*_xhs_.*" --memory --no-trace
```

**Memory Collection Modes:**
1. **Memory Only**: Use `--memory --no-trace --no-perf` to collect only Memory data
2. **Perf + Trace + Memory**: Use `--memory` (default includes perf and trace)
3. **Perf + Memory**: Use `--memory --no-trace` to collect perf and memory without trace

The Memory profiling uses HarmonyOS hiprofiler_cmd with nativehook plugin to collect:
- Memory allocation/deallocation events
- Call stacks with configurable depth (default: 20)
- Malloc/free matching for leak detection
- Offline symbolization support

#### Simplified Test Execution (`prepare`)
```bash
python -m scripts.main prepare [options]
```
Options:
- `--run_testcases <regex_patterns...>`: Run test cases matching specified regex patterns
- `--all_0000`: Execute all test cases ending with _0000
- `--device <device_serial>`: Device serial number (e.g., HX1234567890)

Features:
- **Simplified execution**: No complex folder structure or report generation
- **Quick testing**: Focus on test script logic execution only
- **No retry mechanism**: Avoid unnecessary repeated execution
- **Temporary output**: Uses temporary directories, auto-cleanup after execution
- **One-click execution**: Support for running all _0000 test cases

Example:
```bash
# Execute specific test case
python -m scripts.main prepare --run_testcases ResourceUsage_PerformanceDynamic_jingdong_0000

# Execute all _0000 test cases
python -m scripts.main prepare --all_0000

# Execute test cases with regex patterns
python -m scripts.main prepare --run_testcases ".*_jingdong_0000*" ".*_Douyin_0000*" ".*_bilibili_0000*"

# Execute on specific device
python -m scripts.main prepare --run_testcases ResourceUsage_PerformanceDynamic_jingdong_0000 --device HX1234567890
```

#### Optimization Detection (`opt`)
```bash
python -m scripts.main opt -i <input> -o <output> [options]
```
Options:
- `-i/--input <path>`: Directory/file containing binaries (.hap/.hsp/.apk/.so/.a)
- `-o/--output <path>`: Output report path (default: binary_analysis_report.xlsx)
- `-j/--jobs <N>`: Number of parallel jobs (default: 1)
- `-r/--report_dir <path>`: Directory containing reports to analye invoked symbols (optional)
- `--no-opt`: Disable optimization level (Ox) detection (default: enabled)
- `--no-lto`: Disable LTO (Link-Time Optimization) detection (default: enabled)

**Default behavior**: Both Ox and LTO detection are enabled. Use `--no-opt` or `--no-lto` to disable them.

Example:
```bash
# Analyze binaries with 4 parallel jobs (Ox + LTO both enabled by default)
python -m scripts.main opt -i build_output/ -o optimization_report.xlsx -j4

# Disable Ox detection, only run LTO detection
python -m scripts.main opt -i build_output/ -o lto_only_report.xlsx --no-opt -j4

# Disable LTO detection, only run Ox detection
python -m scripts.main opt -i build_output/ -o ox_only_report.xlsx --no-lto -j4

# Analyze binaries and analyze invoked symbols (Ox + LTO both enabled)
python -m scripts.main opt -i build_output/ -o optimization_report.xlsx -r existing_reports/

# Analyze APK file (Ox + LTO both enabled by default)
python -m scripts.main opt -i app-release.apk -o apk_analysis_report.xlsx -j4

# Analyze multiple APK files in a directory
python -m scripts.main opt -i apk_files/ -o multi_apk_report.xlsx -j4
```
For more detailed information about Optimization Detection, please refer to [so编译优化收益和配置指南](docs/so编译优化收益和配置指南.md)

#### Static Analysis (`static`)
```bash
python -m scripts.main static -i <hap_file> [-o <output_directory>] [options]
```
Options:
- `-i/--input <path>`: HAP file path to analyze (required)
- `-o/--output <path>`: Output directory for analysis results (default: ./static-output)
- `--include-details`: Include detailed analysis information

Features:
- **Framework Detection**: Automatically identifies technology stacks (React Native, Flutter, Unity, etc.)
- **SO File Analysis**: Deep analysis of native libraries and their optimization opportunities
- **Resource Analysis**: Comprehensive scanning of JavaScript, images, and other resources
- **Hermes Bytecode Detection**: Specialized detection for React Native Hermes engine bytecode
- **Nested Archive Support**: Recursive analysis of compressed files within HAP packages

Example:
```bash
# Generate all output formats
python -m scripts.main static -i app.hap -o ./static-output
```

#### Update Reports (`update`)
```bash
python -m scripts.main update --report_dir <report_directory> [--so_dir <so_directory>]
```
Options:
- `--report_dir <path>`: Directory containing existing reports to update (required)
- `--so_dir <path>`: Directory containing updated symbolicated .so files (optional)
- `--mode <int>`: Select mode: 0 COMMUNITY, 1 SIMPLE
- `--perfs <path1> <path2> ...`: Multiple perf data paths (required for SIMPLE mode)
- `--traces <path1> <path2> ...`: Multiple trace file paths (required for SIMPLE mode)
- `--package-name <package_name>`: Application package name (required for SIMPLE mode)
- `--pids <N+>`: Process IDs (optional for SIMPLE mode)
- `--steps <path>`: Path to custom steps.json file (optional for SIMPLE mode)
- `--time-ranges <range1> <range2> ...`: Time range filters in format "startTime-endTime" (nanoseconds), supports multiple ranges (optional)
- `--hapflow <homecheck path>`: Run HapFlow post-processing using the exact Homecheck project root you provide (no auto-search).


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

#### GUI Agent Automation (`gui-agent`)
```bash
python -m scripts.main gui-agent [options]
```
Options:
- `--apps <package1> [package2] ...`: Application package names (required, supports multiple packages)
- `--scenes <scene1> [scene2] ...`: Multiple scenes to execute (optional, natural language descriptions). If not specified, scenes will be automatically loaded from config.yaml based on app category
- `--glm-base-url <url>`: LLM API base URL (default: http://localhost:8000/v1, env: GLM_BASE_URL)
- `--glm-model <name>`: Model name (default: autoglm-phone-9b, env: GLM_MODEL)
- `--glm-api-key <key>`: API key for model authentication (env: GLM_API_KEY)
- `--max-steps <N>`: Maximum steps per task (default: 20)
- `--device-id <id>`: Device ID for multi-device setups
- `-o/--output <path>`: Base path to save step data (default: current directory, creates timestamped reports subdirectory)

Features:
- **AI-powered automation**: Uses LLM to understand and execute natural language scenes
- **Multi-app and multi-scene execution**: Support for testing multiple applications, each with multiple scenes
- **Automatic scene categorization**: Automatically categorizes apps (ecommerce, finance, travel, video, etc.) and loads predefined scenes from config.yaml
- **Step data collection**: Automatically collects UI data after each step (screenshots, element trees, perf/trace, hilog)
- **Real-time analysis**: Parallel analysis process for performance analysis and report generation
- **Automatic report organization**: Data is saved in `output/reports/TIMESTAMP/<app_package>/scene<ID>/` structure

Environment Variables:
- `GLM_BASE_URL`: Model API base URL (default: http://localhost:8000/v1)
- `GLM_API_KEY`: API key for model authentication
- `GLM_MODEL`: Model name (default: autoglm-phone-9b)

**Using Third-Party Model Services**:

If you don't want to deploy the model yourself, you can use the following third-party services that have our model deployed:

**1. 智谱 BigModel (ZhipuAI BigModel)**

- Documentation: https://docs.bigmodel.cn/cn/api/introduction
- `--glm-base-url`: `https://open.bigmodel.cn/api/paas/v4`
- `--glm-model`: `autoglm-phone`
- `--glm-api-key`: Apply for your API Key on the 智谱 platform

```bash
python -m scripts.main gui-agent --app com.tencent.mm \
  --glm-base-url "https://open.bigmodel.cn/api/paas/v4" \
  --glm-model "autoglm-phone" \
  --glm-api-key "your-zhipu-api-key" \
  --output ./
```

**2. ModelScope (魔搭社区)**

- Documentation: https://modelscope.cn/models/ZhipuAI/AutoGLM-Phone-9B
- `--glm-base-url`: `https://api-inference.modelscope.cn/v1`
- `--glm-model`: `ZhipuAI/AutoGLM-Phone-9B`
- `--glm-api-key`: Apply for your API Key on the ModelScope platform

```bash
python -m scripts.main gui-agent --app com.tencent.mm \
  --glm-base-url "https://api-inference.modelscope.cn/v1" \
  --glm-model "ZhipuAI/AutoGLM-Phone-9B" \
  --glm-api-key "your-modelscope-api-key" \
  --output ./
```

**Basic Usage Examples**:
```bash
# Test single app with auto-loaded scenes (from config.yaml based on app category)
python -m scripts.main gui-agent --app com.example.shopping --output ./

# Test multiple apps
python -m scripts.main gui-agent --app com.example.app1 com.example.app2 --output ./

# Test with custom scenes
python -m scripts.main gui-agent --app com.example.app \
  --scenes "浏览首页，切换至少 3 个 Tab" "使用搜索功能搜索商品" --output ./

# With custom model configuration
python -m scripts.main gui-agent --app com.example.app \
  --glm-base-url "http://your-server:8000/v1" \
  --glm-model "your-model" \
  --glm-api-key "your-api-key" \
  --output ./

# Using environment variables
export GLM_BASE_URL="http://localhost:8000/v1"
export GLM_API_KEY="your-api-key"
export GLM_MODEL="autoglm-phone-9b"
python -m scripts.main gui-agent --app com.example.app --output ./

# Execute on specific device
python -m scripts.main gui-agent --app com.example.app --device-id HX1234567890 --output ./

# Limit execution steps
python -m scripts.main gui-agent --app com.example.app --max-steps 10 --output ./
```

**Scene Configuration**:

If you don't specify `--scenes`, the tool automatically categorizes apps based on package names and loads predefined scenes from `config.yaml`. Supported categories include:
- `ecommerce`: E-commerce apps (taobao, tmall, jd, etc.)
- `finance`: Finance apps (alipay, bank apps, etc.)
- `travel`: Travel apps (amap, ctrip, etc.)
- `video`: Video apps (douyin, kuaishou, bilibili, etc.)
- `audio_reading`: Audio/reading apps (qqmusic, ximalaya, etc.)
- `social`: Social apps (weibo, wechat, xiaohongshu, etc.)
- `productivity`: Productivity tools (dingtalk, wps, etc.)
- `news`: News apps
- `photo_video_edit`: Photo/video editing apps
- `education`: Education apps
- `default`: Default scenes for other apps

Scene configuration location: `perf_testing/hapray/core/config/config.yaml`
Configuration node: `gui-agent.scenes.<category>`

**Output Structure**:
```
output/
└── reports/
    └── YYYYMMDDHHMMSS/          # Timestamp directory
        ├── <app_package_1>/
        │   ├── scene1/
        │   │   ├── steps.json          # Step information
        │   │   ├── testInfo.json       # Test metadata
        │   │   ├── hiperf/             # Performance data
        │   │   ├── htrace/             # Trace data
        │   │   └── report/              # Analysis reports
        │   │       ├── hapray_report.html
        │   │       ├── hapray_report.json
        │   │       └── hapray_report.db
        │   └── scene2/
        └── <app_package_2>/
            └── scene1/
```

#### Hilog Analysis (`hilog`)
```bash
python -m scripts.main hilog -d <hilog_directory> [-o <output_excel>]
```
Options:
- `--hilog-dir <path>`: Directory containing hilog files or single hilog file path (required)
- `--output <path>`: Output Excel file path (default: hilog_analysis.xlsx)

Features:
- **Automatic hilog decryption**: Uses hilogtool to decrypt encrypted hilog files
- **Configurable pattern matching**: Supports complex regex patterns with grouping
- **Conditional filtering**: Applies conditions to extracted groups for precise matching
- **Comprehensive reporting**: Generates Excel reports with summary statistics and detailed matches

**Configuration**:
Hilog analysis rules are configured in `perf_testing/hapray/core/config/config.yaml` under the `hilog.patterns` section:

```yaml
hilog:
  patterns:
    # Example rule: Match memory type != 4 (DMA_ALLOC)
    - name: "图片解码没有使用DMA(memType!=4)"
      regex: "CreatePixelMap success,.*memType\\s*:\\s*(\\d+),\\s*cost\\s+\\d+\\s+us"
      groups: [1]  # Extract memory type value
      conditions: ["!=4"]  # Only count when memory type != 4
```

**Pattern Configuration**:
- `name`: Rule name for identification and Excel sheet naming
- `regex`: Regular expression with capture groups
- `groups`: Array of group indices to extract (1-based, 0 for entire match)
- `conditions`: Condition filtering, supports two formats:
  1. **Array format**: Corresponds to groups one-to-one, supports operators: `==`, `!=`, `<`, `>`, `<=`, `>=`
  2. **Expression string**: Supports mathematical operations and comparisons (automatically detected when contains `$`)

**Expression Syntax** (when using `conditions` as expression string):
- `$1`, `$2`, `$3`... represent the 1st, 2nd, 3rd... extracted group values (corresponding to positions in `groups` array)
- Supports mathematical operations: `+`, `-`, `*`, `/`, `%`
- Supports comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Supports parentheses: `()`
- Supports multiple expressions (AND logic): Use comma (`,`) or `&&` to separate expressions. All expressions must be satisfied.

**Examples**:
```yaml
# Array format (simple conditions)
- name: "Memory type != 4"
  regex: "CreatePixelMap success,.*memType\\s*:\\s*(\\d+)"
  groups: [1]
  conditions: ["!=4"]  # Group 1 != 4

# Expression format (complex calculations)
- name: "Compare width*height products"
  regex: "width\\s*:\\s*(\\d+).*height\\s*:\\s*(\\d+).*width2\\s*:\\s*(\\d+).*height2\\s*:\\s*(\\d+)"
  groups: [1, 2, 3, 4]  # Extract: width1, height1, width2, height2
  conditions: "$1 * $2 > $3 * $4"  # Product of first pair > product of second pair

# Multiple expressions (AND logic)
- name: "Multiple conditions"
  regex: "value1\\s*:\\s*(\\d+).*value2\\s*:\\s*(\\d+).*value3\\s*:\\s*(\\d+).*value4\\s*:\\s*(\\d+)"
  groups: [1, 2, 3, 4]
  conditions: "$1*$2>0,$3*$4>512*512"  # Using comma separator: $1*$2>0 AND $3*$4>512*512
  # Or use && separator: conditions: "$1*$2>0 && $3*$4>512*512"
```

Example:
```bash
# Analyze hilog files in a directory
python -m scripts.main hilog --hilog-dir hilog_files/ --output analysis_report.xlsx

```

### Guide: Running Release Program on macOS

When you download the release package (ZIP file) and extract it, macOS may mark the files with a quarantine attribute that prevents execution. You need to remove this attribute before running the program.

#### Using the Helper Script
The release package includes a helper script `run_macos.sh` that automatically removes quarantine attributes from all files in the extracted directory:

```bash
# Extract the ZIP file
unzip ArkAnalyzer-HapRay-darwin-arm64.zip

# Navigate to the extracted directory
cd ArkAnalyzer-HapRay-darwin-arm64  # or the actual directory name

# Remove quarantine attributes
./run_macos.sh
```

The script will:
1. Automatically remove quarantine attributes from all files in the current directory
2. You can then run the executable program directly

After removing quarantine attributes, you can run the executable:
```bash
# Run GUI version
./ArkAnalyzer-HapRay-GUI

# Run CLI version
./ArkAnalyzer-HapRay
```

> **Note:** The `run_macos.sh` script is included in the release package. If you don't see it after extraction, make sure the ZIP file was extracted completely.

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


