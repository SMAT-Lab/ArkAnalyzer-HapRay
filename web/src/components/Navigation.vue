<template>
  <div class="navigation">
    <el-menu
      :default-active="activePage"
      mode="horizontal"
      @select="handleSelect"
      class="nav-menu"
    >
      <el-menu-item index="perf">
        <el-icon><DataAnalysis /></el-icon>
        <span>单版本分析</span>
      </el-menu-item>
      <el-menu-item index="perf_compare">
        <el-icon><Switch /></el-icon>
        <span>版本对比</span>
      </el-menu-item>
      <el-menu-item index="perf_multi">
        <el-icon><TrendCharts /></el-icon>
        <span>多版本趋势</span>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch } from 'vue';
import { DataAnalysis, Switch, TrendCharts } from '@element-plus/icons-vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  pageChange: [page: string];
}>();

const activePage = ref(props.currentPage);

const handleSelect = (key: string) => {
  activePage.value = key;
  emit('pageChange', key);
};

watch(() => props.currentPage, (newPage) => {
  activePage.value = newPage;
});
</script>

<style scoped>
.navigation {
  background: white;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 20px;
}

.nav-menu {
  padding: 0 20px;
}

.el-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.el-icon {
  margin-right: 4px;
}
</style> 