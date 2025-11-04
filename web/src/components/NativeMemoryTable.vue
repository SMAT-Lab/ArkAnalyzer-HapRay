<template>
  <div class="memory-table">
    <!-- 搜索和过滤容器 -->
    <div class="filter-container">
      <el-radio-group v-model="filterModel.filterMode">
        <el-radio-button value="string">字符串模式</el-radio-button>
        <el-radio-button value="regex">正则模式</el-radio-button>
      </el-radio-group>
      
      <!-- 进程维度的搜索框 -->
      <template v-if="!hasCategory">
        <el-input
v-if="dataType === 'thread'" v-model="threadNameQuery" placeholder="根据线程名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'thread'" v-model="processNameQuery" placeholder="根据进程名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'file'" v-model="fileNameQuery" placeholder="根据文件名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'symbol'" v-model="symbolNameQuery" placeholder="根据符号名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </template>

      <!-- 分类维度的搜索框 -->
      <template v-if="hasCategory">
        <el-input
v-if="dataType === 'component'" v-model="categoryNameQuery" placeholder="根据大类搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'component'" v-model="componentNameQuery" placeholder="根据小类搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'file'" v-model="fileNameQuery" placeholder="根据文件名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-input
v-if="dataType === 'symbol'" v-model="symbolNameQuery" placeholder="根据符号名搜索" clearable
          class="search-input" @input="handleFilterChange">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </template>
    </div>

    <!-- 过滤后占比 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div style="margin-bottom:10px;">
          <div style="display: flex; align-items: center;">
            <span style="font-size: 16px; font-weight: bold;">过滤后内存占总内存：</span>
            <span :style="{ color: 'blue' }">
              {{ filterMemoryPercentage }}
            </span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-table
      :data="paginatedData" style="width: 100%" :default-sort="{ prop: 'netSize', order: 'descending' }"
      stripe highlight-current-row
      @sort-change="handleSortChange">
      
      <!-- 小分类表格列 -->
      <template v-if="dataType === 'component'">
        <el-table-column prop="category" label="大类" show-overflow-tooltip />
        <el-table-column prop="componentName" label="小类" show-overflow-tooltip />
      </template>

      <!-- 线程表格列 -->
      <template v-if="dataType === 'thread'">
        <el-table-column v-if="!hasCategory" prop="thread" label="线程" show-overflow-tooltip />
        <el-table-column v-if="!hasCategory" prop="process" label="所属进程" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="category" label="大类" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="componentName" label="小类" show-overflow-tooltip />
      </template>

      <!-- 文件表格列 -->
      <template v-if="dataType === 'file'">
        <el-table-column prop="file" label="文件" show-overflow-tooltip />
        <el-table-column v-if="!hasCategory" prop="thread" label="所属线程" show-overflow-tooltip />
        <el-table-column v-if="!hasCategory" prop="process" label="所属进程" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="category" label="大类" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="componentName" label="小类" show-overflow-tooltip />
      </template>

      <!-- 符号表格列 -->
      <template v-if="dataType === 'symbol'">
        <el-table-column prop="symbol" label="符号" show-overflow-tooltip />
        <el-table-column prop="file" label="所属文件" show-overflow-tooltip />
        <el-table-column v-if="!hasCategory" prop="thread" label="所属线程" show-overflow-tooltip />
        <el-table-column v-if="!hasCategory" prop="process" label="所属进程" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="category" label="大类" show-overflow-tooltip />
        <el-table-column v-if="hasCategory" prop="componentName" label="小类" show-overflow-tooltip />
      </template>

      <!-- 进程表格列 -->
      <template v-if="dataType === 'process'">
        <el-table-column prop="process" label="进程名称" show-overflow-tooltip />
      </template>

      <!-- 分类表格列 -->
      <template v-if="dataType === 'category'">
        <el-table-column prop="componentName" label="大类" show-overflow-tooltip />
      </template>

      <!-- 事件类型表格列 -->
      <template v-if="dataType === 'eventType'">
        <el-table-column prop="eventTypeName" :label="eventTypeLabel" show-overflow-tooltip />
      </template>

      <!-- 通用列 -->
      <!-- <el-table-column prop="eventType" label="事件类型" width="120" show-overflow-tooltip />
      <el-table-column prop="subEventType" label="子事件类型" width="140" show-overflow-tooltip /> -->
      <el-table-column prop="eventNum" label="总事件数" width="100" sortable />
      <el-table-column prop="peakMem" label="峰值内存" width="120" sortable>
        <template #default="{ row }">
          <span :class="getMemoryClass()">
            {{ formatBytes(row.peakMem) }}
          </span>
        </template>
      </el-table-column>
      <!-- curMem 已移除，使用 totalAllocMem 和 totalFreeMem 计算 -->
      <!-- <el-table-column prop="curMem" label="当前内存" width="120" sortable>
        <template #default="{ row }">
          {{ formatBytes(row.curMem) }}
        </template>
      </el-table-column> -->
      <!-- <el-table-column prop="avgMem" label="平均内存" width="120" sortable>
        <template #default="{ row }">
          {{ formatBytes(row.avgMem) }}
        </template>
      </el-table-column> -->
      <el-table-column prop="totalAllocMem" label="分配内存" width="120" sortable>
        <template #default="{ row }">
          {{ formatBytes(row.totalAllocMem) }}
        </template>
      </el-table-column>
      <el-table-column prop="allocEventNum" label="分配事件数" width="110" sortable />
      <el-table-column prop="totalFreeMem" label="释放内存" width="120" sortable>
        <template #default="{ row }">
          {{ formatBytes(row.totalFreeMem) }}
        </template>
      </el-table-column>
      <el-table-column prop="freeEventNum" label="释放事件数" width="110" sortable />
      <el-table-column prop="start_ts" label="峰值时刻(ms)" width="140" sortable>
        <template #default="{ row }">
          {{ (row.start_ts / 1000000).toFixed(2) }}
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      :total="filteredData.length"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';
import { Search } from '@element-plus/icons-vue';

// 定义数据项类型
interface DataItem {
  [key: string]: string | number | undefined;
}

// Props
const props = withDefaults(defineProps<{
  stepId: number;
  data: DataItem[];
  hasCategory: boolean;
  dataType: 'thread' | 'file' | 'symbol' | 'component' | 'process' | 'category' | 'eventType';
  eventTypeLabel?: string;
}>(), {
  eventTypeLabel: '事件类型'
});

// 过滤模式
const filterModel = ref({ filterMode: 'string' });

// 搜索查询
const threadNameQuery = ref('');
const processNameQuery = ref('');
const fileNameQuery = ref('');
const symbolNameQuery = ref('');
const categoryNameQuery = ref('');
const componentNameQuery = ref('');

// 分页
const currentPage = ref(1);
const pageSize = ref(20);

// 排序
const sortProp = ref('maxMem');
const sortOrder = ref('descending');

// 过滤数据
const filteredData = computed(() => {
  let result = [...props.data];

  // 字符串或正则过滤
  const isRegexMode = filterModel.value.filterMode === 'regex';

  if (threadNameQuery.value) {
    result = filterByField(result, 'thread', threadNameQuery.value, isRegexMode);
  }
  if (processNameQuery.value) {
    result = filterByField(result, 'process', processNameQuery.value, isRegexMode);
  }
  if (fileNameQuery.value) {
    result = filterByField(result, 'file', fileNameQuery.value, isRegexMode);
  }
  if (symbolNameQuery.value) {
    result = filterByField(result, 'symbol', symbolNameQuery.value, isRegexMode);
  }
  if (categoryNameQuery.value) {
    result = filterByField(result, 'category', categoryNameQuery.value, isRegexMode);
  }
  if (componentNameQuery.value) {
    result = filterByField(result, 'componentName', componentNameQuery.value, isRegexMode);
  }

  // 排序
  if (sortProp.value) {
    result.sort((a, b) => {
      const aVal = a[sortProp.value];
      const bVal = b[sortProp.value];
      // 处理 undefined 值
      if (aVal === undefined && bVal === undefined) return 0;
      if (aVal === undefined) return 1;
      if (bVal === undefined) return -1;

      if (sortOrder.value === 'ascending') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
  }

  return result;
});

// 分页数据
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredData.value.slice(start, end);
});

// 过滤后内存占比（使用 peakMem 峰值内存）
const filterMemoryPercentage = computed(() => {
  const totalMemory = props.data.reduce((sum, item) => {
    const peakMem = typeof item.peakMem === 'number' ? item.peakMem : 0;
    return sum + peakMem;
  }, 0);
  const filteredMemory = filteredData.value.reduce((sum, item) => {
    const peakMem = typeof item.peakMem === 'number' ? item.peakMem : 0;
    return sum + peakMem;
  }, 0);
  if (totalMemory === 0) return '0.00%';
  return ((filteredMemory / totalMemory) * 100).toFixed(2) + '%';
});

// 工具函数
function filterByField(data: DataItem[], field: string, query: string, isRegex: boolean): DataItem[] {
  if (!query) return data;
  if (isRegex) {
    try {
      const regex = new RegExp(query, 'i');
      return data.filter(item => regex.test(String(item[field] || '')));
    } catch {
      return data;
    }
  } else {
    const lowerQuery = query.toLowerCase();
    return data.filter(item => String(item[field] || '').toLowerCase().includes(lowerQuery));
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(2)} ${sizes[i]}`;
}

function getMemoryClass(): string {
  // 峰值内存统一用绿色显示
  return 'memory-peak';
}

function handleFilterChange() {
  currentPage.value = 1;
}

function handleSortChange({ prop, order }: { prop: string; order: string }) {
  sortProp.value = prop;
  sortOrder.value = order;
}

function handleSizeChange(val: number) {
  pageSize.value = val;
  currentPage.value = 1;
}

function handleCurrentChange(val: number) {
  currentPage.value = val;
}


</script>

<style scoped>
.memory-table {
  padding: 10px 0;
}

.filter-container {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.search-input {
  width: 200px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 内存大小颜色标记 */
.memory-peak {
  color: #67c23a;
  font-weight: 600;
}
</style>

