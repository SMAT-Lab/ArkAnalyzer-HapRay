<template>
  <div class="page-detail" v-if="page">
    <div v-if="page.error" style="padding: 16px;">
      <el-alert
        title="分析失败"
        type="error"
        :description="page.error"
        show-icon
        :closable="false"
      />
    </div>
    <div v-else>
      <!-- CanvasNode数量 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-data-analysis" style="margin-right: 8px;"></i>
            组件树信息
          </span>
        </template>
        <el-statistic title="CanvasNode数量" :value="page.canvasNodeCnt || 0">
          <template #suffix>
            <span style="font-size: 14px;">个</span>
          </template>
        </el-statistic>
      </el-card>

      <!-- Image尺寸分析 -->
      <el-card
        v-if="page.image_size_analysis"
        shadow="never"
        style="margin-bottom: 16px;"
      >
        <template #header>
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-picture-outline-round" style="margin-right: 8px;"></i>
            超出尺寸Image分析
          </span>
        </template>
        <div v-if="page.image_size_analysis.images_exceeding_framerect && page.image_size_analysis.images_exceeding_framerect.length > 0">
          <el-alert
            :title="`检测到 ${page.image_size_analysis.images_exceeding_framerect.length} 个超出尺寸的Image节点`"
            type="warning"
            :closable="false"
            style="margin-bottom: 16px;"
          >
            <template #default>
              <div style="margin-top: 8px;">
                <span style="font-weight: 600; color: #e6a23c;">总超出内存: </span>
                <span style="font-size: 18px; font-weight: 600; color: #f56c6c;">
                  {{ page.image_size_analysis.total_excess_memory_mb?.toFixed(2) || '0.00' }} M
                </span>
              </div>
            </template>
          </el-alert>
          <el-table
            :data="page.image_size_analysis.images_exceeding_framerect"
            border
            stripe
            size="small"
            max-height="300"
          >
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="path" label="路径" min-width="150" show-overflow-tooltip />
            <el-table-column label="FrameRect" width="120" align="center">
              <template #default="{ row }">
                <div style="font-size: 12px;">
                  {{ row.frameRect?.width }} × {{ row.frameRect?.height }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="RenderedImageSize" width="150" align="center">
              <template #default="{ row }">
                <div style="font-size: 12px;">
                  {{ row.renderedImageSize?.width }} × {{ row.renderedImageSize?.height }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="超出内存" width="100" align="center">
              <template #default="{ row }">
                <el-tag type="warning" size="small">
                  {{ row.memory?.excess_memory_mb?.toFixed(2) || '0.00' }} M
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else description="未检测到超出尺寸的Image节点" :image-size="80" />
      </el-card>
    </div>
  </div>
  <div v-else class="empty-state">
    <el-empty description="无页面数据" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { defineProps } from 'vue';
import type { UIAnimatePageData } from '../../../../stores/jsonDataStore';

interface Props {
  page?: UIAnimatePageData;
}

defineProps<Props>();
</script>

<style scoped>
.page-detail {
  padding: 8px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
</style>
