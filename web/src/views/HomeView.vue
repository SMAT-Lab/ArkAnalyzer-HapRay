<template>
  <div class="common-layout">
    <AppNavigation :current-page="showPage" @page-change="changeContent" />
    <el-container style="width: 100%; height: 100%">
      <el-container style="height: 100%-50px">
        <!-- main -->
        <el-main>
          <!-- {{ $t('home.name') }} -->
          <keep-alive>
            <PerfCompare v-if="showPage === 'perf_compare'" />
            <PerfSingle v-else-if="showPage === 'perf'" />
            <PerfMulti v-else-if="showPage === 'perf_multi'" />
            <FlameGraph v-else-if="showPage === 'perf_flame'" />
          </keep-alive>
          <ComponentsDeps v-if="showPage === 'deps'" />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import AppNavigation from '@/components/AppNavigation.vue';
import PerfCompare from '@/components/PerfCompare.vue';
import PerfSingle from '@/components/PerfSingle.vue';
import PerfMulti from '@/components/PerfMulti.vue';
import FlameGraph from '@/components/FlameGraph.vue';
import ComponentsDeps from '@/components/ComponentsDeps.vue';

const showPage = ref('perf');

const changeContent = (page: string) => {
  showPage.value = page;
};
</script>

<style scoped>
/* 上方菜单高度 */
/* .el-menu--horizontal { 
  --el-menu-horizontal-height: 100px;
} */

.code-viewer {
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.title {
  font-size: 15px;
  font-weight: 300;
}

.el-header {
  --el-header-padding: 0;
}

.folder-icon::before {
  content: '📁'; /* 文件夹图标 */
  margin-right: 5px;
}

.file-icon::before {
  content: '📄'; /* 文件图标 */
  margin-right: 5px;
}

.common-layout {
  width: 100%;
  height: 100%;
}

.dropdown {
  display: flex;
  width: 100%;
  margin-top: 1vh;
  margin-bottom: 1vh;
}
</style>
