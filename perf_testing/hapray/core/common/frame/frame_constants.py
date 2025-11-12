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

"""帧分析模块常量定义

统一管理所有帧分析相关的常量，避免魔法数字和重复定义。
"""

# ==================== 帧标志定义 ====================
FLAG_NORMAL = 0  # 实际渲染帧不卡帧（正常帧）
FLAG_STUTTER = 1  # 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
FLAG_NO_DRAW = 2  # 数据不需要绘制（空帧，不参与卡顿分析）
FLAG_PROCESS_ERROR = 3  # rs进程与app进程起止异常

# ==================== 帧类型定义 ====================
FRAME_TYPE_ACTUAL = 0  # 实际帧
FRAME_TYPE_EXPECT = 1  # 期望帧

# ==================== 时间转换常量 ====================
NANOSECONDS_TO_MILLISECONDS = 1_000_000  # 纳秒到毫秒的转换因子
NANOSECONDS_TO_SECONDS = 1_000_000_000  # 纳秒到秒的转换因子
MILLISECONDS_TO_NANOSECONDS = 1_000_000  # 毫秒到纳秒的转换因子
SECONDS_TO_NANOSECONDS = 1_000_000_000  # 秒到纳秒的转换因子

# ==================== 帧分析常量 ====================
FRAME_DURATION_MS = 16.67  # 60fps基准帧时长（毫秒）
FPS_WINDOW_SIZE_MS = 1000  # FPS窗口大小（毫秒）
LOW_FPS_THRESHOLD = 45  # 低FPS阈值

# ==================== 卡顿分级阈值 ====================
STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧（33.34ms）
STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧（100ms）

# ==================== VSync相关常量 ====================
VSYNC_EVENT_COUNT_THRESHOLD = 2_000_000  # VSync事件计数阈值
VSYNC_SYMBOL_ON_READABLE = 'OHOS::Rosen::VSyncCallBackListener::OnReadable'
VSYNC_SYMBOL_HANDLE = 'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks'

# ==================== 进程类型定义 ====================
PROCESS_TYPE_UI = 'ui'
PROCESS_TYPE_RENDER = 'render'
PROCESS_TYPE_SCENEBOARD = 'sceneboard'
PROCESS_NAME_RENDER_SERVICE = 'render_service'
PROCESS_NAME_SCENEBOARD = 'ohos.sceneboard'

# ==================== 性能阈值 ====================
PERF_DB_SIZE_WARNING_MB = 500  # 性能数据库大小警告阈值（MB）
PERF_DB_SIZE_ERROR_MB = 1000  # 性能数据库大小错误阈值（MB）
PERF_RECORDS_WARNING = 1_000_000  # 性能记录数警告阈值
PERF_RECORDS_ERROR = 5_000_000  # 性能记录数错误阈值

# ==================== 分析配置 ====================
TOP_FRAMES_FOR_CALLCHAIN = 10  # 进行调用链分析的Top帧数量
HIGH_LOAD_THRESHOLD = 80  # 高负载帧阈值（百分比）

# ==================== 时间阈值 ====================
ANALYSIS_TIME_WARNING_SECONDS = 60  # 分析耗时警告阈值（秒）
CALLCHAIN_ANALYSIS_TIME_THRESHOLD = 0.01  # 调用链分析耗时阈值（秒）
FRAME_ANALYSIS_TIME_THRESHOLD = 0.1  # 帧分析耗时阈值（秒）

# ==================== 数据验证阈值 ====================
TIMESTAMP_MAX_NANOSECONDS = 1_000_000_000_000_000  # 最大时间戳（约31年）
PROCESS_ERROR_THRESHOLD_MS = 1  # 进程异常阈值（毫秒）
