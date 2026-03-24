<template>
  <div id="perfsTable" class="instructions-table">
    <!-- 搜索和过滤容器：按进程拆解时仅显示实际列对应的搜索框（反序：函数|文件|三级分类|小类|大类|线程|进程），指令数列不搜索 -->
    <div class="filter-container">
      <el-radio-group v-model="filterModel.filterMode">
        <el-radio-button value="string">字符串模式</el-radio-button>
        <el-radio-button value="regex">正则模式</el-radio-button>
      </el-radio-group>
      <!-- 按进程拆解：根据 processDrillPathLevel 显示对应列的搜索框，反序 -->
      <template v-if="processDrillPathLevel !== undefined">
        <el-input v-if="hasCategory && processDrillPathLevel >= 3" v-model="thirdCategoryNameQueryStore.thirdCategoryNameQuery" placeholder="根据三级分类搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-input v-if="hasCategory && processDrillPathLevel >= 2" v-model="componentNameQuery.subCategoryNameQuery" placeholder="根据小类搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-select v-if="hasCategory && processDrillPathLevel >= 1" v-model="category.categoriesQuery" multiple collapse-tags placeholder="选择大类" clearable class="category-select" @change="handleFilterChange">
          <el-option v-for="filter in categoryFilters" :key="filter.value" :label="filter.text" :value="filter.value" />
        </el-select>
        <el-input v-model="threadNameQuery.threadNameQuery" placeholder="根据线程搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-input v-model="processNameQuery.processNameQuery" placeholder="根据进程搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
      </template>
      <!-- 非按进程拆解 -->
      <template v-else>
        <el-input v-if="!hasCategory" v-model="threadNameQuery.threadNameQuery" placeholder="根据线程名搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-input v-if="!hasCategory" v-model="processNameQuery.processNameQuery" placeholder="根据进程名搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-select v-if="hasCategory" v-model="category.categoriesQuery" multiple collapse-tags placeholder="选择分类" clearable class="category-select" @change="handleFilterChange">
          <el-option v-for="filter in categoryFilters" :key="filter.value" :label="filter.text" :value="filter.value" />
        </el-select>
        <el-input v-if="hasCategory" v-model="componentNameQuery.subCategoryNameQuery" placeholder="根据小分类搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
        <el-input v-if="hasCategory && showThirdCategory" v-model="thirdCategoryNameQueryStore.thirdCategoryNameQuery" placeholder="根据三级分类搜索" clearable class="search-input" @input="handleFilterChange">
          <template #prefix><el-icon><search /></el-icon></template>
        </el-input>
      </template>
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
      <!-- 按进程拆解：列顺序反序显示 函数|文件|三级分类|小类|大类|线程|进程，指令数列在最后 -->
      <el-table-column v-if="processDrillPathLevel !== undefined && hasCategory && processDrillPathLevel >= 3" prop="thirdCategoryName" label="三级分类">
        <template #default="{ row }"><div class="category-cell">{{ row.thirdCategoryName || '-' }}</div></template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel !== undefined && hasCategory && processDrillPathLevel >= 2" prop="subCategoryName" label="小类">
        <template #default="{ row }"><div class="category-cell">{{ row.subCategoryName || '-' }}</div></template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel !== undefined && hasCategory && processDrillPathLevel >= 1" prop="category" label="大类">
        <template #default="{ row }"><div class="category-cell">{{ row.category || '-' }}</div></template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel !== undefined" prop="thread" label="线程">
        <template #default="{ row }"><div class="category-cell">{{ row.thread || '-' }}</div></template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel !== undefined" prop="process" label="进程">
        <template #default="{ row }"><div class="category-cell">{{ row.process || '-' }}</div></template>
      </el-table-column>
      <!-- 按分类拆解：列顺序 函数|文件|三级分类|小分类|大分类，线程表为 三级分类|小分类|大分类 -->
      <el-table-column v-if="processDrillPathLevel === undefined && hasCategory && showThirdCategory" prop="thirdCategoryName" label="三级分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.thirdCategoryName || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel === undefined && hasCategory" prop="category" label="小分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.subCategoryName }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel === undefined && hasCategory" prop="category" label="大分类">
        <template #default="{ row }">
          <div class="category-cell">{{ row.category }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel === undefined && !hasCategory" prop="category" label="所属进程">
        <template #default="{ row }">
          <div class="category-cell">{{ row.process }}</div>
        </template>
      </el-table-column>
      <el-table-column v-if="processDrillPathLevel === undefined && !hasCategory" prop="category" label="线程">
        <template #default="{ row }">
          <div class="category-cell">{{ row.thread }}</div>
        </template>
      </el-table-column>
      <el-table-column label="基线指令数" width="160" prop="instructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value" :title="formatNumber(row.instructions)">{{ formatScientific(row.instructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="迭代指令数" width="160" prop="compareInstructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value" :title="formatNumber(row.compareInstructions)">{{ formatScientific(row.compareInstructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="负载增长指令数" width="160" prop="increaseInstructions" sortable>
        <template #default="{ row }">
          <div class="count-cell">
            <span class="value" :title="formatNumber(row.increaseInstructions)">{{ formatScientific(row.increaseInstructions) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isHidden" label="负载增长指百分比" width="160" prop="increasePercentage" sortable>
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
import { useProcessNameQueryStore, useThreadNameQueryStore, useCategoryStore, useFilterModeStore, useComponentNameStore, useThirdCategoryNameQueryStore } from '../../../../../stores/jsonDataStore.ts';
import type { ThreadDataItem } from '../../../../../utils/jsonUtil.ts';
const emit = defineEmits(['custom-event']);

const props = defineProps({
  data: {
    type: Array as PropType<ThreadDataItem[]>,
    required: true,
  },
  hideColumn: {
    type: Boolean,
    required: true,
  },
  hasCategory: {
    type: Boolean,
    required: true,
  },
  showThirdCategory: {
    type: Boolean,
    default: false,
  },
  /** 按进程拆解时的路径层级 0-6，每层增加一列：0=进程+线程 1=+大类 2=+小类 3=+三级 4=+文件 5=+函数 */
  processDrillPathLevel: {
    type: Number as PropType<number | undefined>,
    default: undefined,
  },
});

const isHidden = !props.hideColumn;

const hasCategory = props.hasCategory;

const formatScientific = (num: number) => {
  if (typeof num !== 'number') {
    num = Number(num);
  }
  return num.toExponential(2);
};

const formatNumber = (num: number) => {
  if (typeof num !== 'number') {
    num = Number(num);
  }
  // 格式化为带千分位分隔符的完整数字，用于tooltip显示
  return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
};

const handleRowClick = (row: { name: string }) => {
  emit('custom-event', row.name);
};

// 搜索功能
const filterModel = useFilterModeStore();// 'string' 或 'regex'
const processNameQuery = useProcessNameQueryStore();
const threadNameQuery = useThreadNameQueryStore();
const category = useCategoryStore();
const componentNameQuery = useComponentNameStore();
const thirdCategoryNameQueryStore = useThirdCategoryNameQueryStore();


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
const filteredData = computed<ThreadDataItem[]>(() => {
  let result = [...props.data]
  const level = props.processDrillPathLevel

  // 按进程拆解：仅对实际显示的列进行搜索过滤，指令数列不参与
  if (level !== undefined) {
    result = filterQueryCondition('process', processNameQuery.processNameQuery, result);
    result = filterQueryCondition('thread', threadNameQuery.threadNameQuery, result);
    if (hasCategory && level >= 1 && category.categoriesQuery && category.categoriesQuery.length > 0) {
      result = result.filter((item: ThreadDataItem) => category.categoriesQuery.includes(item.category));
    }
    if (hasCategory && level >= 2) result = filterQueryCondition('subCategoryName', componentNameQuery.subCategoryNameQuery, result);
    if (hasCategory && level >= 3) result = filterQueryCondition('thirdCategoryName', thirdCategoryNameQueryStore.thirdCategoryNameQuery, result);
  } else {
    // 非按进程拆解
    if (!hasCategory) {
      result = filterQueryCondition('process', processNameQuery.processNameQuery, result);
      result = filterQueryCondition('thread', threadNameQuery.threadNameQuery, result);
    }
    if (hasCategory) {
      result = filterQueryCondition('subCategoryName', componentNameQuery.subCategoryNameQuery, result);
    }
    if (hasCategory && props.showThirdCategory) {
      result = filterQueryCondition('thirdCategoryName', thirdCategoryNameQueryStore.thirdCategoryNameQuery, result);
    }
    if (category.categoriesQuery && hasCategory) {
      if (category.categoriesQuery.length > 0) {
        result = result.filter((item: ThreadDataItem) =>
          category.categoriesQuery.includes(item.category))
      }
    }
  }

  // 应用排序（添加类型安全）
  if (sortState.value.order) {
    const sortProp = sortState.value.prop
    const modifier = sortState.value.order === 'ascending' ? 1 : -1

    result.sort((a: ThreadDataItem, b: ThreadDataItem) => {
      // 添加类型断言确保数值比较
      const aVal = a[sortProp] as number
      const bVal = b[sortProp] as number
      return (aVal - bVal) * modifier
    })
  }

  return result
})

function filterQueryCondition(queryName: string, queryCondition: string, result: ThreadDataItem[]): ThreadDataItem[] {
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
      result = result.filter((item: ThreadDataItem) => {
        return regex.test(getDataItemProperty(queryName, item));
      })
      return result;
    } else {
      const searchTerm = queryCondition.toLowerCase()
      result = result.filter((item: ThreadDataItem) =>
        getDataItemProperty(queryName, item).toLowerCase().includes(searchTerm))
      return result;
    }
  } catch (error) {
    console.error(error);
    return result;
  }
}

function getDataItemProperty(queryName: string, dataItem: ThreadDataItem): string {
  if (queryName === 'process') return dataItem.process ?? '';
  if (queryName === 'thread') return dataItem.thread ?? '';
  if (queryName === 'category') return dataItem.category ?? '';
  if (queryName === 'subCategoryName') return dataItem.subCategoryName ?? '';
  if (queryName === 'thirdCategoryName') return dataItem.thirdCategoryName ?? '';
  return '';
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
type SortKey = keyof ThreadDataItem; // 例如：'name' | 'category' | 'instructions'
type SortOrder = 'ascending' | 'descending' | null;

// 2. 修改事件处理函数类型
const handleSortChange = (sort: {
  prop: string; // Element Plus 原始类型为string
  order: SortOrder;
}) => {
  // 3. 添加类型保护
  const validKeys: SortKey[] = ['category', 'subCategoryName', 'instructions', 'compareInstructions', 'increaseInstructions', 'increasePercentage', 'thread', 'process'];

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
    cursor: help;
    text-decoration: underline dotted;
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
