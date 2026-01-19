<template>
  <div v-if="page" class="page-detail">
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

      <!-- Image尺寸分析（仅在存在超出尺寸Image时显示） -->
      <el-card
        v-if="page.image_size_analysis && page.image_size_analysis.images_exceeding_framerect && page.image_size_analysis.images_exceeding_framerect.length > 0"
        shadow="never"
        style="margin-bottom: 16px;"
      >
        <template #header>
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-picture-outline-round" style="margin-right: 8px;"></i>
            超出尺寸Image分析
          </span>
        </template>
        <div>
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
      </el-card>

      <!-- 动画信息 -->
      <el-card
        v-if="page.animations && hasAnyAnimations"
        shadow="never"
        style="margin-bottom: 16px;"
      >
        <template #header>
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-video-play" style="margin-right: 8px;"></i>
            动画信息
          </span>
        </template>
        
        <!-- 动画统计 -->
        <el-alert
          v-if="totalAnimationCount > 0"
          :title="`检测到 ${totalAnimationCount} 个动画差异`"
          type="info"
          :closable="false"
          style="margin-bottom: 16px;"
        />

        <!-- 图像动画 -->
        <div v-if="hasImageAnimations && imageAnimationRegions.length > 0" style="margin-bottom: 16px;">
          <div style="font-weight: 600; margin-bottom: 12px; color: #606266;">
            图像动画 ({{ imageAnimationRegions.length }} 个)
          </div>
          <el-table
            :data="imageAnimationRegions"
            border
            stripe
            size="small"
            max-height="300"
          >
            <el-table-column type="index" label="#" width="50" align="center" />
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
            <el-table-column prop="is_animation" label="是否动画" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_animation ? 'success' : 'info'" size="small">
                  {{ row.is_animation ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 元素树动画 -->
        <div v-if="hasTreeAnimations && treeAnimationRegions.length > 0">
          <div style="font-weight: 600; margin-bottom: 12px; color: #606266;">
            元素树动画 ({{ treeAnimationRegions.length }} 个)
          </div>
          <el-collapse accordion>
            <el-collapse-item
              v-for="(region, index) in treeAnimationRegions"
              :key="`tree-${index}`"
              :name="`tree-${index}`"
            >
              <template #title>
                <div style="display: flex; align-items: center; width: 100%;">
                  <el-tag type="primary" size="small" style="margin-right: 12px;">
                    #{{ index + 1 }}
                  </el-tag>
                  <span style="flex: 1; font-weight: 500;">
                    {{ region.component?.type || '未知组件' }}
                  </span>
                  <el-tag
                    v-if="region.animate_type"
                    :type="region.animate_type === 'attribute_animate' ? 'warning' : 'success'"
                    size="small"
                    style="margin-right: 12px;"
                  >
                    {{ getAnimateTypeLabel(region.animate_type) }}
                  </el-tag>
                </div>
              </template>
              <!-- 组件信息 -->
              <div v-if="region.component" style="margin-bottom: 16px;">
                <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #606266;">组件信息</h4>
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="类型">
                    {{ region.component.type }}
                  </el-descriptions-item>
                  <el-descriptions-item label="ID">
                    {{ region.component.id }}
                  </el-descriptions-item>
                  <el-descriptions-item label="位置" :span="2">
                    {{ formatBounds(region.component.bounds_rect) }}
                  </el-descriptions-item>
                </el-descriptions>
              </div>
              <!-- 属性变化 -->
              <div v-if="region.comparison_result && region.comparison_result.length > 0">
                <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #606266;">属性变化</h4>
                <el-table
                  :data="region.comparison_result"
                  border
                  stripe
                  size="small"
                >
                  <el-table-column prop="attribute" label="属性名" width="150" />
                  <el-table-column prop="value1" label="变化前" min-width="200" show-overflow-tooltip />
                  <el-table-column prop="value2" label="变化后" min-width="200" show-overflow-tooltip />
                </el-table>
              </div>
              </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
    </div>
  </div>
  <div v-else class="empty-state">
    <el-empty description="无页面数据" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { UIAnimatePageData } from '../../../../stores/jsonDataStore';

interface Props {
  page?: UIAnimatePageData;
}

const props = defineProps<Props>();

// 图像动画区域列表
const imageAnimationRegions = computed(() => {
  return props.page?.animations?.image_animations?.animation_regions || [];
});

// 是否有图像动画（必须要有实际的动画区域数据）
const hasImageAnimations = computed(() => {
  return imageAnimationRegions.value.length > 0;
});

// 元素树动画区域列表
const treeAnimationRegions = computed(() => {
  return props.page?.animations?.tree_animations?.animation_regions || [];
});

// 是否有元素树动画（必须要有实际的动画区域数据）
const hasTreeAnimations = computed(() => {
  return treeAnimationRegions.value.length > 0;
});

// 是否有任何动画信息（必须要有实际的动画区域数据）
const hasAnyAnimations = computed(() => {
  return imageAnimationRegions.value.length > 0 || treeAnimationRegions.value.length > 0;
});

// 动画总数
const totalAnimationCount = computed(() => {
  if (!hasAnyAnimations.value) return 0;
  const imageCount = imageAnimationRegions.value.length || 
                     (props.page?.animations?.image_animations?.animation_count ?? 0);
  const treeCount = treeAnimationRegions.value.length || 
                    (props.page?.animations?.tree_animations?.animation_count ?? 0);
  return imageCount + treeCount;
});

// 格式化区域坐标
function formatRegion(region: number[]): string {
  if (!region || region.length !== 4) return '未知';
  return `[${region[0]}, ${region[1]}, ${region[2]}, ${region[3]}]`;
}

// 格式化边界
function formatBounds(bounds: number[]): string {
  if (!bounds || bounds.length !== 4) return '未知';
  const [x1, y1, x2, y2] = bounds;
  const width = x2 - x1;
  const height = y2 - y1;
  return `位置: (${x1}, ${y1}), 大小: ${width}×${height}`;
}

// 获取相似度颜色
function getSimilarityColor(similarity: number): string {
  if (similarity >= 90) return '#67c23a';
  if (similarity >= 70) return '#e6a23c';
  return '#f56c6c';
}

// 获取动画类型标签
function getAnimateTypeLabel(type: string | undefined): string {
  if (!type) return '未知';
  const labels: Record<string, string> = {
    'attribute_animate': '属性动画',
    'position_animate': '位置动画',
    'size_animate': '大小动画',
  };
  return labels[type] || type;
}
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
