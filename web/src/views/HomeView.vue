<template>
  <div class="app-layout">
    <!-- 左侧导航 -->
    <AppNavigation :current-page="showPage" @page-change="changeContent" @collapse-change="handleCollapseChange" />

    <!-- 主内容区域 -->
    <div class="main-content" :class="{ 'nav-collapsed': isNavCollapsed }">
      <div class="content-header">
        <div class="header-main">
          <h1 class="page-title">{{ getPageTitle() }}</h1>
          <div class="breadcrumb-container">
            <div class="breadcrumb">
              <span
                v-for="(item, index) in getBreadcrumbItems()"
                :key="index"
                class="breadcrumb-item">
                {{ item }}
                <span v-if="index < getBreadcrumbItems().length - 1" class="breadcrumb-separator"> / </span>
              </span>
            </div>

            <!-- 当前步骤信息 -->
            <div v-if="shouldShowSteps() && currentStepInfo" class="step-info">
              <div class="step-badge">
                <span class="step-label">
                  <span class="step-icon">📋</span>
                  步骤 {{ currentStepInfo.id }}
                </span>
                <span class="step-name" :title="currentStepInfo.step_name">{{ currentStepInfo.step_name }}</span>
              </div>
              <div class="step-metrics">
                <span class="metric">
                  <span class="metric-icon">📊</span>
                  <span class="metric-label">指令数:</span>
                  <span class="metric-value">{{ formatNumber(currentStepInfo.count) }}</span>
                </span>
                <span class="metric">
                  <span class="metric-icon">⚡</span>
                  <span class="metric-label">功耗:</span>
                  <span class="metric-value">{{ formatEnergy(currentStepInfo.count) }}</span>
                </span>
                <span class="metric">
                  <span class="metric-icon">📈</span>
                  <span class="metric-label">占比:</span>
                  <span class="metric-value">{{ getStepPercentage(currentStepInfo) }}%</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="content-body">
        <keep-alive>
          <CompareOverview v-if="showPage === 'perf_compare'" @navigate="changeContent" />
          <PerfLoadOverview v-else-if="showPage === 'perf_load_overview'" @page-change="changeContent" />
          <PerfStepLoad v-else-if="showPage.startsWith('perf_step_')" :step-id="getStepId(showPage)" />
          <PerfFrameAnalysis v-else-if="showPage.startsWith('frame_step_')" :step="getFrameStepId(showPage)" />
          <FaultTreeAnalysis v-else-if="showPage.startsWith('fault_tree_step_')" :step="getFaultTreeStepId(showPage)" />
          <FlameGraph v-else-if="showPage.startsWith('flame_step_')" :step="getFlameStepId(showPage)" />
          <PerfLoadAnalysis v-else-if="showPage === 'perf_load'" />
          <PerfFrameAnalysis v-else-if="showPage === 'perf_frame'" />
          <CompareOverview v-else-if="showPage === 'compare_overview'" @navigate="changeContent" />
          <CompareStepLoad v-else-if="showPage.startsWith('compare_step_load_')" :step="getCompareStepId(showPage)" @navigate="changeContent" />
          <DetailDataCompare v-else-if="showPage.startsWith('compare_step_detail_')" :step="getCompareStepId(showPage)" />
          <NewDataAnalysis v-else-if="showPage.startsWith('compare_step_new_')" :step="getCompareStepId(showPage)" />
          <Top10DataCompare v-else-if="showPage.startsWith('compare_step_top10_')" :step="getCompareStepId(showPage)" />
          <SceneLoadCompare v-else-if="showPage === 'compare_scene_load'" />
          <StepLoadCompare v-else-if="showPage === 'compare_step_load'" />
          <DetailDataCompare v-else-if="showPage === 'compare_detail_data'" />
          <NewDataAnalysis v-else-if="showPage === 'compare_new_data'" />
          <Top10DataCompare v-else-if="showPage === 'compare_top10_data'" />
          <PerfSingle v-else-if="showPage === 'perf'" />
          <PerfMulti v-else-if="showPage === 'perf_multi'" />
          <FlameGraph v-else-if="showPage === 'perf_flame'" />
        </keep-alive>
        <ComponentsDeps v-if="showPage === 'deps'" />

        <!-- 默认欢迎页面 -->
        <div v-if="showPage === 'welcome'" class="welcome-page">
          <div class="welcome-content">
            <h2>欢迎使用 ArkAnalyzer HapRay</h2>
            <p>专业的负载分析工具，帮助您深入了解应用负载情况</p>
            <div class="feature-grid">
              <div class="feature-card" @click="changeContent('perf_load_overview')">
                <div class="card-icon">📊</div>
                <h3>负载总览</h3>
                <p>查看全局负载分布和统计信息</p>
              </div>
              <div class="feature-card" @click="changeContent('perf_step_1')">
                <div class="card-icon">⚡</div>
                <h3>负载分析</h3>
                <p>分析特定步骤的详细负载数据</p>
              </div>
              <div class="feature-card" @click="changeContent('frame_step_1')">
                <div class="card-icon">🎬</div>
                <h3>帧分析</h3>
                <p>分析特定步骤的帧率和渲染情况</p>
              </div>
              <div class="feature-card" @click="changeContent('fault_tree_step_1')">
                <div class="card-icon">⚠️</div>
                <h3>故障树分析</h3>
                <p>诊断特定步骤的性能问题和故障原因</p>
              </div>
              <div class="feature-card" @click="changeContent('flame_step_1')">
                <div class="card-icon">🔥</div>
                <h3>火焰图分析</h3>
                <p>可视化特定步骤的负载热点和调用栈</p>
              </div>
              <div class="feature-card" @click="changeContent('compare_overview')">
                <div class="card-icon">⇋</div>
                <h3>版本对比</h3>
                <p>对比不同版本间的负载差异</p>
              </div>
              <div class="feature-card" @click="changeContent('perf_multi')">
                <div class="card-icon">📈</div>
                <h3>多版本趋势</h3>
                <p>分析多个版本的负载趋势变化</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import AppNavigation from '@/components/AppNavigation.vue';
import PerfLoadOverview from '@/components/PerfLoadOverview.vue';
import PerfStepLoad from '@/components/PerfStepLoad.vue';
import PerfLoadAnalysis from '@/components/PerfLoadAnalysis.vue';
import PerfFrameAnalysis from '@/components/PerfFrameAnalysis.vue';
import FaultTreeAnalysis from '@/components/FaultTreeAnalysis.vue';
import CompareOverview from '@/components/compare/CompareOverview.vue';
import CompareStepLoad from '@/components/compare/CompareStepLoad.vue';
import SceneLoadCompare from '@/components/compare/SceneLoadCompare.vue';
import StepLoadCompare from '@/components/compare/StepLoadCompare.vue';
import DetailDataCompare from '@/components/compare/DetailDataCompare.vue';
import NewDataAnalysis from '@/components/compare/NewDataAnalysis.vue';
import Top10DataCompare from '@/components/compare/Top10DataCompare.vue';
import PerfSingle from '@/components/PerfSingle.vue';
import PerfMulti from '@/components/PerfMulti.vue';
import FlameGraph from '@/components/FlameGraph.vue';
import ComponentsDeps from '@/components/ComponentsDeps.vue';
import { useJsonDataStore } from '@/stores/jsonDataStore.ts';
import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';

const showPage = ref('perf_load_overview');
const isNavCollapsed = ref(false);

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData;

// 步骤数据
const testSteps = computed(() => {
  if (!perfData) return [];
  return perfData.steps.map((step, index) => ({
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }));
});

const changeContent = (page: string) => {
  showPage.value = page;
  // 页面切换后滚动到顶部
  setTimeout(() => {
    const contentBody = document.querySelector('.content-body');
    if (contentBody) {
      contentBody.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, 100);
};

const handleCollapseChange = (collapsed: boolean) => {
  isNavCollapsed.value = collapsed;
};

// 页面标题映射
const pageTitles: Record<string, string> = {
  'welcome': '欢迎',
  'perf': '单版本负载分析',
  'perf_load': '负载分析',
  'perf_load_overview': '负载总览',
  'perf_frame': '帧分析',
  'compare_overview': '版本对比总览',
  'compare_scene_load': '场景负载对比',
  'compare_step_load': '步骤负载对比',
  'compare_detail_data': '详细数据对比',
  'compare_new_data': '新增数据分析',
  'compare_top10_data': 'Top10数据对比',
  'perf_compare': '版本对比分析',
  'perf_multi': '多版本趋势分析',
  'perf_flame': '火焰图分析'
};

// 面包屑导航映射
const breadcrumbMap: Record<string, string> = {
  'welcome': '首页',
  'perf_load_overview': '单版本分析 / 负载总览',
  'compare_overview': '版本对比 / 总览对比',
  'compare_scene_load': '版本对比 / 场景负载对比',
  'compare_step_load': '版本对比 / 步骤负载对比',
  'compare_detail_data': '版本对比 / 详细数据对比',
  'compare_new_data': '版本对比 / 新增数据分析',
  'compare_top10_data': '版本对比 / Top10数据对比',
  'perf_compare': '版本对比',
  'perf_multi': '多版本趋势'
};

// 从页面ID中提取步骤ID
const getStepId = (pageId: string): number => {
  const match = pageId.match(/perf_step_(\d+)/);
  return match ? parseInt(match[1]) : 1;
};

// 从帧页面ID中提取步骤ID
const getFrameStepId = (pageId: string): number => {
  const match = pageId.match(/frame_step_(\d+)/);
  return match ? parseInt(match[1]) : 1;
};

// 从故障树页面ID中提取步骤ID
const getFaultTreeStepId = (pageId: string): number => {
  const match = pageId.match(/fault_tree_step_(\d+)/);
  return match ? parseInt(match[1]) : 1;
};

// 从版本对比页面ID中提取步骤ID
const getCompareStepId = (pageId: string): number => {
  const match = pageId.match(/compare_step_(?:load|detail|new|top10)_(\d+)/);
  return match ? parseInt(match[1]) : 1;
};

// 从火焰图页面ID中提取步骤ID
const getFlameStepId = (pageId: string): number => {
  const match = pageId.match(/flame_step_(\d+)/);
  return match ? parseInt(match[1]) : 1;
};

// 动态获取步骤页面标题
const getStepPageTitle = (pageId: string): string => {
  const stepId = getStepId(pageId);
  return `步骤${stepId}负载分析`;
};

// 动态获取步骤页面面包屑
const getStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getStepId(pageId);
  return `单版本分析 / 步骤选择 / 步骤${stepId} / 负载分析`;
};

// 动态获取帧步骤页面标题
const getFrameStepPageTitle = (pageId: string): string => {
  const stepId = getFrameStepId(pageId);
  return `步骤${stepId}帧分析`;
};

// 动态获取帧步骤页面面包屑
const getFrameStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getFrameStepId(pageId);
  return `单版本分析 / 步骤选择 / 步骤${stepId} / 帧分析`;
};

// 动态获取故障树步骤页面标题
const getFaultTreeStepPageTitle = (pageId: string): string => {
  const stepId = getFaultTreeStepId(pageId);
  return `步骤${stepId}故障树分析`;
};

// 动态获取故障树步骤页面面包屑
const getFaultTreeStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getFaultTreeStepId(pageId);
  return `单版本分析 / 步骤选择 / 步骤${stepId} / 故障树分析`;
};

// 动态获取版本对比步骤页面标题
const getCompareStepPageTitle = (pageId: string): string => {
  const stepId = getCompareStepId(pageId);
  if (pageId.includes('compare_step_load_')) {
    return `步骤${stepId}负载对比`;
  } else if (pageId.includes('compare_step_detail_')) {
    return `步骤${stepId}详细对比`;
  } else if (pageId.includes('compare_step_new_')) {
    return `步骤${stepId}新增分析`;
  } else if (pageId.includes('compare_step_top10_')) {
    return `步骤${stepId}Top10对比`;
  }
  return `步骤${stepId}对比分析`;
};

// 动态获取版本对比步骤页面面包屑
const getCompareStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getCompareStepId(pageId);
  if (pageId.includes('compare_step_load_')) {
    return `版本对比 / 步骤选择 / 步骤${stepId} / 负载对比`;
  } else if (pageId.includes('compare_step_detail_')) {
    return `版本对比 / 步骤选择 / 步骤${stepId} / 详细对比`;
  } else if (pageId.includes('compare_step_new_')) {
    return `版本对比 / 步骤选择 / 步骤${stepId} / 新增分析`;
  } else if (pageId.includes('compare_step_top10_')) {
    return `版本对比 / 步骤选择 / 步骤${stepId} / Top10对比`;
  }
  return `版本对比 / 步骤选择 / 步骤${stepId}`;
};

// 动态获取火焰图步骤页面标题
const getFlameStepPageTitle = (pageId: string): string => {
  const stepId = getFlameStepId(pageId);
  return `步骤${stepId}火焰图分析`;
};

// 动态获取火焰图步骤页面面包屑
const getFlameStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getFlameStepId(pageId);
  return `单版本分析 / 步骤选择 / 步骤${stepId} / 火焰图分析`;
};

const getPageTitle = () => {
  if (showPage.value.startsWith('perf_step_')) {
    return getStepPageTitle(showPage.value);
  }
  if (showPage.value.startsWith('frame_step_')) {
    return getFrameStepPageTitle(showPage.value);
  }
  if (showPage.value.startsWith('fault_tree_step_')) {
    return getFaultTreeStepPageTitle(showPage.value);
  }
  if (showPage.value.startsWith('compare_step_')) {
    return getCompareStepPageTitle(showPage.value);
  }
  if (showPage.value.startsWith('flame_step_')) {
    return getFlameStepPageTitle(showPage.value);
  }
  return pageTitles[showPage.value] || '未知页面';
};

const getBreadcrumb = () => {
  if (showPage.value.startsWith('perf_step_')) {
    return getStepPageBreadcrumb(showPage.value);
  }
  if (showPage.value.startsWith('frame_step_')) {
    return getFrameStepPageBreadcrumb(showPage.value);
  }
  if (showPage.value.startsWith('fault_tree_step_')) {
    return getFaultTreeStepPageBreadcrumb(showPage.value);
  }
  if (showPage.value.startsWith('compare_step_')) {
    return getCompareStepPageBreadcrumb(showPage.value);
  }
  if (showPage.value.startsWith('flame_step_')) {
    return getFlameStepPageBreadcrumb(showPage.value);
  }
  return breadcrumbMap[showPage.value] || '首页';
};

const getBreadcrumbItems = () => {
  const breadcrumbString = getBreadcrumb();
  return breadcrumbString.split(' / ').map(item => item.trim());
};

// 步骤相关方法
const shouldShowSteps = () => {
  // 在负载总览、负载分析、帧分析、火焰图分析等页面显示步骤
  const pagesWithSteps = [
    'perf_load_overview',
    'perf_load',
    'perf_frame',
    'perf_flame',
    'perf',
    'perf_compare'
  ];
  return pagesWithSteps.includes(showPage.value) ||
         showPage.value.startsWith('perf_step_') ||
         showPage.value.startsWith('frame_step_') ||
         showPage.value.startsWith('fault_tree_step_') ||
         showPage.value.startsWith('compare_step_') ||
         showPage.value.startsWith('flame_step_');
};

// 获取当前步骤信息（计算属性）
const currentStepInfo = computed(() => {
  let currentStepId = null;

  if (showPage.value.startsWith('perf_step_')) {
    currentStepId = getStepId(showPage.value);
  } else if (showPage.value.startsWith('frame_step_')) {
    currentStepId = getFrameStepId(showPage.value);
  } else if (showPage.value.startsWith('fault_tree_step_')) {
    currentStepId = getFaultTreeStepId(showPage.value);
  } else if (showPage.value.startsWith('compare_step_')) {
    currentStepId = getCompareStepId(showPage.value);
  } else if (showPage.value.startsWith('flame_step_')) {
    currentStepId = getFlameStepId(showPage.value);
  }

  if (currentStepId) {
    return testSteps.value.find(step => step.id === currentStepId);
  }

  return null;
});

// 格式化数字
const formatNumber = (num: number) => {
  return num.toLocaleString();
};

// 格式化功耗信息
const formatEnergy = (count: number) => {
  const energy = calculateEnergyConsumption(count);
  return `${energy} mAs`;
};

// 步骤数据类型定义
interface TestStep {
  id: number;
  step_name: string;
  count: number;
  round: number;
  perf_data_path: string;
}

// 计算步骤占比
const getStepPercentage = (step: TestStep) => {
  const total = testSteps.value.reduce((sum, s) => sum + s.count, 0);
  return total > 0 ? ((step.count / total) * 100).toFixed(1) : '0.0';
};
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background: #f5f7fa;
}

.main-content {
  flex: 1;
  margin-left: 280px; /* 左侧导航宽度 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: margin-left 0.3s ease;
}

.main-content.nav-collapsed {
  margin-left: 64px; /* 折叠后的导航宽度 */
}

.content-header {
  background: white;
  padding: 24px 32px;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.header-main {
  width: 100%;
}

.breadcrumb-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
  min-height: 40px;
}

.breadcrumb {
  flex: 0 0 auto;
  min-width: 0;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
  min-width: 0;
}

.step-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0;
  min-width: 0;
  flex: 1;
  max-width: 60%;
}

.step-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.step-icon {
  font-size: 14px;
}

.step-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 500px;
  flex: 1;
}

.step-metrics {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  min-width: 0;
}

.metric {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  white-space: nowrap;
  min-width: 0;
}

.metric-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.metric-label {
  color: #909399;
  font-weight: 500;
}

.metric-value {
  color: #303133;
  font-weight: 600;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  font-size: 14px;
  line-height: 1.5;
}

.breadcrumb-item {
  color: #606266;
  transition: color 0.3s ease;
}

.breadcrumb-item:last-child {
  color: #303133;
  font-weight: 500;
}

.breadcrumb-separator {
  color: #c0c4cc;
  margin: 0 8px;
  font-weight: normal;
}

.content-body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  background: #f5f7fa;
}

/* 欢迎页面样式 */
.welcome-page {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-height: calc(100vh - 200px);
  padding: 40px 20px;
  box-sizing: border-box;
  overflow-y: auto;
  width: 100%;
}

.welcome-content {
  text-align: center;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
}

.welcome-content h2 {
  font-size: 32px;
  color: #303133;
  margin-bottom: 16px;
  font-weight: 600;
}

.welcome-content p {
  font-size: 16px;
  color: #606266;
  margin-bottom: 48px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr));
  gap: 20px;
  margin-top: 40px;
  max-width: 1200px;
  width: 100%;
  box-sizing: border-box;
}

.feature-card {
  background: white;
  padding: 32px 24px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  border-color: #667eea;
}

.card-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.feature-card h3 {
  font-size: 20px;
  color: #303133;
  margin: 0 0 12px 0;
  font-weight: 600;
}

.feature-card p {
  font-size: 14px;
  color: #606266;
  margin: 0;
  line-height: 1.6;
}

/* 代码查看器样式 */
.code-viewer {
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .feature-grid {
    grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
    gap: 18px;
  }
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 220px;
  }

  .main-content.nav-collapsed {
    margin-left: 64px;
  }

  .content-header {
    padding: 16px 20px;
  }

  .breadcrumb-container {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .step-info {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .step-badge {
    padding: 4px 8px;
  }

  .step-badge {
    max-width: 100%;
  }

  .step-name {
    max-width: 100%;
  }

  .step-metrics {
    gap: 8px;
  }

  .page-title {
    font-size: 24px;
  }

  .content-body {
    padding: 16px 20px;
  }

  .welcome-page {
    min-height: calc(100vh - 150px);
    padding: 20px 16px;
    align-items: flex-start;
  }

  .welcome-content {
    max-width: 100%;
    padding: 0;
  }

  .feature-grid {
    grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr));
    gap: 16px;
    margin-top: 32px;
  }

  .feature-card {
    padding: 24px 20px;
  }

  .card-icon {
    font-size: 40px;
    margin-bottom: 12px;
  }

  .feature-card h3 {
    font-size: 18px;
    margin-bottom: 8px;
  }

  .feature-card p {
    font-size: 13px;
  }

  .welcome-content h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .welcome-content p {
    font-size: 15px;
    margin-bottom: 32px;
  }
}

@media (max-width: 480px) {
  .main-content {
    margin-left: 200px;
  }

  .main-content.nav-collapsed {
    margin-left: 64px;
  }

  .content-header {
    padding: 12px 16px;
    gap: 12px;
  }

  .step-badge {
    padding: 3px 6px;
  }

  .step-label {
    font-size: 11px;
  }

  .step-name {
    font-size: 12px;
  }

  .step-metrics {
    gap: 6px;
    flex-direction: column;
    align-items: flex-start;
  }

  .metric {
    font-size: 11px;
  }

  .page-title {
    font-size: 20px;
  }

  .content-body {
    padding: 12px 16px;
  }

  .welcome-page {
    min-height: auto;
    padding: 16px 12px;
    align-items: flex-start;
  }

  .welcome-content {
    max-width: 100%;
    padding: 0;
  }

  .welcome-content h2 {
    font-size: 24px;
    margin-bottom: 8px;
  }

  .welcome-content p {
    font-size: 14px;
    margin-bottom: 24px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
    gap: 12px;
    margin-top: 24px;
  }

  .feature-card {
    padding: 20px 16px;
  }

  .card-icon {
    font-size: 36px;
    margin-bottom: 8px;
  }

  .feature-card h3 {
    font-size: 16px;
    margin-bottom: 6px;
  }

  .feature-card p {
    font-size: 12px;
    line-height: 1.5;
  }
}

/* 超小屏幕优化 */
@media (max-width: 360px) {
  .welcome-page {
    padding: 12px 8px;
  }

  .welcome-content {
    padding: 0;
  }

  .welcome-content h2 {
    font-size: 20px;
  }

  .welcome-content p {
    font-size: 13px;
  }

  .feature-card {
    padding: 16px 12px;
  }

  .card-icon {
    font-size: 32px;
  }

  .feature-card h3 {
    font-size: 15px;
  }

  .feature-card p {
    font-size: 11px;
  }
}

/* 极小屏幕布局优化 */
@media (max-width: 360px) {
  .main-content {
    margin-left: 180px;
  }

  .main-content.nav-collapsed {
    margin-left: 64px;
  }
}

/* 极小屏幕优化 */
@media (max-width: 320px) {
  .main-content {
    margin-left: 160px;
  }

  .main-content.nav-collapsed {
    margin-left: 64px;
  }
  .welcome-page {
    padding: 8px 4px;
  }

  .welcome-content h2 {
    font-size: 18px;
  }

  .welcome-content p {
    font-size: 12px;
    margin-bottom: 16px;
  }

  .feature-grid {
    margin-top: 16px;
    gap: 8px;
  }

  .feature-card {
    padding: 12px 8px;
  }

  .card-icon {
    font-size: 28px;
  }

  .feature-card h3 {
    font-size: 14px;
  }

  .feature-card p {
    font-size: 10px;
  }
}

/* 超极小屏幕 - 移动端优先 */
@media (max-width: 280px) {
  .main-content {
    margin-left: 0;
    width: 100%;
  }

  .main-content.nav-collapsed {
    margin-left: 64px;
  }
}
</style>
