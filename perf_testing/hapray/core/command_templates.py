"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Template for basic performance collection command
PERF_CMD_TEMPLATE = (
    '{cmd} {pids} --call-stack dwarf --kernel-callchain -f 1000 '
    '--cpu-limit 100 -e {event} --enable-debuginfo-symbolic '
    '--clockid boottime -m 1024 -d {duration} {output_path}'
)

# Plugin configuration templates (defined before templates that use them)
FTRACE_PLUGIN_CONFIG = """# ftrace plugin configuration
plugin_configs {
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {
    # ftrace events
    ftrace_events: "sched/sched_switch"
    ftrace_events: "power/suspend_resume"
    ftrace_events: "sched/sched_wakeup"
    ftrace_events: "sched/sched_wakeup_new"
    ftrace_events: "sched/sched_waking"
    ftrace_events: "sched/sched_process_exit"
    ftrace_events: "sched/sched_process_free"
    ftrace_events: "task/task_newtask"
    ftrace_events: "task/task_rename"
    ftrace_events: "power/cpu_frequency"
    ftrace_events: "power/cpu_idle"

    # hitrace categories
    hitrace_categories: "ability"
    hitrace_categories: "ace"
    hitrace_categories: "app"
    hitrace_categories: "ark"
    hitrace_categories: "binder"
    hitrace_categories: "disk"
    hitrace_categories: "freq"
    hitrace_categories: "graphic"
    hitrace_categories: "idle"
    hitrace_categories: "irq"
    hitrace_categories: "memreclaim"
    hitrace_categories: "mmc"
    hitrace_categories: "multimodalinput"
    hitrace_categories: "notification"
    hitrace_categories: "ohos"
    hitrace_categories: "pagecache"
    hitrace_categories: "rpc"
    hitrace_categories: "sched"
    hitrace_categories: "sync"
    hitrace_categories: "window"
    hitrace_categories: "workq"
    hitrace_categories: "zaudio"
    hitrace_categories: "zcamera"
    hitrace_categories: "zimage"
    hitrace_categories: "zmedia"

    # Buffer configuration
    buffer_size_kb: 204800
    flush_interval_ms: 1000
    flush_threshold_kb: 4096
    parse_ksyms: true
    clock: "boot"
    trace_period_ms: 200
    debug_on: false
  }
}"""

# Template for combined trace and performance collection command
# Note: ftrace_config placeholder will be replaced with indented FTRACE_PLUGIN_CONFIG
TRACE_PERF_CMD_TEMPLATE = """hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# Session configuration
 request_id: 1
 session_config {{
  buffers {{
   pages: 16384
  }}
 }}

{ftrace_config}

# hiperf plugin configuration
 plugin_configs {{
  plugin_name: "hiperf-plugin"
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{record_args}"
  }}
 }}
CONFIG"""

# Native Memory 配置模板 - 应用级采集（固定参数，只有 expand_pids 动态替换）
NATIVE_MEMORY_CONFIG = """hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
request_id: 1
session_config {{
  buffers {{
    pages: 16384
  }}
}}
plugin_configs {{
  plugin_name: "nativehook"
  sample_interval: 5000
  config_data {{
    save_file: false
    smb_pages: 16384
    max_stack_depth: {max_stack_depth}
    string_compressed: true
    fp_unwind: true
    blocked: true
    callframe_compress: true
    record_accurately: true
    offline_symbolization: true
    startup_mode: false
    malloc_free_matching_interval: 10
{expand_pids}
  }}
}}
CONFIG"""

# Collection mode constants
COLLECTION_MODE_TRACE_PERF_MEMORY = 'trace_perf_memory'
COLLECTION_MODE_MEMORY_ONLY = 'memory_only'
COLLECTION_MODE_TRACE_PERF = 'trace_perf'
COLLECTION_MODE_PERF_ONLY = 'perf_only'

# File name constants
FILENAME_PIDS_JSON = 'pids.json'
FILENAME_PERF_DATA = 'perf.data'
FILENAME_TRACE_HTRACE = 'trace.htrace'
FILENAME_REDUNDANT_FILE = 'redundant_file.txt'
FILENAME_BJC_COV = 'bjc_cov.json'
FILENAME_PERF_JSON = 'perf.json'

# Directory structure constants
DIR_HIPERF = 'hiperf'
DIR_HTRACE = 'htrace'
DIR_UI = 'ui'

# Process info constants
PROC_MAPS_PATH_TEMPLATE = '/proc/{pid}/maps'
REDUNDANT_FILE_PATH_TEMPLATE = 'data/app/el2/100/base/{app_package}/files/{app_package}_redundant_file.txt'
COVERAGE_FILE_PATH_TEMPLATE = 'data/app/el2/100/base/{app_package}/haps/{module_name}/cache/bjc*'
