<template>
    <div class="app-container">
        <div class="stats-cards">
            <div v-if="hasPerformanceData" class="stat-card data-panel">
                <div class="card-title">
                    <i>📊</i> 有效帧数
                </div>
                <div class="card-value">{{ formatNumber(performanceData.statistics.total_frames) }}</div>
                <div class="progress-bar">
                    <div
class="progress-value"
                        :style="{ width: '100%', background: 'linear-gradient(90deg, #38bdf8, #818cf8)' }"></div>
                </div>
                <div class="card-desc">应用渲染的总帧数，反映整体运行情况</div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">最高FPS</div>
                        <div class="metric-value">{{ performanceData.fps_stats.max_fps.toFixed(2) }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">最低FPS</div>
                        <div class="metric-value">{{ performanceData.fps_stats.min_fps.toFixed(2) }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">平均FPS</div>
                        <div class="metric-value">{{ performanceData.fps_stats.average_fps.toFixed(2) }}</div>
                    </div>
                </div>
            </div>

            <div v-if="hasPerformanceData" class="stat-card data-panel">
                <div class="card-title">
                    <i>⚠️</i> 卡顿帧数
                </div>
                <div class="card-value">{{ performanceData.statistics.total_stutter_frames }} </div>
                <div class="progress-bar">
                    <div
class="progress-value"
                        :style="{ width: (performanceData.statistics.stutter_rate * 100) + '%', background: '#f97316' }">
                    </div>
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label"> 卡顿率</div>
                        <div class="metric-value">{{ (performanceData.statistics.stutter_rate * 100).toFixed(2) }}%
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label"> UI卡顿</div>
                        <div class="metric-value">{{ performanceData.statistics.frame_stats.ui.stutter }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label"> 渲染卡顿</div>
                        <div class="metric-value"> {{ performanceData.statistics.frame_stats.render.stutter }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label"> 大桌面卡顿</div>
                        <div class="metric-value"> {{ performanceData.statistics.frame_stats.sceneboard.stutter }}</div>
                    </div>
                </div>
            </div>

            <div v-if="hasEmptyFrameData" class="stat-card data-panel">
                <div class="card-title">
                    <i>🌀</i> 空刷帧统计
                </div>
                <div class="card-value">{{ summaryData.total_empty_frames.toLocaleString() }}</div>
                <div class="progress-bar">
                    <div
class="progress-value"
                        :style="{ width: Math.min(100, summaryData.empty_frame_percentage) + '%', background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)' }">
                    </div>
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">空刷帧负载</div>
                        <div class="metric-value">{{ formatNumber(summaryData.empty_frame_load) }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">后台线程负载</div>
                        <div class="metric-value">{{ formatNumber(summaryData.background_thread_load) }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">空刷帧占比</div>
                        <div class="metric-value">{{ summaryData.empty_frame_percentage.toFixed(2) }}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">后台线程占比</div>
                        <div class="metric-value">{{ summaryData.background_thread_percentage.toFixed(2) }}%
                        </div>
                    </div>
                </div>
            </div>
            <div v-if="hasFileUsageData" class="stat-card data-panel">
                <div class="card-title">
                    <i>📁</i> 冷加载文件使用分析
                </div>
                <div class="card-value">{{ fileUsageData.summary?.total_file_number || 0 }}</div>
                <div class="progress-bar">
                    <div
class="progress-value"
                        :style="{ width: (fileUsageData.summary ? (fileUsageData.summary.used_file_count / fileUsageData.summary.total_file_number * 100) : 0) + '%', background: 'linear-gradient(90deg, #10b981, #34d399)' }">
                    </div>
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">已使用文件</div>
                        <div class="metric-value">{{ fileUsageData.summary?.used_file_count || 0 }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">未使用文件</div>
                        <div class="metric-value">{{ fileUsageData.summary?.unused_file_count || 0 }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">文件使用率</div>
                        <div class="metric-value">{{ fileUsageData.summary ? (fileUsageData.summary.used_file_count /
                            fileUsageData.summary.total_file_number * 100).toFixed(1) : 0 }}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">总耗时</div>
                        <div class="metric-value">{{ formatFileTime(fileUsageData.summary?.total_time_ms || 0) }}</div>
                    </div>
                </div>
            </div>
            <div v-if="hasGcThreadData && gcThreadData.perf_percentage > 0" class="stat-card data-panel">
                <div class="card-title">
                    <i>🗑️</i> GC线程状态
                </div>
                <div class="card-value">{{ gcThreadData.GCStatus }}</div>
                <div class="progress-bar">
                    <div
class="progress-value"
                        :style="{ width: Math.min(100, gcThreadData.perf_percentage * 100) + '%', background: 'linear-gradient(90deg, #f59e0b, #fbbf24)' }">
                    </div>
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">完整GC</div>
                        <div class="metric-value">{{ gcThreadData.FullGC }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">共享完整GC</div>
                        <div class="metric-value">{{ gcThreadData.SharedFullGC }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">共享GC</div>
                        <div class="metric-value">{{ gcThreadData.SharedGC }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">部分GC</div>
                        <div class="metric-value">{{ gcThreadData.PartialGC }}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">负载占比</div>
                        <div class="metric-value">{{ (gcThreadData.perf_percentage * 100).toFixed(2) }}%</div>
                    </div>
                </div>
            </div>
            <div v-if="hasComponentResuData" class="stat-card data-panel">
                <div class="card-title">
                    <i>ℹ️</i> 其他
                </div>
                <div class="card-value"></div>
                <div class="progress-bar">
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label"><span style="font-weight: bold">复用组件：</span>
                            <a
href="https://docs.openharmony.cn/pages/v5.1/zh-cn/application-dev/performance/component_recycle_case.md"
                                target="_blank" title="查看OpenHarmony官方复用组件案例文档" class="external-link-icon"
                                style="margin-left: 6px; vertical-align: middle;">
                                <svg
width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#409EFF"
                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                                    style="transition:stroke 0.2s;">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                    <polyline points="15 3 21 3 21 9" />
                                    <line x1="10" y1="14" x2="21" y2="3" />
                                </svg>
                            </a>
                        </div>
                        <div class="metric-label">组件名/总组件数/复用组件占比</div>
                        <div class="metric-value">{{ componentResuData.max_component }}/{{
                            componentResuData.total_builds }}/{{
                                componentResuData.reusability_ratio * 100 }}%</div>
                    </div>
                </div>
            </div>

        </div>

        <div class="chart-grid">
            <div class="chart-container data-panel">
                <div class="chart-title">
                    <i class="fas fa-chart-line"></i> FPS、卡顿帧、空刷分析图（相对时间）
                </div>
                <div ref="fpsChart" class="chart"></div>
            </div>
        </div>


        <!-- 空刷帧详情面板 -->
        <div v-if="selectedEmptyFrame" class="detail-panel emptyframe-panel">
            <div class="detail-header">
                <div class="detail-title emptyframe-header">
                    <i class="fas fa-ghost"></i>
                    空刷帧详情 - VSync: {{ selectedEmptyFrame.vsync }} ({{ selectedEmptyFrame.thread_name }})
                </div>
                <el-button type="info" @click="selectedEmptyFrame = null">
                    <i class="fas fa-times"></i> 关闭详情
                </el-button>
            </div>
            <div class="detail-content">
                <div class="stutter-info">
                    <div class="info-title">
                        <i class="fas fa-info-circle"></i>
                        帧信息
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">相对时间</div>
                            <div class="info-value">
                                {{ formatTime(selectedEmptyFrame.ts) }} ms
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">持续时间</div>
                            <div class="info-value">{{ (selectedEmptyFrame.dur / 1000000).toFixed(2) }} ms</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">帧负载</div>
                            <div class="info-value">{{ selectedEmptyFrame.frame_load }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">线程类型</div>
                            <div class="info-value">{{ selectedEmptyFrame.is_main_thread ? '主线程' : '后台线程' }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">进程名称</div>
                            <div class="info-value">{{ selectedEmptyFrame.process_name }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">线程名称</div>
                            <div class="info-value">{{ selectedEmptyFrame.thread_name }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">调用栈数量</div>
                            <div class="info-value">{{ selectedEmptyFrame.sample_callchains?.length || 0 }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">调用栈ID</div>
                            <div class="info-value">{{ selectedEmptyFrame.callstack_id }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 火焰图单独一行 -->
            <div class="flamegraph-section">
                <div class="callstack-info">
                    <div class="info-title">
                        <i class="fas fa-fire"></i>
                        调用栈火焰图
                    </div>
                    <EmptyFrameFlameGraph
                        v-if="selectedEmptyFrame.sample_callchains && selectedEmptyFrame.sample_callchains.length > 0"
                        :data="selectedEmptyFrame.sample_callchains"
                    />
                    <div v-else class="placeholder">
                        <i class="fas fa-exclamation-circle"></i>
                        <h3>未找到调用栈信息</h3>
                        <p>当前空刷帧没有记录调用栈信息</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 卡顿详情面板 -->
        <div v-if="selectedStutter" class="detail-panel">
            <div class="detail-header">
                <div class="detail-title">
                    <i class="fas fa-bug"></i>
                    卡顿详情 - VSync: {{ selectedStutter.vsync }} ({{ selectedStutter.level_description }})
                </div>
                <el-button type="info" @click="selectedStutter = null">
                    <i class="fas fa-times"></i> 关闭详情
                </el-button>
            </div>
            <div class="detail-content">
                <div class="stutter-info">
                    <div class="info-title">
                        <i class="fas fa-info-circle"></i>
                        卡顿信息
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">相对时间</div>
                            <div class="info-value">
                                {{ formatTime(selectedStutter.ts) }} ms
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">实际时长</div>
                            <div class="info-value">{{ (selectedStutter.actual_duration / 1000000).toFixed(2) }} ms
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">预期时长</div>
                            <div class="info-value">{{ (selectedStutter.expected_duration / 1000000).toFixed(2) }}
                                ms</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">超出时间</div>
                            <div class="info-value">{{ selectedStutter.exceed_time.toFixed(2) }} ms</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">超出帧数</div>
                            <div class="info-value">{{ selectedStutter.exceed_frames.toFixed(2) }} 帧</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">卡顿等级</div>
                            <div class="info-value">Level {{ selectedStutter.stutter_level }} ({{
                                selectedStutter.level_description }})</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">卡顿负载</div>
                            <div class="info-value">{{ selectedStutter.frame_load }}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>



        <!-- VSync异常详情面板 -->
        <div v-if="selectedVSyncAnomaly" class="detail-panel vsync-anomaly-panel">
            <div class="detail-header">
                <div class="detail-title vsync-anomaly-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    VSync异常详情 - {{ selectedVSyncAnomaly.anomalyCategory === 'frequency_anomaly' ? '频率异常' : '帧不匹配' }}
                </div>
                <el-button type="info" @click="selectedVSyncAnomaly = null">
                    <i class="fas fa-times"></i> 关闭详情
                </el-button>
            </div>
            <div class="detail-content">
                <!-- 频率异常信息 -->
                <div v-if="selectedVSyncAnomaly.anomalyCategory === 'frequency_anomaly'" class="stutter-info">
                    <div class="info-title">
                        <i class="fas fa-wave-square"></i>
                        频率异常信息
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">异常类型</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.type }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">VSync范围</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.start_vsync }} - {{
                                selectedVSyncAnomaly.end_vsync }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">持续时间</div>
                            <div class="info-value">{{ (selectedVSyncAnomaly.duration / 1000000).toFixed(2) }} ms</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">间隔数量</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.interval_count }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">平均间隔</div>
                            <div class="info-value">{{ (selectedVSyncAnomaly.avg_interval / 1000000).toFixed(2) }} ms
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">平均频率</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.avg_frequency.toFixed(1) }} Hz</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">频率范围</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.min_frequency.toFixed(1) }} - {{
                                selectedVSyncAnomaly.max_frequency.toFixed(1) }} Hz</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">严重程度</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.severity }}</div>
                        </div>
                    </div>
                    <div class="info-description">
                        <div class="info-label">描述</div>
                        <div class="info-value">{{ selectedVSyncAnomaly.description }}</div>
                    </div>
                </div>

                <!-- 帧不匹配信息 -->
                <div v-else-if="selectedVSyncAnomaly.anomalyCategory === 'frame_mismatch'" class="stutter-info">
                    <div class="info-title">
                        <i class="fas fa-unlink"></i>
                        帧不匹配信息
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">异常类型</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.type }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">VSync编号</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.vsync }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">时间戳</div>
                            <div class="info-value">{{ formatTime(selectedVSyncAnomaly.ts) }} ms</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">进程名称</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.process_name }}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">线程名称</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.thread_name }}</div>
                        </div>
                        <div v-if="selectedVSyncAnomaly.expect_frames !== undefined" class="info-item">
                            <div class="info-label">期望帧数</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.expect_frames }}</div>
                        </div>
                        <div v-if="selectedVSyncAnomaly.actual_frames !== undefined" class="info-item">
                            <div class="info-label">实际帧数</div>
                            <div class="info-value">{{ selectedVSyncAnomaly.actual_frames }}</div>
                        </div>
                    </div>
                    <div class="info-description">
                        <div class="info-label">描述</div>
                        <div class="info-value">{{ selectedVSyncAnomaly.description }}</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="table-container data-panel">
            <div class="table-title">
                <i>📋</i> 卡顿详情
            </div>

            <div class="filters">
                <div class="filter-item" :class="{ active: activeFilter === 'all' }" @click="activeFilter = 'all'">
                    全部卡顿 ({{ performanceData.statistics.total_stutter_frames }})
                </div>
                <div
class="filter-item" :class="{ active: activeFilter === 'level_1' }"
                    @click="activeFilter = 'level_1'">
                    轻微卡顿 ({{ performanceData.statistics.stutter_levels.level_1 }})
                </div>
                <div
class="filter-item" :class="{ active: activeFilter === 'level_2' }"
                    @click="activeFilter = 'level_2'">
                    中度卡顿 ({{ performanceData.statistics.stutter_levels.level_2 }})
                </div>
                <div
class="filter-item" :class="{ active: activeFilter === 'level_3' }"
                    @click="activeFilter = 'level_3'">
                    严重卡顿 ({{ performanceData.statistics.stutter_levels.level_3 }})
                </div>
            </div>

            <table class="data-table">
                <thead>
                    <tr>
                        <th>垂直同步(VSync)</th>
                        <th>卡顿级别</th>
                        <th>实际耗时(ms)</th>
                        <th>预期耗时(ms)</th>
                        <th>超出时间</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(stutter, index) in filteredStutters" :key="index">
                        <td>{{ stutter.vsync }}</td>
                        <td :class="'level-' + stutter.stutter_level">
                            <span class="level-badge">{{ stutter.stutter_level }} - {{ stutter.level_description
                                }}</span>
                        </td>
                        <td>{{ (stutter.actual_duration / 1000000).toFixed(2) }}</td>
                        <td>{{ (stutter.expected_duration / 1000000).toFixed(2) }}</td>
                        <td :class="stutter.exceed_time >= 0 ? 'negative' : 'positive'">
                            {{ stutter.exceed_time >= 0 ? '+' : '' }}{{ stutter.exceed_time.toFixed(2) }}ms
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 文件使用分析表格 -->
        <div v-if="hasFileUsageData" class="table-container data-panel">
            <div class="table-title">
                <i>📁</i> 冷加载文件使用分析
            </div>

            <div class="filters">
                <div
class="filter-item" :class="{ active: fileUsageFilter === 'used' }"
                    @click="fileUsageFilter = 'used'">
                    已使用文件 TOP 10 ({{ fileUsageData.used_files_top10.length }})
                </div>
                <div
class="filter-item" :class="{ active: fileUsageFilter === 'unused' }"
                    @click="fileUsageFilter = 'unused'">
                    未使用文件 TOP 10 ({{ fileUsageData.unused_files_top10.length }})
                </div>
            </div>

            <table class="data-table">
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>文件名</th>
                        <th>耗时</th>
                        <!-- <th>父模块</th> -->
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(file, index) in filteredFileUsageData" :key="index">
                        <td>
                            <span class="rank-badge" :class="getFileRankClass(file.rank)">{{ file.rank }}</span>
                        </td>
                        <td class="file-name">{{ file.file_name }}</td>
                        <td>{{ formatFileTime(file.cost_time_ms) }}</td>
                        <!-- <td class="parent-module">
                            <div class="module-content" @click="toggleModuleDetail(index)">
                                <span class="module-text" :class="{ 'truncated': !expandedModules[index] }">
                                    {{ file.parent_module || '-' }}
                                </span>
                                <i v-if="file.parent_module && file.parent_module.length > 30" class="expand-icon"
                                    :class="{ 'expanded': expandedModules[index] }">
                                    {{ expandedModules[index] ? '收起' : '展开' }}
                                </i>
                            </div>
                        </td> -->
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import * as echarts from 'echarts';
import { useJsonDataStore, getDefaultEmptyFrameData, getDefaultColdStartData, safeProcessColdStartData, getDefaultGcThreadStepData, getDefaultFrameStepData, getDefaultEmptyFrameStepData, getDefaultComponentResuStepData, getDefaultColdStartStepData, safeProcessGcThreadData, getDefaultGcThreadData, getDefaultVSyncAnomalyData, getDefaultVSyncAnomalyStepData, safeProcessVSyncAnomalyData } from '../../../../stores/jsonDataStore.ts';
import EmptyFrameFlameGraph from './EmptyFrameFlameGraph.vue';

// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 空刷JSON 数据
const emptyFrameJsonData = jsonDataStore.emptyFrameData ?? getDefaultEmptyFrameData();
const componentResuJsonData = jsonDataStore.componentResuData;
const coldStartJsonData = safeProcessColdStartData(jsonDataStore.coldStartData) ?? getDefaultColdStartData();
const gcThreadJsonData = safeProcessGcThreadData(jsonDataStore.gcThreadData) ?? getDefaultGcThreadData();

const vsyncAnomalyJsonData = safeProcessVSyncAnomalyData(jsonDataStore.vsyncAnomalyData) ?? getDefaultVSyncAnomalyData();

const props = defineProps({
    data: {
        type: Array,
        required: true,
    },
    step: {
        type: Number,
        required: true,
    }
});

// 帧数据
const performanceData = computed(() => {
    const key = props.step === 0 || props.data['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return props.data[key] ?? getDefaultFrameStepData();
});

// 当前步骤空刷信息
const emptyFrameData = computed(() => {
    const key = props.step === 0 || emptyFrameJsonData['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return emptyFrameJsonData[key] ?? getDefaultEmptyFrameStepData();
});

// 当前步骤组件复用信息
const componentResuData = computed(() => {
    const key = props.step === 0 || componentResuJsonData['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return componentResuJsonData[key] ?? getDefaultComponentResuStepData();
});

// 当前步骤GC信息
const gcThreadData = computed(() => {
    const key = props.step === 0 || gcThreadJsonData['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return gcThreadJsonData[key] ?? getDefaultGcThreadStepData();
});

// 当前步骤冷启动文件使用信息
const coldStartData = computed(() => {
    const key = props.step === 0 || coldStartJsonData['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return coldStartJsonData[key] ?? getDefaultColdStartStepData();
});



// 当前步骤VSync异常信息
const vsyncAnomalyData = computed(() => {
    const key = props.step === 0 || vsyncAnomalyJsonData['step' + 2] == undefined ? 'step1' : 'step' + props.step;
    return vsyncAnomalyJsonData[key] ?? getDefaultVSyncAnomalyStepData();
});

// 文件使用分析数据 - 由冷启动数据提供
function mergeFileUsageDataAllSteps(coldStartJsonData) {
    // 合并所有step的used_files_top10和unused_files_top10
    const allUsed = {};
    const allUnused = {};
    const summary = {
        total_file_number: 0,
        total_time_ms: 0,
        used_file_count: 0,
        used_file_time_ms: 0,
        unused_file_count: 0,
        unused_file_time_ms: 0
    };
    Object.values(coldStartJsonData).forEach(step => {
        // 累加summary
        if (step.summary) {
            summary.total_file_number += step.summary.total_file_number;
            summary.total_time_ms += step.summary.total_time_ms;
            summary.used_file_count += step.summary.used_file_count;
            summary.used_file_time_ms += step.summary.used_file_time_ms;
            summary.unused_file_count += step.summary.unused_file_count;
            summary.unused_file_time_ms += step.summary.unused_file_time_ms;
        }
        // 合并used_files_top10
        step.used_files_top10?.forEach(file => {
            if (!allUsed[file.file_name]) {
                allUsed[file.file_name] = { ...file };
            } else {
                allUsed[file.file_name].cost_time_ms += file.cost_time_ms;
                // parent_module合并为多行
                if (file.parent_module && !allUsed[file.file_name].parent_module.includes(file.parent_module)) {
                    allUsed[file.file_name].parent_module += '\n' + file.parent_module;
                }
            }
        });
        // 合并unused_files_top10
        step.unused_files_top10?.forEach(file => {
            if (!allUnused[file.file_name]) {
                allUnused[file.file_name] = { ...file };
            } else {
                allUnused[file.file_name].cost_time_ms += file.cost_time_ms;
                if (file.parent_module && !allUnused[file.file_name].parent_module.includes(file.parent_module)) {
                    allUnused[file.file_name].parent_module += '\n' + file.parent_module;
                }
            }
        });
    });
    // 排序取前10
    const used_files_top10 = Object.values(allUsed)
        .sort((a, b) => b.cost_time_ms - a.cost_time_ms)
        .slice(0, 10)
        .map((file, idx) => ({ ...file, rank: idx + 1 }));
    const unused_files_top10 = Object.values(allUnused)
        .sort((a, b) => b.cost_time_ms - a.cost_time_ms)
        .slice(0, 10)
        .map((file, idx) => ({ ...file, rank: idx + 1 }));
    return { summary, used_files_top10, unused_files_top10 };
}

const fileUsageData = computed(() => {
    if (props.step === 0) {
        return mergeFileUsageDataAllSteps(coldStartJsonData);
    } else {
        return coldStartData.value;
    }
});

const fpsChart = ref(null);
const selectedStutter = ref(null);
const selectedEmptyFrame = ref(null);

const selectedVSyncAnomaly = ref(null);

const activeFilter = ref('all');
const minTimestamp = ref(0); // 存储最小时间戳

// 文件使用分析相关
const fileUsageFilter = ref('used');

// 父模块展开状态管理
//const expandedModules = ref({});

// 切换父模块详情显示
// const toggleModuleDetail = (index) => {
//     expandedModules.value[index] = !expandedModules.value[index];
// };

// 筛选文件使用数据
const filteredFileUsageData = computed(() => {
    if (fileUsageFilter.value === 'used') {
        return fileUsageData.value.used_files_top10;
    } else {
        return fileUsageData.value.unused_files_top10;
    }
});

// 获取文件排名样式类
const getFileRankClass = (rank) => {
    if (rank <= 3) return 'top-rank';
    if (rank <= 5) return 'high-rank';
    return 'normal-rank';
};

// 空刷帧汇总数据
const summaryData = computed(() => emptyFrameData.value.summary);

// 判断冷启动数据是否有效
const hasFileUsageData = computed(() => {
    const data = fileUsageData.value;
    if (!data) return false;
    // summary所有字段都为0，且used_files_top10和unused_files_top10都为空时视为无数据
    const s = data.summary;
    const noSummary = !s || (s.total_file_number === 0 && s.total_time_ms === 0 && s.used_file_count === 0 && s.unused_file_count === 0);
    const noFiles = (!data.used_files_top10 || data.used_files_top10.length === 0) && (!data.unused_files_top10 || data.unused_files_top10.length === 0);
    return !(noSummary && noFiles);
});

// 判断各类step数据是否有效
const hasPerformanceData = computed(() => !!performanceData.value && performanceData.value.statistics && performanceData.value.statistics.total_frames > 0);
const hasEmptyFrameData = computed(() => !!emptyFrameData.value && emptyFrameData.value.summary && emptyFrameData.value.summary.total_empty_frames > 0);
const hasComponentResuData = computed(() => !!componentResuData.value && componentResuData.value.total_builds > 0);
const hasGcThreadData = computed(() => !!gcThreadData.value && Object.keys(gcThreadData.value).length > 0);
//const hasFrameLoadsData = computed(() => !!frameLoadsData.value && frameLoadsData.value.top_frames && frameLoadsData.value.top_frames.length > 0);

// 格式化数字显示
const formatNumber = (num) => {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num;
};

// 格式化时间为相对时间
const formatTime = (timestamp) => {
    // 纳秒转毫秒
    const timeMs = timestamp / 1000000;
    return timeMs.toFixed(2);
};

// 格式化文件时间
const formatFileTime = (timeMs) => {
    if (timeMs < 1) {
        return `${(timeMs * 1000).toFixed(2)}μs`;
    } else if (timeMs < 1000) {
        return `${timeMs.toFixed(2)}ms`;
    } else {
        return `${(timeMs / 1000).toFixed(2)}s`;
    }
};

// 统计数据计算
// const totalFrames = computed(() => performanceData.value.statistics.total_frames);
// const stutterFrames = computed(() => performanceData.value.statistics.total_stutter_frames);
// const stutterRate = computed(() => performanceData.value.statistics.stutter_rate * 100);
// const avgFPS = computed(() => performanceData.value.fps_stats.average_fps);
// const minFPS = computed(() => performanceData.value.fps_stats.min_fps);
// const maxFPS = computed(() => performanceData.value.fps_stats.max_fps);
// const uiStutterFrames = computed(() => performanceData.value.statistics.frame_stats.ui.stutter);
// const renderStutterFrames = computed(() => performanceData.value.statistics.frame_stats.render.stutter);
// const stutterLevels = computed(() => performanceData.value.statistics.stutter_levels);
// const totalStutterFrames = computed(() => stutterFrames.value);

// 筛选卡顿数据
const filteredStutters = computed(() => {
    const allStutters = [
        ...performanceData.value.stutter_details.ui_stutter,
        ...performanceData.value.stutter_details.render_stutter
    ];

    // 显示所有卡顿条目（包括没有调用链的），仅按等级过滤
    if (activeFilter.value === 'all') return allStutters;

    const level = parseInt(activeFilter.value.split('_')[1]);
    return allStutters.filter(stutter => stutter.stutter_level === level);
});

// 卡顿级别颜色
const getStutterColor = (level) => {
    const colors = {
        1: '#eab308', // 轻微卡顿 - 黄色
        2: '#f97316', // 中度卡顿 - 橙色
        3: '#ef4444'  // 严重卡顿 - 红色
    };
    return colors[level] || '#999';
};

// 初始化图表
const initCharts = () => {
    // FPS与卡顿趋势分析图表
    if (fpsChart.value) {
        const fpsChartInstance = echarts.init(fpsChart.value);

        // 收集所有时间戳
        const allTimestamps = [];

        // 收集FPS数据点
        const fpsData = [];
        performanceData.value.fps_stats.fps_windows.forEach(window => {
            // 使用窗口开始时间作为时间点，改用start_time而不是start_time_ts
            const timeMs = window.start_time / 1000000; // 转换为毫秒
            allTimestamps.push(timeMs);
            fpsData.push({
                time: timeMs,
                fps: window.fps,
                window: window
            });
        });

        // 收集卡顿点
        const stutterPoints = [];
        filteredStutters.value.forEach(stutter => {
            const timeMs = stutter.ts / 1000000; // 转换为毫秒
            allTimestamps.push(timeMs);

            // 优化FPS值匹配算法：让卡顿点精确落在FPS折线上
            let matchedFps = 0;

            // 对fpsData按时间排序（确保顺序正确）
            const sortedFpsData = [...fpsData].sort((a, b) => a.time - b.time);

            // 查找卡顿时间戳在FPS折线上的对应位置
            let foundExactMatch = false;

            // 首先检查是否有完全匹配的时间点
            for (const fpsPoint of sortedFpsData) {
                if (Math.abs(fpsPoint.time - timeMs) < 1) { // 1ms容差
                    matchedFps = fpsPoint.fps;
                    foundExactMatch = true;
                    break;
                }
            }

            // 如果没有完全匹配，在FPS折线上进行插值
            if (!foundExactMatch) {
                let prevPoint = null;
                let nextPoint = null;

                // 查找卡顿时间戳前后的FPS数据点
                for (let i = 0; i < sortedFpsData.length; i++) {
                    const fpsPoint = sortedFpsData[i];

                    if (fpsPoint.time <= timeMs) {
                        prevPoint = fpsPoint;
                    } else if (fpsPoint.time > timeMs && !nextPoint) {
                        nextPoint = fpsPoint;
                        break;
                    }
                }

                // 在FPS折线上进行线性插值
                if (prevPoint && nextPoint) {
                    const timeRange = nextPoint.time - prevPoint.time;
                    const timeOffset = timeMs - prevPoint.time;
                    const ratio = timeRange > 0 ? timeOffset / timeRange : 0;

                    matchedFps = prevPoint.fps + (nextPoint.fps - prevPoint.fps) * ratio;
                } else if (prevPoint) {
                    // 只有前一个点，使用前一个点的FPS
                    matchedFps = prevPoint.fps;
                } else if (nextPoint) {
                    // 只有后一个点，使用后一个点的FPS
                    matchedFps = nextPoint.fps;
                } else {
                    // 没有任何FPS数据点，使用平均FPS
                    matchedFps = performanceData.value.fps_stats.average_fps || 0;
                }
            }

            stutterPoints.push({
                time: timeMs,
                stutter: stutter,
                fps: matchedFps  // 使用优化后的FPS值
            });
        });

        // 收集空刷帧点
        const emptyFramePoints = [];
        // 主线程空刷帧
        emptyFrameData.value.top_frames.main_thread_empty_frames.forEach(frame => {
            const timeMs = frame.ts / 1000000; // 转换为毫秒
            if (timeMs !== 0) {
                allTimestamps.push(timeMs);
                emptyFramePoints.push({
                    time: timeMs,
                    frame: frame,
                    type: 'main_thread'
                });
            }

        });
        // 后台线程空刷帧
        emptyFrameData.value.top_frames.background_thread.forEach(frame => {
            const timeMs = frame.ts / 1000000; // 转换为毫秒
            if (timeMs !== 0) {
                allTimestamps.push(timeMs);
                emptyFramePoints.push({
                    time: timeMs,
                    frame: frame,
                    type: 'background_thread'
                });
            }

        });

        // 收集空刷负载（用于柱状图）
        const frameLoadData = [];
        const loadData = [];

        // 主线程空刷帧
        emptyFrameData.value.top_frames.main_thread_empty_frames.forEach(frame => {
            const timeMs = frame.ts / 1000000; // 转换为毫秒
            frameLoadData.push({
                time: timeMs,
                load: frame.frame_load,
                frame: frame,  // 添加完整的帧对象
                type: 'main_thread'
            });
            loadData.push(frame.frame_load);
        });

        // 后台线程空刷帧
        //emptyFrameData.value.top_frames.background_thread.forEach(frame => {
        //    const timeMs = frame.ts / 1000000; // 转换为毫秒
        //    frameLoadData.push({
        //        time: timeMs,
        //        load: frame.frame_load,
        //        frame: frame,  // 添加完整的帧对象
        //        type: 'background_thread'
        //    });
        //    loadData.push(frame.frame_load);
        //});



        // 收集VSync异常数据
        const vsyncAnomalyPoints = [];

        // 收集频率异常点
        vsyncAnomalyData.value.frequency_anomalies.forEach(anomaly => {
            const timeMs = anomaly.start_ts / 1000000; // 转换为毫秒
            allTimestamps.push(timeMs);
            vsyncAnomalyPoints.push({
                time: timeMs,
                anomaly: anomaly,
                type: 'frequency_anomaly'
            });
        });

        // 收集帧不匹配异常点
        // vsyncAnomalyData.value.frame_mismatches.forEach(mismatch => {
        //     const timeMs = mismatch.ts / 1000000; // 转换为毫秒
        //     allTimestamps.push(timeMs);
        //     vsyncAnomalyPoints.push({
        //         time: timeMs,
        //         anomaly: mismatch,
        //         type: 'frame_mismatch',  // 统一标记为frame_mismatch类型
        //         originalType: mismatch.type  // 保存原始类型
        //     });
        // });



        // 找到最小时间戳作为起点
        minTimestamp.value = allTimestamps.length > 0 ? Math.min(...allTimestamps) : 0;

        // 对FPS数据按时间排序
        fpsData.sort((a, b) => a.time - b.time);

        // 配置图表选项 - 使用相对时间
        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#e2e8f0',
                borderWidth: 1,
                textStyle: {
                    color: '#1e293b'
                },
                // 动态定位，确保不超出画布
                position: function (point, params, dom, rect, size) {
                    // point: 鼠标位置 [x, y]
                    // size: tooltip大小 {contentSize: [width, height], viewSize: [width, height]}

                    const tooltipWidth = size.contentSize[0];
                    const tooltipHeight = size.contentSize[1];
                    const chartWidth = size.viewSize[0];
                    const chartHeight = size.viewSize[1];

                    let x = point[0];
                    let y = point[1];

                    // 水平方向调整：如果tooltip会超出右边界，则显示在鼠标左侧
                    if (x + tooltipWidth + 20 > chartWidth) {
                        x = x - tooltipWidth - 20;
                    } else {
                        x = x + 20; // 默认显示在鼠标右侧
                    }

                    // 垂直方向调整：如果tooltip会超出下边界，则向上调整
                    if (y + tooltipHeight + 20 > chartHeight) {
                        y = y - tooltipHeight - 20;
                    } else {
                        y = y + 20; // 默认显示在鼠标下方
                    }

                    // 确保不会超出左边界和上边界
                    x = Math.max(10, x);
                    y = Math.max(10, y);

                    return [x, y];
                },
                formatter: function (params) {
                    // 优化后的tooltip样式
                    let html = `
                    `;

                    // 时间信息 - 使用更清晰的格式
                    const timeParam = params[0];
                    const actualTime = timeParam.value[0];
                    html += `
                        <div style="
                            background: rgba(59, 130, 246, 0.1);
                            padding: 6px 10px;
                            border-radius: 4px;
                            margin-bottom: 8px;
                            border-left: 3px solid #3b82f6;
                        ">
                            🕐 时间: <span style="color:#3b82f6;font-weight:600">${actualTime.toFixed(2)} ms</span>
                        </div>
                    `;

                    // 按类型分组显示数据
                    const fpsData = params.find(p => p.seriesName === 'FPS值');
                    const emptyLoadData = params.find(p => p.seriesName === '空刷负载');
                    const stutterData = params.find(p => p.seriesName === '卡顿点');
                    const vsyncAnomalyData = params.find(p => p.seriesName === 'VSync异常');

                    // FPS信息
                    if (fpsData) {
                        const fpsValue = fpsData.value[1];
                        const fpsColor = fpsValue >= 55 ? '#3b82f6' : fpsValue >= 30 ? '#3b82f6' : '#3b82f6';
                        const fpsIcon = fpsValue >= 55 ? '🔵' : fpsValue >= 30 ? '🔵' : '🔵';
                        html += `
                            <div style="
                                background: rgba(16, 185, 129, 0.1);
                                padding: 6px 10px;
                                border-radius: 4px;
                                margin-bottom: 6px;
                                border-left: 3px solid ${fpsColor};
                            ">
                                ${fpsIcon} FPS: <span style="color:${fpsColor};font-weight:bold;font-size:14px">${fpsValue}</span>
                            </div>
                        `;
                    }

                    // 空刷负载信息
                    if (emptyLoadData) {
                        const threadType = emptyLoadData.data.type === 'main_thread' ? '主线程' : '后台线程';
                        const threadIcon = emptyLoadData.data.type === 'main_thread' ? '🧵' : '⚙️';
                        html += `
                            <div style="
                                background: rgba(139, 92, 246, 0.1);
                                padding: 6px 10px;
                                border-radius: 4px;
                                margin-bottom: 6px;
                                border-left: 3px solid #8b5cf6;
                            ">
                                ${threadIcon} 空刷负载: <span style="color:#8b5cf6;font-weight:bold">${emptyLoadData.value[1]}</span>
                                <br><small style="color:#6b7280">类型: ${threadType}</small>
                            </div>
                        `;
                    }



                    // 卡顿点信息
                    if (stutterData) {
                        const stutter = stutterData.data.stutter;
                        const severityIcon = stutter.stutter_level === 3 ? '🔴' : stutter.stutter_level === 2 ? '🟡' : '🟠';
                        html += `
                            <div style="
                                background: rgba(239, 68, 68, 0.1);
                                padding: 6px 10px;
                                border-radius: 4px;
                                margin-bottom: 6px;
                                border-left: 3px solid ${stutterData.color};
                            ">
                                ${severityIcon} 卡顿: <span style="color:${stutterData.color};font-weight:bold">${stutter.level_description}</span>
                                <br><small style="color:#6b7280">VSync: ${stutter.vsync}</small>
                                <br><small style="color:#6b7280">超出: ${stutter.exceed_time.toFixed(2)} ms</small>
                            </div>
                        `;
                    }

                    // VSync异常信息
                    if (vsyncAnomalyData) {
                        const anomaly = vsyncAnomalyData.data.anomaly;
                        if (anomaly.type && anomaly.type.includes('frequency')) {
                            const severityIcon = anomaly.severity === 'high' ? '🔴' : anomaly.severity === 'medium' ? '🟡' : '🟢';
                            html += `
                                <div style="
                                    background: rgba(220, 38, 38, 0.1);
                                    padding: 6px 10px;
                                    border-radius: 4px;
                                    margin-bottom: 6px;
                                    border-left: 3px solid ${vsyncAnomalyData.color};
                                ">
                                    ${severityIcon} VSync频率异常
                                    <br><small style="color:#6b7280">范围: ${anomaly.start_vsync} - ${anomaly.end_vsync}</small>
                                    <br><small style="color:#6b7280">频率: ${anomaly.avg_frequency.toFixed(1)} Hz</small>
                                    <br><small style="color:#6b7280">严重程度: ${anomaly.severity}</small>
                                </div>
                            `;
                        } else if (anomaly.type && (anomaly.type.includes('frame') || anomaly.type.includes('actual') || anomaly.type.includes('expect'))) {
                            html += `
                                <div style="
                                    background: rgba(124, 58, 237, 0.1);
                                    padding: 6px 10px;
                                    border-radius: 4px;
                                    margin-bottom: 6px;
                                    border-left: 3px solid #7c3aed;
                                ">
                                    🔗 VSync帧不匹配
                                    <br><small style="color:#6b7280">VSync: ${anomaly.vsync}</small>
                                    <br><small style="color:#6b7280">线程: ${anomaly.thread_name}</small>
                                    ${anomaly.expect_frames !== undefined ? `<br><small style="color:#6b7280">期望: ${anomaly.expect_frames}帧</small>` : ''}
                                    ${anomaly.actual_frames !== undefined ? `<br><small style="color:#6b7280">实际: ${anomaly.actual_frames}帧</small>` : ''}
                                </div>
                            `;
                        }
                    }

                    // 检查是否有可点击的数据类型
                    const hasClickableData = emptyLoadData || stutterData || vsyncAnomalyData;

                    // 只有当存在可点击数据时才显示操作提示
                    if (hasClickableData) {
                        html += `
                            <div style="
                                background: rgba(107, 114, 128, 0.1);
                                padding: 4px 8px;
                                border-radius: 4px;
                                margin-top: 8px;
                                text-align: center;
                                font-size: 11px;
                                color: #6b7280;
                            ">
                                💡 点击数据点查看详细信息
                            </div>
                        `;
                    }

                    return html;
                }
            },
            legend: {
                data: ['FPS值', {
                    name: '空刷负载',
                    // 统一图例颜色为主线程紫色（#8b5cf6）
                    icon: 'rect',
                    itemStyle: { color: '#8b5cf6' }
                }, {
                    name: '卡顿点',
                    icon: 'circle',
                    itemStyle: { color: '#eab308' }  // 黄色
                }, {
                        name: 'VSync异常',
                        icon: 'diamond',
                        itemStyle: { color: '#dc2626' }
                    }, '空刷帧'],
                top: 10,
                textStyle: {
                    color: '#64748b'
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '10%',
                containLabel: true
            },
            xAxis: {
                type: 'value',
                name: '相对时间 (ms)',
                nameLocation: 'middle',
                nameGap: 30,
                nameTextStyle: {
                    color: '#64748b'
                },
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                axisLabel: {
                    color: '#64748b',
                    formatter: function (value) {
                        // 显示相对时间数字
                        return parseInt(value).toLocaleString();
                    }
                }
            },
            yAxis: [
                {
                    type: 'value',
                    name: 'FPS',
                    min: 0,
                    max: 120,
                    nameTextStyle: {
                        color: '#64748b'
                    },
                    axisLine: {
                        lineStyle: {
                            color: '#94a3b8'
                        }
                    },
                    axisLabel: {
                        color: '#64748b'
                    },
                    splitLine: {
                        lineStyle: {
                            color: 'rgba(148, 163, 184, 0.2)'
                        }
                    }
                },
                {
                    type: 'value',
                    name: '空刷负载',
                    min: 0,
                    nameTextStyle: {
                        color: '#64748b'
                    },
                    position: 'right',
                    axisLine: {
                        lineStyle: {
                            color: '#94a3b8'
                        }
                    },
                    axisLabel: {
                        color: '#64748b',
                        formatter: function (value) {
                            // 格式化空刷负载显示
                            if (value >= 1000000) {
                                return (value / 1000000).toFixed(1) + 'M';
                            } else if (value >= 1000) {
                                return (value / 1000).toFixed(0) + 'K';
                            }
                            return value;
                        }
                    },
                    splitLine: {
                        show: false
                    }
                }
            ],
            dataZoom: [
                {
                    type: 'inside',
                    start: 0,
                    end: 100
                },
                {
                    type: 'slider',
                    start: 0,
                    end: 100,
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                    fillerColor: 'rgba(59, 130, 246, 0.15)',
                    borderColor: 'rgba(203, 213, 225, 0.6)',
                    textStyle: {
                        color: '#64748b'
                    },
                    height: 20,
                    bottom: 5
                }
            ],
            series: [
                {
                    name: '空刷负载',
                    type: 'bar',
                    yAxisIndex: 1, // 使用第二个y轴
                    barWidth: 6,
                    data: frameLoadData.map(item => {
                        // 确保每个数据点包含完整信息
                        return {
                            value: [item.time, item.load],
                            frame: item.frame, // 传递帧对象
                            type: item.type    // 传递线程类型
                        };
                    }),
                    itemStyle: {
                        color: function (params) {
                            // 根据类型设置不同颜色
                            const frameType = params.data.type;
                            if (frameType === 'main_thread') {
                                return '#8b5cf6'; // 主线程空刷帧 - 紫色
                            } else if (frameType === 'background_thread') {
                                return '#ec4899'; // 后台线程空刷帧 - 粉红色
                            }
                            return '#8b5cf6'; // 默认也用主线程紫色
                        }
                    },
                    triggerEvent: true  // 确保柱状图可以触发事件
                },
                {
                    name: 'FPS值',
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 4, // 缩小点的大小，从6改为4
                    data: fpsData.map(item => [item.time, item.fps]),
                    itemStyle: {
                        color: '#3b82f6' // 统一为蓝色，移除动态颜色判断
                    },
                    lineStyle: {
                        color: '#3b82f6' // 确保线条也是蓝色
                    }
                },
                {
                    name: '卡顿点',
                    type: 'scatter',
                    symbol: 'circle',
                    symbolSize: 16,
                    z: 10, // 设置较高的z-index，确保在最上层显示
                    data: stutterPoints.map(p => {
                        return {
                            value: [p.time, p.fps],  // 使用对应时间点的FPS值作为y坐标
                            time: p.time, // 保存绝对时间用于对齐
                            stutter: p.stutter
                        };
                    }),
                    itemStyle: {
                        color: function (params) {
                            const stutter = params.data.stutter;
                            return getStutterColor(stutter.stutter_level);
                        },
                        borderColor: '#ffffff', // 添加白色边框，增强可见性
                        borderWidth: 2
                    },
                    tooltip: {
                        formatter: function (params) {
                            const stutter = params.data.stutter;
                            return `
                                <div style="font-weight:bold;color:${getStutterColor(stutter.stutter_level)};">
                                    ${stutter.level_description}
                                </div>
                                <div>VSync: ${stutter.vsync}</div>
                                <div>FPS: ${params.value[1].toFixed(2)}</div>
                                <div>超出时间: ${stutter.exceed_time.toFixed(2)} ms</div>
                            `;
                        }
                    }
                },
                {
                    name: 'VSync异常',
                    type: 'scatter',
                    symbol: 'diamond',
                    symbolSize: 14,
                    z: 12, // 设置较高的z-index，确保在最上层显示
                    data: vsyncAnomalyPoints.map(p => {
                        // 找到对应时间点的FPS值
                        let matchedFps = 0;
                        const sortedFpsData = [...fpsData].sort((a, b) => a.time - b.time);

                        for (const fpsPoint of sortedFpsData) {
                            if (Math.abs(fpsPoint.time - p.time) < 1) {
                                matchedFps = fpsPoint.fps;
                                break;
                            }
                        }

                        if (matchedFps === 0 && sortedFpsData.length > 0) {
                            // 如果没有精确匹配，使用最近的FPS值
                            let closestFps = sortedFpsData[0];
                            let minDistance = Math.abs(sortedFpsData[0].time - p.time);

                            for (const fpsPoint of sortedFpsData) {
                                const distance = Math.abs(fpsPoint.time - p.time);
                                if (distance < minDistance) {
                                    minDistance = distance;
                                    closestFps = fpsPoint;
                                }
                            }
                            matchedFps = closestFps.fps;
                        }

                        return {
                            value: [p.time, matchedFps],
                            time: p.time,
                            anomaly: p.anomaly,
                            type: p.type
                        };
                    }),
                    itemStyle: {
                        color: function (params) {
                            const anomalyType = params.data.type;
                            if (anomalyType === 'frequency_anomaly') {
                                const severity = params.data.anomaly.severity;
                                if (severity === 'high') return '#dc2626'; // 红色 - 严重
                                if (severity === 'medium') return '#ea580c'; // 橙色 - 中度
                                return '#facc15'; // 黄色 - 轻微
                            } else if (anomalyType === 'frame_mismatch') {
                                return '#7c3aed'; // 紫色 - 帧不匹配
                            }
                            return '#6b7280'; // 默认灰色
                        },
                        borderColor: '#ffffff',
                        borderWidth: 2
                    },
                    tooltip: {
                        formatter: function (params) {
                            const anomaly = params.data.anomaly;
                            const anomalyType = params.data.type;

                            if (anomalyType === 'frequency_anomaly') {
                                return `
                                    <div style="font-weight:bold;color:#dc2626;">
                                        VSync频率异常
                                    </div>
                                    <div>类型: ${anomaly.type}</div>
                                    <div>VSync范围: ${anomaly.start_vsync} - ${anomaly.end_vsync}</div>
                                    <div>平均频率: ${anomaly.avg_frequency.toFixed(1)} Hz</div>
                                    <div>持续时间: ${(anomaly.duration / 1000000).toFixed(1)} ms</div>
                                    <div>严重程度: ${anomaly.severity}</div>
                                `;
                            } else if (anomalyType === 'frame_mismatch') {
                                let content = `
                                    <div style="font-weight:bold;color:#7c3aed;">
                                        VSync帧不匹配
                                    </div>
                                    <div>类型: ${anomaly.type}</div>
                                    <div>VSync: ${anomaly.vsync}</div>
                                    <div>线程: ${anomaly.thread_name}</div>
                                `;
                                if (anomaly.expect_frames !== undefined) {
                                    content += `<div>期望帧数: ${anomaly.expect_frames}</div>`;
                                }
                                if (anomaly.actual_frames !== undefined) {
                                    content += `<div>实际帧数: ${anomaly.actual_frames}</div>`;
                                }
                                return content;
                            }
                            return '';
                        }
                    }
                }

            ]
        };

        fpsChartInstance.setOption(option);

        //绑定点击事件
        fpsChartInstance.on('click', function (params) {
            console.log('点击事件触发', params);

            // 只处理空刷负载系列的点击事件
            if (params.seriesName === '空刷负载') {
                // 检查数据点是否包含frame对象
                if (params.data && params.data.frame) {
                    console.log('找到帧对象', params.data.frame);
                    selectedEmptyFrame.value = params.data.frame;
                    selectedStutter.value = null;

                    selectedVSyncAnomaly.value = null;
                } else {
                    console.warn('点击柱状图但未找到frame对象', params);
                }
            }



            // 处理卡顿点系列的点击事件
            if (params.seriesName === '卡顿点') {
                if (params.data && params.data.stutter) {
                    selectedStutter.value = params.data.stutter;
                    selectedEmptyFrame.value = null;
                    selectedVSyncAnomaly.value = null;
                }
            }

            // 处理VSync异常系列的点击事件
            if (params.seriesName === 'VSync异常') {
                if (params.data && params.data.anomaly) {
                    console.log('找到VSync异常对象', params.data.anomaly);
                    // 为异常对象添加类别标识，便于详情面板判断
                    const anomalyWithCategory = {
                        ...params.data.anomaly,
                        anomalyCategory: params.data.type  // 添加类别字段
                    };
                    selectedVSyncAnomaly.value = anomalyWithCategory;
                    selectedStutter.value = null;
                    selectedEmptyFrame.value = null;
                }
            }
        });

    }

};

onMounted(() => {

    initCharts();

    // 响应窗口大小变化
    window.addEventListener('resize', () => {
        if (fpsChart.value) echarts.getInstanceByDom(fpsChart.value)?.resize();
    });
});

watch(performanceData, (newVal, oldVal) => {
    if (newVal !== oldVal) {
        initCharts();
    }
}, { deep: true });

// 监听步骤变化
watch(() => props.step, () => {
    // 当步骤变化时关闭所有详情面板
    selectedStutter.value = null;
    selectedEmptyFrame.value = null;
    selectedVSyncAnomaly.value = null;
});

</script>

<style scoped>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

body {

    min-height: 100vh;
    padding: 20px;
}


.header {
    text-align: center;
    /* margin-bottom: 30px; */
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    position: relative;
    overflow: hidden;
}

.header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
}

.header h1 {
    font-size: 2.5rem;
    /* margin-bottom: 10px; */
    background: linear-gradient(90deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 700;
}

.header p {
    font-size: 1.1rem;
    /* color: #94a3b8; */
    max-width: 800px;
    margin: 0 auto;
    line-height: 1.6;
}

.runtime-info {
    margin-top: 15px;
    font-size: 0.95rem;
    color: #38bdf8;
    padding: 8px 15px;
    border-radius: 8px;
    display: inline-block;
}

.stats-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    /* margin-bottom: 30px; */
}

.stat-card {
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    position: relative;
    overflow: hidden;
}

.stat-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.card-title {
    font-size: 1rem;
    /* color: #94a3b8; */
    /* margin-bottom: 15px; */
    display: flex;
    align-items: center;
}

.card-title i {
    margin-right: 8px;
    font-size: 1.2rem;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.card-value {
    font-size: 2.2rem;
    font-weight: 700;
    /* margin-bottom: 10px; */
}

.card-desc {
    font-size: 0.9rem;
    /* color: #94a3b8; */
    line-height: 1.5;
}

.card-badge {
    position: absolute;
    top: 20px;
    right: 20px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}

.chart-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
    gap: 20px;
    /* margin-bottom: 30px; */
}

.chart-container {
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    height: 400px;
    position: relative;
    overflow: hidden;
}

.chart-title {
    font-size: 1.2rem;
    /* margin-bottom: 20px; */
    display: flex;
    align-items: center;
    color: #38bdf8;
    font-weight: 600;
}

.chart-title i {
    margin-right: 10px;
    font-size: 1.4rem;
    border-radius: 8px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.chart {
    width: 100%;
    height: calc(100% - 40px);
}

.table-container {
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    /* margin-bottom: 30px; */
}

.table-title {
    font-size: 1.2rem;
    /* margin-bottom: 20px; */
    display: flex;
    align-items: center;
    color: #38bdf8;
    font-weight: 600;
}

.table-title i {
    margin-right: 10px;
    font-size: 1.4rem;
    border-radius: 8px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table th {

    text-align: left;
    padding: 12px 15px;
    font-weight: 600;
}

.data-table td {
    padding: 12px 15px;
    border-bottom: 1px solid rgba(74, 85, 104, 0.3);

}


.level-1 {
    color: #fbbf24;
}

.level-2 {
    color: #f97316;
}

.level-3 {
    color: #ef4444;
}

.positive {
    color: #10b981;
}

.negative {
    color: #ef4444;
}

.footer {
    text-align: center;
    padding: 20px;
    /* color: #94a3b8; */
    font-size: 0.9rem;
}

.filters {
    display: flex;
    gap: 15px;
    /* margin-bottom: 20px; */
    flex-wrap: wrap;
}

.filter-item {
    /* background: rgba(30, 41, 59, 0.8); */
    /* border: 1px solid rgba(74, 85, 104, 0.5); */
    border-radius: 8px;
    padding: 8px 15px;
    display: flex;
    align-items: center;
    cursor: pointer;
    transition: all 0.3s ease;
}

.filter-item:hover {
    background: rgba(56, 189, 248, 0.2);
    border-color: #38bdf8;
}

.filter-item.active {
    background: rgba(56, 189, 248, 0.3);
    border-color: #38bdf8;
    color: #38bdf8;
}

.progress-bar {
    height: 6px;
    /* background: rgba(74, 85, 104, 0.3); */
    border-radius: 3px;
    margin-top: 10px;
    overflow: hidden;
}

.progress-value {
    height: 100%;
    border-radius: 3px;
}

.stat-trend {
    display: flex;
    align-items: center;
    font-size: 0.9rem;
    margin-top: 5px;
}

.trend-up {
    color: #ef4444;
}

.trend-down {
    color: #10b981;
}

@media (max-width: 768px) {
    .chart-grid {
        grid-template-columns: 1fr;
    }

    .chart-container {
        height: 350px;
    }

    .stats-cards {
        grid-template-columns: 1fr;
    }

    .header h1 {
        font-size: 2rem;
    }
}

.app-container {
    background: #f5f7fa;
}

.data-panel {
    background: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
}

/* 详情面板基础样式 */
.detail-panel {
    background: white;
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
    margin-bottom: 25px;
    border: 1px solid rgba(226, 232, 240, 0.6);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.detail-panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
}

.detail-panel:hover {
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
}

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 25px;
    padding-bottom: 20px;
    border-bottom: 2px solid rgba(226, 232, 240, 0.6);
    position: relative;
}

.detail-header::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 60px;
    height: 2px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    border-radius: 1px;
}

.detail-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1e293b;
    display: flex;
    align-items: center;
    gap: 12px;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.detail-title i {
    font-size: 1.4rem;
    padding: 8px;
    border-radius: 8px;
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
}

.detail-content {
    display: block;
    margin-bottom: 25px;
}

.flamegraph-section {
    margin-top: 25px;
}


.stutter-info,
.callstack-info {
    background: linear-gradient(135deg, rgba(248, 250, 252, 0.95) 0%, rgba(241, 245, 249, 0.95) 100%);
    border-radius: 16px;
    padding: 24px;
    border: 1px solid rgba(226, 232, 240, 0.6);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    position: relative;
    overflow: hidden;
}

.stutter-info::before,
.callstack-info::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
}

.info-title {
    font-size: 1.4rem;
    color: #1e293b;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-weight: 700;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}

.info-title i {
    font-size: 1.2rem;
    padding: 6px;
    border-radius: 6px;
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}

.info-item {
    padding: 18px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    transition: all 0.3s ease;
    border: 1px solid rgba(226, 232, 240, 0.6);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    position: relative;
    overflow: hidden;
}

.info-item::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: linear-gradient(180deg, #3b82f6, #8b5cf6);
    opacity: 0;
    transition: opacity 0.3s ease;
}

.info-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.info-item:hover::before {
    opacity: 1;
}

.info-label {
    color: #64748b;
    font-size: 0.9rem;
    margin-bottom: 8px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.info-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.4;
    color: #1e293b;
}

.callstack-list {
    max-height: 500px;
    overflow-y: auto;
    padding-right: 10px;
}

.callstack-list::-webkit-scrollbar {
    width: 8px;
}

.callstack-list::-webkit-scrollbar-track {
    background: rgba(203, 213, 225, 0.2);
    border-radius: 4px;
}

.callstack-list::-webkit-scrollbar-thumb {
    background: #94a3b8;
    border-radius: 4px;
}

.callstack-item {
    padding: 20px;
    margin-bottom: 15px;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 12px;
    border-left: 4px solid #3b82f6;
    transition: all 0.2s ease;
    border: 1px solid rgba(226, 232, 240, 0.8);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.callstack-item:hover {
    transform: translateX(5px);
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.05);
}

.callstack-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 15px;
}

.callstack-timestamp {
    color: #3b82f6;
    font-weight: 600;
    font-size: 1.1rem;
}

.callstack-load {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
    padding: 6px 15px;
    border-radius: 20px;
    font-size: 0.95rem;
    font-weight: 600;
}

.callstack-chain {
    margin-top: 15px;
    padding-left: 15px;
}

.callstack-frame {
    margin: 12px 0;
    font-family: 'Courier New', monospace;
    color: #475569;
    font-size: 0.95rem;
    word-break: break-all;
    display: flex;
    align-items: flex-start;
}

.callstack-frame i {
    color: #eab308;
    margin-right: 12px;
    margin-top: 4px;
}

.placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 300px;
    color: #94a3b8;
    text-align: center;
    padding: 40px;
    border-radius: 16px;
    background: rgba(241, 245, 249, 0.85);
    border: 2px dashed rgba(203, 213, 225, 0.6);
}

.placeholder i {
    font-size: 3.5rem;
    margin-bottom: 25px;
    color: #94a3b8;
}

.placeholder h3 {
    font-size: 1.6rem;
    margin-bottom: 15px;
    color: #475569;
    font-weight: 600;
}

.placeholder p {
    max-width: 500px;
    line-height: 1.6;
    color: #94a3b8;
    font-size: 1.05rem;
}

.legend {
    display: flex;
    justify-content: center;
    gap: 25px;
    margin-top: 20px;
    flex-wrap: wrap;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 18px;
    background: rgba(241, 245, 249, 0.85);
    border-radius: 25px;
    font-size: 0.95rem;
    color: #475569;
    font-weight: 500;
    border: 1px solid rgba(203, 213, 225, 0.6);
}

.legend-color {
    width: 20px;
    height: 20px;
    border-radius: 5px;
}

.fps-legend {
    background-color: #3b82f6;
}

.trend-legend {
    background-color: #0ea5e9;
}

.stutter-legend {
    background-color: #ef4444;
}

.emptyframe-legend {
    background-color: #8b5cf6;
}

.load-legend {
    background-color: #ec4899;
}

.callstack-list {
    max-height: 350px;
    overflow-y: auto;
    padding-right: 10px;
}

.callstack-list::-webkit-scrollbar {
    width: 8px;
}

.callstack-list::-webkit-scrollbar-track {
    background: rgba(203, 213, 225, 0.2);
    border-radius: 4px;
}

.callstack-list::-webkit-scrollbar-thumb {
    background: #94a3b8;
    border-radius: 4px;
}

.callstack-item {
    padding: 20px;
    margin-bottom: 15px;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 12px;
    border-left: 4px solid #3b82f6;
    transition: all 0.2s ease;
    border: 1px solid rgba(226, 232, 240, 0.8);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.callstack-item:hover {
    transform: translateX(5px);
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.05);
}

.callstack-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 15px;
}

.callstack-timestamp {
    color: #3b82f6;
    font-weight: 600;
    font-size: 1.1rem;
}

.callstack-load {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
    padding: 6px 15px;
    border-radius: 20px;
    font-size: 0.95rem;
    font-weight: 600;
}

.callstack-chain {
    margin-top: 15px;
    padding-left: 15px;
}

.callstack-frame {
    margin: 12px 0;
    font-family: 'Courier New', monospace;
    color: #475569;
    font-size: 0.95rem;
    word-break: break-all;
    display: flex;
    align-items: flex-start;
}

.callstack-frame i {
    color: #eab308;
    margin-right: 12px;
    margin-top: 4px;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-top: 15px;
}

.metric-item {
    background: rgba(255, 255, 255, 0.7);
    border-radius: 12px;
    padding: 15px;
    text-align: center;
    transition: all 0.2s ease;
    border: 1px solid rgba(226, 232, 240, 0.6);
}

.metric-item:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    background: rgba(255, 255, 255, 0.9);
}

.metric-label {
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 8px;
    font-weight: 500;
}

.metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #1e293b;
}

/* 文件使用分析样式 */
.rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 600;
    color: white;
}

.rank-badge.top-rank {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
}

.rank-badge.high-rank {
    background: linear-gradient(135deg, #ffa726 0%, #ff9800 100%);
}

.rank-badge.normal-rank {
    background: linear-gradient(135deg, #66bb6a 0%, #4caf50 100%);
}

.file-name {
    font-size: 14px;
    color: #2d3748;
    font-weight: 500;
    word-break: break-all;
    max-width: 300px;
}

.parent-module {
    font-size: 12px;
    color: #718096;
    word-break: break-all;
    max-width: 200px;
}

/* 父模块展开/收起样式 */
.module-content {
    cursor: pointer;
    display: flex;
    align-items: flex-start;
    gap: 8px;
    transition: all 0.2s ease;
}

.module-content:hover {
    background: rgba(59, 130, 246, 0.05);
    border-radius: 4px;
    padding: 2px 4px;
    margin: -2px -4px;
}

.module-text {
    flex: 1;
    line-height: 1.4;
}

.module-text.truncated {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
}

.expand-icon {
    font-size: 10px;
    color: #3b82f6;
    background: rgba(59, 130, 246, 0.1);
    padding: 2px 6px;
    border-radius: 10px;
    white-space: nowrap;
    font-style: normal;
    font-weight: 500;
    transition: all 0.2s ease;
    flex-shrink: 0;
}

.expand-icon:hover {
    background: rgba(59, 130, 246, 0.2);
    color: #2563eb;
}

.expand-icon.expanded {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
}

.expand-icon.expanded:hover {
    background: rgba(239, 68, 68, 0.2);
    color: #dc2626;
}

/* 空刷帧详情面板样式 */
.emptyframe-panel::before {
    background: linear-gradient(90deg, #8b5cf6, #a855f7);
}

.emptyframe-panel .detail-title i {
    background: rgba(139, 92, 246, 0.1);
    color: #8b5cf6;
}

.emptyframe-panel .detail-header::after {
    background: linear-gradient(90deg, #8b5cf6, #a855f7);
}

.emptyframe-panel .info-title i {
    background: rgba(139, 92, 246, 0.1);
    color: #8b5cf6;
}

.emptyframe-panel .stutter-info::before,
.emptyframe-panel .callstack-info::before {
    background: linear-gradient(90deg, #8b5cf6, #a855f7);
}



/* VSync异常详情面板样式 */
.vsync-anomaly-panel::before {
    background: linear-gradient(90deg, #dc2626, #ef4444);
}

.vsync-anomaly-panel .detail-title i {
    background: rgba(220, 38, 38, 0.1);
    color: #dc2626;
}

.vsync-anomaly-panel .detail-header::after {
    background: linear-gradient(90deg, #dc2626, #ef4444);
}

.vsync-anomaly-panel .info-title i {
    background: rgba(220, 38, 38, 0.1);
    color: #dc2626;
}

.vsync-anomaly-panel .stutter-info::before,
.vsync-anomaly-panel .callstack-info::before {
    background: linear-gradient(90deg, #dc2626, #ef4444);
}

.info-description {
    margin-top: 20px;
    padding: 16px;
    background: linear-gradient(135deg, rgba(248, 250, 252, 0.9) 0%, rgba(241, 245, 249, 0.9) 100%);
    border-radius: 12px;
    border: 1px solid rgba(226, 232, 240, 0.6);
    position: relative;
    overflow: hidden;
}

.info-description::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: linear-gradient(180deg, #3b82f6, #8b5cf6);
}

.info-description .info-label {
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 8px;
    font-size: 0.95rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.info-description .info-value {
    color: #475569;
    line-height: 1.6;
    font-size: 0.95rem;
}
</style>
