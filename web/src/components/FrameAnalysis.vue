<template>
    <div class="app-container">
        <div class="header">
            <h1>卡顿帧数据分析</h1>
            <p>全面展示场景的帧率表现、卡顿情况和性能指标，帮助开发者优化用户体验</p>
        </div>

        <div class="stats-cards">
            <div class="stat-card">
                <div class="card-title">
                    <i>📊</i> 总帧数
                </div>
                <div class="card-value">{{ formatNumber(performanceData.statistics.total_frames) }}</div>
                <div class="card-desc">应用程序渲染的总帧数，反映了整体运行情况</div>
            </div>
            <!-- <div class="stat-card">
                <div class="card-title">
                    <i>📉</i> 丢帧数
                </div>
                <div class="card-value">{{ formatNumber(performanceData.statistics.total_frames) }}</div>
                <div class="card-desc">渲染过程中丢失的帧数，反映渲染稳定性</div>
            </div>
            <div class="stat-card">
                <div class="card-title">
                    <i>🚦</i> 丢帧率
                </div>
                <div class="card-value">{{ (performanceData.statistics.stutter_rate * 100).toFixed(2) }}%</div>
                <div class="card-desc">丢帧数占总帧数的比例，越低表示渲染越流畅</div>
            </div> -->
            <div class="stat-card">
                <div class="card-title">
                    <i>⚠️</i> 卡顿帧数
                </div>
                <div class="card-value">{{ performanceData.statistics.total_stutter_frames }}</div>
                <div class="card-desc">UI卡顿: {{ performanceData.statistics.ui_stutter_frames }} | 渲染卡顿: {{
                    performanceData.statistics.render_stutter_frames }}</div>
            </div>

            <div class="stat-card">
                <div class="card-title">
                    <i>📉</i> 卡顿率
                </div>
                <div class="card-value">{{ (performanceData.statistics.stutter_rate * 100).toFixed(2) }}%</div>
                <div class="card-desc">卡顿帧数占总帧数的比例，越低越好</div>
            </div>

            <div class="stat-card">
                <div class="card-title">
                    <i>⚡</i> 平均FPS
                </div>
                <div class="card-value">{{ performanceData.fps_stats.average_fps.toFixed(2) }}</div>
                <div class="card-desc">最低: {{ performanceData.fps_stats.min_fps.toFixed(2) }} | 最高: {{
                    performanceData.fps_stats.max_fps.toFixed(2) }}</div>
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
                            {{ stutter.stutter_level }} - {{ stutter.level_description }}
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
    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import * as echarts from 'echarts';
// 性能数据
const performanceData = ref({
    "statistics": {
        "total_frames": 2421,
        "ui_stutter_frames": 4,
        "render_stutter_frames": 0,
        "total_stutter_frames": 4,
        "stutter_rate": 0.17,
        "stutter_levels": {
            "level_1": 4,
            "level_2": 0,
            "level_3": 0
        }
    },
    "stutter_details": {
        "ui_stutter": [
            {
                "vsync": 115880,
                "timestamp": 73872642502082,
                "actual_duration": 2146875,
                "expected_duration": 8365755,
                "exceed_time": -6.21888,
                "exceed_frames": -0.3730581883623275,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 6548
            },
            {
                "vsync": 117577,
                "timestamp": 73888101290101,
                "actual_duration": 19391666,
                "expected_duration": 16724478,
                "exceed_time": 2.667188,
                "exceed_frames": 0.1599992801439712,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 16563
            },
            {
                "vsync": 117769,
                "timestamp": 73891104478121,
                "actual_duration": 21165104,
                "expected_duration": 16721093,
                "exceed_time": 4.444011,
                "exceed_frames": 0.26658734253149363,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 17474
            },
            {
                "vsync": 117961,
                "timestamp": 73894109691142,
                "actual_duration": 16583332,
                "expected_duration": 16711328,
                "exceed_time": -0.127996,
                "exceed_frames": -0.007678224355128973,
                "stutter_level": 1,
                "level_description": "轻微卡顿",
                "src": "",
                "dst": 18373
            }
        ],
        "render_stutter": []
    },
    "fps_stats": {
        "average_fps": 95.73022447015995,
        "min_fps": 0.0,
        "max_fps": 919.1765096346386,
        "low_fps_window_count": 9,
        "fps_windows": [
            {
                "start_time": 73865624093229,
                "end_time": 73866624093229,
                "frame_count": 111,
                "fps": 111.0
            },
            {
                "start_time": 73866624093229,
                "end_time": 73867624093229,
                "frame_count": 82,
                "fps": 82.0
            },
            {
                "start_time": 73867624093229,
                "end_time": 73868624093229,
                "frame_count": 84,
                "fps": 84.0
            },
            {
                "start_time": 73868624093229,
                "end_time": 73869624093229,
                "frame_count": 119,
                "fps": 119.0
            },
            {
                "start_time": 73869624093229,
                "end_time": 73870624093229,
                "frame_count": 65,
                "fps": 65.0
            },
            {
                "start_time": 73870624093229,
                "end_time": 73871624093229,
                "frame_count": 89,
                "fps": 89.0
            },
            {
                "start_time": 73871624093229,
                "end_time": 73872624093229,
                "frame_count": 120,
                "fps": 120.0
            },
            {
                "start_time": 73872624093229,
                "end_time": 73873624093229,
                "frame_count": 62,
                "fps": 62.0
            },
            {
                "start_time": 73873624093229,
                "end_time": 73874624093229,
                "frame_count": 117,
                "fps": 117.0
            },
            {
                "start_time": 73874624093229,
                "end_time": 73875624093229,
                "frame_count": 13,
                "fps": 13.0
            },
            {
                "start_time": 73875624093229,
                "end_time": 73876624093229,
                "frame_count": 58,
                "fps": 58.0
            },
            {
                "start_time": 73876624093229,
                "end_time": 73877624093229,
                "frame_count": 72,
                "fps": 72.0
            },
            {
                "start_time": 73877624093229,
                "end_time": 73878624093229,
                "frame_count": 105,
                "fps": 105.0
            },
            {
                "start_time": 73878624093229,
                "end_time": 73879624093229,
                "frame_count": 119,
                "fps": 119.0
            },
            {
                "start_time": 73879624093229,
                "end_time": 73880624093229,
                "frame_count": 16,
                "fps": 16.0
            },
            {
                "start_time": 73880624093229,
                "end_time": 73881624093229,
                "frame_count": 82,
                "fps": 82.0
            },
            {
                "start_time": 73881624093229,
                "end_time": 73882624093229,
                "frame_count": 70,
                "fps": 70.0
            },
            {
                "start_time": 73882624093229,
                "end_time": 73883624093229,
                "frame_count": 0,
                "fps": 0.0
            },
            {
                "start_time": 73883624093229,
                "end_time": 73884624093229,
                "frame_count": 111,
                "fps": 111.0
            },
            {
                "start_time": 73884624093229,
                "end_time": 73885624093229,
                "frame_count": 84,
                "fps": 84.0
            },
            {
                "start_time": 73885624093229,
                "end_time": 73886624093229,
                "frame_count": 88,
                "fps": 88.0
            },
            {
                "start_time": 73886624093229,
                "end_time": 73887624093229,
                "frame_count": 78,
                "fps": 78.0
            },
            {
                "start_time": 73887624093229,
                "end_time": 73888624093229,
                "frame_count": 43,
                "fps": 43.0
            },
            {
                "start_time": 73888624093229,
                "end_time": 73889624093229,
                "frame_count": 6,
                "fps": 6.0
            },
            {
                "start_time": 73889624093229,
                "end_time": 73890624093229,
                "frame_count": 19,
                "fps": 19.0
            },
            {
                "start_time": 73890624093229,
                "end_time": 73891624093229,
                "frame_count": 44,
                "fps": 44.0
            },
            {
                "start_time": 73891624093229,
                "end_time": 73892624093229,
                "frame_count": 0,
                "fps": 0.0
            },
            {
                "start_time": 73892624093229,
                "end_time": 73893624093229,
                "frame_count": 0,
                "fps": 0.0
            },
            {
                "start_time": 73893624093229,
                "end_time": 73894237685933,
                "frame_count": 564,
                "fps": 919.1765096346386
            }
        ]
    }
});

// 图表引用
const fpsChart = ref(null);
const stutterPieChart = ref(null);

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

// 初始化图表
const initCharts = (aggregatedData) => {
    // FPS折线图
    const fpsChartInstance = echarts.init(fpsChart.value);
    const timeLabels = aggregatedData.map(item => item.x);
    const fpsValues = aggregatedData.map(item => item.y);
    const stutterMarkers = aggregatedData.map(item => item.hasStutter);

    const fpsOption = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            formatter: '{b0}<br/>FPS: {c0}'
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            top: '10%',
            containLabel: true
        },
        xAxis: { data: timeLabels },
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
                handleSize: 8,
                backgroundColor: 'rgba(30, 41, 59, 0.8)',
                fillerColor: 'rgba(56, 189, 248, 0.2)',
                borderColor: 'rgba(74, 85, 104, 0.5)',
                handleStyle: {
                    color: '#38bdf8'
                }
            }
        ],
        series: [
            {
                name: 'FPS',
                type: 'line',
                data: fpsValues.map((y, i) => ({
                    value: y,
                    symbol: stutterMarkers[i] ? 'circle' : 'circle',
                    symbolSize: 8,
                    itemStyle: { color: stutterMarkers[i] ? '#ff9f1a' : '#38bdf8' } // 黄点（#ff9f1a）替代红点示例
                })),
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
                                position: 'end'
                            }
                        }
                    ]
                }
            }
        ]
    };
    fpsChartInstance.setOption(fpsOption);

    // 卡顿级别饼图
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
            top: 'center',
            //   textStyle: {
            //     color: '#e2e8f0'
            //   }
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
                        // fontWeight: 'bold',
                        // color: '#e2e8f0'
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

    // 响应窗口大小变化
    window.addEventListener('resize', () => {
        fpsChartInstance.resize();
        stutterPieChartInstance.resize();
    });
};

const aggregateByTimeWindow = (data, windowSize = 1000) => {
    const grouped = {};
    data.forEach((item) => {
        const windowStart = Math.floor(item.timestamp / windowSize) * windowSize;
        if (!grouped[windowStart]) {
            grouped[windowStart] = { start: windowStart, fpsValues: [], hasStutter: false };
        }
        grouped[windowStart].fpsValues.push(item.fps);
        grouped[windowStart].hasStutter = grouped[windowStart].hasStutter || (item.fps < 30);
    });
    
    // 格式化时间戳为完整的日期时间字符串
    return Object.values(grouped).map(group => ({
        x: formatTimestamp(group.start), // 使用自定义格式化函数
        y: group.fpsValues.length ? group.fpsValues.reduce((a, b) => a + b, 0) / group.fpsValues.length : 0,
        hasStutter: group.hasStutter
    }));
};

// 新增：自定义时间戳格式化函数
const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false // 使用24小时制
    }).replace(/\//g, '-'); // 将斜杠替换为连字符，使格式更统一
};
onMounted(() => {
    const rawFrames = performanceData.value.fps_stats.fps_windows.flatMap(window =>
        Array(window.frame_count).fill({
            timestamp: window.start_time,
            fps: window.fps
        })
    );
    const aggregatedData = aggregateByTimeWindow(rawFrames, 2000); // 2秒窗口
    initCharts(aggregatedData);
});



</script>

<!-- 自定义统计卡片组件 -->
<!-- <template #StatCard="{ title, value, unit, color }">
  <el-card class="stat-card" :style="{ backgroundColor: color + '10' }">
    <div class="stat-content">
      <span class="stat-title">{{ title }}</span>
      <div class="stat-value">
        {{ value }}
        <span class="unit">{{ unit }}</span>
      </div>
    </div>
  </el-card>
</template> -->

<style scoped>
.app-container {
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    margin-bottom: 20px;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
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

.stats-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.stat-card {
    border-radius: 12px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
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

.chart-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.chart-container {
    border-radius: 12px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    height: 400px;
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
}

.chart {
    width: 100%;
    height: calc(100% - 40px);
}

.table-container {
    border-radius: 12px;
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