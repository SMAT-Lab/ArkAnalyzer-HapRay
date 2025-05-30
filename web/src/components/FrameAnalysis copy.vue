<template>
    <div class="app-container">
        <div class="header">
            <h1>卡顿帧数据分析</h1>
            <p>场景性能指标，分析卡顿问题，优化用户体验</p>
        </div>

        <div class="stats-cards">
            <div class="stat-card">
                <div class="card-title">
                    <i>📊</i> 总帧数
                </div>
                <div class="card-value">{{ formatNumber(performanceData.statistics.total_frames) }}</div>
                <div class="progress-bar">
                    <div class="progress-value"
                        :style="{ width: '100%', background: 'linear-gradient(90deg, #38bdf8, #818cf8)' }"></div>
                </div>
                <div class="card-desc">应用渲染的总帧数，反映整体运行情况</div>
                <div class="card-badge" style="background: rgba(56, 189, 248, 0.1); color: #38bdf8;">基准指标</div>
            </div>

            <div class="stat-card">
                <div class="card-title">
                    <i>⚠️</i> 卡顿帧数
                </div>
                <div class="card-value">{{ performanceData.statistics.total_stutter_frames }}</div>
                <div class="progress-bar">
                    <div class="progress-value"
                        :style="{ width: (performanceData.statistics.stutter_rate * 100) + '%', background: '#f97316' }">
                    </div>
                </div>
                <div class="card-desc">UI卡顿: {{ performanceData.statistics.ui_stutter_frames }} | 渲染卡顿: {{
                    performanceData.statistics.render_stutter_frames }}</div>
                <div class="stat-trend"
                    :class="performanceData.statistics.stutter_rate < 0.2 ? 'trend-down' : 'trend-up'">
                    <span v-if="performanceData.statistics.stutter_rate < 0.2">↓ 低于阈值</span>
                    <span v-else>↑ 高于阈值</span>
                    (阈值: 20%)
                </div>
            </div>

            <div class="stat-card">
                <div class="card-title">
                    <i>📉</i> 卡顿率
                </div>
                <div class="card-value">{{ (performanceData.statistics.stutter_rate * 100).toFixed(2) }}%</div>
                <div class="progress-bar">
                    <div class="progress-value"
                        :style="{ width: (performanceData.statistics.stutter_rate * 100) + '%', background: '#ef4444' }">
                    </div>
                </div>
                <div class="card-desc">卡顿帧数占总帧数的比例，越低越好</div>
                <div class="card-badge"
                    :style="performanceData.statistics.stutter_rate < 0.2 ? 'background: rgba(16, 185, 129, 0.1); color: #10b981;' : 'background: rgba(239, 68, 68, 0.1); color: #ef4444;'">
                    {{ performanceData.statistics.stutter_rate < 0.2 ? '良好' : '警告' }} </div>
                </div>

                <div class="stat-card">
                    <div class="card-title">
                        <i>⚡</i> 平均FPS
                    </div>
                    <div class="card-value">{{ performanceData.fps_stats.average_fps.toFixed(2) }}</div>
                    <div class="progress-bar">
                        <div class="progress-value"
                            :style="{ width: Math.min(100, (performanceData.fps_stats.average_fps / 120) * 100) + '%', background: 'linear-gradient(90deg, #10b981, #38bdf8)' }">
                        </div>
                    </div>
                    <div class="card-desc">最低: {{ performanceData.fps_stats.min_fps.toFixed(2) }} | 最高: {{
                        performanceData.fps_stats.max_fps.toFixed(2) }}</div>
                    <div class="stat-trend"
                        :class="performanceData.fps_stats.average_fps > 60 ? 'trend-down' : 'trend-up'">
                        <span v-if="performanceData.fps_stats.average_fps > 60">✓ 流畅体验</span>
                        <span v-else>⚠ 需优化</span>
                        (目标: 60 FPS)
                    </div>
                </div>
            </div>

            <div class="chart-grid">
                <div class="chart-container">
                    <div class="chart-title">
                        <i>📈</i> FPS变化趋势
                    </div>
                    <div class="chart" ref="fpsChart"></div>
                </div>

                <div class="chart-container">
                    <div class="chart-title">
                        <i>🍰</i> 卡顿级别分布
                    </div>
                    <div class="chart" ref="stutterPieChart"></div>
                </div>
            </div>

            <div class="chart-grid">
                <div class="chart-container">
                    <div class="chart-title">
                        <i>⏱️</i> 帧耗时分析
                    </div>
                    <div class="chart" ref="durationChart"></div>
                </div>

                <div class="chart-container">
                    <div class="chart-title">
                        <i>📊</i> FPS分布统计
                    </div>
                    <div class="chart" ref="fpsHistogram"></div>
                </div>
            </div>

            <div class="table-container">
                <div class="table-title">
                    <i>📋</i> 卡顿详情
                </div>

                <div class="filters">
                    <div class="filter-item" :class="{ active: activeFilter === 'all' }" @click="activeFilter = 'all'">
                        全部卡顿 ({{ performanceData.statistics.total_stutter_frames }})
                    </div>
                    <div class="filter-item" :class="{ active: activeFilter === 'level_1' }"
                        @click="activeFilter = 'level_1'">
                        轻微卡顿 ({{ performanceData.statistics.stutter_levels.level_1 }})
                    </div>
                    <div class="filter-item" :class="{ active: activeFilter === 'level_2' }"
                        @click="activeFilter = 'level_2'">
                        中度卡顿 ({{ performanceData.statistics.stutter_levels.level_2 }})
                    </div>
                    <div class="filter-item" :class="{ active: activeFilter === 'level_3' }"
                        @click="activeFilter = 'level_3'">
                        严重卡顿 ({{ performanceData.statistics.stutter_levels.level_3 }})
                    </div>
                </div>

                <table class="data-table">
                    <thead>
                        <tr>
                            <th>VSync</th>
                            <th>卡顿级别</th>
                            <th>实际耗时(ms)</th>
                            <th>预期耗时(ms)</th>
                            <th>超出时间</th>
                            <th>超出帧数</th>
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
                            <td :class="stutter.exceed_frames >= 0 ? 'negative' : 'positive'">
                                {{ stutter.exceed_frames >= 0 ? '+' : '' }}{{ stutter.exceed_frames.toFixed(2) }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="footer">
                <p>性能监控仪表盘 © 2023 | 基于 Vue3 + TypeScript + ECharts | 数据更新时间: {{ new Date().toLocaleString() }}</p>
            </div>
        </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  hideColumn: {
    type: Boolean,
    required: true,
  }
});

// 性能数据
const performanceData = ref({
    "runtime": "2025-05-30 19:05:3",
    "statistics": {
        "total_frames": 3049,
        "ui_stutter_frames": 4,
        "render_stutter_frames": 0,
        "total_stutter_frames": 4,
        "stutter_rate": 0.13,
        "stutter_levels": {
            "level_1": 4,
            "level_2": 0,
            "level_3": 0
        }
    },
    "stutter_details": {
        "ui_stutter": [
            {
                "vsync": 238043,
                "timestamp": 166441508002025,
                "actual_duration": 5166666,
                "expected_duration": 8359114,
                "exceed_time": -3.192448,
                "exceed_frames": -0.19150857828434312,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 3050
            },
            {
                "vsync": 238486,
                "timestamp": 166445214378587,
                "actual_duration": 4370833,
                "expected_duration": 8359765,
                "exceed_time": -3.988932,
                "exceed_frames": -0.23928806238752248,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 6630
            },
            {
                "vsync": 240368,
                "timestamp": 166460939655667,
                "actual_duration": 17349480,
                "expected_duration": 8336588,
                "exceed_time": 9.012892,
                "exceed_frames": 0.5406653869226155,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 20686
            },
            {
                "vsync": 240369,
                "timestamp": 166460959777021,
                "actual_duration": 1351042,
                "expected_duration": 8336588,
                "exceed_time": -6.985546,
                "exceed_frames": -0.41904895020995797,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 20686
            }
        ],
        "render_stutter": []
    },
    "fps_stats": {
        "average_fps": 73.82758620689656,
        "min_fps": 29.0,
        "max_fps": 118.0,
        "fps_windows": [
            {
                "start_time": 0.0,
                "end_time": 1.0,
                "start_time_ts": 166438361085358,
                "end_time_ts": 166439361085358,
                "frame_count": 85,
                "fps": 85.0
            },
            {
                "start_time": 1.0,
                "end_time": 2.0,
                "start_time_ts": 166439361085358,
                "end_time_ts": 166440361085358,
                "frame_count": 95,
                "fps": 95.0
            },
            {
                "start_time": 2.0,
                "end_time": 3.0,
                "start_time_ts": 166440361085358,
                "end_time_ts": 166441361085358,
                "frame_count": 87,
                "fps": 87.0
            },
            {
                "start_time": 3.0,
                "end_time": 4.0,
                "start_time_ts": 166441361085358,
                "end_time_ts": 166442361085358,
                "frame_count": 118,
                "fps": 118.0
            },
            {
                "start_time": 4.0,
                "end_time": 5.0,
                "start_time_ts": 166442361085358,
                "end_time_ts": 166443361085358,
                "frame_count": 77,
                "fps": 77.0
            },
            {
                "start_time": 5.0,
                "end_time": 6.0,
                "start_time_ts": 166443361085358,
                "end_time_ts": 166444361085358,
                "frame_count": 90,
                "fps": 90.0
            },
            {
                "start_time": 6.0,
                "end_time": 7.0,
                "start_time_ts": 166444361085358,
                "end_time_ts": 166445361085358,
                "frame_count": 98,
                "fps": 98.0
            },
            {
                "start_time": 7.0,
                "end_time": 8.0,
                "start_time_ts": 166445361085358,
                "end_time_ts": 166446361085358,
                "frame_count": 62,
                "fps": 62.0
            },
            {
                "start_time": 8.0,
                "end_time": 9.0,
                "start_time_ts": 166446361085358,
                "end_time_ts": 166447361085358,
                "frame_count": 112,
                "fps": 112.0
            },
            {
                "start_time": 9.0,
                "end_time": 10.0,
                "start_time_ts": 166447361085358,
                "end_time_ts": 166448361085358,
                "frame_count": 42,
                "fps": 42.0
            },
            {
                "start_time": 10.0,
                "end_time": 11.0,
                "start_time_ts": 166448361085358,
                "end_time_ts": 166449361085358,
                "frame_count": 70,
                "fps": 70.0
            },
            {
                "start_time": 11.0,
                "end_time": 12.0,
                "start_time_ts": 166449361085358,
                "end_time_ts": 166450361085358,
                "frame_count": 91,
                "fps": 91.0
            },
            {
                "start_time": 12.0,
                "end_time": 13.0,
                "start_time_ts": 166450361085358,
                "end_time_ts": 166451361085358,
                "frame_count": 35,
                "fps": 35.0
            },
            {
                "start_time": 13.0,
                "end_time": 14.0,
                "start_time_ts": 166451361085358,
                "end_time_ts": 166452361085358,
                "frame_count": 103,
                "fps": 103.0
            },
            {
                "start_time": 14.0,
                "end_time": 15.0,
                "start_time_ts": 166452361085358,
                "end_time_ts": 166453361085358,
                "frame_count": 53,
                "fps": 53.0
            },
            {
                "start_time": 15.0,
                "end_time": 16.0,
                "start_time_ts": 166453361085358,
                "end_time_ts": 166454361085358,
                "frame_count": 69,
                "fps": 69.0
            },
            {
                "start_time": 16.0,
                "end_time": 17.0,
                "start_time_ts": 166454361085358,
                "end_time_ts": 166455361085358,
                "frame_count": 89,
                "fps": 89.0
            },
            {
                "start_time": 17.0,
                "end_time": 18.0,
                "start_time_ts": 166455361085358,
                "end_time_ts": 166456361085358,
                "frame_count": 36,
                "fps": 36.0
            },
            {
                "start_time": 18.0,
                "end_time": 19.0,
                "start_time_ts": 166456361085358,
                "end_time_ts": 166457361085358,
                "frame_count": 118,
                "fps": 118.0
            },
            {
                "start_time": 19.0,
                "end_time": 20.0,
                "start_time_ts": 166457361085358,
                "end_time_ts": 166458361085358,
                "frame_count": 91,
                "fps": 91.0
            },
            {
                "start_time": 20.0,
                "end_time": 21.0,
                "start_time_ts": 166458361085358,
                "end_time_ts": 166459361085358,
                "frame_count": 84,
                "fps": 84.0
            },
            {
                "start_time": 21.0,
                "end_time": 22.0,
                "start_time_ts": 166459361085358,
                "end_time_ts": 166460361085358,
                "frame_count": 104,
                "fps": 104.0
            },
            {
                "start_time": 22.0,
                "end_time": 23.0,
                "start_time_ts": 166460361085358,
                "end_time_ts": 166461361085358,
                "frame_count": 65,
                "fps": 65.0
            },
            {
                "start_time": 23.0,
                "end_time": 24.0,
                "start_time_ts": 166461361085358,
                "end_time_ts": 166462361085358,
                "frame_count": 49,
                "fps": 49.0
            },
            {
                "start_time": 24.0,
                "end_time": 25.0,
                "start_time_ts": 166462361085358,
                "end_time_ts": 166463361085358,
                "frame_count": 45,
                "fps": 45.0
            },
            {
                "start_time": 25.0,
                "end_time": 26.0,
                "start_time_ts": 166463361085358,
                "end_time_ts": 166464361085358,
                "frame_count": 54,
                "fps": 54.0
            },
            {
                "start_time": 26.0,
                "end_time": 27.0,
                "start_time_ts": 166464361085358,
                "end_time_ts": 166465361085358,
                "frame_count": 32,
                "fps": 32.0
            },
            {
                "start_time": 27.0,
                "end_time": 28.0,
                "start_time_ts": 166465361085358,
                "end_time_ts": 166466361085358,
                "frame_count": 29,
                "fps": 29.0
            },
            {
                "start_time": 28.0,
                "end_time": 29.0,
                "start_time_ts": 166466361085358,
                "end_time_ts": 166467361085358,
                "frame_count": 58,
                "fps": 58.0
            }
        ],
        "low_fps_window_count": 45
    }
});

// 图表引用
const fpsChart = ref(null);
const stutterPieChart = ref(null);
const durationChart = ref(null);
const fpsHistogram = ref(null);

// 卡顿筛选
const activeFilter = ref('all');

// 格式化大数字
const formatNumber = (num) => {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

// 筛选卡顿数据
const filteredStutters = computed(() => {
    const allStutters = [
        ...performanceData.value.stutter_details.ui_stutter,
        ...performanceData.value.stutter_details.render_stutter
    ];

    if (activeFilter.value === 'all') return allStutters;

    const level = parseInt(activeFilter.value.split('_')[1]);
    return allStutters.filter(stutter => stutter.stutter_level === level);
});

// 获取卡顿级别对应的颜色
const getStutterColor = (level) => {
    const colors = {
        1: '#fbbf24', // 轻微卡顿 - 黄色
        2: '#f97316', // 中度卡顿 - 橙色
        3: '#ef4444'  // 严重卡顿 - 红色
    };
    return colors[level] || '#999';
};

// 初始化图表
const initCharts = () => {
    // FPS折线图
    if (fpsChart.value) {
        const fpsChartInstance = echarts.init(fpsChart.value);
        const fpsData = performanceData.value.fps_stats.fps_windows;
        const fpsValues = fpsData.map(item => item.fps);
        const timeLabels = fpsData.map((item, index) => `${index + 1}`);

        // 找出所有卡顿点
        const stutterPoints = [];
        const allStutters = [
            ...performanceData.value.stutter_details.ui_stutter,
            ...performanceData.value.stutter_details.render_stutter
        ];

        // 为每个卡顿点找到最近的FPS窗口
        allStutters.forEach(stutter => {
            // 找到时间戳最接近的FPS窗口
            let minDiff = Infinity;
            let closestIndex = -1;

            fpsData.forEach((window, index) => {
                const diff = Math.abs(stutter.timestamp - window.start_time_ts);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIndex = index;
                }
            });

            if (closestIndex !== -1) {
                stutterPoints.push({
                    x: closestIndex,
                    y: fpsValues[closestIndex],
                    stutter: stutter
                });
            }
        });

        const fpsOption = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                formatter: function (params) {
                    const data = params[0];
                    const index = data.dataIndex;
                    const windowData = fpsData[index];
                    let tooltip = `窗口: ${index + 1}<br/>
                                开始时间: ${windowData.start_time}<br/>
                                结束时间: ${windowData.end_time}<br/>
                                FPS: ${data.value}`;

                    // 检查是否有卡顿点
                    const stutterInWindow = stutterPoints.filter(p => p.x === index);
                    if (stutterInWindow.length > 0) {
                        tooltip += '<br/><br/><strong>卡顿事件:</strong>';
                        stutterInWindow.forEach((p, i) => {
                            tooltip += `<br/>${i + 1}. VSync: ${p.stutter.vsync} (${p.stutter.level_description})`;
                        });
                    }

                    return tooltip;
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '12%',
                top: '10%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: timeLabels,
                name: '时间窗口',
                nameLocation: 'middle',
                nameGap: 30,
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                axisLabel: {
                    interval: Math.floor(timeLabels.length / 5),
                    rotate: 45,
                    color: '#94a3b8'
                }
            },
            yAxis: {
                type: 'value',
                name: 'FPS',
                nameTextStyle: {
                    color: '#94a3b8'
                },
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(148, 163, 184, 0.1)'
                    }
                }
            },
            dataZoom: [
                {
                    type: 'inside',
                    start: 0,
                    end: 100
                },
                {
                    type: 'slider',
                    show: true,
                    start: 0,
                    end: 100,
                    height: 20,
                    bottom: 20,
                    handleSize: 10,
                    fillerColor: 'rgba(56, 189, 248, 0.2)',
                    borderColor: 'rgba(74, 85, 104, 0.5)',
                    handleStyle: {
                        color: '#38bdf8'
                    },
                    textStyle: {
                        color: '#94a3b8'
                    }
                }
            ],
            series: [
                {
                    name: 'FPS',
                    type: 'line',
                    data: fpsValues,
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    lineStyle: {
                        width: 3,
                        color: '#38bdf8'
                    },
                    itemStyle: {
                        color: '#38bdf8'
                    },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(56, 189, 248, 0.3)' },
                            { offset: 1, color: 'rgba(56, 189, 248, 0.05)' }
                        ])
                    },
                    markLine: {
                        silent: true,
                        lineStyle: {
                            color: '#10b981'
                        },
                        data: [
                            {
                                yAxis: 60,
                                name: '目标FPS',
                                label: {
                                    formatter: '目标FPS: 60',
                                    position: 'end',
                                    color: '#94a3b8'
                                }
                            }
                        ]
                    }
                },
                // 卡顿点系列
                {
                    name: '卡顿点',
                    type: 'scatter',
                    data: stutterPoints.map(p => [p.x, p.y]),
                    symbolSize: 16,
                    itemStyle: {
                        color: function (params) {
                            return getStutterColor(stutterPoints[params.dataIndex].stutter.stutter_level);
                        },
                        borderColor: '#fff',
                        borderWidth: 2,
                        shadowColor: 'rgba(0, 0, 0, 0.5)',
                        shadowBlur: 5
                    },
                    tooltip: {
                        formatter: function (params) {
                            const stutter = stutterPoints[params.dataIndex].stutter;
                            return `卡顿事件<br/>
                              VSync: ${stutter.vsync}<br/>
                              级别: ${stutter.stutter_level} - ${stutter.level_description}<br/>
                              实际耗时: ${(stutter.actual_duration / 1000000).toFixed(2)}ms<br/>
                              预期耗时: ${(stutter.expected_duration / 1000000).toFixed(2)}ms`;
                        }
                    }
                }
            ]
        };
        fpsChartInstance.setOption(fpsOption);
    }

    // 卡顿级别饼图
    if (stutterPieChart.value) {
        const stutterPieChartInstance = echarts.init(stutterPieChart.value);
        const stutterLevels = performanceData.value.statistics.stutter_levels;

        const pieOption = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'item',
                formatter: '{a} <br/>{b}: {c} 帧 ({d}%)'
            },
            legend: {
                orient: 'vertical',
                right: 10,
                top: 'center'
            },
            series: [
                {
                    name: '卡顿级别',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    center: ['40%', '50%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 10,
                        borderColor: 'rgba(15, 23, 42, 0.7)',
                        borderWidth: 2
                    },
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: '18',
                            fontWeight: 'bold',
                        }
                    },
                    labelLine: {
                        show: false
                    },
                    data: [
                        {
                            value: stutterLevels.level_1,
                            name: '轻微卡顿',
                            itemStyle: {
                                color: '#fbbf24'
                            }
                        },
                        {
                            value: stutterLevels.level_2,
                            name: '中度卡顿',
                            itemStyle: {
                                color: '#f97316'
                            }
                        },
                        {
                            value: stutterLevels.level_3,
                            name: '严重卡顿',
                            itemStyle: {
                                color: '#ef4444'
                            }
                        }
                    ]
                }
            ]
        };
        stutterPieChartInstance.setOption(pieOption);
    }

    // 帧耗时分析图
    if (durationChart.value) {
        const durationChartInstance = echarts.init(durationChart.value);
        const stutters = performanceData.value.stutter_details.ui_stutter;

        const durationOption = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                },
                formatter: function (params) {
                    const data = params[0];
                    const stutter = stutters[data.dataIndex];
                    return `VSync: ${stutter.vsync}<br/>
                          实际耗时: ${(stutter.actual_duration / 1000000).toFixed(2)}ms<br/>
                          预期耗时: ${(stutter.expected_duration / 1000000).toFixed(2)}ms<br/>
                          级别: <span style="color:${getStutterColor(stutter.stutter_level)}">${stutter.level_description}</span>`;
                }
            },
            legend: {
                data: ['实际耗时', '预期耗时'],
                textStyle: {
                    color: '#94a3b8'
                },
                right: 10,
                top: 10
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                top: '15%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: stutters.map(s => s.vsync),
                name: 'VSync',
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                axisLabel: {
                    color: '#94a3b8'
                }
            },
            yAxis: {
                type: 'value',
                name: '耗时 (ms)',
                nameTextStyle: {
                    color: '#94a3b8'
                },
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(148, 163, 184, 0.1)'
                    }
                }
            },
            series: [
                {
                    name: '实际耗时',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    data: stutters.map(s => s.actual_duration / 1000000),
                    itemStyle: {
                        color: function (params) {
                            return getStutterColor(stutters[params.dataIndex].stutter_level);
                        }
                    }
                },
                {
                    name: '预期耗时',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    data: stutters.map(s => s.expected_duration / 1000000),
                    itemStyle: {
                        color: '#10b981'
                    }
                }
            ]
        };
        durationChartInstance.setOption(durationOption);
    }

    // FPS分布直方图
    if (fpsHistogram.value) {
        const fpsHistogramInstance = echarts.init(fpsHistogram.value);
        const fpsData = performanceData.value.fps_stats.fps_windows.map(w => w.fps);

        // 计算FPS分布区间
        const bins = [0, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120];
        const counts = new Array(bins.length - 1).fill(0);

        fpsData.forEach(fps => {
            for (let i = 0; i < bins.length - 1; i++) {
                if (fps >= bins[i] && fps < bins[i + 1]) {
                    counts[i]++;
                    break;
                }
            }
        });

        const histogramOption = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                },
                formatter: '{b0}<br/>计数: {c0}'
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                top: '10%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: bins.slice(0, -1).map((_, i) => `${bins[i]}-${bins[i + 1]}`),
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                axisLabel: {
                    interval: 0,
                    rotate: 45,
                    color: '#94a3b8'
                }
            },
            yAxis: {
                type: 'value',
                name: '计数',
                nameTextStyle: {
                    color: '#94a3b8'
                },
                axisLine: {
                    lineStyle: {
                        color: '#94a3b8'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(148, 163, 184, 0.1)'
                    }
                }
            },
            series: [
                {
                    name: 'FPS分布',
                    type: 'bar',
                    data: counts,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#38bdf8' },
                            { offset: 1, color: '#818cf8' }
                        ])
                    },
                    markLine: {
                        silent: true,
                        lineStyle: {
                            color: '#10b981'
                        },
                        data: [
                            {
                                xAxis: '60-70',
                                name: '目标FPS区间',
                                label: {
                                    formatter: '目标FPS: 60+',
                                    position: 'end',
                                    color: '#94a3b8'
                                }
                            }
                        ]
                    }
                }
            ]
        };
        fpsHistogramInstance.setOption(histogramOption);
    }

    // 响应窗口大小变化
    window.addEventListener('resize', () => {
        if (fpsChart.value) echarts.getInstanceByDom(fpsChart.value)?.resize();
        if (stutterPieChart.value) echarts.getInstanceByDom(stutterPieChart.value)?.resize();
        if (durationChart.value) echarts.getInstanceByDom(durationChart.value)?.resize();
        if (fpsHistogram.value) echarts.getInstanceByDom(fpsHistogram.value)?.resize();
    });
};

// 格式化时间戳
const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    // 简化为只显示时间部分
    const date = new Date(ts / 1000000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};
onMounted(() => {
    initCharts();
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
    /* color: #e2e8f0; */
    min-height: 100vh;
    padding: 20px;
}

.app-container {
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    margin-bottom: 30px;
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
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
    margin-bottom: 10px;
    background: linear-gradient(90deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 700;
}

.header p {
    font-size: 1.1rem;
    color: #94a3b8;
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
    margin-bottom: 30px;
}

.stat-card {
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    position: relative;
    overflow: hidden;
}

.stat-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}

.card-title {
    font-size: 1rem;
    color: #94a3b8;
    margin-bottom: 15px;
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
    margin-bottom: 10px;
}

.card-desc {
    font-size: 0.9rem;
    color: #94a3b8;
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
    margin-bottom: 30px;
}

.chart-container {
    border-radius: 16px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    height: 400px;
    position: relative;
    overflow: hidden;
}

.chart-title {
    font-size: 1.2rem;
    margin-bottom: 20px;
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
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    margin-bottom: 30px;
}

.table-title {
    font-size: 1.2rem;
    margin-bottom: 20px;
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
    color: #94a3b8;
    font-size: 0.9rem;
}

.filters {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
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
</style>