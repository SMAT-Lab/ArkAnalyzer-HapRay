<template>
  <div class="sidebar-navigation" :class="{ collapsed: isCollapsed }">
    <div class="logo-section" @click="goToHome">
      <!-- <h2 v-show="!isCollapsed" class="app-title">ArkAnalyzer</h2> -->
      <h2 v-show="!isCollapsed" class="app-title">HapRay</h2>
      <div v-show="isCollapsed" class="logo-icon">H</div>
    </div>

    <!-- 折叠/展开按钮 -->
    <div class="collapse-toggle" @click="toggleCollapse">
      <el-icon>
        <ArrowLeft v-if="!isCollapsed" />
        <ArrowRight v-if="isCollapsed" />
      </el-icon>
    </div>

    <el-menu
      :default-active="activePage"
      mode="vertical"
      class="nav-menu"
      :unique-opened="true"
      :collapse="isCollapsed"
      @select="handleSelect"
    >
      <!-- 单版本分析子菜单 -->
      <el-sub-menu index="single-analysis">
        <template #title>
          <el-icon><DataAnalysis /></el-icon>
          <span>单版本分析</span>
        </template>

        <el-tooltip
          effect="dark"
          content="负载总览"
          placement="right"
          :disabled="!isCollapsed">
          <el-menu-item index="perf_load_overview">
            <el-icon><PieChart /></el-icon>
            <span>负载总览</span>
          </el-menu-item>
        </el-tooltip>

        <!-- 步骤选择子菜单 -->
        <el-sub-menu index="step-selection">
          <template #title>
            <el-icon><List /></el-icon>
            <span>步骤选择</span>
          </template>

          <!-- 动态生成步骤菜单 -->
          <el-sub-menu
            v-for="step in testSteps"
            :key="step.id"
            :index="`step_${step.id}`">
            <template #title>
              <el-icon><Document /></el-icon>
              <span :title="step.step_name">步骤{{ step.id }}</span>
            </template>

            <!-- 步骤下的分析类型子菜单 -->
            <el-menu-item :index="`perf_step_${step.id}`" :title="step.step_name">
              <el-icon><Monitor /></el-icon>
              <span>负载分析</span>
            </el-menu-item>

            <el-menu-item :index="`frame_step_${step.id}`" :title="step.step_name">
              <el-icon><VideoPlay /></el-icon>
              <span>帧分析</span>
            </el-menu-item>

            <el-menu-item :index="`flame_step_${step.id}`" :title="step.step_name">
              <el-icon><Histogram /></el-icon>
              <span>火焰图分析</span>
            </el-menu-item>
          </el-sub-menu>
        </el-sub-menu>
      </el-sub-menu>

      <!-- 其他负载分析菜单项 -->
      <el-tooltip
        effect="dark"
        content="版本对比"
        placement="right"
        :disabled="!isCollapsed">
        <el-menu-item index="perf_compare">
          <el-icon><Switch /></el-icon>
          <span>版本对比</span>
        </el-menu-item>
      </el-tooltip>

      <el-tooltip
        effect="dark"
        content="多版本趋势"
        placement="right"
        :disabled="!isCollapsed">
        <el-menu-item index="perf_multi">
          <el-icon><TrendCharts /></el-icon>
          <span>多版本趋势</span>
        </el-menu-item>
      </el-tooltip>
    </el-menu>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch, computed } from 'vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';
import {
  DataAnalysis,
  Switch,
  TrendCharts,
  Histogram,
  VideoPlay,
  PieChart,
  List,
  Document,
  Monitor,
  ArrowLeft,
  ArrowRight
} from '@element-plus/icons-vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  pageChange: [page: string];
  collapseChange: [collapsed: boolean];
}>();

const activePage = ref(props.currentPage);
const isCollapsed = ref(false);

const handleSelect = (key: string) => {
  activePage.value = key;
  emit('pageChange', key);
};

const goToHome = () => {
  activePage.value = 'welcome';
  emit('pageChange', 'welcome');
};

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
  emit('collapseChange', isCollapsed.value);
};

watch(() => props.currentPage, (newPage) => {
  activePage.value = newPage;
});

// 获取步骤数据
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData;

const testSteps = computed(() => {
  if (!perfData?.steps) return [];
  return perfData.steps.map((step, index) => ({
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }));
});


</script>

<style scoped>
.sidebar-navigation {
  width: 280px;
  min-width: 280px;
  height: 100vh;
  background: white;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 1000;
  border-right: 1px solid #e4e7ed;
  transition: width 0.3s ease;
}

.sidebar-navigation.collapsed {
  width: 64px;
  min-width: 64px;
}

.logo-section {
  padding: 32px 24px;
  text-align: center;
  border-bottom: 1px solid #e4e7ed;
  background: #f8f9fa;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.logo-section:hover {
  background: #e9ecef;
  transform: translateY(-1px);
}

.logo-section:active {
  transform: translateY(0);
}

.collapsed .logo-section {
  padding: 16px 8px;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  margin: 0 auto;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.logo-icon::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(45deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transform: rotate(45deg);
  transition: all 0.6s ease;
  opacity: 0;
}

.logo-icon:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.logo-icon:hover::before {
  opacity: 1;
  animation: shine 1.5s ease-in-out;
}

@keyframes shine {
  0% {
    transform: translateX(-100%) translateY(-100%) rotate(45deg);
  }
  100% {
    transform: translateX(100%) translateY(100%) rotate(45deg);
  }
}

/* 折叠按钮样式 */
.collapse-toggle {
  position: absolute;
  right: -15px;
  top: 50%;
  transform: translateY(-50%);
  width: 30px;
  height: 30px;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 2px solid #e4e7ed;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1001;
}

.collapse-toggle:hover {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: #667eea;
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  transform: translateY(-50%) scale(1.1);
}

.collapse-toggle .el-icon {
  font-size: 14px;
  color: #606266;
  transition: all 0.3s ease;
}

.collapse-toggle:hover .el-icon {
  color: white;
  transform: scale(1.1);
}

/* 折叠按钮的脉动效果 */
.collapse-toggle::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: -1;
}

.collapse-toggle:hover::before {
  opacity: 1;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.3;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.1;
  }
  100% {
    transform: scale(1.4);
    opacity: 0;
  }
}

.app-title {
  color: #303133;
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.app-subtitle {
  color: #909399;
  font-size: 14px;
  margin: 8px 0 0 0;
  font-weight: 400;
}

.nav-menu {
  flex: 1;
  border: none;
  background: white;
  padding: 24px 0;
}

/* 重写Element Plus菜单样式 */
.nav-menu :deep(.el-sub-menu) {
  background: transparent;
}

.nav-menu :deep(.el-sub-menu__title) {
  color: #606266;
  background: transparent;
  padding: 16px 24px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 12px;
  transition: all 0.3s ease;
  margin: 4px 16px;
  border: 1px solid transparent;
  min-height: 52px;
  display: flex;
  align-items: center;
}

.nav-menu :deep(.el-sub-menu__title:hover) {
  background: #f8f9fa;
  color: #303133;
  transform: translateX(2px);
  border-color: #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.nav-menu :deep(.el-sub-menu.is-opened .el-sub-menu__title) {
  background: #f8f9fa;
  color: #303133;
  border-color: #e4e7ed;
}

.nav-menu :deep(.el-menu-item) {
  color: #606266;
  background: transparent;
  padding: 16px 24px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 0;
  transition: all 0.3s ease;
  margin: 4px 16px;
  border-radius: 12px;
  border: 1px solid transparent;
  min-height: 52px;
  display: flex;
  align-items: center;
}

.nav-menu :deep(.el-menu-item:hover) {
  background: #f8f9fa;
  color: #303133;
  transform: translateX(2px);
  border-color: #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.nav-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.nav-menu :deep(.el-menu-item.is-active:hover) {
  background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
  transform: translateX(2px);
}

/* 子菜单项样式 */
.nav-menu :deep(.el-sub-menu .el-menu-item) {
  padding: 12px 20px 12px 48px;
  font-size: 14px;
  margin: 2px 12px 2px 20px;
  min-height: 44px;
  display: flex;
  align-items: center;
}

.nav-menu :deep(.el-sub-menu .el-menu-item:hover) {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.nav-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background: rgba(102, 126, 234, 0.15);
  color: #667eea;
  font-weight: 600;
  border-left: 3px solid #667eea;
  padding-left: 45px;
}

/* 三级菜单样式 */
.nav-menu :deep(.el-sub-menu .el-sub-menu) {
  background: rgba(248, 249, 250, 0.3);
  border-radius: 8px;
  margin: 2px 8px;
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-sub-menu__title) {
  padding: 12px 16px 12px 40px;
  font-size: 13px;
  margin: 2px 8px;
  border-radius: 6px;
  min-height: 40px;
  display: flex;
  align-items: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-sub-menu__title:hover) {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

/* 三级菜单中的步骤菜单项样式 */
.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item) {
  padding: 8px 12px 8px 56px;
  font-size: 12px;
  margin: 1px 4px;
  border-radius: 4px;
  min-height: 32px;
  display: flex;
  align-items: center;
  position: relative;
  transition: all 0.3s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: calc(100% - 8px);
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item:hover) {
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  transform: translateX(1px);
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item.is-active) {
  background: rgba(102, 126, 234, 0.15);
  color: #667eea;
  font-weight: 600;
  border-left: 2px solid #667eea;
  padding-left: 54px;
}

/* 步骤菜单项的图标和文字对齐 */
.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item .el-icon) {
  margin-right: 6px;
  font-size: 12px;
  width: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item span) {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

/* 二级菜单标题的图标和文字样式 */
.nav-menu :deep(.el-sub-menu .el-sub-menu .el-sub-menu__title .el-icon) {
  margin-right: 6px;
  font-size: 12px;
  width: 12px;
  flex-shrink: 0;
}

.nav-menu :deep(.el-sub-menu .el-sub-menu .el-sub-menu__title span) {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.nav-menu :deep(.el-icon) {
  color: inherit;
  margin-right: 12px;
  font-size: 18px;
  width: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-menu :deep(.el-sub-menu__icon-arrow) {
  color: #909399;
  transition: transform 0.3s ease;
}

.nav-menu :deep(.el-sub-menu.is-opened .el-sub-menu__icon-arrow) {
  transform: rotate(90deg);
}

/* 子菜单容器 */
.nav-menu :deep(.el-menu) {
  background: rgba(248, 249, 250, 0.5);
  border-radius: 8px;
  margin: 4px 8px 8px 8px;
  padding: 4px 0;
}



/* 三级子菜单容器 */
.nav-menu :deep(.el-sub-menu .el-sub-menu .el-menu) {
  background: rgba(248, 249, 250, 0.8);
  border-radius: 6px;
  margin: 2px 4px;
  padding: 2px 0;
}

/* 折叠状态下的样式优化 */
.collapsed .nav-menu {
  padding: 16px 0;
}

/* 折叠状态下的菜单项样式 */
.collapsed .nav-menu :deep(.el-sub-menu__title) {
  padding: 12px 0;
  margin: 4px 8px;
  border-radius: 8px;
  justify-content: center;
  position: relative;
}

.collapsed .nav-menu :deep(.el-menu-item) {
  padding: 12px 0;
  margin: 4px 8px;
  border-radius: 8px;
  justify-content: center;
  position: relative;
}

/* 折叠状态下的图标样式 */
.collapsed .nav-menu :deep(.el-icon) {
  margin-right: 0;
  font-size: 20px;
  width: 20px;
  color: #606266;
  transition: all 0.3s ease;
}

/* 折叠状态下的悬停效果 */
.collapsed .nav-menu :deep(.el-sub-menu__title:hover) {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  transform: translateX(0);
  border-color: rgba(102, 126, 234, 0.3);
}

.collapsed .nav-menu :deep(.el-sub-menu__title:hover .el-icon) {
  color: #667eea;
  transform: scale(1.1);
}

.collapsed .nav-menu :deep(.el-menu-item:hover) {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  transform: translateX(0);
  border-color: rgba(102, 126, 234, 0.3);
}

.collapsed .nav-menu :deep(.el-menu-item:hover .el-icon) {
  color: #667eea;
  transform: scale(1.1);
}

/* 折叠状态下的激活状态 */
.collapsed .nav-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.collapsed .nav-menu :deep(.el-menu-item.is-active .el-icon) {
  color: white;
  transform: scale(1.1);
}

/* 隐藏折叠状态下的箭头和文字 */
.collapsed .nav-menu :deep(.el-sub-menu__icon-arrow) {
  opacity: 0;
  transform: scale(0);
  transition: all 0.3s ease;
}

.collapsed .nav-menu :deep(span) {
  opacity: 0;
  transform: translateX(-10px);
  transition: all 0.3s ease;
  pointer-events: none;
}

/* 展开状态下的文字和箭头动画 */
.nav-menu :deep(.el-sub-menu__icon-arrow) {
  opacity: 1;
  transform: scale(1);
  transition: all 0.3s ease;
}

.nav-menu :deep(span) {
  opacity: 1;
  transform: translateX(0);
  transition: all 0.3s ease;
}

/* 折叠状态下的菜单项间距调整 */
.collapsed .nav-menu :deep(.el-sub-menu) {
  margin: 2px 0;
}

.collapsed .nav-menu :deep(.el-menu-item) {
  margin: 2px 8px;
}

/* 为折叠状态添加微妙的背景渐变 */
.sidebar-navigation.collapsed {
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

/* 折叠状态下的分隔线效果 */
.collapsed .logo-section {
  border-bottom: 2px solid #f0f2f5;
  position: relative;
}

.collapsed .logo-section::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 30px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #667eea, transparent);
  border-radius: 1px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .sidebar-navigation {
    width: 220px;
  }

  .logo-section {
    padding: 24px 20px;
  }

  .app-title {
    font-size: 20px;
  }

  .nav-menu {
    padding: 16px 0;
  }

  .nav-menu :deep(.el-menu-item) {
    font-size: 14px;
    padding: 14px 20px;
    margin: 3px 12px;
  }
}

@media (max-width: 480px) {
  .sidebar-navigation {
    width: 200px;
  }

  .logo-section {
    padding: 20px 16px;
  }

  .app-title {
    font-size: 18px;
  }

  .nav-menu :deep(.el-menu-item) {
    font-size: 13px;
    padding: 12px 16px;
    margin: 2px 8px;
  }

  .nav-menu :deep(.el-icon) {
    font-size: 16px;
    margin-right: 8px;
  }
}
</style>
