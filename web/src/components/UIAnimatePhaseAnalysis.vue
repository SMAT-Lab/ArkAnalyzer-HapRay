<template>
  <div class="phase-analysis">
    <!-- 错误信息 -->
    <el-alert
      v-if="phaseData.error"
      title="分析失败"
      type="error"
      :description="phaseData.error"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    />

    <!-- 标记图片 -->
    <el-card v-if="hasMarkedImages" shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-picture" style="margin-right: 8px;"></i>
            动画区域标记图
          </span>
          <el-tag v-if="animationCount > 0" type="success" size="small">
            检测到 {{ animationCount }} 个动画区域
          </el-tag>
          <el-tag v-else type="info" size="small">
            未检测到动画
          </el-tag>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col
          v-for="(image, index) in markedImages"
          :key="index"
          :span="12"
        >
          <div class="image-container">
            <div class="image-label">截图 {{ index + 1 }}</div>
            <el-image
              :src="`data:image/png;base64,${image}`"
              fit="contain"
              :preview-src-list="markedImages.map((img: string) => `data:image/png;base64,${img}`)"
              :initial-index="index"
              style="width: 50%;height: 50%; border-radius: 4px; border: 1px solid #dcdfe6;"
            >
              <template #error>
                <div class="image-error">
                  <i class="el-icon-picture-outline"></i>
                  <span>图片加载失败</span>
                </div>
              </template>
            </el-image>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 图像动画分析 -->
    <el-card v-if="imageAnimations" shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span style="font-weight: 600; font-size: 15px;">
          <i class="el-icon-view" style="margin-right: 8px;"></i>
          图像动画分析
        </span>
      </template>

      <div v-if="imageAnimations.animation_count > 0">
        <el-table
          :data="imageAnimations.animation_regions"
          border
          stripe
          size="small"
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
      <el-empty v-else description="未检测到图像动画" :image-size="80" />
    </el-card>

    <!-- 元素树动画分析 -->
    <el-card v-if="treeAnimations" shadow="never">
      <template #header>
        <span style="font-weight: 600; font-size: 15px;">
          <i class="el-icon-document" style="margin-right: 8px;"></i>
          元素树动画分析
        </span>
      </template>

      <div v-if="treeAnimations.animation_count > 0">
        <el-collapse accordion>
          <el-collapse-item
            v-for="(region, index) in treeAnimations.animation_regions"
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
                <el-tag
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
                <!--<el-descriptions-item label="路径" :span="2">
                  <el-tooltip :content="region.component.path" placement="top">
                    <span class="path-text">{{ region.component.path }}</span>
                  </el-tooltip>
                </el-descriptions-item>-->
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
      <el-empty v-else description="未检测到元素树动画" :image-size="80" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { UIAnimatePhaseData } from '@/stores/jsonDataStore';

interface Props {
  phaseData: UIAnimatePhaseData;
  phaseName: string;
}

const props = defineProps<Props>();

// 标记图片
const markedImages = computed(() => {
  return props.phaseData.marked_images_base64 || [];
});

const hasMarkedImages = computed(() => {
  return markedImages.value.length > 0;
});

// 图像动画
const imageAnimations = computed(() => {
  return props.phaseData.image_animations;
});

// 元素树动画
const treeAnimations = computed(() => {
  return props.phaseData.tree_animations;
});

// 动画数量
const animationCount = computed(() => {
  const imageCount = imageAnimations.value?.animation_count || 0;
  const treeCount = treeAnimations.value?.animation_count || 0;
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
.phase-analysis {
  padding: 16px;
}

.image-container {
  position: relative;
  margin-bottom: 16px;
}

.image-label {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  z-index: 1;
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

.path-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
}

:deep(.el-collapse-item__header) {
  padding: 12px 16px;
  background-color: #f5f7fa;
}

:deep(.el-collapse-item__content) {
  padding: 16px;
}
</style>

