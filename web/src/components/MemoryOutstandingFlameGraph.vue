<template>
  <div class="memory-outstanding-flame-graph">
    <div class="memory-outstanding-flame-graph__panel">
      <div class="memory-outstanding-flame-graph__panel-header">
        <span class="memory-outstanding-flame-graph__panel-title">
          未释放调用链火焰图
        </span>
      </div>
      <div
        v-if="!shouldQuery"
        class="memory-outstanding-flame-graph__placeholder"
      >
        <el-empty description="请选择时间点以查看未释放调用链火焰图" />
      </div>
      <div v-else class="memory-outstanding-flame-graph__content">
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
          class="memory-outstanding-flame-graph__alert"
        />
        <el-alert
          v-else-if="infoMessage && !isLoading"
          :title="infoMessage"
          type="info"
          :closable="false"
          show-icon
          class="memory-outstanding-flame-graph__alert"
        />
        <MemoryFlameGraph
          :data="flameGraphData"
          :loading="isLoading"
          title=""
          unit-label="未释放内存"
          :height="flameGraphHeight"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import MemoryFlameGraph from '@/components/MemoryFlameGraph.vue';
import {
  EventType,
  fetchCallchainFrames,
  fetchRecordsUpToTime,
} from '@/stores/nativeMemory';
import type {
  CallchainFrame,
  CallchainFrameMap,
  NativeMemoryRecord,
} from '@/stores/nativeMemory';

type DrillDownLevel = 'overview' | 'category' | 'subCategory' | 'process' | 'thread' | 'file';
type ViewMode = 'category' | 'process';

interface FlameGraphNode {
  name: string;
  value: number;
  children?: FlameGraphNode[];
  tooltip?: string;
}

interface OutstandingFlameGraphProps {
  stepId: number;
  selectedTimePoint: number | null;
  drillLevel: DrillDownLevel;
  viewMode?: ViewMode;
  selectedCategory: string;
  selectedSubCategory: string;
  selectedProcess?: string;
  selectedThread?: string;
  selectedFile: string;
  maxCallchains?: number;
}

const props = withDefaults(defineProps<OutstandingFlameGraphProps>(), {
  maxCallchains: 200,
  viewMode: 'category',
  selectedProcess: '',
  selectedThread: '',
  selectedFile: '',
});

const flameGraphData = ref<FlameGraphNode[]>([]);
const isLoading = ref(false);
const errorMessage = ref<string | null>(null);
const infoMessage = ref<string | null>(null);

const shouldQuery = computed(
  () =>
    props.drillLevel !== 'overview' && props.selectedTimePoint !== null,
);

let requestToken = 0;

const MIN_FLAME_GRAPH_HEIGHT = 280;
const LEVEL_HEIGHT = 28;
const EXTRA_HEIGHT = 40;

function computeMaxDepth(nodes: readonly FlameGraphNode[], depth = 1): number {
  if (!nodes || nodes.length === 0) {
    return depth;
  }
  return nodes.reduce((maxDepth, node) => {
    const childDepth = node.children
      ? computeMaxDepth(node.children, depth + 1)
      : depth;
    return Math.max(maxDepth, childDepth);
  }, depth);
}

const flameGraphHeight = computed(() => {
  if (!flameGraphData.value.length) {
    return `${MIN_FLAME_GRAPH_HEIGHT}px`;
  }
  const depth = computeMaxDepth(flameGraphData.value);
  const dynamicHeight = depth * LEVEL_HEIGHT + EXTRA_HEIGHT;
  return `${Math.max(MIN_FLAME_GRAPH_HEIGHT, dynamicHeight)}px`;
});

watch(
  [
    () => props.stepId,
    () => props.selectedTimePoint,
    () => props.drillLevel,
    () => props.viewMode,
    () => props.selectedCategory,
    () => props.selectedSubCategory,
    () => props.selectedProcess,
    () => props.selectedThread,
    () => props.selectedFile,
    () => props.maxCallchains,
  ],
  () => {
    refreshData();
  },
  { immediate: true },
);

interface OutstandingEntry {
  callchainId: number;
  value: number;
  allocCount: number;
  freeCount: number;
  tooltip?: string;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const absBytes = Math.abs(bytes);
  const unitIndex = Math.min(
    Math.floor(Math.log(absBytes) / Math.log(1024)),
    units.length - 1,
  );
  const formatted = (absBytes / 1024 ** unitIndex).toFixed(
    unitIndex === 0 ? 0 : 2,
  );
  return `${formatted} ${units[unitIndex]}`;
}

function normalizeFileName(fileName?: string | null): string | null {
  if (!fileName || fileName === 'N/A') {
    return null;
  }
  return fileName;
}

function getFrameLabel(frame: CallchainFrame, index: number): string {
  if (frame.symbol) {
    return frame.symbol;
  }
  if (frame.file) {
    return frame.file;
  }
  if (frame.ip) {
    return `0x${frame.ip.toString(16)}`;
  }
  return `Frame #${index}`;
}

function buildLeafTooltip(
  callchainId: number,
  entry: OutstandingEntry,
  frames: CallchainFrame[] | undefined,
): string {
  const parts = [
    `<div>Callchain ID：${callchainId}</div>`,
    `<div>未释放内存：${formatBytes(entry.value)}</div>`,
    `<div>分配次数：${entry.allocCount}</div>`,
    `<div>释放次数：${entry.freeCount}</div>`,
  ];

  const topFrame = frames?.[frames.length - 1];
  if (topFrame?.file) {
    parts.push(`<div>文件：${topFrame.file}</div>`);
  }
  if (topFrame?.symbol) {
    parts.push(`<div>符号：${topFrame.symbol}</div>`);
  }

  return parts.join('');
}

interface TreeAccumulator {
  name: string;
  value: number;
  tooltip?: string;
  children: Map<string, TreeAccumulator>;
}

function createTreeNode(name: string): TreeAccumulator {
  return {
    name,
    value: 0,
    tooltip: undefined,
    children: new Map<string, TreeAccumulator>(),
  };
}

function insertCallchainIntoTree(
  root: Map<string, TreeAccumulator>,
  frames: CallchainFrame[] | undefined,
  entry: OutstandingEntry,
): void {
  const pathFrames = frames && frames.length > 0 ? frames : undefined;
  const labels =
    pathFrames?.map((frame, index) => getFrameLabel(frame, index)) ??
    ['未知调用链'];

  let currentLevel = root;

  labels.forEach((label, idx) => {
    let node = currentLevel.get(label);
    if (!node) {
      node = createTreeNode(label);
      currentLevel.set(label, node);
    }
    node.value += entry.value;
    if (idx === labels.length - 1) {
      node.tooltip = entry.tooltip;
    }
    currentLevel = node.children;
  });
}

function transformTreeToFlameNodes(
  nodes: Map<string, TreeAccumulator>,
): FlameGraphNode[] {
  const flameNodes: FlameGraphNode[] = [];

  nodes.forEach(node => {
    const children = transformTreeToFlameNodes(node.children);
    const flameNode: FlameGraphNode = {
      name: node.name,
      value: node.value,
    };
    if (children.length > 0) {
      flameNode.children = children.sort((a, b) => b.value - a.value);
    }
    if (node.tooltip) {
      flameNode.tooltip = node.tooltip;
    }
    flameNodes.push(flameNode);
  });

  flameNodes.sort((a, b) => b.value - a.value);
  return flameNodes;
}

function calculateOutstanding(
  records: NativeMemoryRecord[],
): OutstandingEntry[] {
  const outstandingMap = new Map<number, OutstandingEntry>();

  records.forEach(record => {
    const callchainId = Number(record.callchainId ?? 0);
    if (!outstandingMap.has(callchainId)) {
      outstandingMap.set(callchainId, {
        callchainId,
        value: 0,
        allocCount: 0,
        freeCount: 0,
      });
    }

    const entry = outstandingMap.get(callchainId)!;
    const size = record.heapSize || 0;

    if (
      record.eventType === EventType.AllocEvent ||
      record.eventType === EventType.MmapEvent
    ) {
      entry.value += size;
      entry.allocCount += 1;
    } else if (
      record.eventType === EventType.FreeEvent ||
      record.eventType === EventType.MunmapEvent
    ) {
      entry.value -= size;
      entry.freeCount += 1;
      if (entry.value < 0) {
        entry.value = 0;
      }
    }
  });

  const filtered = Array.from(outstandingMap.values())
    .filter(entry => entry.value > 0)
    .sort((a, b) => b.value - a.value);

  return filtered.slice(0, props.maxCallchains);
}

function buildFlameGraphData(
  outstandingEntries: OutstandingEntry[],
  callchainFrames: CallchainFrameMap,
): FlameGraphNode[] {
  const root = new Map<string, TreeAccumulator>();

  outstandingEntries.forEach(entry => {
    const frames = entry.callchainId
      ? callchainFrames[entry.callchainId]
      : undefined;
    entry.tooltip = buildLeafTooltip(entry.callchainId, entry, frames);
    insertCallchainIntoTree(root, frames, entry);
  });

  return transformTreeToFlameNodes(root);
}

async function refreshData(): Promise<void> {
  flameGraphData.value = [];
  infoMessage.value = null;
  errorMessage.value = null;

  if (!shouldQuery.value) {
    isLoading.value = false;
    return;
  }

  const token = ++requestToken;
  isLoading.value = true;

  try {
    let category: string | undefined;
    let subCategory: string | undefined;

    if (props.viewMode === 'category') {
      category =
        props.drillLevel === 'category' ||
        props.drillLevel === 'subCategory' ||
        props.drillLevel === 'file'
          ? props.selectedCategory
          : undefined;
      subCategory =
        props.drillLevel === 'subCategory' || props.drillLevel === 'file'
          ? props.selectedSubCategory
          : undefined;
    }

    let records = await fetchRecordsUpToTime(
      props.stepId,
      props.selectedTimePoint!,
      category,
      subCategory,
    );
    if (token !== requestToken) {
      return;
    }

    let filteredRecords = records;

    if (props.viewMode === 'category') {
      if (props.drillLevel === 'file' && props.selectedFile) {
        const targetFile = props.selectedFile;
        filteredRecords = records.filter(
          record => normalizeFileName(record.file) === targetFile,
        );
      }
    } else {
      if (props.drillLevel === 'process' && props.selectedProcess) {
        filteredRecords = records.filter(
          record => record.process === props.selectedProcess,
        );
      } else if (
        props.drillLevel === 'thread' &&
        props.selectedProcess &&
        props.selectedThread
      ) {
        filteredRecords = records.filter(
          record =>
            record.process === props.selectedProcess &&
            record.thread === props.selectedThread,
        );
      } else if (
        props.drillLevel === 'file' &&
        props.selectedProcess &&
        props.selectedThread &&
        props.selectedFile
      ) {
        filteredRecords = records.filter(
          record =>
            record.process === props.selectedProcess &&
            record.thread === props.selectedThread &&
            normalizeFileName(record.file) === props.selectedFile,
        );
      }
    }

    const outstandingEntries = calculateOutstanding(filteredRecords);
    if (outstandingEntries.length === 0) {
      infoMessage.value = '选中时间点前没有未释放的调用链。';
      return;
    }

    const targetCallchainIds = outstandingEntries
      .map(entry => entry.callchainId)
      .filter(id => id > 0);

    const frames =
      targetCallchainIds.length > 0
        ? await fetchCallchainFrames(props.stepId, targetCallchainIds)
        : ({} as CallchainFrameMap);

    if (token !== requestToken) {
      return;
    }

    flameGraphData.value = buildFlameGraphData(outstandingEntries, frames);
  } catch (error) {
    console.error('[MemoryOutstandingFlameGraph] 加载火焰图失败:', error);
    errorMessage.value = '加载火焰图失败，请稍后重试。';
  } finally {
    if (token === requestToken) {
      isLoading.value = false;
    }
  }
}
</script>

<style scoped>
.memory-outstanding-flame-graph {
  margin-top: 16px;
}

.memory-outstanding-flame-graph__panel {
  background: #ffffff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.memory-outstanding-flame-graph__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.memory-outstanding-flame-graph__panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.memory-outstanding-flame-graph__placeholder {
  padding: 24px 0;
  text-align: center;
}

.memory-outstanding-flame-graph__content {
  position: relative;
}

.memory-outstanding-flame-graph__alert {
  margin-bottom: 12px;
}
</style>


