<template>
  <div class="load-overview-container">
    <div class="info-box">
      负载分类说明：
      <p>APP_ABC => 应用代码 |
        APP_LIB => 应用三方ArkTS库 |
        APP_SO => 应用native库 |
        OS_Runtime => 系统运行时 |
        SYS_SDK => 系统SDK |
        RN => 三方框架React Native |
        Flutter => 三方框架Flutter |
        WEB => 三方框架ArkWeb</p>
    </div>
    
    <el-descriptions :title="performanceData.app_name" :column="1" class="beautified-descriptions">
      <el-descriptions-item label="系统版本：">{{ performanceData.rom_version }}</el-descriptions-item>
      <el-descriptions-item label="应用版本：">{{ performanceData.app_version }}</el-descriptions-item>
      <el-descriptions-item>
        <div class="description-item-content">
          场景名称：{{ performanceData.scene }}
        </div>
      </el-descriptions-item>
    </el-descriptions>

    <!-- 总体统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="card-icon">📊</div>
        <div class="card-content">
          <h3>总步骤数</h3>
          <div class="card-value">{{ testSteps.length }}</div>
          <p class="card-desc">测试场景包含的步骤总数</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="card-icon">⚡</div>
        <div class="card-content">
          <h3>总指令数</h3>
          <div class="card-value">{{ formatNumber(getTotalTestStepsCount(testSteps)) }}</div>
          <p class="card-desc">所有步骤的指令数总和</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="card-icon">🔋</div>
        <div class="card-content">
          <h3>总功耗</h3>
          <div class="card-value">{{ formatEnergy(getTotalTestStepsCount(testSteps)) }}</div>
          <p class="card-desc">预估的总功耗消耗</p>
        </div>
      </div>
      
      <!-- <div class="stat-card">
        <div class="card-icon">📈</div>
        <div class="card-content">
          <h3>平均负载</h3>
          <div class="card-value">{{ formatNumber(Math.round(getTotalTestStepsCount(testSteps) / testSteps.length)) }}</div>
          <p class="card-desc">每个步骤的平均指令数</p>
        </div>
      </div> -->
    </div>
    
    <!-- 全局图表 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">全局负载分布</span>
          </h3>
          <PieChart :chart-data="scenePieData" :title="pieChartTitle" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">步骤负载对比</span>
          </h3>
          <BarChart :chart-data="perfData" />
        </div>
      </el-col>
    </el-row>
    
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">负载趋势（柱状图）</span>
          </h3>
          <LineChart :chart-data="perfData" :series-type="'bar'" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">负载趋势（折线图）</span>
          </h3>
          <LineChart :chart-data="perfData" :series-type="'line'" />
        </div>
      </el-col>
    </el-row>

    <!-- 步骤概览表格 -->
    <div class="data-panel">
      <h3 class="panel-title">
        <span class="version-tag">步骤概览</span>
      </h3>
      <el-table :data="testSteps" style="width: 100%" stripe>
        <el-table-column prop="id" label="步骤编号" width="100" />
        <el-table-column prop="step_name" label="步骤名称" min-width="200" />
        <el-table-column label="指令数" width="150">
          <template #default="scope">
            {{ formatInstructions(scope.row.count) }}
          </template>
        </el-table-column>
        <el-table-column label="功耗估算" width="150">
          <template #default="scope">
            {{ formatEnergyValue(scope.row.count) }}
          </template>
        </el-table-column>
        <el-table-column label="占比" width="100">
          <template #default="scope">
            {{ ((scope.row.count / getTotalTestStepsCount(testSteps)) * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewStepDetail(scope.row.id)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import PieChart from '../../common/charts/PieChart.vue';
import BarChart from '../../common/charts/BarChart.vue';
import LineChart from '../../common/charts/LineChart.vue';
import { useJsonDataStore } from '../../../stores/jsonDataStore.ts';
import { processJson2PieChartData } from '@/utils/jsonUtil.ts';
import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const basicInfo = jsonDataStore.basicInfo;
const perfData = jsonDataStore.perfData;

console.log('负载总览组件获取到的 JSON 数据:');

const testSteps = ref(
  perfData!.steps.map((step, index) => ({
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }))
);

interface TestStep {
  id: number;
  step_name: string;
  count: number;
  round: number;
  perf_data_path: string;
}

const performanceData = ref({
  app_name: basicInfo!.app_name,
  rom_version: basicInfo!.rom_version,
  app_version: basicInfo!.app_version,
  scene: basicInfo!.scene,
});

const getTotalTestStepsCount = (testSteps: TestStep[]) => {
  let total = 0;
  testSteps.forEach((step) => {
    total += step.count;
  });
  return total;
};

// 格式化数字
const formatNumber = (num: number) => {
  return num.toLocaleString();
};

// 格式化功耗信息
const formatEnergy = (milliseconds: number) => {
  const energy = calculateEnergyConsumption(milliseconds);
  return `${energy} mAs`;
};

const formatEnergyValue = (milliseconds: number) => {
  const energy = calculateEnergyConsumption(milliseconds);
  return `${energy} mAs`;
};

// 表格格式化函数
const formatInstructions = (cellValue: number) => {
  return formatNumber(cellValue);
};

const scenePieData = ref(processJson2PieChartData(perfData!, 0));
const pieChartTitle = perfData?.steps[0].data[0].eventType == 0 ? 'cycles' : 'instructions';

// 事件处理
const emit = defineEmits<{
  pageChange: [page: string];
}>();

const viewStepDetail = (stepId: number) => {
  // 跳转到对应的负载分析步骤页面
  const targetPage = `perf_step_${stepId}`;
  emit('pageChange', targetPage);
};

</script>

<style scoped>
.load-overview-container {
  padding: 20px;
  background: #f5f7fa;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin: 24px 0;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: transform 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.card-icon {
  font-size: 32px;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.card-content h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #606266;
  font-weight: 500;
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.card-desc {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.data-panel {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.version-tag {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 500;
}

.beautified-descriptions {
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 24px;
}

.beautified-descriptions .el-descriptions__title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.description-item-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-box {
  background: linear-gradient(135deg, #e7f3fe 0%, #f0f8ff 100%);
  border-left: 6px solid #667eea;
  padding: 16px;
  margin-bottom: 24px;
  font-family: Arial, sans-serif;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-radius: 8px;
}

.info-box p {
  margin: 0;
  color: #333;
  line-height: 1.6;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .load-overview-container {
    padding: 16px;
  }
  
  .stats-cards {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .stat-card {
    padding: 20px;
  }
  
  .card-icon {
    font-size: 28px;
    width: 50px;
    height: 50px;
  }
  
  .card-value {
    font-size: 20px;
  }
}
</style>
