<template>
  <div class="memory-meminfo">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!hasData" class="no-data">暂无一级内存数据</div>
    <MeminfoStackedAreaChart v-else :data="chartData" :height="props.height" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { getDbApi } from '@/utils/dbApi';
import MeminfoStackedAreaChart from './MeminfoStackedAreaChart.vue';

const props = withDefaults(defineProps<{
  stepId: number;
  height?: string;
}>(), {
  height: '500px'
});

const emit = defineEmits<{
  hasData: [hasData: boolean];
}>();

const loading = ref(false);
const hasData = ref(false);
const chartData = ref<Record<string, unknown>[]>([]);

onMounted(() => {
  loadData();
});

watch(() => props.stepId, () => {
  loadData();
});

async function loadData() {
  loading.value = true;
  hasData.value = false;
  chartData.value = [];

  try {
    const dbApi = getDbApi();
    const rows = await dbApi.queryMemoryMeminfo(props.stepId);

    if (!rows || rows.length === 0) {
      hasData.value = false;
      emit('hasData', false);
      return;
    }

    chartData.value = rows;
    hasData.value = true;
    emit('hasData', true);
  } catch (error) {
    console.error('加载meminfo数据失败:', error);
    hasData.value = false;
    emit('hasData', false);
  } finally {
    loading.value = false;
  }
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

