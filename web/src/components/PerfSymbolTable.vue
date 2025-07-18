<template>
  <div id="perfsTable" class="instructions-table">
    <!-- 搜索和过滤容器 -->
    <div class="filter-container">
      <el-radio-group v-model="filterModel.filterMode">
        <el-radio-button value="string">字符串模式</el-radio-button>
        <el-radio-button value="regex">正则模式</el-radio-button>
      </el-radio-group>
      <el-input
v-model="symbolNameQuery.symbolNameQuery" placeholder="根据函数搜索" clearable class="search-input"
        @input="handleFilterChange">
        <template #prefix>
          <el-icon>
            <search />
          </el-icon>
        </template>
      </el-input>

      <el-input
v-model="fileNameQuery.fileNameQuery" placeholder="根据文件搜索" clearable class="search-input"
        @input="handleFilterChange">
        <template #prefix>
          <el-icon>
            <search />
          </el-icon>
        </template>
      </el-input>
      <el-input
v-if="!hasCategory" v-model="threadNameQuery.threadNameQuery" placeholder="根据线程名搜索" clearable
        class="search-input" @input="handleFilterChange">
        <template #prefix>
          <el-icon>
            <search />
          </el-icon>
        </template>
      </el-input>
      <el-input
v-if="!hasCategory" v-model="processNameQuery.processNameQuery" placeholder="根据进程名搜索" clearable
        class="search-input" @input="handleFilterChange">
        <template #prefix>
          <el-icon>
            <search />
          </el-icon>
        </template>
      </el-input>
      <el-select
v-if="hasCategory" v-model="category.categoriesQuery" multiple collapse-tags placeholder="选择分类"
        clearable class="category-select" @change="handleFilterChange">
        <el-option v-for="filter in categoryFilters" :key="filter.value" :label="filter.text" :value="filter.value" />
      </el-select>
      <el-input
v-if="hasCategory" v-model="componentNameQuery.componentNameQuery" placeholder="根据小分类搜索" clearable
        class="search-input" @input="handleFilterChange">
        <template #prefix>
          <el-icon>
            <search />
          </el-icon>
        </template>
      </el-input>
    </div>

    <!-- 过滤后占比 -->
    <el-row :gutter="20">
      <el-col :span="8">
        <div style="margin-bottom:10px;">
          <div style="display: flex; align-items: center;">
            <span style="font-size: 16px; font-weight: bold;">过滤后负载占总负载：</span>
            <span :style="{ color: 'blue' }">
              {{ filterAllBaseInstructionsCompareTotal }}
            </span>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div v-if="isHidden" style="margin-bottom:10px;">
          <div style="display: flex;align-items: center;">
            <span style="font-size: 16px; font-weight: bold;">过滤后迭代负载占总负载：</span>
            <span :style="{ color: 'blue' }">
              {{ filterAllCompareInstructionsCompareTotal }}
            </span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-table
:data="paginatedData" style="width: 100%" :default-sort="{ prop: 'instructions', order: 'descending' }"
      stripe highlight-current-row @row-click="handleRowClick"
      @sort-change="handleSortChange">
      <el-table-column prop="name" label="函数" sortable>
        <template #default="{ row }">
          <div class="name-cell">{{ row.symbol }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="file" label="所属文件" sortable>
        <template #default="{ row }">
          <div class="name-cell">{{ row.file }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="!hasCategory" prop="category" label="所属线程">
        <template #default="{ row }">
          <div class="category-cell">{{ row.thread }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="!hasCategory" prop="category" label="所属进程">
        <template #default="{ row }">
          <div class="category-cell">{{ row.process }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="hasCategory" prop="category" label="大分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.category }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="hasCategory" prop="componentName" label="小分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.componentName }}</div>
        </template>
      </el-table-column>
      <el-table-column label="指令数" width="160" prop="instructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ formatScientific(row.instructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="迭代指令数" width="160" prop="compareInstructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ formatScientific(row.compareInstructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="负载增长指令数" width="160" prop="increaseInstructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ formatScientific(row.increaseInstructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="负载增长百分比" width="160" prop="increasePercentage" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value">{{ row.increasePercentage }} %</span>
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
        <el-select v-model="pageSize" class="page-size-select" @change="handlePageSizeChange">
          <el-option v-for="size in pageSizeOptions" :key="size" :label="`每页 ${size} 条`" :value="size" />
        </el-select>

        <el-pagination
v-model:current-page="currentPage" :page-size="pageSize" :total="total" :background="true"
          layout="prev, pager, next" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch, type PropType } from 'vue';
import { useProcessNameQueryStore, useThreadNameQueryStore, useFileNameQueryStore, useSymbolNameQueryStore, useCategoryStore, useFilterModeStore, useComponentNameStore } from '../stores/jsonDataStore.ts';
import type { SymbolDataItem } from '../utils/jsonUtil.ts';
const emit = defineEmits(['custom-event']);

const props = defineProps({
  data: {
    type: Array as PropType<SymbolDataItem[]>,
    required: true,
  },
  hideColumn: {
    type: Boolean,
    required: true,
  },
  hasCategory: {
    type: Boolean,
    required: true,
  }
});
const isHidden = !props.hideColumn;

const hasCategory = props.hasCategory;

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
const filterModel = useFilterModeStore();// 'string' 或 'regex'
const processNameQuery = useProcessNameQueryStore();
const threadNameQuery = useThreadNameQueryStore();
const symbolNameQuery = useSymbolNameQueryStore();
const fileNameQuery = useFileNameQueryStore();
const category = useCategoryStore();
const componentNameQuery = useComponentNameStore();

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

//过滤后的所有函数行对总体函数的占比统计
const filterAllBaseInstructionsCompareTotal = ref('');
const filterAllCompareInstructionsCompareTotal = ref('');

// 统计原始总指令数
const beforeFilterBaseInstructions = ref(0);
const beforeFilterCompareInstructions = ref(0);

watch(() => props.data, (newVal) => {
  let base = 0;
  let compare = 0;
  newVal.forEach((dataItem) => {
    base += dataItem.instructions;
    compare += dataItem.compareInstructions;
  });
  beforeFilterBaseInstructions.value = base;
  beforeFilterCompareInstructions.value = compare;
}, { immediate: true });

// 数据处理（添加完整类型注解）
const filteredData = computed<SymbolDataItem[]>(() => {
  let result = [...props.data]
  let beforeFilterBaseInstructions = 0;
  let beforeFilterCompareInstructions = 0;
  result.forEach((dataItem) => {
    beforeFilterBaseInstructions = beforeFilterBaseInstructions + dataItem.instructions;
    beforeFilterCompareInstructions = beforeFilterCompareInstructions + dataItem.compareInstructions;
  });

  // 应用进程过滤
  if (!hasCategory) {
    result = filterQueryCondition('process', processNameQuery.processNameQuery, result);
  }

  // 应用线程过滤
  if (!hasCategory) {
    result = filterQueryCondition('thread', threadNameQuery.threadNameQuery, result);
  }

  // 函数搜索过滤
  result = filterQueryCondition('symbol', symbolNameQuery.symbolNameQuery, result);

  // 文件搜索过滤
  result = filterQueryCondition('file', fileNameQuery.fileNameQuery, result);

  // 应用小分类过滤
  if (hasCategory) {
    result = filterQueryCondition('componentName', componentNameQuery.componentNameQuery, result);
  }

  // 应用分类过滤
  if (category.categoriesQuery && hasCategory) {
    if (category.categoriesQuery.length > 0) {
      result = result.filter((item: SymbolDataItem) =>
        category.categoriesQuery.includes(item.category))
    }
  }

  let afterFilterBaseInstructions = 0;
  let afterFilterCompareInstructions = 0;
  result.forEach((dataItem) => {
    afterFilterBaseInstructions = afterFilterBaseInstructions + dataItem.instructions;
    afterFilterCompareInstructions = afterFilterCompareInstructions + dataItem.compareInstructions;
  });

  // 排序
  if (sortState.value.order) {
    const sortProp = sortState.value.prop
    const modifier = sortState.value.order === 'ascending' ? 1 : -1
    result = [...result].sort((a: SymbolDataItem, b: SymbolDataItem) => {
      const aVal = a[sortProp] as number
      const bVal = b[sortProp] as number
      return (aVal - bVal) * modifier
    })
  }

  return result
})

function filterQueryCondition(queryName: string, queryCondition: string, result: SymbolDataItem[]): SymbolDataItem[] {
  try {
    if (filterModel.filterMode === 'regex') {
      // 正则表达式模式
      // 允许用户直接输入正则模式，也支持 /pattern/flags 格式
      // /^(?!.*@0x[0-9a-fA-F]+$).*$/ 找到不是偏移量的函数名正则
      let pattern = queryCondition;
      let flags = 'i'; // 默认忽略大小写

      // 检查是否使用了 /pattern/flags 格式
      if (pattern.startsWith('/') && pattern.lastIndexOf('/') > 0) {
        const lastSlashIndex = pattern.lastIndexOf('/');
        flags = pattern.substring(lastSlashIndex + 1);
        pattern = pattern.substring(1, lastSlashIndex);
      }

      const regex = new RegExp(pattern, flags);
      result = result.filter((item: SymbolDataItem) => {
        return regex.test(getDataItemProperty(queryName, item));
      })
      return result;
    } else {
      const searchTerm = queryCondition.toLowerCase()
      result = result.filter((item: SymbolDataItem) =>
        getDataItemProperty(queryName, item).toLowerCase().includes(searchTerm))
      return result;
    }
  } catch (error) {
    console.error(error);
    return result;
  }
}

function getDataItemProperty(queryName: string, dataItem: SymbolDataItem): string {
  if (queryName === 'process') {
    return dataItem.process;
  } else if (queryName === 'thread') {
    return dataItem.thread;
  } else if (queryName === 'componentName') {
    return dataItem.componentName;
  } else if (queryName === 'file') {
    return dataItem.file;
  } else if (queryName === 'symbol') {
    return dataItem.symbol;
  } else {
    return ''
  }
}

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
type SortKey = keyof SymbolDataItem; // 例如：'name' | 'category' | 'instructions'
type SortOrder = 'ascending' | 'descending' | null;

// 2. 修改事件处理函数类型
const handleSortChange = (sort: {
  prop: string; // Element Plus 原始类型为string
  order: SortOrder;
}) => {
  // 3. 添加类型保护
  const validKeys: SortKey[] = ['symbol', 'componentName', 'category', 'instructions', 'compareInstructions', 'increaseInstructions', 'increasePercentage', 'file', 'thread', 'process'];

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

const categoriesExit = new Set();

props.data.forEach((item) => {
  categoriesExit.add(item.category);
})

// 分类过滤选项
const categoryFilters = Array.from(categoriesExit).map(item => ({
  text: item,
  value: item
}));

// 副作用赋值移到watch
watch(filteredData, (newVal) => {
  let afterFilterBaseInstructions = 0;
  let afterFilterCompareInstructions = 0;
  newVal.forEach((dataItem) => {
    afterFilterBaseInstructions += dataItem.instructions;
    afterFilterCompareInstructions += dataItem.compareInstructions;
  });
  const basePercent = (afterFilterBaseInstructions / beforeFilterBaseInstructions.value) * 100;
  filterAllBaseInstructionsCompareTotal.value = Number.isNaN(Number.parseFloat(basePercent.toFixed(2))) ? '100%' : Number.parseFloat(basePercent.toFixed(2)) + '%';
  const comparePercent = (afterFilterCompareInstructions / beforeFilterCompareInstructions.value) * 100;
  filterAllCompareInstructionsCompareTotal.value = Number.isNaN(Number.parseFloat(comparePercent.toFixed(2))) ? '100%' : Number.parseFloat(comparePercent.toFixed(2)) + '%';
}, { immediate: true });

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

.no-body-card .el-card__body {
  display: none;
  padding: 0;
  /* 确保没有额外的间距 */
}
</style>
