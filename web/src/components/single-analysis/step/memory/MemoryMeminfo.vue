<template>
  <div class="memory-meminfo">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!hasData" class="no-data">暂无一级内存数据</div>
    <el-table v-else :data="tableData" border stripe style="width: 100%">
      <el-table-column prop="timestamp" label="时间" width="180" fixed />
      <el-table-column v-for="col in dataColumns" :key="col" :prop="col" :label="col" width="150" align="right">
        <template #default="{ row }">
          {{ formatBytes(row[col]) }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { getDbApi } from '@/utils/dbApi';

const props = withDefaults(defineProps<{
  stepId: number;
  height?: string;
}>(), {
  height: '300px'
});

const emit = defineEmits<{
  hasData: [hasData: boolean];

}>();

const loading = ref(false);
const hasData = ref(false);

const tableData = ref<Record<string, unknown>[]>([]);
const dataColumns = ref<string[]>([]);

onMounted(() => {
  loadData();
});

watch(() => props.stepId, () => {
  loadData();
});

async function loadData() {
  loading.value = true;
  try {
    const dbApi = getDbApi();
    const rows = await dbApi.queryMemoryMeminfo(props.stepId);

    if (!rows || rows.length === 0) {
      hasData.value = false;
      emit('hasData', false);
      return;
    }

    hasData.value = true;
    emit('hasData', true);

    // 收集所有列名
    const columnsSet = new Set<string>();
    rows.forEach((row: Record<string, unknown>) => {
      const data = JSON.parse(row.data as string);
      Object.keys(data).forEach(key => columnsSet.add(key));
    });
    dataColumns.value = Array.from(columnsSet);

    // 构建表格数据
    tableData.value = rows.map((row: Record<string, unknown>) => {
      const data = JSON.parse(row.data as string);
      return {
        timestamp: row.timestamp,
        ...data
      };
    });
  } catch (error) {
    console.error('加载meminfo数据失败:', error);
    hasData.value = false;
    emit('hasData', false);
  } finally {
    loading.value = false;
  }
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${bytes} B`;
}
</script>

<style scoped>
.memory-meminfo {
  width: 100%;
}

.loading, .no-data {
  text-align: center;
  padding: 20px;
  color: #999;
}

.meminfo-chart {
  width: 100%;
}
</style>

