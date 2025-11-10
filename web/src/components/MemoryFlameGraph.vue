<template>
  <div class="memory-flame-graph">
    <div v-if="props.title" class="memory-flame-graph__title">
      <span>{{ props.title }}</span>
    </div>
    <div v-if="props.loading" class="memory-flame-graph__loading">
      <el-icon class="loading-icon" :size="20">
        <Loading />
      </el-icon>
      <span>正在生成火焰图...</span>
    </div>
    <div v-else-if="!hasData" class="memory-flame-graph__empty">
      <el-empty description="暂无未释放的调用链数据" />
    </div>
    <div
      v-show="!props.loading && hasData"
      ref="chartContainer"
      class="memory-flame-graph__chart"
      :style="{ height: props.height }"
    />
  </div>
</template>

<script lang="ts" setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { select, type Selection } from 'd3-selection';
import type { HierarchyRectangularNode } from 'd3-hierarchy';
import {
  flamegraph,
  type FlameGraph,
  type FlamegraphDatum,
  type FlamegraphTooltip,
} from 'd3-flame-graph';
import { defaultFlamegraphTooltip } from 'd3-flame-graph/dist/d3-flamegraph-tooltip.js';
import 'd3-flame-graph/dist/d3-flamegraph.css';
import { Loading } from '@element-plus/icons-vue';

interface FlameGraphNode extends FlamegraphDatum {
  name: string;
  value: number;
  children?: FlameGraphNode[];
  tooltip?: string;
  callchainId?: number;
  depth?: number;
}

interface FlameGraphProps {
  data?: FlameGraphNode[];
  height?: string;
  title?: string;
  unitLabel?: string;
  loading?: boolean;
}

const props = withDefaults(defineProps<FlameGraphProps>(), {
  data: () => [],
  height: '260px',
  title: '调用链火焰图',
  unitLabel: '未释放内存',
  loading: false,
});

const chartContainer = ref<HTMLDivElement | null>(null);
type FlameGraphRoot = FlameGraphNode & {
  name: string;
  value: number;
  children: FlameGraphNode[];
};
type FlameGraphNodeRect = HierarchyRectangularNode<FlamegraphDatum>;
let flameGraphInstance: FlameGraph | null = null;
let tooltipInstance: FlamegraphTooltip | null = null;
let containerSelection: Selection<HTMLDivElement, FlameGraphRoot, null, undefined> | null = null;
let isMounted = false;

const hasData = computed(() => Array.isArray(props.data) && props.data.length > 0);

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const absValue = Math.abs(value);
  const index = Math.min(Math.floor(Math.log(absValue) / Math.log(1024)), units.length - 1);
  const formatted = (absValue / 1024 ** index).toFixed(index === 0 ? 0 : 2);
  return `${formatted} ${units[index]}`;
}

function cloneNodes(nodes: readonly FlameGraphNode[]): FlameGraphNode[] {
  return nodes.map(node => ({
    ...node,
    children: node.children ? cloneNodes(node.children) : undefined,
  }));
}

function resolveHeight(height: string | undefined): number {
  if (!height) {
    return 260;
  }
  const match = /\d+/.exec(height);
  if (!match) {
    return 260;
  }
  const parsed = Number.parseInt(match[0] ?? '0', 10);
  return Number.isNaN(parsed) ? 260 : parsed;
}

function buildTooltipHtml(node: FlameGraphNodeRect): string {
  const ancestors = node.ancestors().reverse();
  const pathItems = ancestors
    .slice(1)
    .map((item: FlameGraphNodeRect) => item.data.name)
    .filter((name): name is string => typeof name === 'string' && name.length > 0);
  const path = pathItems.join(' → ');
  const nodeValue = node.data.value ?? 0;
  const baseSections = [
    `<div class="tooltip-title">${path || '调用链'}</div>`,
    `<div class="tooltip-section"><span class="label">${props.unitLabel}：</span><span class="value">${formatBytes(nodeValue)}</span></div>`,
  ];
  if (node.data.tooltip) {
    baseSections.push(`<div class="tooltip-section">${node.data.tooltip}</div>`);
  }
  return ['<div class="flame-tooltip">', ...baseSections, '</div>'].join('');
}

function buildLabel(node: FlameGraphNodeRect): string {
  const name = node.data.name ?? '';
  const nodeValue = node.data.value ?? 0;
  return `${name}\n${formatBytes(nodeValue)}`;
}

function clearFlameGraph(): void {
  if (chartContainer.value) {
    select(chartContainer.value).selectAll('*').remove();
  }
}

function renderFlameGraph(): void {
  if (!isMounted || !chartContainer.value) {
    return;
  }

  if (!hasData.value || props.loading) {
    clearFlameGraph();
    return;
  }

  const height = resolveHeight(props.height);
  const width = chartContainer.value.clientWidth || chartContainer.value.getBoundingClientRect().width || chartContainer.value.offsetWidth;
  const rootData: FlameGraphRoot = {
    name: props.title ?? '调用链火焰图',
    value: (props.data ?? []).reduce((sum, node) => sum + (node.value ?? 0), 0),
    children: cloneNodes(props.data ?? []),
  };

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
      .cellHeight(18)
      .transitionDuration(200)
      .minFrameSize(1)
      .tooltip(tooltipInstance)
      .label(buildLabel)
      .sort((a, b) => {
        const aValue = a.data.value ?? 0;
        const bValue = b.data.value ?? 0;
        return bValue - aValue;
      });
  } else {
    flameGraphInstance.height(height).width(width);
  }

  if (!flameGraphInstance) {
    return;
  }

  containerSelection.datum(rootData).call(flameGraphInstance);
}

function handleResize(): void {
  if (!props.loading) {
    renderFlameGraph();
  }
}

watch(
  () => props.data,
  () => {
    if (!props.loading) {
      nextTick(() => renderFlameGraph());
    }
  },
  { deep: true },
);

watch(
  () => props.loading,
  () => {
    if (!props.loading) {
      nextTick(() => renderFlameGraph());
    } else {
      clearFlameGraph();
    }
  },
);

watch(
  () => props.height,
  () => {
    if (!props.loading) {
      nextTick(() => renderFlameGraph());
    }
  },
);

onMounted(() => {
  isMounted = true;
  if (!props.loading && hasData.value) {
    nextTick(() => renderFlameGraph());
  }
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  clearFlameGraph();
  flameGraphInstance = null;
  tooltipInstance = null;
  containerSelection = null;
  isMounted = false;
});
</script>

<style scoped>
.memory-flame-graph {
  position: relative;
  width: 100%;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  box-sizing: border-box;
}

.memory-flame-graph__title {
  text-align: center;
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}

.memory-flame-graph__chart {
  width: 100%;
}

.memory-flame-graph__loading,
.memory-flame-graph__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 140px;
  color: #909399;
}

.memory-flame-graph__loading {
  gap: 8px;
  font-size: 13px;
}

.loading-icon {
  animation: flame-rotate 1s linear infinite;
}

@keyframes flame-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.flame-tooltip {
  min-width: 200px;
}

.flame-tooltip .tooltip-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #303133;
}

.flame-tooltip .tooltip-section {
  margin-bottom: 4px;
  color: #606266;
  font-size: 12px;
}

.flame-tooltip .tooltip-section .label {
  font-weight: 600;
}

.flame-tooltip .tooltip-section .value {
  color: #409eff;
}
</style>


