<template>
  <div class="data-card native-distribution-card">
    <div class="card-title-row">
      <div class="card-title">Native 内存分类分布</div>
      <span class="time-scope-tag">{{ timeScopeLabel }}</span>
    </div>
    <p class="chart-desc">
      按分类统计 Native 净内存（申请 - 释放）分布。默认统计全场景所有步骤；
      在上方时间线选中时间点后，自动切换为截至该时刻的累计分布。
      点击饼图扇区或表格「下钻」可查看分类下的 .so / 库文件明细。
    </p>

    <div v-if="drillLevel === 'subCategory'" class="drill-bar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item>
          <a href="#" class="crumb-link" @click.prevent="backToCategory">分类总览</a>
        </el-breadcrumb-item>
        <el-breadcrumb-item>
          <span class="crumb-current">{{ selectedCategory }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div v-if="loading" class="loading-tip">加载中...</div>
    <div v-else-if="!rows.length" class="loading-tip">暂无分类数据</div>
    <template v-else>
      <div ref="pieRef" class="pie-chart"></div>

      <el-table
        :data="tableRows"
        stripe
        border
        style="width: 100%"
        show-summary
        :summary-method="getSummaryRow"
      >
        <el-table-column label="#" width="50" align="center">
          <template #default="{ $index }">{{ $index + 1 }}</template>
        </el-table-column>
        <el-table-column
          :label="drillLevel === 'category' ? '分类' : 'SO / 库文件'"
          min-width="240"
          align="left"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <span
              v-if="drillLevel === 'category'"
              class="cat-link"
              :title="`下钻查看 ${row.name} 下的 .so 文件`"
              @click="drillToCategory(row.name)"
            >
              {{ row.name }}
            </span>
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净内存 (MB)" min-width="120" align="right">
          <template #default="{ row }">
            <span :class="{ 'growth-down-text': row.netMb < 0 }">{{ fmtMb(row.netMb) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="事件数" min-width="100" align="right">
          <template #default="{ row }">{{ row.eventCount.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="占比" min-width="90" align="right">
          <template #default="{ row }">
            {{ row.percent != null ? `${row.percent.toFixed(2)}%` : '—' }}
          </template>
        </el-table-column>
        <el-table-column v-if="drillLevel === 'category'" label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="drillToCategory(row.name)">下钻</el-link>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { ECharts } from 'echarts';
import {
  fetchSummaryCategoryDistribution,
  fetchSummarySubCategoryDistribution,
} from '@/stores/nativeMemory';
import type { NativeMemoryDistributionRow } from '@/stores/nativeMemory';

const props = withDefaults(defineProps<{
  /** 时间线上选中的累计时间点（秒）；为空时统计全场景 */
  selectedTimePoint?: number | null;
}>(), {
  selectedTimePoint: null,
});

const MB = 1024 * 1024;

const loading = ref(false);
const drillLevel = ref<'category' | 'subCategory'>('category');
const selectedCategory = ref('');
const rows = ref<NativeMemoryDistributionRow[]>([]);

const pieRef = ref<HTMLElement>();
let chartInstance: ECharts | null = null;

const timeScopeLabel = computed(() =>
  props.selectedTimePoint == null
    ? '全场景 · 截至结束'
    : `截至累计 ${formatSeconds(props.selectedTimePoint)}`
);

interface TableRow {
  name: string;
  netMb: number;
  eventCount: number;
  percent: number | null;
}

/** 表格行：占比按正值总量计算，负值（净释放）不参与饼图与占比 */
const tableRows = computed<TableRow[]>(() => {
  const positiveTotal = rows.value.reduce((acc, r) => acc + Math.max(0, r.netSize), 0);
  return rows.value.map((r) => ({
    name: r.name,
    netMb: r.netSize / MB,
    eventCount: r.eventCount,
    percent: positiveTotal > 0 && r.netSize > 0 ? (r.netSize / positiveTotal) * 100 : null,
  }));
});

function fmtMb(value: number): string {
  if (!Number.isFinite(value)) return '—';
  return `${value.toFixed(2)} MB`;
}

function formatSeconds(seconds: number): string {
  return seconds < 1 ? `${(seconds * 1000).toFixed(2)} ms` : `${seconds.toFixed(2)} s`;
}

function drillToCategory(name: string) {
  if (drillLevel.value !== 'category' || !name) return;
  selectedCategory.value = name;
  drillLevel.value = 'subCategory';
}

function backToCategory() {
  drillLevel.value = 'category';
  selectedCategory.value = '';
}

async function load() {
  loading.value = true;
  try {
    rows.value =
      drillLevel.value === 'category'
        ? await fetchSummaryCategoryDistribution(props.selectedTimePoint)
        : await fetchSummarySubCategoryDistribution(selectedCategory.value, props.selectedTimePoint);
  } catch (error) {
    console.warn('[MemoryCategoryPie] Failed to load distribution:', error);
    rows.value = [];
  } finally {
    loading.value = false;
  }
  await nextTick();
  renderPie();
}

function getSummaryRow({ columns }: { columns: { property?: string }[] }): string[] {
  const totalNet = rows.value.reduce((acc, r) => acc + r.netSize, 0);
  const totalEvents = rows.value.reduce((acc, r) => acc + r.eventCount, 0);
  return columns.map((col, index) => {
    if (index === 0) return '总计';
    switch (col.property) {
      case 'netMb':
        return fmtMb(totalNet / MB);
      case 'eventCount':
        return totalEvents.toLocaleString();
      default:
        return '';
    }
  });
}

function renderPie() {
  if (!pieRef.value) return;
  const positive = tableRows.value.filter((r) => r.netMb > 0);
  if (!positive.length) return;

  if (chartInstance) {
    chartInstance.dispose();
  }
  chartInstance = echarts.init(pieRef.value);

  chartInstance.setOption({
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (params: unknown) => {
        const p = params as { name?: string; value?: number; percent?: number; marker?: string };
        return `${p.marker ?? ''}${p.name}<br/>净内存: <strong>${(p.value ?? 0).toFixed(2)} MB</strong> (${p.percent ?? 0}%)`;
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 'middle',
      textStyle: { fontSize: 12 },
    },
    series: [
      {
        name: '净内存分布',
        type: 'pie',
        radius: ['38%', '68%'],
        center: ['36%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          formatter: '{b}\n{d}%',
          fontSize: 11,
        },
        emphasis: {
          label: { show: true, fontWeight: 'bold' },
        },
        data: positive.map((r) => ({ name: r.name, value: Number(r.netMb.toFixed(2)) })),
      },
    ],
  });

  chartInstance.on('click', (params: unknown) => {
    const name = (params as { name?: string }).name;
    if (name) {
      drillToCategory(name);
    }
  });
}

function handleResize() {
  chartInstance?.resize();
}

onMounted(() => {
  void load();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});

watch(
  [drillLevel, selectedCategory, () => props.selectedTimePoint],
  () => {
    void load();
  }
);
</script>

<style scoped>
.native-distribution-card {
  margin-top: 16px;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.card-title-row .card-title {
  margin-bottom: 4px;
}

.time-scope-tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: #f0f9eb;
  color: #67c23a;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.chart-desc {
  margin: 0 0 10px 0;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}

.drill-bar {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.crumb-link {
  color: #409eff;
  text-decoration: none;
}

.crumb-current {
  font-weight: 600;
  color: #333;
}

.pie-chart {
  width: 100%;
  height: 340px;
  margin-bottom: 16px;
}

.loading-tip {
  text-align: center;
  padding: 40px 0;
  color: #909399;
  font-size: 13px;
}

.cat-link {
  color: #409eff;
  cursor: pointer;
}

.cat-link:hover {
  text-decoration: underline;
}

.growth-down-text {
  color: #67c23a;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
}
</style>
