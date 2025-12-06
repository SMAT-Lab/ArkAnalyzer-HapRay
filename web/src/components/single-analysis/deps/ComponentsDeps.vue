<template>
  <el-card :body-style="{ padding: '20px' }">
    <div ref="chartContainer" style="width: 100%; height: 400px"></div>
  </el-card>
  <div class="instructions-table">
    <el-table :data="paginatedData" style="width: 100%">
      <el-table-column prop="name" label="组件名称">
        <template #default="{ row }">
          <div class="name-cell">{{ row.name }}</div>
        </template>
      </el-table-column>

      <el-table-column label="版本号" width="160">
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ row.version }}</span>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页控件 -->
    <div class="pagination-container">
      <div class="pagination-info">共 {{ total }} 条</div>

      <div class="pagination-controls">
        <el-select v-model="pageSize" class="page-size-select" @change="handlePageSizeChange">
          <el-option v-for="size in pageSizeOptions" :key="size" :label="`每页 ${size} 条`" :value="size" />
        </el-select>

        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          :background="true"
          layout="prev, pager, next"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import * as echarts from 'echarts';
import { getCurrentInstance, ref, onMounted, watch, computed } from 'vue';

const vscode = getCurrentInstance()!.appContext.config.globalProperties.$vscode;

const chartContainer = ref(null);
let chartInstance: echarts.ECharts;

const handleChartClick = (params: unknown) => {
  console.log(params);
};

const depsData = ref({ nodes: [], edges: [], categories: [] });

const initChart = () => {
  const usedCategories = new Set<number>();
  depsData.value.nodes.map((node: { kind: number }) => {
    usedCategories.add(node.kind);
  });

  const chartOption = {
    legend: {
      orient: 'vertical',
      right: 10,
      data: depsData.value.categories
        .filter((category: { id: number; name: string }) => usedCategories.has(category.id))
        .map((category: { id: number; name: string }) => category.name),
    },

    series: [
      {
        type: 'graph',
        layout: 'force',
        animation: false,

        label: {
          position: 'right',
          formatter: '{b}',
        },
        draggable: true,
        data: depsData.value.nodes.map((node: { kind: number; id: number; category: number }, idx: number) => {
          node.id = idx;
          node.category = node.kind;
          return node;
        }),
        categories: depsData.value.categories,
        force: {
          edgeLength: 5,
          repulsion: 20,
          gravity: 0.2,
        },
        edges: depsData.value.edges,
      },
    ],
  };

  // 如果图表实例已存在，更新配置，否则初始化图表
  if (chartInstance) {
    chartInstance.setOption(chartOption);
    chartInstance.on('click', handleChartClick);
  } else {
    chartInstance = echarts.init(chartContainer.value);
    chartInstance.setOption(chartOption);
    chartInstance.on('click', handleChartClick);
  }
};

window.addEventListener('message', (event) => {
  const message = event.data;
  console.log(message);

  switch (message.command) {
    case '/api/v1/components/deps':
      depsData.value = message.data;
      break;
  }
});

watch(depsData, () => {
  initChart();
});

const getData = () => {
  vscode.postMessage({
    command: '/api/v1/components/deps',
  });
};

onMounted(() => {
  getData();
  window.addEventListener('resize', () => {
    chartInstance.resize();
  });
});

// 分页状态
const currentPage = ref(1);
const pageSize = ref(10);
const pageSizeOptions = [10, 20, 50];

// 分页数据计算
const total = computed(() => depsData.value.nodes.filter((node: { kind: number }) => node.kind === 2).length);

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return depsData.value.nodes.filter((node: { kind: number }) => node.kind === 2).slice(start, end);
});

// 显示范围
// const rangeStart = computed(() => (currentPage.value - 1) * pageSize.value + 1);
// const rangeEnd = computed(() => Math.min(currentPage.value * pageSize.value, total.value));

// 数据变化重置页码
watch(
  () => depsData.value.nodes,
  () => {
    currentPage.value = 1;
  }
);

// 分页事件处理
const handlePageSizeChange = (newSize: number) => {
  pageSize.value = newSize;
  currentPage.value = 1;
};
</script>

<style scoped>
div {
  width: 100%;
  height: 100%;
}
.instructions-table {
  :deep(.el-table) {
    --el-table-header-bg-color: #f5f7fa;
    --el-table-border-color: #e0e0e0;
  }

  .name-cell {
    font-weight: 500;
    color: #424242;
  }

  .count-cell {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .value {
    font-family: monospace;
  }

  .trend {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-size: 0.9em;
    padding: 2px 6px;
    border-radius: 4px;

    &.up {
      color: #4caf50;
      background: #e8f5e9;
    }

    &.down {
      color: #ef5350;
      background: #ffebee;
    }
  }

  .pagination-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    padding: 8px 0;
    background: #f8fafc;
    border-radius: 4px;
  }

  .pagination-controls {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .page-size-select {
    width: 120px;
  }

  :deep(.el-pagination) {
    padding: 0;

    .btn-prev,
    .btn-next {
      padding: 0 8px;
      min-width: 32px;
    }

    .el-pager li {
      min-width: 32px;
      height: 32px;
      line-height: 32px;
      margin: 0 2px;
      border-radius: 4px;
    }
  }

  .pagination-info {
    color: #606266;
    font-size: 0.9em;
    padding-left: 12px;
  }
}
</style>
