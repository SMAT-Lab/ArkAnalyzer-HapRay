<template>
  <div class="empty-frame-flame-graph">
    <div v-if="!hasData" class="empty-frame-flame-graph__empty">
      <el-empty description="暂无调用栈数据" />
    </div>
    <div v-show="hasData" ref="chartContainer" class="empty-frame-flame-graph__chart" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { select } from 'd3-selection';
import { flamegraph } from 'd3-flame-graph';
import { defaultFlamegraphTooltip } from 'd3-flame-graph/dist/d3-flamegraph-tooltip.js';
import 'd3-flame-graph/dist/d3-flamegraph.css';

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  threadName: {
    type: String,
    default: ''
  },
  processName: {
    type: String,
    default: ''
  },
  threadId: {
    type: Number,
    default: 0
  }
});

const chartContainer = ref(null);
let containerSelection = null;
let flameGraphInstance = null;
let tooltipInstance = null;
let isMounted = false;

const hasData = computed(() => props.data && props.data.length > 0);

// 计算最大深度
function getMaxDepth(sampleCallchains) {
  let maxDepth = 0;
  sampleCallchains.forEach(sample => {
    const depth = (sample.callchain || []).length;
    if (depth > maxDepth) maxDepth = depth;
  });
  return maxDepth;
}

// 获取帧标签，参考 native memory 的逻辑
function getFrameLabel(call, index) {
  if (call.symbol) {
    return call.symbol;
  }
  if (call.path) {
    return call.path;
  }
  return `Frame #${index}`;
}

function buildFlameGraphData(sampleCallchains) {
  const root = new Map();

  console.log('=== buildFlameGraphData 开始 ===');
  console.log('sampleCallchains数量:', sampleCallchains.length);

  sampleCallchains.forEach((sample, idx) => {
    const callchain = sample.callchain || [];
    const sampleValue = sample.event_count || 0;

    // 获取线程信息，优先使用sample中的，否则使用props中的
    let threadId = sample.thread_id;
    let threadName = sample.thread_name;

    if (idx === 0) {
      console.log('第一个sample:');
      console.log('  sample.thread_id:', threadId);
      console.log('  sample.thread_name:', threadName);
      console.log('  props.threadId:', props.threadId);
      console.log('  props.threadName:', props.threadName);
    }

    // Fallback: 如果sample没有thread_id，使用props中的信息
    if (!threadId || threadId === 'unknown') {
      threadId = props.threadId || 'unknown';
      threadName = props.threadName || '';
    }

    // 如果还是没有threadName，使用props中的
    if (!threadName) {
      threadName = props.threadName || '';
    }

    // 第一层：线程分组（强制显示）
    const threadKey = `Thread-${threadId}`;
    let threadNode = root.get(threadKey);
    if (!threadNode) {
      threadNode = {
        name: threadName ? `${threadName} (TID:${threadId})` : `线程 ${threadId}`,
        value: 0,
        threadId: threadId,
        threadName: threadName,
        isThread: true,
        mergeCount: 0,
        children: new Map()
      };
      root.set(threadKey, threadNode);
      console.log('创建线程节点:', threadNode.name);
    }
    threadNode.value += sampleValue;
    threadNode.mergeCount += 1;

    // 第二层开始：符号调用栈
    let currentLevel = threadNode.children;
    callchain.forEach((call, idx) => {
      const label = getFrameLabel(call, idx);
      const key = `${label}_${call.depth || idx}`;

      let node = currentLevel.get(key);
      if (!node) {
        node = {
          name: label,
          value: 0,
          file: call.path || '',
          symbol: call.symbol || '',
          mergeCount: 0,
          children: new Map()
        };
        currentLevel.set(key, node);
      }
      node.value += sampleValue;
      node.mergeCount += 1;
      currentLevel = node.children;
    });
  });

  function transformToArray(nodeMap) {
    const result = [];
    nodeMap.forEach(node => {
      const flameNode = {
        name: node.name,
        value: node.value,
        file: node.file || '',
        symbol: node.symbol || '',
        threadId: node.threadId,
        threadName: node.threadName,
        isThread: node.isThread,
        mergeCount: node.mergeCount
      };
      if (node.children.size > 0) {
        flameNode.children = transformToArray(node.children);
      }
      result.push(flameNode);
    });
    return result.sort((a, b) => b.value - a.value);
  }

  const result = transformToArray(root);
  console.log('=== buildFlameGraphData 结束 ===');
  console.log('返回节点数量:', result.length);
  if (result.length > 0) {
    console.log('第一个节点:', result[0].name, 'isThread:', result[0].isThread, 'children:', result[0].children?.length);
    if (result[0].children && result[0].children.length > 0) {
      console.log('第一个child:', result[0].children[0].name, 'children:', result[0].children[0].children?.length);
      if (result[0].children[0].children && result[0].children[0].children.length > 0) {
        console.log('第二层child:', result[0].children[0].children[0].name);
      }
    }
  }
  return result;
}

function buildTooltipHtml(node) {
  const name = node.data.name || '未知';
  const file = node.data.file || '';
  const value = node.data.value || 0;
  const mergeCount = node.data.mergeCount || 0;
  const threadId = node.data.threadId;
  const threadName = node.data.threadName;
  const isThread = node.data.isThread;

  return `
    <div style="background: rgba(30, 41, 59, 0.95); padding: 14px; border-radius: 6px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
      <div style="font-size: 15px; font-weight: 700; color: #ffffff; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3);">
        ${name}
      </div>
      ${isThread ? `
        <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
          <span style="color: #e2e8f0; font-weight: 600;">类型：</span>
          <span style="color: #ffffff; font-weight: 700;">线程</span>
        </div>
        ${threadName ? `
          <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
            <span style="color: #e2e8f0; font-weight: 600;">线程名：</span>
            <span style="color: #ffffff; font-weight: 700;">${threadName}</span>
          </div>
        ` : ''}
        <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
          <span style="color: #e2e8f0; font-weight: 600;">线程ID：</span>
          <span style="color: #ffffff; font-weight: 700;">${threadId}</span>
        </div>
      ` : `
        <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
          <span style="color: #e2e8f0; font-weight: 600;">类型：</span>
          <span style="color: #ffffff; font-weight: 700;">符号</span>
        </div>
        ${file ? `
          <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
            <span style="color: #e2e8f0; font-weight: 600;">文件：</span>
            <span style="color: #ffffff; font-weight: 700; max-width: 360px; white-space: normal; word-break: break-all;">${file}</span>
          </div>
        ` : ''}
      `}
      <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
        <span style="color: #e2e8f0; font-weight: 600;">负载：</span>
        <span style="color: #ffffff; font-weight: 700;">${value.toLocaleString()}</span>
      </div>
      <div style="font-size: 13px; margin: 6px 0; display: flex; justify-content: space-between; gap: 16px;">
        <span style="color: #e2e8f0; font-weight: 600;">合并次数：</span>
        <span style="color: #ffffff; font-weight: 700;">${mergeCount}</span>
      </div>
      ${props.processName ? `
        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.2);">
          <div style="font-size: 12px; margin: 4px 0; display: flex; justify-content: space-between; gap: 16px;">
            <span style="color: #94a3b8; font-weight: 500;">进程：</span>
            <span style="color: #e2e8f0; font-weight: 600;">${props.processName}</span>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

function buildLabel(node) {
  const name = node.data.name || '';
  const value = node.data.value || 0;
  return `${name}\n${value}`;
}

function renderFlameGraph() {
  if (!isMounted || !chartContainer.value || !hasData.value) return;

  const flameData = buildFlameGraphData(props.data);

  // 调试：打印数据结构
  console.log('FlameData length:', flameData.length);
  if (flameData.length > 0) {
    console.log('First node:', flameData[0].name, 'isThread:', flameData[0].isThread);
    console.log('First node children count:', flameData[0].children?.length || 0);
  }

  const width = chartContainer.value.clientWidth || 800;
  // 根据最大深度动态计算高度
  const maxDepth = getMaxDepth(props.data);
  const cellHeight = 18;
  const minHeight = 400;
  const height = Math.max(minHeight, maxDepth * cellHeight + 50);
  
  if (!containerSelection) {
    containerSelection = select(chartContainer.value);
  }
  
  if (!tooltipInstance) {
    tooltipInstance = defaultFlamegraphTooltip().html(buildTooltipHtml);
  }
  
  if (!flameGraphInstance) {
    flameGraphInstance = flamegraph()
      .height(height)
      .width(width)
      .cellHeight(cellHeight)
      .transitionDuration(200)
      .minFrameSize(1)
      .tooltip(tooltipInstance)
      .label(buildLabel)
      .sort((a, b) => (b.value || 0) - (a.value || 0));
  } else {
    flameGraphInstance.height(height).width(width);
  }

  // 更新容器高度
  if (chartContainer.value) {
    chartContainer.value.style.height = `${height}px`;
  }

  // 始终创建虚拟根节点，让线程节点显示在底部
  // d3-flame-graph会隐藏根节点，只显示children
  const rootData = {
    name: 'all',
    value: flameData.reduce((sum, node) => sum + (node.value || 0), 0),
    children: flameData
  };

  console.log('传给d3-flame-graph的根节点:', rootData.name, 'children:', rootData.children.length);
  containerSelection.datum(rootData).call(flameGraphInstance);
}

watch(() => props.data, () => {
  nextTick(() => renderFlameGraph());
}, { deep: true });

onMounted(() => {
  isMounted = true;
  nextTick(() => renderFlameGraph());
});

onUnmounted(() => {
  isMounted = false;
  if (chartContainer.value) {
    select(chartContainer.value).selectAll('*').remove();
  }
});
</script>

<style scoped>
.empty-frame-flame-graph {
  width: 100%;
  min-height: 400px;
}

.empty-frame-flame-graph__chart {
  width: 100%;
  min-height: 400px;
}

.empty-frame-flame-graph__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}
</style>

<style>
/* 覆盖 d3-flame-graph 的默认 tooltip 样式 */
:deep(.d3-flame-graph-tip) {
  background: rgba(30, 41, 59, 0.95) !important;
  border: none !important;
  border-radius: 6px !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4) !important;
  padding: 0 !important;
  pointer-events: none !important;
  overflow: hidden !important;
}
</style>

