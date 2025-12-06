<template>
  <div class="flame-graph-container">
    <!-- 当前步骤信息卡片 -->
    <!-- <div v-if="currentStepInfo" class="step-info-card">
      <div class="step-header">
        <div class="step-badge">STEP {{ currentStepIndex }}</div>
        <div class="step-details">
          <h2 class="step-title">{{ currentStepInfo.step_name }}</h2>
          <div class="step-metrics">
            <div class="metric-item">
              <span class="metric-label">指令数：</span>
              <span class="metric-value">{{ formatDuration(currentStepInfo.count) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">功耗估算：</span>
              <span class="metric-value">{{ formatEnergy(currentStepInfo.count) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">轮次：</span>
              <span class="metric-value">{{ currentStepInfo.round }}</span>
            </div>
          </div>
        </div>
        <div class="step-actions">
          <el-button :loading="isExporting" type="primary" @click="exportFlameGraph">
            <el-icon><Download /></el-icon>
            导出火焰图
          </el-button>
        </div>
      </div>
    </div> -->

    <div class="embed-container">
        <!-- 通过iframe嵌入当前步骤对应的静态HTML -->
        <iframe :srcdoc="htmlContent" class="html-iframe" frameborder="0" scrolling="auto"></iframe>
    </div>
  </div>
</template>

<script lang='ts' setup>
import { ref, computed, watch, onMounted } from 'vue';
//import { ElMessage } from 'element-plus';
//import { Download } from '@element-plus/icons-vue';
import { useJsonDataStore } from '../../../../stores/jsonDataStore.ts';
//import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';
import flameTemplateHtml from '../../../../../../third-party/report.html?raw';
import pako from 'pako';

// 定义props
const props = defineProps<{
  step?: number;
}>();

const jsonDataStore = useJsonDataStore();
//const perfData = jsonDataStore.perfData;
const script_start = '<script id="record_data" type="application/json">';
const script_end = atob('PC9zY3JpcHQ+PC9ib2R5PjwvaHRtbD4=');

// const testSteps = ref(
//     perfData!.steps.map((step, index) => ({
//         //从1开始
//         id: index + 1,
//         step_name: step.step_name,
//         count: step.count,
//         round: step.round,
//         perf_data_path: step.perf_data_path,
//     }))
// );

// interface TestStep {
//   id: number;
//   step_name: string;
//   count: number;
//   round: number;
//   perf_data_path: string;
// }

// 当前步骤索引，如果传入了step参数则使用，否则默认为1
const currentStepIndex = ref(props.step || 1);

// 当前步骤信息
// const currentStepInfo = computed(() => {
//   return testSteps.value.find(step => step.id === currentStepIndex.value);
// });

// 监听props.step变化
watch(() => props.step, (newStep) => {
  if (newStep) {
    currentStepIndex.value = newStep;
  }
}, { immediate: true });

// 格式化功耗信息
// const formatEnergy = (milliseconds: number) => {
//     const energy = calculateEnergyConsumption(milliseconds);
//     return `核算功耗（mAs）：${energy}`;
// };

// 格式化持续时间的方法
// const formatDuration = (milliseconds: number) => {
//     return `指令数：${milliseconds}`;
// };

// 解压缩火焰图数据
const decompressFlameGraphData = (compressedData: string): string => {
    try {
        // Base64解码
        const binaryString = atob(compressedData);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // 使用pako解压缩
        const decompressed = pako.inflate(bytes, { to: 'string' });
        return decompressed;
    } catch (error) {
        console.error('解压缩火焰图数据失败:', error);
        return '';
    }
};

// 根据当前步骤生成HTML内容
const htmlContent = computed(() => {
    const stepId = currentStepIndex.value;
    const stepKey = 'step' + stepId;

    if (jsonDataStore.flameGraph && jsonDataStore.flameGraph[stepKey]) {
        // 检查数据是否已经是解压缩的JSON字符串
        let flameData = jsonDataStore.flameGraph[stepKey];

        // 如果数据看起来是压缩的base64字符串，则解压缩
        if (typeof flameData === 'string' && !flameData.startsWith('{')) {
            flameData = decompressFlameGraphData(flameData);
        }

        return flameTemplateHtml + script_start + flameData + script_end;
    } else {
        return flameTemplateHtml + script_start + script_end;
    }
});

// 导出状态
//const isExporting = ref(false);

// 导出火焰图为HTML文件
// const exportFlameGraph = async () => {
//   if (!currentStepInfo.value) {
//     ElMessage.error('当前步骤信息不可用');
//     return;
//   }

//   isExporting.value = true;

//   try {
//     // 获取当前步骤的火焰图HTML内容
//     const flameGraphHtml = htmlContent.value;

//     // 创建Blob对象
//     const blob = new Blob([flameGraphHtml], { type: 'text/html;charset=utf-8' });

//     // 创建下载链接
//     const url = URL.createObjectURL(blob);
//     const link = document.createElement('a');
//     link.href = url;

//     // 使用步骤名称作为文件名，去除特殊字符
//     const fileName = `${currentStepInfo.value.step_name.replace(/[^\w\u4e00-\u9fa5]/g, '_')}_火焰图.html`;
//     link.download = fileName;

//     // 触发下载
//     document.body.appendChild(link);
//     link.click();
//     document.body.removeChild(link);

//     // 清理URL对象
//     URL.revokeObjectURL(url);

//     ElMessage.success(`火焰图已导出为 ${fileName}`);
//   } catch (error) {
//     console.error('导出火焰图失败:', error);
//     ElMessage.error('导出火焰图失败，请重试');
//   } finally {
//     isExporting.value = false;
//   }
// };

onMounted(() => {
    console.log(`初始化步骤 ${currentStepIndex.value} 的火焰图`);
})

</script>

<style scoped>
.flame-graph-container {
  padding: 20px;
  background: #f5f7fa;
}

/* 步骤信息卡片样式 */
.step-info-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 24px;
}

.step-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.step-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 16px;
  min-width: 100px;
  text-align: center;
}

.step-details {
  flex: 1;
}

.step-title {
  margin: 0 0 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.step-metrics {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-label {
  color: #606266;
  font-size: 14px;
}

.metric-value {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.embed-container {
    width: 100%;
    height: calc(100vh - 200px);
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;
    background: white;
}

.html-iframe {
    width: 100%;
    height: 100%;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .flame-graph-container {
    padding: 16px;
  }

  .step-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .step-metrics {
    flex-direction: column;
    gap: 12px;
  }

  .embed-container {
    height: calc(100vh - 250px);
  }
}

@media (max-width: 480px) {
  .step-info-card {
    padding: 16px;
  }

  .step-title {
    font-size: 20px;
  }

  .step-badge {
    padding: 8px 16px;
    font-size: 14px;
  }
}
</style>
