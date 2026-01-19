<template>
  <div class="ui-analysis">
    <el-card v-if="!hasData" shadow="never">
      <el-empty description="暂无 UI 分析数据" />
    </el-card>

    <template v-else>
      <!-- UI总览 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span style="font-weight: 600; font-size: 16px;">
            <i class="el-icon-data-analysis" style="margin-right: 8px;"></i>
            UI总览
          </span>
        </template>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-statistic title="页面总数" :value="currentPageList.length">
              <template #suffix>
                <span style="font-size: 14px;">个</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="页面Canvas总数" :value="totalCanvasNodes">
              <template #suffix>
                <span style="font-size: 14px;">个</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="页面内存超尺寸" :value="totalExcessMemory">
              <template #suffix>
                <span style="font-size: 14px;">MB</span>
              </template>
            </el-statistic>
          </el-col>
        </el-row>
      </el-card>

      <!-- 页面Canvas和内存超尺寸统计行 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <el-row :gutter="16">
          <el-col :span="12">
            <div style="display: flex; align-items: center;">
              <span style="font-weight: 600; margin-right: 12px;">页面Canvas:</span>
              <div ref="canvasNodeChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div style="display: flex; align-items: center;">
              <span style="font-weight: 600; margin-right: 12px;">页面内存超尺寸:</span>
              <div ref="memoryChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 三栏布局：左侧页面列表、中间截图、右侧详细信息 -->
      <el-row :gutter="16" style="min-height: 600px;">
        <!-- 左侧：页面列表 -->
        <el-col :span="4">
          <el-card shadow="never" style="height: 100%;">
            <template #header>
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-weight: 600; font-size: 15px;">页面列表</span>
                <el-button
                  v-if="selectedPages.length > 0"
                  type="text"
                  size="small"
                  @click="clearSelection"
                >
                  清空
                </el-button>
              </div>
            </template>
            <el-input
              v-model="pageFilterText"
              placeholder="搜索页面"
              size="small"
              style="margin-bottom: 12px;"
              clearable
            >
              <template #prefix>
                <i class="el-icon-search"></i>
              </template>
            </el-input>
            <el-checkbox-group v-model="selectedPages" :max="2">
              <div
                v-for="page in filteredPageList"
                :key="page.page_idx"
                style="margin-bottom: 8px;"
              >
                <el-checkbox
                  :label="page.page_idx"
                  :disabled="selectedPages.length >= 2 && !selectedPages.includes(page.page_idx)"
                >
                  <div style="display: flex; flex-direction: column; margin-left: 8px;">
                    <span style="font-weight: 500;">Page {{ page.page_idx }}</span>
                    <span v-if="page.page_name" style="font-size: 12px; color: #409eff; font-weight: 500;">
                      {{ page.page_name }}
                    </span>
                    <span style="font-size: 12px; color: #909399;">
                      Canvas: {{ page.canvasNodeCnt || 0 }}
                    </span>
                  </div>
                </el-checkbox>
              </div>
            </el-checkbox-group>
            <el-empty
              v-if="filteredPageList.length === 0"
              description="无匹配页面"
              :image-size="60"
            />
          </el-card>
        </el-col>

        <!-- 中间：手机截图区域 -->
        <el-col :span="10">
          <el-card shadow="never" style="height: 100%;">
            <template #header>
              <span style="font-weight: 600; font-size: 15px;">
                <i class="el-icon-mobile-phone" style="margin-right: 8px;"></i>
                手机截图
              </span>
            </template>
            <div v-if="selectedPages.length === 0" class="screenshot-placeholder">
              <el-empty description="请从左侧选择页面查看截图" :image-size="100" />
            </div>
            <div v-else-if="selectedPages.length === 1" class="screenshot-container">
              <div
                v-for="pageIdx in selectedPages"
                :key="pageIdx"
                class="screenshot-item"
              >
                <div class="screenshot-header">
                  <span style="font-weight: 600;">Page {{ pageIdx }}</span>
                </div>
                <el-image
                  v-if="getPageByIdx(pageIdx)?.image_size_analysis?.marked_image"
                  :src="`data:image/png;base64,${getPageByIdx(pageIdx)?.image_size_analysis?.marked_image}`"
                  fit="contain"
                  class="screenshot-image"
                  :preview-src-list="[
                    `data:image/png;base64,${getPageByIdx(pageIdx)?.image_size_analysis?.marked_image}`
                  ]"
                >
                  <template #error>
                    <div class="image-error">
                      <i class="el-icon-picture-outline"></i>
                      <span>图片加载失败</span>
                    </div>
                  </template>
                </el-image>
                <el-empty v-else description="暂无截图" :image-size="80" />
              </div>
            </div>
            <div v-else class="screenshot-container">
              <!-- 对比模式：显示两个截图 -->
              <el-row :gutter="16">
                <el-col
                  v-for="(pageIdx, index) in selectedPages"
                  :key="pageIdx"
                  :span="12"
                >
                  <div class="screenshot-item">
                    <div class="screenshot-header">
                      <span style="font-weight: 600;">Page {{ pageIdx }}</span>
                    </div>
                    <el-image
                      v-if="getPageByIdx(pageIdx)?.image_size_analysis?.marked_image"
                      :src="`data:image/png;base64,${getPageByIdx(pageIdx)?.image_size_analysis?.marked_image}`"
                      fit="contain"
                      class="screenshot-image"
                      :preview-src-list="selectedPages.map(idx => 
                        `data:image/png;base64,${getPageByIdx(idx)?.image_size_analysis?.marked_image || ''}`
                      )"
                    >
                      <template #error>
                        <div class="image-error">
                          <i class="el-icon-picture-outline"></i>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                    <el-empty v-else description="暂无截图" :image-size="80" />
                  </div>
                </el-col>
              </el-row>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：页面详细信息 -->
        <el-col :span="10">
          <el-card shadow="never" style="height: 100%; overflow-y: auto;">
            <template #header>
              <span style="font-weight: 600; font-size: 15px;">
                <i class="el-icon-document" style="margin-right: 8px;"></i>
                页面详细信息
              </span>
            </template>
            <div v-if="selectedPages.length === 0" class="info-placeholder">
              <el-empty description="请从左侧选择页面查看详细信息" :image-size="100" />
            </div>
            <div v-else-if="selectedPages.length === 1" class="page-detail">
              <PageDetail :page="getPageByIdx(selectedPages[0])" />
            </div>
            <div v-else class="page-detail">
              <!-- 对比模式：显示两个页面的详细信息 -->
              <el-tabs v-model="detailActiveTab" type="border-card">
                <el-tab-pane
                  v-for="pageIdx in selectedPages"
                  :key="pageIdx"
                  :label="`Page ${pageIdx}`"
                  :name="`page_${pageIdx}`"
                >
                  <PageDetail :page="getPageByIdx(pageIdx)" />
                </el-tab-pane>
              </el-tabs>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 底部：两个页面对比信息（当选择2个page时显示） -->
      <el-card
        v-if="selectedPages.length === 2"
        shadow="never"
        style="margin-top: 16px;"
      >
        <template #header>
          <span style="font-weight: 600; font-size: 16px;">
            <i class="el-icon-compare" style="margin-right: 8px;"></i>
            页面对比分析
          </span>
        </template>
        <PageComparison
          :page1="getPageByIdx(selectedPages[0])"
          :page2="getPageByIdx(selectedPages[1])"
        />
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useJsonDataStore, type UIAnimatePageData } from '../../../../stores/jsonDataStore';
import * as echarts from 'echarts';
import PageDetail from './PageDetail.vue';
import PageComparison from './PageComparison.vue';

interface Props {
  stepId?: number;
}

const props = withDefaults(defineProps<Props>(), {
  stepId: 1,
});

const jsonDataStore = useJsonDataStore();
const uiAnimateData = computed(() => jsonDataStore.uiAnimateData);

// 检查是否有数据
const hasData = computed(() => {
  return uiAnimateData.value && Object.keys(uiAnimateData.value).length > 0;
});

// 根据 stepId 计算当前步骤的 key
const currentStepKey = computed(() => {
  return `step${props.stepId}`;
});

// 当前步骤的page列表
const currentPageList = computed((): UIAnimatePageData[] => {
  if (!uiAnimateData.value) return [];
  const stepData = uiAnimateData.value[currentStepKey.value];
  if (Array.isArray(stepData)) {
    return stepData;
  }
  if (stepData && typeof stepData === 'object' && 'pages' in stepData && Array.isArray(stepData.pages)) {
    return stepData.pages;
  }
  return [];
});

// 页面过滤
const pageFilterText = ref('');
const filteredPageList = computed(() => {
  if (!pageFilterText.value) {
    return currentPageList.value;
  }
  const filter = pageFilterText.value.toLowerCase();
  return currentPageList.value.filter(page => 
    `page ${page.page_idx}`.includes(filter) ||
    String(page.page_idx).includes(filter)
  );
});

// 选中的页面（最多2个）
const selectedPages = ref<number[]>([]);

// 清空选择
const clearSelection = () => {
  selectedPages.value = [];
};

// 根据page_idx获取page数据
const getPageByIdx = (pageIdx: number): UIAnimatePageData | undefined => {
  return currentPageList.value.find(page => page.page_idx === pageIdx);
};

// UI总览统计
const totalCanvasNodes = computed(() => {
  return currentPageList.value.reduce((sum, page) => sum + (page.canvasNodeCnt || 0), 0);
});

const totalExcessMemory = computed(() => {
  return currentPageList.value.reduce((sum, page) => {
    const excess = page.image_size_analysis?.total_excess_memory_mb || 0;
    return sum + excess;
  }, 0).toFixed(2);
});

// CanvasNode折线图
const canvasNodeChartRef = ref<HTMLElement | null>(null);
let canvasNodeChart: echarts.ECharts | null = null;

// 内存超尺寸折线图
const memoryChartRef = ref<HTMLElement | null>(null);
let memoryChart: echarts.ECharts | null = null;

// 详情页激活的tab
const detailActiveTab = ref('');

// 初始化图表
const initCharts = () => {
  if (currentPageList.value.length === 0) return;

  const sortedPages = [...currentPageList.value].sort((a, b) => (a.page_idx || 0) - (b.page_idx || 0));
  const xData = sortedPages.map(page => `Page ${page.page_idx}`);
  const canvasData = sortedPages.map(page => page.canvasNodeCnt || 0);
  const memoryData = sortedPages.map(page => page.image_size_analysis?.total_excess_memory_mb || 0);

  // CanvasNode折线图
  if (canvasNodeChartRef.value) {
    canvasNodeChart = echarts.init(canvasNodeChartRef.value);
    canvasNodeChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const param = Array.isArray(params) ? params[0] : params;
          return `${param.name}<br/>CanvasNode数量: <strong>${param.value}</strong>`;
        },
      },
      grid: {
        left: '3%',
        right: '3%',
        bottom: '10%',
        top: '10%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: xData,
        axisLabel: {
          interval: 0,
          rotate: 45,
          fontSize: 10,
        },
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        name: '数量',
      },
      series: [
        {
          name: 'CanvasNode数量',
          type: 'line',
          data: canvasData,
          smooth: true,
          itemStyle: { color: '#409EFF' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
                { offset: 1, color: 'rgba(64, 158, 255, 0.1)' },
              ],
            },
          },
        },
      ],
    });
  }

  // 内存超尺寸折线图
  if (memoryChartRef.value) {
    memoryChart = echarts.init(memoryChartRef.value);
    memoryChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const param = Array.isArray(params) ? params[0] : params;
          return `${param.name}<br/>超尺寸内存: <strong>${param.value.toFixed(2)} MB</strong>`;
        },
      },
      grid: {
        left: '3%',
        right: '3%',
        bottom: '10%',
        top: '10%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: xData,
        axisLabel: {
          interval: 0,
          rotate: 45,
          fontSize: 10,
        },
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        name: 'MB',
      },
      series: [
        {
          name: '超尺寸内存',
          type: 'line',
          data: memoryData,
          smooth: true,
          itemStyle: { color: '#E6A23C' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(230, 162, 60, 0.3)' },
                { offset: 1, color: 'rgba(230, 162, 60, 0.1)' },
              ],
            },
          },
        },
      ],
    });
  }
};

// 更新图表
const updateCharts = () => {
  if (canvasNodeChart) {
    const sortedPages = [...currentPageList.value].sort((a, b) => (a.page_idx || 0) - (b.page_idx || 0));
    const xData = sortedPages.map(page => `Page ${page.page_idx}`);
    const canvasData = sortedPages.map(page => page.canvasNodeCnt || 0);
    
    canvasNodeChart.setOption({
      xAxis: { data: xData },
      series: [{ data: canvasData }],
    });
  }

  if (memoryChart) {
    const sortedPages = [...currentPageList.value].sort((a, b) => (a.page_idx || 0) - (b.page_idx || 0));
    const xData = sortedPages.map(page => `Page ${page.page_idx}`);
    const memoryData = sortedPages.map(page => page.image_size_analysis?.total_excess_memory_mb || 0);
    
    memoryChart.setOption({
      xAxis: { data: xData },
      series: [{ data: memoryData }],
    });
  }
};

// 监听数据变化
watch([currentPageList, selectedPages], () => {
  if (currentPageList.value.length > 0) {
    setTimeout(() => {
      updateCharts();
      if (selectedPages.value.length > 0 && !detailActiveTab.value) {
        detailActiveTab.value = `page_${selectedPages.value[0]}`;
      }
    }, 100);
  }
}, { deep: true });

onMounted(() => {
  if (currentPageList.value.length > 0) {
    setTimeout(() => {
      initCharts();
      // 默认选择第一个页面
      if (currentPageList.value.length > 0) {
        selectedPages.value = [currentPageList.value[0].page_idx];
        detailActiveTab.value = `page_${currentPageList.value[0].page_idx}`;
      }
    }, 100);
  }
});

onBeforeUnmount(() => {
  if (canvasNodeChart) {
    canvasNodeChart.dispose();
    canvasNodeChart = null;
  }
  if (memoryChart) {
    memoryChart.dispose();
    memoryChart = null;
  }
});
</script>

<style scoped>
.ui-analysis {
  padding: 16px;
}

.screenshot-placeholder,
.info-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.screenshot-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.screenshot-item {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  background-color: #fafafa;
}

.screenshot-header {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.screenshot-image {
  width: 100%;
  max-height: 500px;
  border-radius: 4px;
  object-fit: contain;
}

:deep(.screenshot-image .el-image__inner) {
  width: 100% !important;
  height: auto !important;
  max-height: 500px;
  object-fit: contain;
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
}

.image-error i {
  font-size: 48px;
  margin-bottom: 8px;
}

.page-detail {
  max-height: 600px;
  overflow-y: auto;
}

:deep(.el-statistic__head) {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

:deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
</style>
