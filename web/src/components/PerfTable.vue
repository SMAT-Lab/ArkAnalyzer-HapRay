<template>
  <div class="instructions-table" id="perfsTable">
    <!-- 搜索和过滤容器 -->
    <div class="filter-container">
      <el-input
        v-model="searchQuery"
        placeholder="根据文件名搜索"
        clearable
        @input="handleFilterChange"
        class="search-input"
      >
        <template #prefix>
          <el-icon><search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="activeCategory"
        placeholder="选择分类"
        clearable
        @change="handleFilterChange"
        class="category-select"
      >
        <el-option
          v-for="filter in categoryFilters"
          :key="filter.value"
          :label="filter.text"
          :value="filter.value"
        />
      </el-select>
    </div>

    <!-- 数据表格 -->
    <el-table
      :data="paginatedData"
      @row-click="handleRowClick"
      style="width: 100%"
      :default-sort="{ prop: 'instructions', order: 'descending' }"
      @sort-change="handleSortChange"
      stripe
      highlight-current-row
    >
      <el-table-column prop="name" label="文件" sortable>
        <template #default="{ row }">
          <div class="name-cell">{{ row.name }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.category }}</div>
        </template>
      </el-table-column>
      <el-table-column label="指令数" width="160" prop="instructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ formatScientific(row.instructions) }}</span>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页控件 -->
    <div class="pagination-container">
      <div class="pagination-info">
        显示 {{ rangeStart }} - {{ rangeEnd }} 条，共 {{ total }} 条
      </div>

      <div class="pagination-controls">
        <el-select
          v-model="pageSize"
          class="page-size-select"
          @change="handlePageSizeChange"
        >
          <el-option
            v-for="size in pageSizeOptions"
            :key="size"
            :label="`每页 ${size} 条`"
            :value="size"
          />
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
import { ref, computed, watch, type PropType } from 'vue';
const emit = defineEmits(['custom-event']);

// 定义数据类型接口
interface DataItem {
  stepId: number
  name: string
  category: string
  instructions: number
}

const props = defineProps({
  data: {
    type: Array as PropType<DataItem[]>,
    required: true,
  },
});

const formatScientific = (num: number) => {
  if (typeof num !== 'number') {
    num = Number(num);
  }
  return num.toExponential(2);
};

const handleRowClick = (row: { name: string }) => {
  emit('custom-event', row.name);
};

// 搜索功能
const searchQuery = ref('');
const activeCategory = ref('');


// 分页状态
const currentPage = ref(1);
const pageSize = ref(10);
const pageSizeOptions = [10, 20, 50];
const sortState = ref<{
  prop: SortKey
  order: SortOrder
}>({ 
  prop: 'instructions', 
  order: 'descending' 
})


// 数据处理（添加完整类型注解）
const filteredData = computed<DataItem[]>(() => {
  let result = [...props.data]

  // 应用搜索过滤
  if (searchQuery.value) {
    const searchTerm = searchQuery.value.toLowerCase()
    result = result.filter((item: DataItem) => 
      item.name.toLowerCase().includes(searchTerm))
  }

  // 应用分类过滤
  if (activeCategory.value) {
    result = result.filter((item: DataItem) => 
      item.category === activeCategory.value)
  }

  // 应用排序（添加类型安全）
  if (sortState.value.order) {
    const sortProp = sortState.value.prop
    const modifier = sortState.value.order === 'ascending' ? 1 : -1

    result.sort((a: DataItem, b: DataItem) => {
      // 添加类型断言确保数值比较
      const aVal = a[sortProp] as number
      const bVal = b[sortProp] as number
      return (aVal - bVal) * modifier
    })
  }

  return result
})



// 分页数据
const total = computed(() => filteredData.value.length);
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredData.value.slice(start, start + pageSize.value);
});

// 显示范围
const rangeStart = computed(() => (currentPage.value - 1) * pageSize.value + 1);
const rangeEnd = computed(() =>
  Math.min(currentPage.value * pageSize.value, total.value)
);

// 数据变化重置页码
watch(
  () => props.data,
  () => {
    currentPage.value = 1;
  }
);

// 事件处理
const handleFilterChange = () => {
  currentPage.value = 1;
};
const handlePageSizeChange = (newSize: number) => {
  pageSize.value = newSize;
  currentPage.value = 1;
};

// 1. 定义严格的类型
type SortKey = keyof DataItem; // 例如：'name' | 'category' | 'instructions'
type SortOrder = 'ascending' | 'descending' | null;

// 2. 修改事件处理函数类型
const handleSortChange = (sort: {
  prop: string; // Element Plus 原始类型为string
  order: SortOrder;
}) => {
  // 3. 添加类型保护
  const validKeys: SortKey[] = ['name', 'category', 'instructions'];
  
  if (validKeys.includes(sort.prop as SortKey)) {
    sortState.value = {
      prop: sort.prop as SortKey, // 安全断言
      order: sort.order
    };
    currentPage.value = 1;
  } else {
    // 处理无效排序字段的情况
    console.warn(`Invalid sort property: ${sort.prop}`);
    sortState.value = {
      prop: 'instructions', // 重置为默认值
      order: null
    };
  }
};

// 分类过滤选项
const categoryFilters: {text: string, value: string}[] = [
  { text: 'APP_ABC', value: 'APP_ABC' },
  { text: 'APP_SO', value: 'APP_SO' },
  { text: 'APP_LIB', value: 'APP_LIB' },
  { text: 'OS_Runtime', value: 'OS_Runtime' },
  { text: 'SYS_SDK', value: 'SYS_SDK' },
  { text: 'RN', value: 'RN' },
  { text: 'Flutter', value: 'Flutter' },
  { text: 'WEB', value: 'WEB' },
  { text: 'SYS_Other', value: 'SYS_Other' },
];

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

.filter-container {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  max-width: 300px;
}

.category-select {
  width: 200px;
}

.pagination-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 12px 16px;
  background-color: #f8fafc;
  border-radius: 8px;
}

.pagination-info {
  color: #606266;
  font-size: 0.9em;
}
</style>
