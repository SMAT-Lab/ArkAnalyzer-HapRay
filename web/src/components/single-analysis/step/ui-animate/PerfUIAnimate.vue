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
              <span style="font-weight: 600; font-size: 15px;">页面列表</span>
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
            <div class="page-menu-list">
              <div
                v-for="page in filteredPageList"
                :key="page.page_idx"
                class="page-menu-item"
                :class="{ 'is-active': selectedPage === page.page_idx }"
                @click="selectedPage = page.page_idx"
              >
                <el-tooltip
                  :content="`Page${page.page_idx}:${page.description || ''}`"
                  placement="right"
                  effect="dark"
                >
                  <span class="page-name-text">
                    Page{{ page.page_idx }}:{{ page.description || '' }}
                  </span>
                </el-tooltip>
              </div>
            </div>
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
            <div v-if="!selectedPage" class="screenshot-placeholder">
              <el-empty description="请从左侧选择页面查看截图" :image-size="100" />
            </div>
            <div v-else class="screenshot-container">
              <el-row :gutter="16">
                <!-- 内存超尺寸截图 -->
                <el-col :span="currentPageHasAnimation ? 12 : 24">
                  <div class="screenshot-item">
                    <div class="screenshot-header">
                      <span style="font-weight: 600;">Page {{ selectedPage }} - 内存超尺寸截图</span>
                    </div>
                    <el-image
                      v-if="getPageByIdx(selectedPage)?.image_size_analysis?.marked_image"
                      :src="`data:image/png;base64,${getPageByIdx(selectedPage)?.image_size_analysis?.marked_image}`"
                      fit="contain"
                      class="screenshot-image"
                      :preview-src-list="[
                        `data:image/png;base64,${getPageByIdx(selectedPage)?.image_size_analysis?.marked_image}`
                      ]"
                    >
                      <template #error>
                        <div class="image-error">
                          <i class="el-icon-picture-outline"></i>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                    <el-empty v-else description="暂无内存超尺寸截图" :image-size="80" />
                  </div>
                </el-col>
                <!-- 动画截图 -->
                <el-col v-if="currentPageHasAnimation" :span="12">
                  <div class="screenshot-item">
                    <div class="screenshot-header">
                      <span style="font-weight: 600;">Page {{ selectedPage }} - 动画截图</span>
                    </div>
                    <el-image
                      v-if="selectedPage && getPageByIdx(selectedPage)?.animations?.marked_image"
                      :src="`data:image/png;base64,${getPageByIdx(selectedPage)?.animations?.marked_image}`"
                      fit="contain"
                      class="screenshot-image"
                      :preview-src-list="selectedPage ? getAnimationPreviewList(selectedPage) : []"
                    >
                      <template #error>
                        <div class="image-error">
                          <i class="el-icon-picture-outline"></i>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                    <el-empty v-else description="暂无动画截图" :image-size="80" />
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
            <div v-if="!selectedPage" class="info-placeholder">
              <el-empty description="请从左侧选择页面查看详细信息" :image-size="100" />
            </div>
            <div v-else class="page-detail">
              <PageDetail :page="getPageByIdx(selectedPage)" />
            </div>
          </el-card>
        </el-col>
      </el-row>

    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useJsonDataStore, type UIAnimatePageData } from '../../../../stores/jsonDataStore';
import * as echarts from 'echarts';
import PageDetail from './PageDetail.vue';

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
  return currentPageList.value.filter(page => {
    const pageIdxStr = String(page.page_idx);
    const pageNameStr = ((page.description) || '').toLowerCase();
    return pageIdxStr.includes(filter) || 
           pageNameStr.includes(filter) ||
           `page${pageIdxStr}`.includes(filter);
  });
});

// 选中的页面（单选）
const selectedPage = ref<number | null>(null);

// 根据page_idx获取page数据
const getPageByIdx = (pageIdx: number): UIAnimatePageData | undefined => {
  return currentPageList.value.find(page => page.page_idx === pageIdx);
};

// CanvasNode折线图
const canvasNodeChartRef = ref<HTMLElement | null>(null);
let canvasNodeChart: echarts.ECharts | null = null;

// 内存超尺寸折线图
const memoryChartRef = ref<HTMLElement | null>(null);
let memoryChart: echarts.ECharts | null = null;

// 检查是否有动画图片
const hasAnimationImage = (pageIdx: number | null): boolean => {
  if (!pageIdx) return false;
  const page = getPageByIdx(pageIdx);
  if (!page?.animations) return false;
  const animations = page.animations;
  return !!(animations.marked_image || 
           (animations.marked_images && Array.isArray(animations.marked_images) && animations.marked_images.length > 0));
};

// 当前选中页面是否有动画图片
const currentPageHasAnimation = computed(() => {
  return selectedPage.value ? hasAnimationImage(selectedPage.value) : false;
});

// 获取动画预览图片列表
const getAnimationPreviewList = (pageIdx: number): string[] => {
  const page = getPageByIdx(pageIdx);
  if (!page?.animations) return [];
  
  const images: string[] = [];
  if (page.animations.marked_image) {
    images.push(`data:image/png;base64,${page.animations.marked_image}`);
  }
  if (page.animations.marked_images && Array.isArray(page.animations.marked_images)) {
    page.animations.marked_images.forEach(img => {
      if (img && !images.includes(`data:image/png;base64,${img}`)) {
        images.push(`data:image/png;base64,${img}`);
      }
    });
  }
  return images;
};

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
        formatter: (params: unknown) => {
          const paramArray = Array.isArray(params) ? params : [params];
          const param = paramArray[0] as { name?: string; value?: number };
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
        formatter: (params: unknown) => {
          const paramArray = Array.isArray(params) ? params : [params];
          const param = paramArray[0] as { name?: string; value?: number };
          return `${param.name}<br/>超尺寸内存: <strong>${param.value?.toFixed(2)} MB</strong>`;
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
watch([currentPageList, selectedPage], () => {
  if (currentPageList.value.length > 0) {
    setTimeout(() => {
      updateCharts();
    }, 100);
  }
}, { deep: true });

onMounted(() => {
  if (currentPageList.value.length > 0) {
    setTimeout(() => {
      initCharts();
      // 默认选择第一个页面
      if (currentPageList.value.length > 0) {
        selectedPage.value = currentPageList.value[0].page_idx;
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

/* 页面列表样式 - 类似左侧菜单样式 */
.page-menu-list {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.page-menu-item {
  color: #606266;
  background: transparent;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 12px;
  border: 1px solid transparent;
  margin-bottom: 4px;
  min-height: 44px;
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.page-menu-item:hover {
  background: #f8f9fa;
  color: #303133;
  transform: translateX(2px);
  border-color: #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.page-menu-item.is-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.page-menu-item.is-active:hover {
  background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
  transform: translateX(2px);
}

.page-name-text {
  font-weight: inherit;
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  flex: 1;
  min-width: 0;
}
</style>
