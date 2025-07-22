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
          </keep-alive>
          <ComponentsDeps v-if="showPage === 'deps'" />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
//import { Document, Menu as IconMenu, Location, Setting } from '@element-plus/icons-vue';
import { onMounted, ref } from 'vue';
//import type Node from 'element-plus/es/components/tree/src/model/node';
//import type { TreeNodeData } from 'element-plus/es/components/tree/src/tree.type';

import PerfCompare from '@/components/PerfCompare.vue';
import ComponentsDeps from '@/components/ComponentsDeps.vue';
import PerfSingle from '@/components/PerfSingle.vue';
import PerfMulti from '@/components/PerfMulti.vue';
import AppNavigation from '@/components/AppNavigation.vue';

//import { getCurrentInstance } from 'vue';
//import { ElMessage } from 'element-plus';

const showPage = ref('');


async function changeContent(page: string) {
  showPage.value = '';
  setTimeout(() => {
    showPage.value = page;
  }, 300); // 这里设置一个延迟，

  console.log(`切换到按钮${page}的内容`);
}

// const { proxy } = getCurrentInstance() as any;

// function handleLanguageChange(newLanguage: string) {
//   console.log('old language is:', proxy.$i18n.locale);
//   proxy.$i18n.locale = newLanguage;
// }

onMounted(() => {
  changeContent(window.initialPage?.toLowerCase())
  // changeContent('perf')
});
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
