<template>
  <div class="performance-comparison">
    <!-- 上传组件 -->
    <div v-if="!hasCompareData" style="margin-bottom: 16px;">
      <UploadHtml />
    </div>

    <template v-else>
      <!-- 说明信息 -->
      <div class="info-box">
        故障树对比分析：
        <p>对比两个版本在步骤{{ step }}中的故障树分析结果，识别性能差异和潜在问题</p>
      </div>

      <!-- ArkUI 故障分析对比 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🎨</i> ArkUI 故障分析 - 基线版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">帧动画数量</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.arkui.animator, 50)">
                  {{ formatNumber(baselineFaultTree.arkui.animator) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">区域变化监听</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.arkui.HandleOnAreaChangeEvent, 1000)">
                  {{ formatNumber(baselineFaultTree.arkui.HandleOnAreaChangeEvent) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">可见区域变化</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.arkui.HandleVisibleAreaChangeEvent, 1000)">
                  {{ formatNumber(baselineFaultTree.arkui.HandleVisibleAreaChangeEvent) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">屏幕宽高获取</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.arkui.GetDefaultDisplay, 100)">
                  {{ formatNumber(baselineFaultTree.arkui.GetDefaultDisplay) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">事务数据序列化</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.arkui.MarshRSTransactionData, 3000)">
                  {{ formatNumber(baselineFaultTree.arkui.MarshRSTransactionData) }}
                </div>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🎨</i> ArkUI 故障分析 - 对比版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">帧动画数量</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.arkui.animator, 50)">
                  {{ formatNumber(compareFaultTree.arkui.animator) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.arkui.animator - baselineFaultTree.arkui.animator)">
                    {{ getDiffText(compareFaultTree.arkui.animator - baselineFaultTree.arkui.animator) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">区域变化监听</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.arkui.HandleOnAreaChangeEvent, 1000)">
                  {{ formatNumber(compareFaultTree.arkui.HandleOnAreaChangeEvent) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.arkui.HandleOnAreaChangeEvent - baselineFaultTree.arkui.HandleOnAreaChangeEvent)">
                    {{ getDiffText(compareFaultTree.arkui.HandleOnAreaChangeEvent - baselineFaultTree.arkui.HandleOnAreaChangeEvent) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">可见区域变化</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.arkui.HandleVisibleAreaChangeEvent, 1000)">
                  {{ formatNumber(compareFaultTree.arkui.HandleVisibleAreaChangeEvent) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.arkui.HandleVisibleAreaChangeEvent - baselineFaultTree.arkui.HandleVisibleAreaChangeEvent)">
                    {{ getDiffText(compareFaultTree.arkui.HandleVisibleAreaChangeEvent - baselineFaultTree.arkui.HandleVisibleAreaChangeEvent) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">屏幕宽高获取</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.arkui.GetDefaultDisplay, 100)">
                  {{ formatNumber(compareFaultTree.arkui.GetDefaultDisplay) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.arkui.GetDefaultDisplay - baselineFaultTree.arkui.GetDefaultDisplay)">
                    {{ getDiffText(compareFaultTree.arkui.GetDefaultDisplay - baselineFaultTree.arkui.GetDefaultDisplay) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">事务数据序列化</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.arkui.MarshRSTransactionData, 3000)">
                  {{ formatNumber(compareFaultTree.arkui.MarshRSTransactionData) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.arkui.MarshRSTransactionData - baselineFaultTree.arkui.MarshRSTransactionData)">
                    {{ getDiffText(compareFaultTree.arkui.MarshRSTransactionData - baselineFaultTree.arkui.MarshRSTransactionData) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- RS 渲染服务故障分析对比 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🖼️</i> RS 渲染服务故障分析 - 基线版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">处理节点数</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.RS.ProcessedNodes.count, 200)">
                  {{ formatNumber(baselineFaultTree.RS.ProcessedNodes.count) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">处理时间(s)</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.RS.ProcessedNodes.ts, 5)">
                  {{ baselineFaultTree.RS.ProcessedNodes.ts.toFixed(3) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">跳过次数</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.RS.DisplayNodeSkipTimes, 10)">
                  {{ formatNumber(baselineFaultTree.RS.DisplayNodeSkipTimes) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">反序列化次数</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.RS.UnMarshRSTransactionData, 60)">
                  {{ formatNumber(baselineFaultTree.RS.UnMarshRSTransactionData) }}
                </div>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🖼️</i> RS 渲染服务故障分析 - 对比版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">处理节点数</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.RS.ProcessedNodes.count, 200)">
                  {{ formatNumber(compareFaultTree.RS.ProcessedNodes.count) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.RS.ProcessedNodes.count - baselineFaultTree.RS.ProcessedNodes.count)">
                    {{ getDiffText(compareFaultTree.RS.ProcessedNodes.count - baselineFaultTree.RS.ProcessedNodes.count) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">处理时间(s)</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.RS.ProcessedNodes.ts, 5)">
                  {{ compareFaultTree.RS.ProcessedNodes.ts.toFixed(3) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.RS.ProcessedNodes.ts - baselineFaultTree.RS.ProcessedNodes.ts)">
                    {{ getDiffText(compareFaultTree.RS.ProcessedNodes.ts - baselineFaultTree.RS.ProcessedNodes.ts, true) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">跳过次数</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.RS.DisplayNodeSkipTimes, 10)">
                  {{ formatNumber(compareFaultTree.RS.DisplayNodeSkipTimes) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.RS.DisplayNodeSkipTimes - baselineFaultTree.RS.DisplayNodeSkipTimes)">
                    {{ getDiffText(compareFaultTree.RS.DisplayNodeSkipTimes - baselineFaultTree.RS.DisplayNodeSkipTimes) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">反序列化次数</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.RS.UnMarshRSTransactionData, 60)">
                  {{ formatNumber(compareFaultTree.RS.UnMarshRSTransactionData) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.RS.UnMarshRSTransactionData - baselineFaultTree.RS.UnMarshRSTransactionData)">
                    {{ getDiffText(compareFaultTree.RS.UnMarshRSTransactionData - baselineFaultTree.RS.UnMarshRSTransactionData) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 音视频编解码故障分析对比 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🎬</i> 音视频编解码故障分析 - 基线版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">软解码器</div>
                <div class="metric-value" :class="baselineFaultTree.av_codec.soft_decoder ? 'status-warning' : 'status-normal'">
                  {{ baselineFaultTree.av_codec.soft_decoder ? '是' : '否' }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">播控指令数</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.av_codec.BroadcastControlInstructions, 1000000)">
                  {{ formatNumber(baselineFaultTree.av_codec.BroadcastControlInstructions) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">视频解码输入帧</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.av_codec.VideoDecodingInputFrameCount, 10000)">
                  {{ formatNumber(baselineFaultTree.av_codec.VideoDecodingInputFrameCount) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">视频解码输出帧</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.av_codec.VideoDecodingConsumptionFrame, 10000)">
                  {{ formatNumber(baselineFaultTree.av_codec.VideoDecodingConsumptionFrame) }}
                </div>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🎬</i> 音视频编解码故障分析 - 对比版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">软解码器</div>
                <div class="metric-value" :class="compareFaultTree.av_codec.soft_decoder ? 'status-warning' : 'status-normal'">
                  {{ compareFaultTree.av_codec.soft_decoder ? '是' : '否' }}
                  <span
v-if="compareFaultTree.av_codec.soft_decoder !== baselineFaultTree.av_codec.soft_decoder"
                        class="diff-indicator" :class="compareFaultTree.av_codec.soft_decoder ? 'diff-worse' : 'diff-better'">
                    {{ compareFaultTree.av_codec.soft_decoder ? '变为软解' : '变为硬解' }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">播控指令数</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.av_codec.BroadcastControlInstructions, 1000000)">
                  {{ formatNumber(compareFaultTree.av_codec.BroadcastControlInstructions) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.av_codec.BroadcastControlInstructions - baselineFaultTree.av_codec.BroadcastControlInstructions)">
                    {{ getDiffText(compareFaultTree.av_codec.BroadcastControlInstructions - baselineFaultTree.av_codec.BroadcastControlInstructions) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">视频解码输入帧</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.av_codec.VideoDecodingInputFrameCount, 10000)">
                  {{ formatNumber(compareFaultTree.av_codec.VideoDecodingInputFrameCount) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.av_codec.VideoDecodingInputFrameCount - baselineFaultTree.av_codec.VideoDecodingInputFrameCount)">
                    {{ getDiffText(compareFaultTree.av_codec.VideoDecodingInputFrameCount - baselineFaultTree.av_codec.VideoDecodingInputFrameCount) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">视频解码输出帧</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.av_codec.VideoDecodingConsumptionFrame, 10000)">
                  {{ formatNumber(compareFaultTree.av_codec.VideoDecodingConsumptionFrame) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.av_codec.VideoDecodingConsumptionFrame - baselineFaultTree.av_codec.VideoDecodingConsumptionFrame)">
                    {{ getDiffText(compareFaultTree.av_codec.VideoDecodingConsumptionFrame - baselineFaultTree.av_codec.VideoDecodingConsumptionFrame) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 音频故障分析对比 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🔊</i> 音频故障分析 - 基线版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">音频写回调</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.Audio.AudioWriteCB, 5000000)">
                  {{ formatNumber(baselineFaultTree.Audio.AudioWriteCB) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频读回调</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.Audio.AudioReadCB, 1000000)">
                  {{ formatNumber(baselineFaultTree.Audio.AudioReadCB) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频播放回调</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.Audio.AudioPlayCb, 1000000)">
                  {{ formatNumber(baselineFaultTree.Audio.AudioPlayCb) }}
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频录制回调</div>
                <div class="metric-value" :class="getStatusClass(baselineFaultTree.Audio.AudioRecCb, 1000000)">
                  {{ formatNumber(baselineFaultTree.Audio.AudioRecCb) }}
                </div>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="stat-card data-panel">
            <div class="card-title">
              <i>🔊</i> 音频故障分析 - 对比版本
            </div>
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">音频写回调</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.Audio.AudioWriteCB, 5000000)">
                  {{ formatNumber(compareFaultTree.Audio.AudioWriteCB) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.Audio.AudioWriteCB - baselineFaultTree.Audio.AudioWriteCB)">
                    {{ getDiffText(compareFaultTree.Audio.AudioWriteCB - baselineFaultTree.Audio.AudioWriteCB) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频读回调</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.Audio.AudioReadCB, 1000000)">
                  {{ formatNumber(compareFaultTree.Audio.AudioReadCB) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.Audio.AudioReadCB - baselineFaultTree.Audio.AudioReadCB)">
                    {{ getDiffText(compareFaultTree.Audio.AudioReadCB - baselineFaultTree.Audio.AudioReadCB) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频播放回调</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.Audio.AudioPlayCb, 1000000)">
                  {{ formatNumber(compareFaultTree.Audio.AudioPlayCb) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.Audio.AudioPlayCb - baselineFaultTree.Audio.AudioPlayCb)">
                    {{ getDiffText(compareFaultTree.Audio.AudioPlayCb - baselineFaultTree.Audio.AudioPlayCb) }}
                  </span>
                </div>
              </div>
              <div class="metric-item">
                <div class="metric-label">音频录制回调</div>
                <div class="metric-value" :class="getStatusClass(compareFaultTree.Audio.AudioRecCb, 1000000)">
                  {{ formatNumber(compareFaultTree.Audio.AudioRecCb) }}
                  <span class="diff-indicator" :class="getDiffClass(compareFaultTree.Audio.AudioRecCb - baselineFaultTree.Audio.AudioRecCb)">
                    {{ getDiffText(compareFaultTree.Audio.AudioRecCb - baselineFaultTree.Audio.AudioRecCb) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import UploadHtml from '../UploadHtml.vue';
import { useJsonDataStore, getDefaultFaultTreeStepData } from '../../stores/jsonDataStore';

const props = defineProps<{
  step: number;
}>();

// 获取存储实例
const jsonDataStore = useJsonDataStore();

// 检查是否有对比数据
const hasCompareData = computed(() => {
  return jsonDataStore.comparePerfData && jsonDataStore.comparePerfData.steps.length > 0;
});



// 获取故障树数据
const baselineFaultTree = computed(() => {
  const stepKey = `step${props.step}`;
  if (jsonDataStore.faultTreeData && jsonDataStore.faultTreeData[stepKey]) {
    return jsonDataStore.faultTreeData[stepKey];
  }
  return getDefaultFaultTreeStepData();
});

const compareFaultTree = computed(() => {
  const stepKey = `step${props.step}`;
  if (jsonDataStore.compareFaultTreeData && jsonDataStore.compareFaultTreeData[stepKey]) {
    return jsonDataStore.compareFaultTreeData[stepKey];
  }
  return getDefaultFaultTreeStepData();
});

// 格式化数字
const formatNumber = (num: number) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};

// 获取状态样式类
const getStatusClass = (value: number, threshold: number) => {
  if (value > threshold) {
    return 'status-warning';
  }
  return 'status-normal';
};

// 获取差异样式类
const getDiffClass = (diff: number) => {
  if (diff > 0) {
    return 'diff-worse';
  } else if (diff < 0) {
    return 'diff-better';
  }
  return 'diff-same';
};

// 获取差异文本
const getDiffText = (diff: number, isDecimal = false) => {
  if (diff === 0) {
    return '无变化';
  }

  const sign = diff > 0 ? '+' : '';
  const value = isDecimal ? diff.toFixed(3) : formatNumber(Math.abs(diff));

  if (diff > 0) {
    return `${sign}${value}`;
  } else {
    return `-${value}`;
  }
};

</script>

<style scoped>
.performance-comparison {
  padding: 20px;
}

.info-box {
  background: #f0f9ff;
  border: 1px solid #0ea5e9;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  color: #0c4a6e;
}

.info-box p {
  margin: 8px 0 0 0;
  font-size: 14px;
}

.data-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.stat-card {
  margin-bottom: 20px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #333;
  border-bottom: 2px solid #f0f0f0;
  padding-bottom: 8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.metric-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  border: 1px solid #e9ecef;
}

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.status-normal {
  color: #28a745;
}

.status-warning {
  color: #ffc107;
}

.status-critical {
  color: #dc3545;
}

.diff-indicator {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.diff-better {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.diff-worse {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.diff-same {
  background-color: #e2e3e5;
  color: #383d41;
  border: 1px solid #d6d8db;
}

.beautified-descriptions {
  margin-bottom: 20px;
}

.beautified-descriptions :deep(.el-descriptions__title) {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.beautified-descriptions :deep(.el-descriptions__body) {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.beautified-descriptions :deep(.el-descriptions-item__label) {
  font-weight: 500;
  color: #666;
}

.beautified-descriptions :deep(.el-descriptions-item__content) {
  color: #333;
  font-weight: 600;
}
</style>
