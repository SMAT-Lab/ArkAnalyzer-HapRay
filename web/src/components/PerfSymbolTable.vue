<template>
  <div class="instructions-table">
    <el-table :data="paginatedData" style="width: 100%">
      <el-table-column prop="name" label="符号">
        <template #default="{ row }">
          <div class="name-cell">{{ row.name }}</div>
        </template>
      </el-table-column>

      <el-table-column label="指令数" width="160">
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ formatScientific(row.count) }}</span>
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
import { ref, computed, watch } from 'vue';

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
});

const formatScientific = (num: number) => {
  if (typeof num !== 'number') {
    num = Number(num);
  }
  return num.toExponential(2);
};

// 分页状态
const currentPage = ref(1);
const pageSize = ref(10);
const pageSizeOptions = [10, 20, 50];

// 分页数据计算
const total = computed(() => props.data.length);

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return props.data.slice(start, end);
});

// 显示范围
const rangeStart = computed(() => (currentPage.value - 1) * pageSize.value + 1);
const rangeEnd = computed(() => Math.min(currentPage.value * pageSize.value, total.value));

// 数据变化重置页码
watch(
  () => props.data,
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
