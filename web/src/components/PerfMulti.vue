<template>
  <div class="perf-multi">
    <div class="info-box">
      多版本负载趋势分析：
      <p>支持上传多个对比html文件，自动解析并展示不同维度的数据变化趋势</p>
    </div>

    <!-- 文件上传区域 -->
    <div class="upload-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>数据文件上传</span>
          </div>
        </template>
        <div class="upload-content">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleHtmlFileChange"
            :on-remove="handleFileRemove"
            :file-list="fileList"
            multiple
            accept=".html"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将html文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持上传多个对比html文件，自动解析base64数据
              </div>
            </template>
          </el-upload>
        </div>
      </el-card>
    </div>

    <!-- 数据概览 -->
    <div v-if="multiData.length > 0" class="data-overview">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>数据概览</span>
            <el-button type="success" @click="analyzeTrends">开始分析</el-button>
          </div>
        </template>
        <el-table :data="multiData" style="width: 100%">
          <el-table-column prop="fileName" label="文件名" width="200" />
          <el-table-column prop="basicInfo.app_name" label="应用名称" width="150" />
          <el-table-column prop="basicInfo.rom_version" label="ROM版本" width="120" />
          <el-table-column prop="basicInfo.app_version" label="应用版本" width="120" />
          <el-table-column prop="basicInfo.scene" label="场景" />
          <el-table-column prop="basicInfo.timestamp" label="时间戳" width="180">
            <template #default="{ row }">
              {{ formatTimestamp(row.basicInfo.timestamp) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ $index }">
              <el-button type="danger" size="small" @click="removeData($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 趋势分析区域 -->
    <div v-if="showAnalysis" class="trend-analysis">
      <!-- 筛选器 -->
      <el-card class="filter-card">
        <template #header>
          <span>数据筛选</span>
        </template>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-select v-model="selectedApp" placeholder="选择应用" clearable @change="updateFilteredData">
              <el-option
                v-for="app in availableApps"
                :key="app"
                :label="app"
                :value="app"
              />
            </el-select>
          </el-col>
          <el-col :span="6">
            <el-select v-model="selectedRomVersion" placeholder="选择ROM版本" clearable @change="updateFilteredData">
              <el-option
                v-for="rom in availableRomVersions"
                :key="rom"
                :label="rom"
                :value="rom"
              />
            </el-select>
          </el-col>
          <el-col :span="6">
            <el-select v-model="selectedAppVersion" placeholder="选择应用版本" clearable @change="updateFilteredData">
              <el-option
                v-for="version in availableAppVersions"
                :key="version"
                :label="version"
                :value="version"
              />
            </el-select>
          </el-col>
          <el-col :span="6">
            <el-select v-model="selectedScene" placeholder="选择场景" clearable @change="updateFilteredData">
              <el-option
                v-for="scene in availableScenes"
                :key="scene"
                :label="scene"
                :value="scene"
              />
            </el-select>
          </el-col>
        </el-row>
      </el-card>

      <!-- 场景负载趋势 -->
      <el-card class="trend-card">
        <template #header>
          <span>场景负载趋势</span>
        </template>
        <div class="chart-container">
          <TrendChart :chart-data="sceneTrendData" :title="'场景负载趋势'" :series-type="'line'" />
        </div>
      </el-card>

      <!-- 分类负载趋势 -->
      <el-card class="trend-card">
        <template #header>
          <span>分类负载趋势</span>
        </template>
        <div class="chart-container">
          <TrendChart :chart-data="categoryTrendData" :title="'分类负载趋势'" :series-type="'line'" />
        </div>
      </el-card>

      <!-- 步骤负载趋势 -->
      <!-- <el-card class="trend-card">
        <template #header>
          <span>步骤负载趋势</span>
        </template>
        <div class="chart-container">
          <TrendChart :chart-data="stepTrendData" :title="'步骤负载趋势'" :series-type="'line'" />
        </div>
      </el-card> -->

      <!-- 版本对比表格 -->
      <!-- <el-card class="trend-card">
        <template #header>
          <span>版本对比详情</span>
        </template>
        <el-table :data="comparisonTableData" style="width: 100%">
          <el-table-column prop="version" label="版本信息" width="200" />
          <el-table-column prop="totalLoad" label="总负载" width="120" />
          <el-table-column prop="appLoad" label="应用负载" width="120" />
          <el-table-column prop="systemLoad" label="系统负载" width="120" />
          <el-table-column prop="thirdPartyLoad" label="三方负载" width="120" />
          <el-table-column prop="changeRate" label="变化率" width="120">
            <template #default="{ row }">
              <span :style="{ color: row.changeRate > 0 ? 'red' : 'green' }">
                {{ row.changeRate > 0 ? '+' : '' }}{{ row.changeRate }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card> -->
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import TrendChart from './TrendChart.vue';
import type { JSONData, BasicInfo, PerfData } from '../stores/jsonDataStore';
import { processJson2PieChartData, calculateCategorysData } from '../utils/jsonUtil';
import * as pako from 'pako';

interface PieChartData {
  legendData: string[];
  seriesData: Array<{ name: string; value: number }>;
}

interface CategoryDataItem {
  category: string;
  instructions: number;
}

interface StepDataItem {
  stepId: number;
  stepName: string;
  count: number;
}

interface MultiDataItem {
  fileName: string;
  basicInfo: BasicInfo;
  perfData: PerfData;
  scenePieData: PieChartData;
  categoryData: CategoryDataItem[];
  stepData: StepDataItem[];
}

interface UploadFile {
  name: string;
  raw: File;
}

const uploadRef = ref();
const fileList = ref([]);
const multiData = ref<MultiDataItem[]>([]);
const showAnalysis = ref(false);

// 筛选器
const selectedApp = ref('');
const selectedRomVersion = ref('');
const selectedAppVersion = ref('');
const selectedScene = ref('');

// 计算属性
const availableApps = computed(() => {
  const apps = new Set(multiData.value.map(item => item.basicInfo.app_name));
  return Array.from(apps);
});

const availableRomVersions = computed(() => {
  const roms = new Set(multiData.value.map(item => item.basicInfo.rom_version));
  return Array.from(roms);
});

const availableAppVersions = computed(() => {
  const versions = new Set(multiData.value.map(item => item.basicInfo.app_version));
  return Array.from(versions);
});

const availableScenes = computed(() => {
  const scenes = new Set(multiData.value.map(item => item.basicInfo.scene));
  return Array.from(scenes);
});

const filteredData = computed(() => {
  return multiData.value.filter(item => {
    if (selectedApp.value && item.basicInfo.app_name !== selectedApp.value) return false;
    if (selectedRomVersion.value && item.basicInfo.rom_version !== selectedRomVersion.value) return false;
    if (selectedAppVersion.value && item.basicInfo.app_version !== selectedAppVersion.value) return false;
    if (selectedScene.value && item.basicInfo.scene !== selectedScene.value) return false;
    return true;
  });
});

// 趋势数据
const sceneTrendData = computed(() => {
  const sortedData = [...filteredData.value].sort((a, b) => a.basicInfo.timestamp - b.basicInfo.timestamp);
  return {
    xAxis: sortedData.map(item => `${item.basicInfo.rom_version}-${item.basicInfo.app_version}`),
    series: [{
      name: '总负载',
      data: sortedData.map(item => {
        const total = item.scenePieData.seriesData.reduce((sum: number, d: { value: number }) => sum + d.value, 0);
        return total;
      })
    }]
  };
});

const categoryTrendData = computed(() => {
  const sortedData = [...filteredData.value].sort((a, b) => a.basicInfo.timestamp - b.basicInfo.timestamp);
  const categories = ['APP_ABC', 'APP_LIB', 'APP_SO', 'OS_Runtime', 'SYS_SDK', 'RN', 'Flutter', 'WEB'];
  
  return {
    xAxis: sortedData.map(item => `${item.basicInfo.rom_version}-${item.basicInfo.app_version}`),
    series: categories.map(category => ({
      name: category,
      data: sortedData.map(item => {
        const categoryItem = item.categoryData.find((d: CategoryDataItem) => d.category === category);
        return categoryItem ? categoryItem.instructions : 0;
      })
    }))
  };
});

// const stepTrendData = computed(() => {
//   const sortedData = [...filteredData.value].sort((a, b) => a.basicInfo.timestamp - b.basicInfo.timestamp);
//   return {
//     xAxis: sortedData.map(item => `${item.basicInfo.rom_version}-${item.basicInfo.app_version}`),
//     series: [{
//       name: '步骤负载',
//       data: sortedData.map(item => {
//         const total = item.stepData.reduce((sum: number, d: any) => sum + d.count, 0);
//         return total;
//       })
//     }]
//   };
// });

// const comparisonTableData = computed(() => {
//   const sortedData = [...filteredData.value].sort((a, b) => a.basicInfo.timestamp - b.basicInfo.timestamp);
  
//   return sortedData.map((item, index) => {
//     const totalLoad = item.scenePieData.seriesData.reduce((sum: number, d: any) => sum + d.value, 0);
//     const appLoad = item.categoryData
//       .filter((d: any) => ['APP_ABC', 'APP_LIB', 'APP_SO'].includes(d.category))
//       .reduce((sum: number, d: any) => sum + d.instructions, 0);
//     const systemLoad = item.categoryData
//       .filter((d: any) => ['OS_Runtime', 'SYS_SDK'].includes(d.category))
//       .reduce((sum: number, d: any) => sum + d.instructions, 0);
//     const thirdPartyLoad = item.categoryData
//       .filter((d: any) => ['RN', 'Flutter', 'WEB'].includes(d.category))
//       .reduce((sum: number, d: any) => sum + d.instructions, 0);
    
//     let changeRate = 0;
//     if (index > 0) {
//       const prevTotal = sortedData[index - 1].scenePieData.seriesData.reduce((sum: number, d: any) => sum + d.value, 0);
//       changeRate = ((totalLoad - prevTotal) / prevTotal) * 100;
//     }
    
//     return {
//       version: `${item.basicInfo.rom_version}-${item.basicInfo.app_version}`,
//       totalLoad: totalLoad.toFixed(2),
//       appLoad: appLoad.toFixed(2),
//       systemLoad: systemLoad.toFixed(2),
//       thirdPartyLoad: thirdPartyLoad.toFixed(2),
//       changeRate: changeRate.toFixed(2)
//     };
//   });
// });

const handleHtmlFileChange = async (file: UploadFile) => {
  try {
    const content = await readFileContent(file.raw);
    // 提取const json = 'base64...'字符串
    const match = content.match(/const\s+json\s*=\s*['"]([A-Za-z0-9+/=]+)['"]/);
    if (!match) {
      ElMessage.error(`文件 ${file.name} 未找到base64 json数据`);
      return;
    }
    const base64Str = match[1];
    // base64解码
    const binaryString = atob(base64Str);
    // 转为Uint8Array
    const charData = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      charData[i] = binaryString.charCodeAt(i);
    }
    // pako解压
    const decompressed = pako.inflate(charData, { to: 'string' });
    const jsonData = JSON.parse(decompressed) as JSONData;
    // 处理数据
    const processedData = await processJsonData(jsonData, file.name);
    multiData.value.push(processedData);
    ElMessage.success(`文件 ${file.name} 上传成功`);
  } catch (error) {
    ElMessage.error(`文件 ${file.name} 处理失败: ${error}`);
  }
};

const handleFileRemove = (file: UploadFile) => {
  const index = multiData.value.findIndex(item => item.fileName === file.name);
  if (index !== -1) {
    multiData.value.splice(index, 1);
  }
};

const removeData = (index: number) => {
  multiData.value.splice(index, 1);
};

const readFileContent = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target?.result as string);
    reader.onerror = reject;
    reader.readAsText(file);
  });
};

const processJsonData = async (jsonData: JSONData, fileName: string): Promise<MultiDataItem> => {
  let scenePieData: PieChartData;
  let categoryData: CategoryDataItem[];
  
  try {
    scenePieData = processJson2PieChartData(jsonData.perf, 0);
    categoryData = calculateCategorysData(jsonData.perf, null, true);
  } catch (error) {
    console.error('数据处理错误:', error);
    // 提供默认数据
    scenePieData = { legendData: [], seriesData: [] };
    categoryData = [];
  }
  
  const stepData: StepDataItem[] = jsonData.perf.steps.map(step => ({
    stepId: step.step_id,
    stepName: step.step_name,
    count: step.count
  }));
  
  return {
    fileName,
    basicInfo: jsonData.basicInfo,
    perfData: jsonData.perf,
    scenePieData,
    categoryData,
    stepData
  };
};

const updateFilteredData = () => {
  // 筛选器变化时的处理
  console.log('筛选器更新');
};

const analyzeTrends = () => {
  if (multiData.value.length < 2) {
    ElMessage.warning('至少需要2个数据文件才能进行趋势分析');
    return;
  }
  showAnalysis.value = true;
  ElMessage.success('开始趋势分析');
};

const formatTimestamp = (timestamp: number) => {
  return new Date(timestamp).toLocaleString();
};

onMounted(() => {
  // 初始化 - 添加一些示例数据用于测试
  if (import.meta.env.DEV) {
    // 开发环境下添加示例数据
    console.log('PerfMulti 组件已加载，可以开始上传数据文件进行多版本趋势分析');
  }
});
</script>

<style scoped>
.perf-multi {
  padding: 20px;
  background: #f5f7fa;
}

.info-box {
  background-color: #e7f3fe;
  border-left: 6px solid #2196F3;
  padding: 12px;
  margin-bottom: 20px;
  font-family: Arial, sans-serif;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.info-box p {
  margin: 0;
  color: #333;
}

.upload-section {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-content {
  padding: 20px;
}

.data-overview {
  margin-bottom: 20px;
}

.trend-analysis {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.trend-card {
  margin-bottom: 20px;
}

.chart-container {
  height: 400px;
  width: 100%;
}

.el-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
}

.el-card__header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.el-table {
  border-radius: 8px;
  overflow: hidden;
}

.el-upload {
  width: 100%;
}

.el-upload-dragger {
  width: 100%;
  height: 200px;
}
</style> 



