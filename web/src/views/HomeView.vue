<template>
  <div class="app-layout">
    <!-- 左侧导航 -->
    <AppNavigation :current-page="showPage" @page-change="changeContent" @collapse-change="handleCollapseChange" />

    <!-- 主内容区域 -->
    <div class="main-content" :class="{ 'nav-collapsed': isNavCollapsed }">
      <div class="content-header">
        <h1 class="page-title">{{ getPageTitle() }}</h1>
        <div class="breadcrumb">
          <span class="breadcrumb-item">{{ getBreadcrumb() }}</span>
        </div>
      </div>

      <div class="content-body">
        <keep-alive>
          <PerfCompare v-if="showPage === 'perf_compare'" />
          <PerfLoadOverview v-else-if="showPage === 'perf_load_overview'" @page-change="changeContent" />
          <PerfStepLoad v-else-if="showPage.startsWith('perf_step_')" :step-id="getStepId(showPage)" />
          <PerfFrameAnalysis v-else-if="showPage.startsWith('frame_step_')" :step="getFrameStepId(showPage)" />
          <FlameGraph v-else-if="showPage.startsWith('flame_step_')" :step="getFlameStepId(showPage)" />
          <PerfLoadAnalysis v-else-if="showPage === 'perf_load'" />
          <PerfFrameAnalysis v-else-if="showPage === 'perf_frame'" />
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
              <div class="feature-card" @click="changeContent('flame_step_1')">
                <div class="card-icon">🔥</div>
                <h3>火焰图分析</h3>
                <p>可视化特定步骤的负载热点和调用栈</p>
              </div>
              <div class="feature-card" @click="changeContent('perf_compare')">
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
import { ref } from 'vue';
import AppNavigation from '@/components/AppNavigation.vue';
import PerfCompare from '@/components/PerfCompare.vue';
import PerfLoadOverview from '@/components/PerfLoadOverview.vue';
import PerfStepLoad from '@/components/PerfStepLoad.vue';
import PerfLoadAnalysis from '@/components/PerfLoadAnalysis.vue';
import PerfFrameAnalysis from '@/components/PerfFrameAnalysis.vue';
import PerfSingle from '@/components/PerfSingle.vue';
import PerfMulti from '@/components/PerfMulti.vue';
import FlameGraph from '@/components/FlameGraph.vue';
import ComponentsDeps from '@/components/ComponentsDeps.vue';

const showPage = ref('perf_load_overview');
const isNavCollapsed = ref(false);

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
  'perf_compare': '版本对比分析',
  'perf_multi': '多版本趋势分析',
  'perf_flame': '火焰图分析'
};

// 面包屑导航映射
const breadcrumbMap: Record<string, string> = {
  'welcome': '首页',
  'perf': '负载分析 / 单版本分析',
  'perf_load': '负载分析 / 单版本分析 / 负载分析',
  'perf_load_overview': '负载分析 / 单版本分析 / 负载总览',
  'perf_frame': '负载分析 / 单版本分析 / 帧分析',
  'perf_compare': '负载分析 / 版本对比',
  'perf_multi': '负载分析 / 多版本趋势',
  'perf_flame': '负载分析 / 火焰图'
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
  return `负载分析 / 单版本分析 / 负载分析 / 步骤${stepId}`;
};

// 动态获取帧步骤页面标题
const getFrameStepPageTitle = (pageId: string): string => {
  const stepId = getFrameStepId(pageId);
  return `步骤${stepId}帧分析`;
};

// 动态获取帧步骤页面面包屑
const getFrameStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getFrameStepId(pageId);
  return `负载分析 / 单版本分析 / 帧分析 / 步骤${stepId}`;
};

// 动态获取火焰图步骤页面标题
const getFlameStepPageTitle = (pageId: string): string => {
  const stepId = getFlameStepId(pageId);
  return `步骤${stepId}火焰图分析`;
};

// 动态获取火焰图步骤页面面包屑
const getFlameStepPageBreadcrumb = (pageId: string): string => {
  const stepId = getFlameStepId(pageId);
  return `负载分析 / 单版本分析 / 火焰图分析 / 步骤${stepId}`;
};

const getPageTitle = () => {
  if (showPage.value.startsWith('perf_step_')) {
    return getStepPageTitle(showPage.value);
  }
  if (showPage.value.startsWith('frame_step_')) {
    return getFrameStepPageTitle(showPage.value);
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
  if (showPage.value.startsWith('flame_step_')) {
    return getFlameStepPageBreadcrumb(showPage.value);
  }
  return breadcrumbMap[showPage.value] || '首页';
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

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.breadcrumb {
  color: #909399;
  font-size: 14px;
}

.breadcrumb-item {
  color: #606266;
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
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 500px;
}

.welcome-content {
  text-align: center;
  max-width: 800px;
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
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 40px;
  max-width: 1200px;
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
@media (max-width: 768px) {
  .main-content {
    margin-left: 220px;
  }

  .content-header {
    padding: 16px 20px;
  }

  .page-title {
    font-size: 24px;
  }

  .content-body {
    padding: 16px 20px;
  }

  .feature-grid {
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 16px;
  }

  .welcome-content h2 {
    font-size: 28px;
  }
}

@media (max-width: 480px) {
  .main-content {
    margin-left: 0;
  }

  .content-header {
    padding: 12px 16px;
  }

  .page-title {
    font-size: 20px;
  }

  .content-body {
    padding: 12px 16px;
  }
}
</style>
