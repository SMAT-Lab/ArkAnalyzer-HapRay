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
  fetchRecordsUpToTimeByCategory,
  fetchRecordsUpToTimeByProcess,
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
  file?: string;
  symbol?: string;
  mergeCount?: number;
  allocCount?: number;
  freeCount?: number;
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
  selectedFile?: string;
  // 选中的系列名称（来自时间线图表点击的线），用于进一步过滤（如小类/线程/文件）
  selectedSeriesName?: string;
  maxCallchains?: number;
}

const props = withDefaults(defineProps<OutstandingFlameGraphProps>(), {
  maxCallchains: 200,
  viewMode: 'category',
  selectedProcess: '',
  selectedThread: '',
  selectedFile: '',
  selectedSeriesName: '',
});

const flameGraphData = ref<FlameGraphNode[]>([]);
const isLoading = ref(false);
const errorMessage = ref<string | null>(null);
const infoMessage = ref<string | null>(null);

const shouldQuery = computed(
  () =>
    props.selectedTimePoint !== null &&
    (props.drillLevel !== 'overview' ||
      props.selectedSeriesName !== ''),
);

let requestToken = 0;

// 进一步收紧高度和额外留白，尽量减少顶部空白
const MIN_FLAME_GRAPH_HEIGHT = 320;
const LEVEL_HEIGHT = 22;
const EXTRA_HEIGHT = 0;

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
    () => props.selectedSeriesName,
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
  mergeCount: number;
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

interface TreeAccumulator {
  name: string;
  value: number;
  mergeCount: number;
  file?: string;
  symbol?: string;
  allocCount: number;
  freeCount: number;
  children: Map<string, TreeAccumulator>;
}

function createTreeNode(name: string): TreeAccumulator {
  return {
    name,
    value: 0,
    mergeCount: 0,
    file: undefined,
    symbol: undefined,
    allocCount: 0,
    freeCount: 0,
    children: new Map<string, TreeAccumulator>(),
  };
}

function insertCallchainIntoTree(
  root: Map<string, TreeAccumulator>,
  frames: CallchainFrame[] | undefined,
  entry: OutstandingEntry,
): void {
  let pathFrames = frames && frames.length > 0 ? frames : undefined;

  // 去除重复的帧（基于depth、symbol、file的组合）
  if (pathFrames) {
    const seen = new Set<string>();
    pathFrames = pathFrames.filter(frame => {
      const key = `${frame.depth}-${frame.symbol || ''}-${frame.file || ''}-${frame.ip || 0}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

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
    node.mergeCount += entry.mergeCount;

    const frame = pathFrames?.[idx];
    if (frame) {
      if (frame.file) {
        node.file = frame.file;
      }
      if (frame.symbol) {
        node.symbol = frame.symbol;
      }
    }

    if (idx === labels.length - 1) {
      node.allocCount += entry.allocCount;
      node.freeCount += entry.freeCount;
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
      mergeCount: node.mergeCount,
    };
    if (children.length > 0) {
      flameNode.children = children.sort((a, b) => b.value - a.value);
    }
    if (node.file) {
      flameNode.file = node.file;
    }
    if (node.symbol) {
      flameNode.symbol = node.symbol;
    }
    if (node.allocCount > 0) {
      flameNode.allocCount = node.allocCount;
    }
    if (node.freeCount > 0) {
      flameNode.freeCount = node.freeCount;
    }
    flameNodes.push(flameNode);
  });

  flameNodes.sort((a, b) => b.value - a.value);
  return flameNodes;
}

function normalizeFileName(fileName?: string | null): string | null {
  if (!fileName || fileName === 'N/A') {
    return null;
  }
  return fileName;
}

function filterRecordsBySeriesName(
  records: NativeMemoryRecord[],
  seriesName: string,
  drillLevel: DrillDownLevel,
  viewMode: ViewMode,
): NativeMemoryRecord[] {
  if (!seriesName) {
    return records;
  }

  return records.filter(record => {
    if (viewMode === 'category') {
      if (drillLevel === 'category') {
        // 系列名称为小类名称
        return record.subCategoryName === seriesName;
      } else if (drillLevel === 'subCategory') {
        // 系列名称为文件名
        const normalizedFile = normalizeFileName(record.file);
        return normalizedFile === seriesName;
      }
    } else {
      if (drillLevel === 'process') {
        // 系列名称为线程名
        const threadName = record.thread || 'Unknown Thread';
        return threadName === seriesName;
      } else if (drillLevel === 'thread') {
        // 系列名称为文件名
        const normalizedFile = normalizeFileName(record.file);
        return normalizedFile === seriesName;
      }
    }
    return true;
  });
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
        mergeCount: 0,
      });
    }

    const entry = outstandingMap.get(callchainId)!;
    const size = record.heapSize || 0;
    entry.mergeCount += 1;

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

  // 保存当前的状态，避免在异步操作过程中状态改变导致数据不一致
  const currentDrillLevel = props.drillLevel;
  const currentViewMode = props.viewMode;
  const currentSelectedSeriesName = props.selectedSeriesName;
  const currentSelectedCategory = props.selectedCategory;
  const currentSelectedSubCategory = props.selectedSubCategory;
  const currentSelectedProcess = props.selectedProcess;
  const currentSelectedThread = props.selectedThread;
  const currentSelectedFile = props.selectedFile;
  const currentSelectedTimePoint = props.selectedTimePoint!;
  const currentStepId = props.stepId;

  try {
    let category: string | undefined;
    let subCategory: string | undefined;
    let process: string | undefined;
    let thread: string | undefined;
    let file: string | undefined;

    if (currentViewMode === 'category') {
      if (currentDrillLevel === 'overview') {
        // overview 层级时，根据 selectedSeriesName 设置 category
        category = currentSelectedSeriesName && currentSelectedSeriesName !== '总内存'
          ? currentSelectedSeriesName
          : undefined;
      } else {
        category =
          currentDrillLevel === 'category' ||
          currentDrillLevel === 'subCategory' ||
          currentDrillLevel === 'file'
            ? currentSelectedCategory
            : undefined;
        subCategory =
          currentDrillLevel === 'subCategory' || currentDrillLevel === 'file'
            ? currentSelectedSubCategory
            : undefined;
        file = currentDrillLevel === 'file' ? currentSelectedFile : undefined;
      }
    } else {
      if (currentDrillLevel === 'overview') {
        // overview 层级时，根据 selectedSeriesName 设置 process
        process = currentSelectedSeriesName && currentSelectedSeriesName !== '总内存'
          ? currentSelectedSeriesName
          : undefined;
      } else {
        process =
          currentDrillLevel === 'process' ||
          currentDrillLevel === 'thread' ||
          currentDrillLevel === 'file'
            ? currentSelectedProcess
            : undefined;
        thread =
          currentDrillLevel === 'thread' || currentDrillLevel === 'file'
            ? currentSelectedThread
            : undefined;
        file = currentDrillLevel === 'file' ? currentSelectedFile : undefined;
      }
    }

    let records =
      currentViewMode === 'category'
        ? await fetchRecordsUpToTimeByCategory(
            currentStepId,
            currentSelectedTimePoint,
            category,
            subCategory,
            file,
          )
        : await fetchRecordsUpToTimeByProcess(
            currentStepId,
            currentSelectedTimePoint,
            process,
            thread,
            file,
          );
    if (token !== requestToken) {
      return;
    }

    // 根据选中的系列名称进一步过滤记录
    if (currentSelectedSeriesName) {
      records = filterRecordsBySeriesName(records, currentSelectedSeriesName, currentDrillLevel, currentViewMode);
    }

    const outstandingEntries = calculateOutstanding(records);
    if (outstandingEntries.length === 0) {
      infoMessage.value = '选中时间点前没有未释放的调用链。';
      return;
    }

    const targetCallchainIds = outstandingEntries
      .map(entry => entry.callchainId)
      .filter(id => id > 0);

    const frames =
      targetCallchainIds.length > 0
        ? await fetchCallchainFrames(currentStepId, targetCallchainIds)
        : ({} as CallchainFrameMap);

    if (token !== requestToken) {
      return;
    }

    const result = buildFlameGraphData(outstandingEntries, frames);
    if (token === requestToken) {
      flameGraphData.value = result;
    }
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
  margin-top: 0;
}

.memory-outstanding-flame-graph__panel {
  background: #ffffff;
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.memory-outstanding-flame-graph__panel-header {
  /* 顶部区域不展示，避免占据火焰图上方空间 */
  display: none;
  margin: 0;
  padding: 0;
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
  margin-bottom: 8px;
}
</style>


