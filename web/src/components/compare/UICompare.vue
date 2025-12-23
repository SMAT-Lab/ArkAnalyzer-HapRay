<template>
  <div class="ui-compare">
    <el-card v-if="!hasData" shadow="never">
      <el-empty description="暂无UI对比数据">
        <template #description>
          <div style="color: #909399; font-size: 14px;">
            <p>两个版本都需要包含UI动画数据才能进行对比</p>
            <p style="margin-top: 8px;">请确保测试时启用了UI截图功能</p>
          </div>
        </template>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 摘要信息 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span style="font-weight: 600; font-size: 16px;">
            <i class="el-icon-data-analysis" style="margin-right: 8px;"></i>
            UI对比摘要 - 步骤{{ stepId }}
          </span>
        </template>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-statistic title="发现差异" :value="currentPairData.diff_count">
              <template #suffix>
                <span style="font-size: 14px;">处</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="总差异数" :value="currentPairData.total_differences">
              <template #suffix>
                <span style="font-size: 14px;">处</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="已过滤" :value="currentPairData.filtered_count">
              <template #suffix>
                <span style="font-size: 14px;">处</span>
              </template>
            </el-statistic>
          </el-col>
        </el-row>
      </el-card>

      <!-- 截图对选择器 -->
      <el-card v-if="currentStepData && currentStepData.pairs && currentStepData.pairs.length > 1" shadow="never" style="margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-weight: 500;">选择对比图片：</span>
          <el-select v-model="currentPairIndex" style="width: 300px;">
            <el-option
              v-for="(pair, index) in currentStepData.pairs"
              :key="index"
              :label="`${pair.phase === 'start' ? '开始' : '结束'}阶段 #${pair.index} (差异: ${pair.diff_count})`"
              :value="index"
            />
          </el-select>
          <el-tag type="info" size="small">
            共 {{ currentStepData.pairs.length }} 对截图
          </el-tag>
        </div>
      </el-card>

      <!-- 对比图片 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="font-weight: 600; font-size: 15px;">
              <i class="el-icon-picture" style="margin-right: 8px;"></i>
              UI差异标记图
            </span>
            <el-tag v-if="currentPairData.diff_count > 0" type="danger" size="small">
              检测到 {{ currentPairData.diff_count }} 处差异
            </el-tag>
            <el-tag v-else type="success" size="small">
              无差异
            </el-tag>
          </div>
        </template>

        <el-row :gutter="16">
          <el-col :span="12">
            <div class="image-container">
              <div class="image-label">基准版本</div>
              <canvas
                ref="baseCanvasRef"
                style="width: 100%; border-radius: 4px; border: 1px solid #dcdfe6; display: block;"
              />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="image-container">
              <div class="image-label">对比版本</div>
              <canvas
                ref="compareCanvasRef"
                style="width: 100%; border-radius: 4px; border: 1px solid #dcdfe6; display: block;"
              />
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 差异详情 -->
      <el-card v-if="currentPairData.differences?.length > 0" shadow="never">
        <template #header>
          <span style="font-weight: 600; font-size: 15px;">
            <i class="el-icon-document" style="margin-right: 8px;"></i>
            差异详情
          </span>
        </template>

        <el-collapse accordion>
          <el-collapse-item
            v-for="(diff, index) in currentPairData.differences"
            :key="index"
            :name="index"
          >
            <template #title>
              <div style="display: flex; align-items: center; width: 100%;">
                <el-tag type="primary" size="small" style="margin-right: 12px;">
                  #{{ index + 1 }}
                </el-tag>
                <span style="flex: 1; font-weight: 500;">
                  {{ diff.component?.type || '未知组件' }}
                </span>
                <el-tag type="warning" size="small" style="margin-right: 12px;">
                  {{ diff.comparison_result?.length || 0 }} 个属性差异
                </el-tag>
              </div>
            </template>

            <!-- 组件信息 -->
            <div v-if="diff.component" style="margin-bottom: 16px;">
              <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #606266;">组件信息</h4>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="类型">
                  {{ diff.component.type }}
                </el-descriptions-item>
                <el-descriptions-item label="ID">
                  {{ diff.component.id || 'N/A' }}
                </el-descriptions-item>
                <el-descriptions-item label="位置" :span="2">
                  {{ formatBounds(diff.component.bounds_rect) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 属性差异 -->
            <div v-if="diff.comparison_result?.length > 0">
              <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #606266;">属性差异</h4>
              <el-table :data="diff.comparison_result" border stripe size="small">
                <el-table-column prop="attribute" label="属性名" width="150" />
                <el-table-column prop="value1" label="基准值" min-width="150">
                  <template #default="{ row }">
                    <el-tag size="small" type="info">{{ row.value1 }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="value2" label="对比值" min-width="150">
                  <template #default="{ row }">
                    <el-tag size="small" type="warning">{{ row.value2 }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { useJsonDataStore, type UIComponentDifference } from '@/stores/jsonDataStore';

interface Props {
  stepId?: number;
}

const props = withDefaults(defineProps<Props>(), {
  stepId: 1,
});

const jsonDataStore = useJsonDataStore();

// 当前选择的截图对索引
const currentPairIndex = ref(0);

// Canvas引用
const baseCanvasRef = ref<HTMLCanvasElement | null>(null);
const compareCanvasRef = ref<HTMLCanvasElement | null>(null);

// 检查是否有UI对比数据
const hasData = computed(() => {
  const stepKey = `step${props.stepId}`;
  return jsonDataStore.uiCompareData && jsonDataStore.uiCompareData[stepKey];
});

// 当前步骤的所有截图对
const currentStepData = computed(() => {
  const stepKey = `step${props.stepId}`;
  if (!jsonDataStore.uiCompareData || !jsonDataStore.uiCompareData[stepKey]) {
    return null;
  }
  return jsonDataStore.uiCompareData[stepKey];
});

// 当前选择的截图对数据
const currentPairData = computed(() => {
  if (!currentStepData.value || !currentStepData.value.pairs) {
    return {
      diff_count: 0,
      total_differences: 0,
      filtered_count: 0,
      differences: [],
      marked_images_base64: []
    };
  }
  return currentStepData.value.pairs[currentPairIndex.value] || {
    diff_count: 0,
    total_differences: 0,
    filtered_count: 0,
    differences: [],
    marked_images_base64: []
  };
});

// 绘制带差异标记的图片
// 注意：此函数需要与后端逻辑完全一致
// 后端代码位置: perf_testing/hapray/ui_detector/ui_tree_comparator.py UITreeComparator._mark_differences (第148-165行)
const drawMarkedImage = async (canvasRef: HTMLCanvasElement | null, imageBase64: string, differences: UIComponentDifference[]) => {
  if (!canvasRef || !imageBase64) return;

  const img = new Image();
  img.onload = () => {
    const ctx = canvasRef.getContext('2d');
    if (!ctx) return;

    // 设置canvas尺寸
    canvasRef.width = img.width;
    canvasRef.height = img.height;

    // 绘制原图
    ctx.drawImage(img, 0, 0);

    // 绘制差异标记框（与后端完全一致）
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 3;
    // 修改字体以更接近PIL默认字体效果
    // 后端使用PIL的默认字体，这里使用sans-serif模拟
    ctx.font = '12px sans-serif';
    ctx.fillStyle = 'red';
    // 设置文本基线为top，使文本Y坐标行为更接近PIL
    // Canvas默认基线是alphabetic（字母基线），改为top后y坐标表示文本顶部
    ctx.textBaseline = 'top';

    differences.forEach((diff, index) => {
      const bounds = diff.component?.bounds_rect;
      if (bounds && bounds.length === 4) {
        const [x1, y1, x2, y2] = bounds;
        // 后端第161行：验证坐标有效性
        if (x2 >= x1 && y2 >= y1) {
          // 后端第162行：绘制红框
          // draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

          // 后端第163行：绘制标记编号
          // draw.text((x1 + 5, y1 + 5), f'D{i}', fill='red')
          // ⚠️ 关键修复：文本Y坐标从 y1+20 改为 y1+5，与后端一致
          ctx.fillText(`D${index + 1}`, x1 + 5, y1 + 5);
        }
      }
    });
  };
  img.src = `data:image/png;base64,${imageBase64}`;
};

// 监听当前截图对变化，重新绘制
watch([currentPairData, baseCanvasRef, compareCanvasRef], async () => {
  await nextTick();
  if (currentPairData.value.marked_images_base64?.length === 2) {
    drawMarkedImage(baseCanvasRef.value, currentPairData.value.marked_images_base64[0], currentPairData.value.differences);
    drawMarkedImage(compareCanvasRef.value, currentPairData.value.marked_images_base64[1], currentPairData.value.differences);
  }
}, { immediate: true });

// 格式化边界坐标
const formatBounds = (bounds: number[] | undefined) => {
  if (!bounds || bounds.length !== 4) return 'N/A';
  const [x1, y1, x2, y2] = bounds;
  return `(${x1}, ${y1}) - (${x2}, ${y2})`;
};
</script>

<style scoped>
.ui-compare {
  padding: 20px;
}

.image-container {
  text-align: center;
}

.image-label {
  font-weight: bold;
  margin-bottom: 10px;
  color: #606266;
  font-size: 14px;
}
</style>

