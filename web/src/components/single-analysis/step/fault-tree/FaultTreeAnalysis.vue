<template>
  <div class="app-container">
    <div class="stats-cards">
      <!-- ArkUI 故障分析 -->
      <div class="stat-card data-panel">
        <div class="card-title">
          <i>🎨</i> ArkUI 故障分析
        </div>
        <div class="metric-grid">
          <div class="metric-item">
            <div class="metric-label">帧动画数量</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.arkui.animator, 50)">
              {{ formatNumber(faultTreeData.arkui.animator) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">区域变化监听</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.arkui.HandleOnAreaChangeEvent, 1000)">
              {{ formatNumber(faultTreeData.arkui.HandleOnAreaChangeEvent) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">可见区域变化</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.arkui.HandleVisibleAreaChangeEvent, 1000)">
              {{ formatNumber(faultTreeData.arkui.HandleVisibleAreaChangeEvent) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">屏幕宽高获取</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.arkui.GetDefaultDisplay, 100)">
              {{ formatNumber(faultTreeData.arkui.GetDefaultDisplay) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">事务数据序列化</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.arkui.MarshRSTransactionData, 3000)">
              {{ formatNumber(faultTreeData.arkui.MarshRSTransactionData) }}
            </div>
          </div>
        </div>
      </div>

      <!-- RS 渲染服务故障分析 -->
      <div class="stat-card data-panel">
        <div class="card-title">
          <i>🖼️</i> RS 渲染服务故障分析
        </div>
        <div class="metric-grid">
          <div class="metric-item">
            <div class="metric-label">处理节点数</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.ProcessedNodes.count, 200)">
              {{ formatNumber(faultTreeData.RS.ProcessedNodes.count) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">处理时间(s)</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.ProcessedNodes.ts, 5)">
              {{ faultTreeData.RS.ProcessedNodes.ts.toFixed(3) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">跳过次数</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.DisplayNodeSkipTimes, 10)">
              {{ formatNumber(faultTreeData.RS.DisplayNodeSkipTimes) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">反序列化数量</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.UnMarshRSTransactionData, 60)">
              {{ formatNumber(faultTreeData.RS.UnMarshRSTransactionData) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">动画节点总大小</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.AnimateSize.nodeSizeSum, 1000)">
              {{ formatNumber(faultTreeData.RS.AnimateSize.nodeSizeSum) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">动画总大小</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.RS.AnimateSize.totalAnimationSizeSum, 2000)">
              {{ formatNumber(faultTreeData.RS.AnimateSize.totalAnimationSizeSum) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 音视频编解码故障分析 -->
      <div class="stat-card data-panel">
        <div class="card-title">
          <i>🎬</i> 音视频编解码故障分析
        </div>
        <div class="metric-grid">
          <div class="metric-item">
            <div class="metric-label">软解码器</div>
            <div class="metric-value" :class="faultTreeData.av_codec.soft_decoder ? 'status-warning' : 'status-normal'">
              {{ faultTreeData.av_codec.soft_decoder ? '是' : '否' }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">播控指令数</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.av_codec.BroadcastControlInstructions, 1000000)">
              {{ formatNumber(faultTreeData.av_codec.BroadcastControlInstructions) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">视频解码输入帧</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.av_codec.VideoDecodingInputFrameCount, 300)">
              {{ formatNumber(faultTreeData.av_codec.VideoDecodingInputFrameCount) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">视频解码消费帧</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.av_codec.VideoDecodingConsumptionFrame, 250)">
              {{ formatNumber(faultTreeData.av_codec.VideoDecodingConsumptionFrame) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 音频故障分析 -->
      <div class="stat-card data-panel">
        <div class="card-title">
          <i>🔊</i> 音频故障分析
        </div>
        <div class="metric-grid">
          <div class="metric-item">
            <div class="metric-label">音频写回调</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.Audio.AudioWriteCB, 5000000)">
              {{ formatNumber(faultTreeData.Audio.AudioWriteCB) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">音频读回调</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.Audio.AudioReadCB, 1000000)">
              {{ formatNumber(faultTreeData.Audio.AudioReadCB) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">音频播放回调</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.Audio.AudioPlayCb, 1000000)">
              {{ formatNumber(faultTreeData.Audio.AudioPlayCb) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">音频录制回调</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.Audio.AudioRecCb, 1000000)">
              {{ formatNumber(faultTreeData.Audio.AudioRecCb) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- IPC Binder 进程间通信故障分析 (独立全宽卡片) -->
    <div v-if="faultTreeData.ipc_binder" class="ipc-binder-section">
      <div class="stat-card data-panel ipc-card">
        <div class="card-title">
          <i>🔗</i> IPC Binder 进程间通信故障分析
        </div>

        <div class="metric-grid-compact">
          <div class="metric-item">
            <div class="metric-label">总通信次数</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.ipc_binder.total_transactions, 10000)">
              {{ formatNumber(faultTreeData.ipc_binder.total_transactions) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">高延迟通信</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.ipc_binder.high_latency_count, 10)">
              {{ formatNumber(faultTreeData.ipc_binder.high_latency_count) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">平均延迟(ms)</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.ipc_binder.avg_latency, 50)">
              {{ faultTreeData.ipc_binder.avg_latency.toFixed(2) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">最大延迟(ms)</div>
            <div class="metric-value" :class="getStatusClass(faultTreeData.ipc_binder.max_latency, 100)">
              {{ faultTreeData.ipc_binder.max_latency.toFixed(2) }}
            </div>
          </div>
        </div>

        <!-- Top 进程对详情 -->
        <div v-if="faultTreeData.ipc_binder.top_processes.length > 0" class="detail-section">
          <div class="detail-title">
            <span>高频通信进程对 (Top 5)</span>
            <span class="detail-subtitle">展示通信次数最多的进程对及其性能指标</span>
          </div>
          <div class="process-grid">
            <div v-for="(proc, idx) in faultTreeData.ipc_binder.top_processes" :key="idx" class="process-card">
              <div class="process-rank">#{{ idx + 1 }}</div>
              <div class="process-content">
                <div class="process-info">
                  <span class="process-name">{{ proc.caller_proc }}</span>
                  <span class="arrow">→</span>
                  <span class="process-name">{{ proc.callee_proc }}</span>
                </div>
                <div class="process-metrics">
                  <span class="metric-badge count">
                    <span class="badge-label">通信次数</span>
                    <span class="badge-value">{{ formatNumber(proc.count) }}</span>
                  </span>
                  <span class="metric-badge avg">
                    <span class="badge-label">平均延迟</span>
                    <span class="badge-value">{{ proc.avg_latency }}ms</span>
                  </span>
                  <span class="metric-badge max" :class="{ critical: proc.max_latency > 100 }">
                    <span class="badge-label">峰值延迟</span>
                    <span class="badge-value">{{ proc.max_latency }}ms</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 故障树诊断建议 -->
    <div class="diagnosis-section">
      <div class="section-title">
        <i>🔍</i> 故障诊断建议
      </div>
      <div class="diagnosis-cards">
        <div
v-for="suggestion in getDiagnosisSuggestions()" :key="suggestion.category" 
             class="diagnosis-card" :class="suggestion.severity">
          <div class="diagnosis-header">
            <span class="diagnosis-icon">{{ suggestion.icon }}</span>
            <span class="diagnosis-title">{{ suggestion.title }}</span>
            <span class="diagnosis-level">{{ suggestion.level }}</span>
          </div>
          <div class="diagnosis-content">
            <p class="diagnosis-description">{{ suggestion.description }}</p>
            <ul class="diagnosis-suggestions">
              <li v-for="item in suggestion.suggestions" :key="item">{{ item }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useJsonDataStore, getDefaultFaultTreeStepData } from '../../../../stores/jsonDataStore.ts';

const props = defineProps({
  step: {
    type: Number,
    required: true
  }
});

const jsonDataStore = useJsonDataStore();

// 获取当前步骤的故障树数据
const faultTreeData = computed(() => {
  const stepKey = `step${props.step}`;
  if (jsonDataStore.faultTreeData && jsonDataStore.faultTreeData[stepKey]) {
    return jsonDataStore.faultTreeData[stepKey];
  }
  return getDefaultFaultTreeStepData();
});

// 格式化数字显示
const formatNumber = (num) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};

// 根据数值和阈值返回状态样式类
const getStatusClass = (value, threshold) => {
  if (value > threshold * 2) {
    return 'status-critical';
  } else if (value > threshold) {
    return 'status-warning';
  }
  return 'status-normal';
};

// 生成诊断建议
const getDiagnosisSuggestions = () => {
  const suggestions = [];
  const data = faultTreeData.value;

  // ArkUI 相关诊断
  if (data.arkui.animator > 50) {
    suggestions.push({
      category: 'arkui_animator',
      icon: '⚠️',
      title: 'ArkUI 帧动画过多',
      level: '高风险',
      severity: 'critical',
      description: `检测到帧动画数量过多 (${formatNumber(data.arkui.animator)})，可能导致性能问题。`,
      suggestions: [
        '减少不必要的动画效果',
        '优化动画实现，使用硬件加速',
        '考虑使用更轻量级的动画方案'
      ]
    });
  }

  // ArkUI 事务数据序列化诊断
  if (data.arkui.MarshRSTransactionData > 3000) {
    suggestions.push({
      category: 'arkui_marsh',
      icon: '📦',
      title: 'ArkUI 事务数据序列化频繁',
      level: '中风险',
      severity: 'warning',
      description: `事务数据序列化次数过多 (${formatNumber(data.arkui.MarshRSTransactionData)})，可能影响UI响应性能。`,
      suggestions: [
        '减少UI状态变更频率',
        '优化数据绑定逻辑',
        '考虑批量处理UI更新'
      ]
    });
  }

  // RS 渲染服务诊断
  if (data.RS.ProcessedNodes.count > 200) {
    suggestions.push({
      category: 'rs_nodes',
      icon: '🖼️',
      title: 'RS 处理节点过多',
      level: '中风险',
      severity: 'warning',
      description: `RS 处理节点数量较多 (${data.RS.ProcessedNodes.count})，可能影响渲染性能。`,
      suggestions: [
        '优化UI层级结构，减少不必要的节点',
        '使用组件复用减少节点创建',
        '检查是否存在内存泄漏导致节点未释放'
      ]
    });
  }

  // RS 反序列化诊断
  if (data.RS.UnMarshRSTransactionData > 60) {
    suggestions.push({
      category: 'rs_unmarsh',
      icon: '📤',
      title: 'RS 反序列化频繁',
      level: '高风险',
      severity: 'critical',
      description: `RS 反序列化次数过多 (${formatNumber(data.RS.UnMarshRSTransactionData)})，可能严重影响渲染性能。`,
      suggestions: [
        '减少渲染状态变更频率',
        '优化渲染数据传输机制',
        '考虑使用渲染缓存策略',
        '检查是否存在不必要的重复渲染'
      ]
    });
  }

  // 音视频诊断
  if (data.av_codec.soft_decoder) {
    suggestions.push({
      category: 'codec',
      icon: '🎬',
      title: '使用软解码器',
      level: '中风险',
      severity: 'warning',
      description: '当前使用软解码器，可能消耗更多CPU资源。',
      suggestions: [
        '检查硬件解码器支持情况',
        '优化视频编码格式',
        '考虑降低视频分辨率或码率'
      ]
    });
  }

  // 音频诊断
  if (data.Audio.AudioWriteCB > 5000000) {
    suggestions.push({
      category: 'audio',
      icon: '🔊',
      title: '音频写回调频繁',
      level: '中风险',
      severity: 'warning',
      description: `音频写回调次数过多 (${formatNumber(data.Audio.AudioWriteCB)})，可能影响音频性能。`,
      suggestions: [
        '检查音频缓冲区配置',
        '优化音频处理逻辑',
        '考虑调整音频采样率'
      ]
    });
  }

  // IPC Binder 诊断
  if (data.ipc_binder) {
    // 高延迟通信诊断
    if (data.ipc_binder.high_latency_count > 10) {
      suggestions.push({
        category: 'ipc_high_latency',
        icon: '⚠️',
        title: 'IPC Binder 高延迟通信',
        level: '高风险',
        severity: 'critical',
        description: `检测到 ${data.ipc_binder.high_latency_count} 次高延迟(>100ms)的进程间通信，可能严重影响性能。`,
        suggestions: [
          '检查高延迟通信的进程对，优化跨进程调用逻辑',
          '考虑使用异步通信替代同步 Binder 调用',
          '减少跨进程数据传输量，使用共享内存等机制',
          '检查是否存在死锁或资源竞争问题'
        ]
      });
    }

    // 通信频率过高诊断
    if (data.ipc_binder.total_transactions > 10000) {
      suggestions.push({
        category: 'ipc_high_frequency',
        icon: '📡',
        title: 'IPC Binder 通信频率过高',
        level: '中风险',
        severity: 'warning',
        description: `检测到 ${formatNumber(data.ipc_binder.total_transactions)} 次进程间通信，频率过高可能影响性能。`,
        suggestions: [
          '批量处理 IPC 请求，减少通信次数',
          '使用缓存机制避免重复的跨进程查询',
          '检查是否存在不必要的进程间调用',
          '考虑将频繁通信的模块合并到同一进程'
        ]
      });
    }

    // 平均延迟过高诊断
    if (data.ipc_binder.avg_latency > 50) {
      suggestions.push({
        category: 'ipc_avg_latency',
        icon: '🐌',
        title: 'IPC Binder 平均延迟过高',
        level: '中风险',
        severity: 'warning',
        description: `IPC 平均延迟为 ${data.ipc_binder.avg_latency.toFixed(2)}ms，超过正常水平。`,
        suggestions: [
          '优化 Binder 接口实现，减少处理时间',
          '检查被调用进程的负载情况',
          '避免在 Binder 调用中执行耗时操作',
          '使用性能分析工具定位具体的慢接口'
        ]
      });
    }
  }

  // 如果没有发现问题，添加正常状态
  if (suggestions.length === 0) {
    suggestions.push({
      category: 'normal',
      icon: '✅',
      title: '系统运行正常',
      level: '正常',
      severity: 'normal',
      description: '未检测到明显的性能问题，系统运行状态良好。',
      suggestions: [
        '继续保持当前的优化水平',
        '定期监控性能指标',
        '关注用户反馈和体验'
      ]
    });
  }

  return suggestions;
};
</script>

<style scoped>
.app-container {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  padding: 8px 12px;
  border-radius: 6px;
}

.status-normal {
  color: #059669;
  background: #d1fae5;
}

.status-warning {
  color: #d97706;
  background: #fef3c7;
}

.status-critical {
  color: #dc2626;
  background: #fee2e2;
}

/* IPC Binder 独立区域样式 */
.ipc-binder-section {
  margin-bottom: 24px;
}

.ipc-card {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 2px solid #e2e8f0;
}

.metric-grid-compact {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

/* 详情区域样式 */
.detail-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 2px dashed #e2e8f0;
}

.detail-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-subtitle {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
  margin-left: auto;
}

/* 进程网格布局 */
.process-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
  gap: 12px;
}

.process-card {
  display: flex;
  gap: 12px;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  padding: 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.process-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.process-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  font-size: 13px;
  font-weight: 700;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.process-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.process-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.process-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  background: white;
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid #cbd5e1;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.arrow {
  color: #64748b;
  font-weight: bold;
  font-size: 14px;
}

.process-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.metric-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  padding: 6px 10px;
  border-radius: 5px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.metric-badge.count {
  background: #dbeafe;
  color: #1e40af;
  border: 1px solid #93c5fd;
}

.metric-badge.avg {
  background: #e0e7ff;
  color: #4338ca;
  border: 1px solid #a5b4fc;
}

.metric-badge.max {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fcd34d;
}

.metric-badge.max.critical {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
  animation: pulse 2s ease-in-out infinite;
}

.badge-label {
  font-size: 10px;
  opacity: 0.8;
}

.badge-value {
  font-size: 13px;
  font-weight: 700;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

/* 诊断建议区域样式 */
.diagnosis-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diagnosis-cards {
  display: grid;
  gap: 16px;
}

.diagnosis-card {
  border-radius: 8px;
  padding: 16px;
  border-left: 4px solid;
}

.diagnosis-card.normal {
  background: #f0fdf4;
  border-left-color: #22c55e;
}

.diagnosis-card.warning {
  background: #fffbeb;
  border-left-color: #f59e0b;
}

.diagnosis-card.critical {
  background: #fef2f2;
  border-left-color: #ef4444;
}

.diagnosis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.diagnosis-title {
  font-weight: 600;
  flex: 1;
}

.diagnosis-level {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.1);
}

.diagnosis-description {
  margin-bottom: 12px;
  color: #4b5563;
}

.diagnosis-suggestions {
  margin: 0;
  padding-left: 20px;
}

.diagnosis-suggestions li {
  margin-bottom: 4px;
  color: #6b7280;
}
</style>
