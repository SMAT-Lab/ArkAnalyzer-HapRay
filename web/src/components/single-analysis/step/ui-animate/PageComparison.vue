<template>
  <div class="page-comparison" v-if="page1 && page2">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 动画对比 -->
      <el-tab-pane label="动画对比" name="animation">
        <div v-if="!isAdjacentPages" style="margin-bottom: 16px;">
          <el-alert
            title="提示"
            type="info"
            :closable="false"
            description="当前选择的两个页面不是相邻页面，无法进行动画对比分析。动画分析仅支持相邻页面的对比。"
          />
        </div>
        <div v-else-if="hasAnimationComparison">
          <el-alert
            :title="`检测到 ${animationComparison.animation_count} 个动画差异`"
            type="info"
            :closable="false"
            style="margin-bottom: 16px;"
          />
          
          <!-- 图像动画对比 -->
          <el-card v-if="animationComparison.image_animations && animationComparison.image_animations.animation_count > 0" shadow="never" style="margin-bottom: 16px;">
            <template #header>
              <span style="font-weight: 600;">图像动画差异</span>
            </template>
            <el-table
              :data="animationComparison.image_animations.animation_regions"
              border
              stripe
              size="small"
            >
              <el-table-column type="index" label="#" width="50" align="center" />
              <el-table-column prop="component.type" label="组件类型" width="120" />
              <el-table-column prop="region" label="区域坐标" min-width="150">
                <template #default="{ row }">
                  <el-tag size="small">{{ formatRegion(row.region) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="similarity" label="相似度" width="120" align="center">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.similarity"
                    :color="getSimilarityColor(row.similarity)"
                    :stroke-width="16"
                  />
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 元素树动画对比 -->
          <el-card v-if="animationComparison.tree_animations && animationComparison.tree_animations.animation_count > 0" shadow="never">
            <template #header>
              <span style="font-weight: 600;">元素树差异</span>
            </template>
            <el-collapse accordion>
              <el-collapse-item
                v-for="(region, index) in animationComparison.tree_animations.animation_regions"
                :key="index"
                :name="index"
              >
                <template #title>
                  <div style="display: flex; align-items: center; width: 100%;">
                    <el-tag type="primary" size="small" style="margin-right: 12px;">
                      #{{ index + 1 }}
                    </el-tag>
                    <span style="flex: 1; font-weight: 500;">
                      {{ region.component?.type || '未知组件' }}
                    </span>
                  </div>
                </template>
                <div v-if="region.comparison_result && region.comparison_result.length > 0">
                  <el-table
                    :data="region.comparison_result"
                    border
                    stripe
                    size="small"
                  >
                    <el-table-column prop="attribute" label="属性名" width="150" />
                    <el-table-column prop="value1" :label="`Page ${page1.page_idx} 值`" min-width="200" show-overflow-tooltip />
                    <el-table-column prop="value2" :label="`Page ${page2.page_idx} 值`" min-width="200" show-overflow-tooltip />
                  </el-table>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-card>
          
          <!-- 动画标记截图 -->
          <el-card v-if="animationComparison.marked_image" shadow="never" style="margin-top: 16px;">
            <template #header>
              <span style="font-weight: 600;">动画标记截图</span>
            </template>
            <el-image
              :src="`data:image/png;base64,${animationComparison.marked_image}`"
              fit="contain"
              class="animation-marked-image"
              :preview-src-list="[`data:image/png;base64,${animationComparison.marked_image}`]"
            >
              <template #error>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: #909399;">
                  <i class="el-icon-picture-outline" style="font-size: 48px; margin-bottom: 8px;"></i>
                  <span>图片加载失败</span>
                </div>
              </template>
            </el-image>
          </el-card>
          
          <el-empty v-if="!hasAnimationComparison" description="未检测到动画差异" :image-size="80" />
        </div>
        <el-empty v-else-if="isAdjacentPages" description="未检测到动画差异" :image-size="80" />
      </el-tab-pane>

      <!-- 组件树对比 -->
      <el-tab-pane label="组件树对比" name="tree">
        <el-alert
          title="组件树对比"
          type="info"
          :closable="false"
          style="margin-bottom: 16px;"
        >
          <template #default>
            <div>
              <p><strong>Page {{ page1.page_idx }}:</strong> CanvasNode数量 {{ page1.canvasNodeCnt || 0 }}</p>
              <p><strong>Page {{ page2.page_idx }}:</strong> CanvasNode数量 {{ page2.canvasNodeCnt || 0 }}</p>
              <p style="margin-top: 8px;">
                <strong>差异:</strong> 
                <span :style="{ color: canvasDiff >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ canvasDiff >= 0 ? '+' : '' }}{{ canvasDiff }}
                </span>
              </p>
            </div>
          </template>
        </el-alert>
      </el-tab-pane>

      <!-- 内存对比 -->
      <el-tab-pane label="内存对比" name="memory">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>Page {{ page1.page_idx }}</span>
              </template>
              <el-statistic
                title="超尺寸内存"
                :value="page1.image_size_analysis?.total_excess_memory_mb || 0"
              >
                <template #suffix>
                  <span style="font-size: 14px;">MB</span>
                </template>
              </el-statistic>
              <div v-if="page1.image_size_analysis?.images_exceeding_framerect" style="margin-top: 16px;">
                <p style="font-size: 14px; color: #606266;">
                  超出尺寸Image节点: {{ page1.image_size_analysis.images_exceeding_framerect.length }} 个
                </p>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>Page {{ page2.page_idx }}</span>
              </template>
              <el-statistic
                title="超尺寸内存"
                :value="page2.image_size_analysis?.total_excess_memory_mb || 0"
              >
                <template #suffix>
                  <span style="font-size: 14px;">MB</span>
                </template>
              </el-statistic>
              <div v-if="page2.image_size_analysis?.images_exceeding_framerect" style="margin-top: 16px;">
                <p style="font-size: 14px; color: #606266;">
                  超出尺寸Image节点: {{ page2.image_size_analysis.images_exceeding_framerect.length }} 个
                </p>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { UIAnimatePageData } from '../../../../stores/jsonDataStore';

interface Props {
  page1?: UIAnimatePageData;
  page2?: UIAnimatePageData;
}

const props = defineProps<Props>();

const activeTab = ref('animation');

// 判断两个页面是否相邻
const isAdjacentPages = computed(() => {
  if (!props.page1 || !props.page2) return false;
  return Math.abs((props.page2.page_idx || 0) - (props.page1.page_idx || 0)) === 1;
});

  // 动画对比数据（仅当两个页面相邻时，使用后一个page的animations数据）
const animationComparison = computed(() => {
  if (!isAdjacentPages.value) {
    return {
      animation_count: 0,
      image_animations: null,
      tree_animations: null,
      marked_image: null,
    };
  }
  
  // 使用后一个page的animations数据（它是对比前一个page的结果）
  const laterPage = (props.page2?.page_idx || 0) > (props.page1?.page_idx || 0) ? props.page2 : props.page1;
  
  if (!laterPage?.animations) {
    return {
      animation_count: 0,
      image_animations: null,
      tree_animations: null,
      marked_image: null,
    };
  }
  
  return {
    animation_count: 
      (laterPage.animations.image_animations?.animation_count || 0) +
      (laterPage.animations.tree_animations?.animation_count || 0),
    image_animations: laterPage.animations.image_animations,
    tree_animations: laterPage.animations.tree_animations,
    marked_image: laterPage.animations.marked_image || (laterPage.animations.marked_images && laterPage.animations.marked_images[0]) || null,
  };
});

const hasAnimationComparison = computed(() => {
  return isAdjacentPages.value && animationComparison.value.animation_count > 0;
});

// CanvasNode数量差异
const canvasDiff = computed(() => {
  if (!props.page1 || !props.page2) return 0;
  return (props.page2.canvasNodeCnt || 0) - (props.page1.canvasNodeCnt || 0);
});

// 格式化区域坐标
function formatRegion(region: number[]): string {
  if (!region || region.length !== 4) return '未知';
  return `[${region[0]}, ${region[1]}, ${region[2]}, ${region[3]}]`;
}

// 获取相似度颜色
function getSimilarityColor(similarity: number): string {
  if (similarity >= 90) return '#67c23a';
  if (similarity >= 70) return '#e6a23c';
  return '#f56c6c';
}
</script>

<style scoped>
.page-comparison {
  padding: 8px;
}

.animation-marked-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
}

:deep(.animation-marked-image .el-image__inner) {
  width: 100% !important;
  height: auto !important;
  max-height: 400px;
  object-fit: contain;
}
</style>
