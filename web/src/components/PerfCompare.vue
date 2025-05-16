<template>
  <div class="performance-comparison">
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
    <el-row :gutter="20">
      <el-col :span="12">
        <el-descriptions :title="performanceData.name" :column="1" class="beautified-descriptions">
          <el-descriptions-item label="系统版本：">{{ performanceData.rom_version }}</el-descriptions-item>
          <el-descriptions-item label="应用版本：">{{ performanceData.version }}</el-descriptions-item>
          <el-descriptions-item label="场景名称：">{{ performanceData.scene }}</el-descriptions-item>
        </el-descriptions>
      </el-col>
      <el-col :span="12">
        <el-descriptions :title="comparePerformanceData.name" :column="1" class="beautified-descriptions">
          <el-descriptions-item label="系统版本：">{{ comparePerformanceData.rom_version }}</el-descriptions-item>
          <el-descriptions-item label="应用版本：">{{ comparePerformanceData.version }}</el-descriptions-item>
          <el-descriptions-item label="场景名称：">{{ comparePerformanceData.scene }}</el-descriptions-item>
        </el-descriptions>
      </el-col>
    </el-row>
    <!--场景负载饼状图 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <PieChart :chart-data="scenePieData" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <PieChart :chart-data="compareScenePieData" />
        </div>
      </el-col>
    </el-row>
    <!-- 场景负载增长卡片 -->
    <el-row :gutter="20">
      <el-col :span="24">

        <div class="card-container" style="margin-bottom:10px;">
          <div v-for="item in sceneDiff.values()" :key="item.category" class="category-card">
            <el-card>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 16px; font-weight: bold;">{{ item.category }}</span>
                  <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                    {{ item.percentage }}
                  </span>
                </div>
              </template>
              <div style="padding: 16px;">
                <p>
                  负载增长：<br>
                  <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">{{ item.diff }}</span>
                </p>
              </div>
            </el-card>
          </div>
        </div>
      </el-col>
    </el-row>
    <!-- 场景负载对比折线图 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <LineChart :chartData="compareSceneLineChartData" :seriesType="RightLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>
    <!-- 步骤负载排名横向柱状图 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <BarChart :chart-data="json" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <BarChart :chart-data="compareJson" />
        </div>
      </el-col>
    </el-row>
    <!-- 步骤负载柱状图 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="json" :seriesType="LeftLineChartSeriesType" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="compareJson" :seriesType="LeftLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>
    <!-- 步骤负载折线图 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="json" :seriesType="RightLineChartSeriesType" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="compareJson" :seriesType="RightLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>
    <!-- 测试步骤导航 -->
    <div class="step-nav">
      <div :class="[
        'step-item',
        {
          active: currentStepIndex === 0,
        },
      ]" @click="handleStepClick(0)">
        <div class="step-header">
          <span class="step-order">STEP 0</span>
          <span class="step-duration">{{ getTotalTestStepsCount(testSteps) }}</span>
        </div>
        <div class="step-name">全部步骤</div>
      </div>
      <div v-for="(step, index) in testSteps" :key="index" :class="[
        'step-item',
        {
          active: currentStepIndex === step.id,
        },
      ]" @click="handleStepClick(step.id)">
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>
          <span class="step-duration">{{ formatDuration(step.count) }}</span>
        </div>
        <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
        <div class="step-name">测试轮次：{{ step.round }}</div>
        <!-- <div class="step-name" :title="step.perf_data_path">perf文件位置：{{ step.perf_data_path }}</div> -->
      </div>
    </div>

    <!-- 性能对比区域 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 基准步骤饼图 -->
        <div class="data-panel">
          <PieChart :stepId="currentStepIndex" :chart-data="stepPieData" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 对比步骤饼图 -->
        <div class="data-panel">
          <PieChart :stepId="currentStepIndex" :chart-data="compareStepPieData" />
        </div>
      </el-col>
    </el-row>
    <!-- 步骤负载增长卡片 -->
    <el-row :gutter="20">
      <el-col :span="24">

        <div class="card-container" style="margin-bottom:10px;">
          <div v-for="item in stepDiff.values()" :key="item.category" class="category-card">
            <el-card>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 16px; font-weight: bold;">{{ item.category }}</span>
                  <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                    {{ item.percentage }}
                  </span>
                </div>
              </template>
              <div style="padding: 16px;">
                <p>
                  负载增长：<br>
                  <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">{{ item.diff }}</span>
                </p>
              </div>
            </el-card>
          </div>
        </div>
      </el-col>
    </el-row>
    <!-- 步骤负载对比折线图-->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <LineChart :stepId="currentStepIndex" :chartData="compareLineChartData"
            :seriesType="RightLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="24">
        <!-- 文件负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfTable :stepId="currentStepIndex" :data="filteredFilesPerformanceData" :hideColumn="isHidden" />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="24">
        <!-- 函数负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载</span>
          </h3>
          <PerfSymbolTable :stepId="currentStepIndex" :data="filteredSymbolsPerformanceData" :hideColumn="isHidden" />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 新增文件负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">新增文件负载表格</span>
          </h3>
          <PerfTable :stepId="currentStepIndex" :data="increaseFilesPerformanceData" :hideColumn="hidden" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 新增符号负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">新增符号负载表格</span>
          </h3>
          <PerfSymbolTable :stepId="currentStepIndex" :data="increaseSymbolsPerformanceData" :hideColumn="hidden" />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 基线函数负载top10表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">基线函数负载top10</span>
          </h3>
          <PerfSymbolTable :stepId="currentStepIndex" :data="filteredBaseSymbolsPerformanceData" :hideColumn="hidden" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 对比函数负载top10表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">对比函数负载top10</span>
          </h3>
          <PerfSymbolTable :stepId="currentStepIndex" :data="filteredCompareSymbolsPerformanceData"
            :hideColumn="hidden" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import PerfTable, { type FileDataItem } from './PerfTable.vue';
import PerfSymbolTable, { type SymbolDataItem } from './PerfSymbolTable.vue';
import PieChart from './PieChart.vue';
import BarChart from './BarChart.vue';
import LineChart from './LineChart.vue';
import { useJsonDataStore, type JSONData, type MergeJSONData } from '../stores/jsonDataStore.ts';

interface SceneLoadDiff {
  category: string;
  diff: number;
  percentage: string;
}
//初始化数据
const isHidden = false;
const hidden = true;
const LeftLineChartSeriesType = 'bar';
const RightLineChartSeriesType = 'line';
const currentStepIndex = ref(0);

// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 JSON 数据
const json = jsonDataStore.jsonData;
const compareJson = jsonDataStore.compareJsonData;


const fileDataItem: FileDataItem[] = convertToFileDataItem(json!, compareJson!);
const symbolDataItem: SymbolDataItem[] = convertToSymbolDataItem(json!, compareJson!);

const increaseFile: FileDataItem[] = collectZeroToNonZeroFiles(json!, compareJson!);
const increaseSymbol: SymbolDataItem[] = collectZeroToNonZeroSymbols(json!, compareJson!);


/**
 * 将 JSONData 转换为 FileDataItem 数组（解析到file层，包含两个数据源的所有文件）
 */
function convertToFileDataItem(
  data: JSONData,
  compareData?: JSONData
): FileDataItem[] {
  const dataItems: FileDataItem[] = [];

  // 创建主数据源的步骤映射
  const primaryStepMap = new Map<number, JSONData['steps'][0]>(
    data.steps.map(step => [step.step_id, step])
  );

  // 创建对比数据源的步骤映射
  const compareStepMap = compareData
    ? new Map<number, JSONData['steps'][0]>(
      compareData.steps.map(step => [step.step_id, step])
    )
    : null;

  // 获取所有步骤ID的并集
  const allStepIds = new Set([
    ...primaryStepMap.keys(),
    ...(compareStepMap?.keys() || [])
  ]);

  // 处理每个步骤
  allStepIds.forEach(stepId => {
    const primaryStep = primaryStepMap.get(stepId);
    const compareStep = compareStepMap?.get(stepId);

    // 创建category到dataItem的映射
    const primaryDataMap = new Map<number, JSONData['steps'][0]['data'][0]>();
    if (primaryStep) {
      primaryStep.data.forEach(item => {
        primaryDataMap.set(item.category, item);
      });
    }

    const compareDataMap = new Map<number, JSONData['steps'][0]['data'][0]>();
    if (compareStep) {
      compareStep.data.forEach(item => {
        compareDataMap.set(item.category, item);
      });
    }

    // 获取所有category的并集
    const allCategories = new Set([
      ...primaryDataMap.keys(),
      ...compareDataMap.keys()
    ]);

    // 处理每个category
    allCategories.forEach(category => {
      const categoryName = data.categories[category] || `category_${category}`;
      const primaryDataItem = primaryDataMap.get(category);
      const compareDataItem = compareDataMap.get(category);

      // 创建subDataName到subDataItem的映射
      const primarySubDataMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]>();
      if (primaryDataItem) {
        primaryDataItem.subData.forEach(item => {
          primarySubDataMap.set(item.name, item);
        });
      }

      const compareSubDataMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]>();
      if (compareDataItem) {
        compareDataItem.subData.forEach(item => {
          compareSubDataMap.set(item.name, item);
        });
      }

      // 获取所有subDataName的并集
      const allSubDataNames = new Set([
        ...primarySubDataMap.keys(),
        ...compareSubDataMap.keys()
      ]);

      // 处理每个subData
      allSubDataNames.forEach(subDataName => {
        const primarySubData = primarySubDataMap.get(subDataName);
        const compareSubData = compareSubDataMap.get(subDataName);

        // 创建fileName到fileItem的映射
        const primaryFileMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]>();
        if (primarySubData) {
          primarySubData.files.forEach(item => {
            primaryFileMap.set(item.file, item);
          });
        }

        const compareFileMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]>();
        if (compareSubData) {
          compareSubData.files.forEach(item => {
            compareFileMap.set(item.file, item);
          });
        }

        // 获取所有fileName的并集
        const allFileNames = new Set([
          ...primaryFileMap.keys(),
          ...compareFileMap.keys()
        ]);

        // 处理每个文件
        allFileNames.forEach(fileName => {
          const primaryFile = primaryFileMap.get(fileName);
          const compareFile = compareFileMap.get(fileName);

          // 计算指令数（如果文件不存在，指令数为0）
          const instructions = primaryFile
            ? primaryFile.symbols.reduce((sum, symbol) => sum + symbol.count, 0)
            : 0;

          const compareInstructions = compareFile
            ? compareFile.symbols.reduce((sum, symbol) => sum + symbol.count, 0)
            : 0;

          const increaseInstructions = compareInstructions - instructions;
          const increasePercentage = calculatePercentageWithFixed(increaseInstructions, instructions);

          dataItems.push({
            stepId,
            name: fileName,
            category: categoryName,
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage: Number(increasePercentage.toFixed(2))
          });
        });
      });
    });
  });

  return dataItems;
}



/**
 * 收集 data 中指令数为 0 但 compareData 中指令数不为 0 的文件层级信息
 * @param data JSONData 数据源
 * @param compareData 对比数据源
 * @returns 符合条件的文件层级 FileDataItem 数组
 */
function collectZeroToNonZeroFiles(
  data: JSONData,
  compareData: JSONData
): FileDataItem[] {
  const dataItems: FileDataItem[] = [];

  // 构建主数据源的文件映射（stepId-category-subDataName-file → 指令数）
  const primaryFileMap = buildFileInstructionMap(data);

  // 遍历对比数据源的所有文件
  compareData.steps.forEach(step => {
    step.data.forEach(dataItem => {
      const categoryName = compareData.categories[dataItem.category] || `category_${dataItem.category}`;

      dataItem.subData.forEach(subData => {
        subData.files.forEach(file => {
          // 构建文件唯一标识
          const fileKey = `${step.step_id}-${dataItem.category}-${subData.name}-${file.file}`;

          // 计算文件在对比数据源中的总指令数
          const compareInstructions = file.symbols.reduce(
            (sum, symbol) => sum + symbol.count,
            0
          );

          // 跳过对比数据源中指令数为0的文件
          if (compareInstructions === 0) return;

          // 获取主数据源中该文件的指令数
          const instructions = primaryFileMap.get(fileKey) || 0;

          // 仅收集主数据源中指令数为0，对比数据源中不为0的文件
          if (instructions === 0) {
            dataItems.push({
              stepId: step.step_id,
              name: file.file,
              category: categoryName,
              instructions: compareInstructions,
              compareInstructions,
              increaseInstructions: compareInstructions, // 增长值等于对比值
              increasePercentage: Infinity // 无限增长（从0到非0）
            });
          }
        });
      });
    });
  });

  return dataItems;
}

/**
 * 构建文件指令数映射
 */
function buildFileInstructionMap(data: JSONData): Map<string, number> {
  const fileMap = new Map<string, number>();

  data.steps.forEach(step => {
    step.data.forEach(dataItem => {
      dataItem.subData.forEach(subData => {
        subData.files.forEach(file => {
          const fileKey = `${step.step_id}-${dataItem.category}-${subData.name}-${file.file}`;
          const instructions = file.symbols.reduce(
            (sum, symbol) => sum + symbol.count,
            0
          );
          fileMap.set(fileKey, instructions);
        });
      });
    });
  });

  return fileMap;
}







/**
 * 将 JSONData 转换为 SymbolDataItem 数组（解析到symbol层，包含文件信息）
 * @param data JSONData 数据源
 * @param compareData 对比数据源（可选）
 * @returns 转换后的 SymbolDataItem 数组
 */
function convertToSymbolDataItem(
  data: JSONData,
  compareData?: JSONData
): SymbolDataItem[] {
  const dataItems: SymbolDataItem[] = [];

  // 创建主数据源的步骤映射
  const primaryStepMap = new Map<number, JSONData['steps'][0]>(
    data.steps.map(step => [step.step_id, step])
  );

  // 创建对比数据源的步骤映射
  const compareStepMap = compareData
    ? new Map<number, JSONData['steps'][0]>(
      compareData.steps.map(step => [step.step_id, step])
    )
    : null;

  // 获取所有步骤ID的并集
  const allStepIds = new Set([
    ...primaryStepMap.keys(),
    ...(compareStepMap?.keys() || [])
  ]);

  // 处理每个步骤
  allStepIds.forEach(stepId => {
    const primaryStep = primaryStepMap.get(stepId);
    const compareStep = compareStepMap?.get(stepId);

    // 创建category到dataItem的映射
    const primaryDataMap = new Map<number, JSONData['steps'][0]['data'][0]>();
    if (primaryStep) {
      primaryStep.data.forEach(item => {
        primaryDataMap.set(item.category, item);
      });
    }

    const compareDataMap = new Map<number, JSONData['steps'][0]['data'][0]>();
    if (compareStep) {
      compareStep.data.forEach(item => {
        compareDataMap.set(item.category, item);
      });
    }

    // 获取所有category的并集
    const allCategories = new Set([
      ...primaryDataMap.keys(),
      ...compareDataMap.keys()
    ]);

    // 处理每个category
    allCategories.forEach(category => {
      const categoryName = data.categories[category] || `category_${category}`;
      const primaryDataItem = primaryDataMap.get(category);
      const compareDataItem = compareDataMap.get(category);

      // 创建subDataName到subDataItem的映射
      const primarySubDataMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]>();
      if (primaryDataItem) {
        primaryDataItem.subData.forEach(item => {
          primarySubDataMap.set(item.name, item);
        });
      }

      const compareSubDataMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]>();
      if (compareDataItem) {
        compareDataItem.subData.forEach(item => {
          compareSubDataMap.set(item.name, item);
        });
      }

      // 获取所有subDataName的并集
      const allSubDataNames = new Set([
        ...primarySubDataMap.keys(),
        ...compareSubDataMap.keys()
      ]);

      // 处理每个subData
      allSubDataNames.forEach(subDataName => {
        const primarySubData = primarySubDataMap.get(subDataName);
        const compareSubData = compareSubDataMap.get(subDataName);

        // 创建fileName到fileItem的映射
        const primaryFileMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]>();
        if (primarySubData) {
          primarySubData.files.forEach(item => {
            primaryFileMap.set(item.file, item);
          });
        }

        const compareFileMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]>();
        if (compareSubData) {
          compareSubData.files.forEach(item => {
            compareFileMap.set(item.file, item);
          });
        }

        // 获取所有fileName的并集
        const allFileNames = new Set([
          ...primaryFileMap.keys(),
          ...compareFileMap.keys()
        ]);

        // 处理每个文件
        allFileNames.forEach(fileName => {
          const primaryFile = primaryFileMap.get(fileName);
          const compareFile = compareFileMap.get(fileName);

          // 创建symbol到symbolItem的映射
          const primarySymbolMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]['symbols'][0]>();
          if (primaryFile) {
            primaryFile.symbols.forEach(item => {
              primarySymbolMap.set(item.symbol, item);
            });
          }

          const compareSymbolMap = new Map<string, JSONData['steps'][0]['data'][0]['subData'][0]['files'][0]['symbols'][0]>();
          if (compareFile) {
            compareFile.symbols.forEach(item => {
              compareSymbolMap.set(item.symbol, item);
            });
          }

          // 获取所有symbol的并集
          const allSymbols = new Set([
            ...primarySymbolMap.keys(),
            ...compareSymbolMap.keys()
          ]);

          // 处理每个符号
          allSymbols.forEach(symbol => {
            const primarySymbol = primarySymbolMap.get(symbol);
            const compareSymbol = compareSymbolMap.get(symbol);

            // 计算指令数（如果符号不存在，指令数为0）
            const instructions = primarySymbol?.count ?? 0;
            const compareInstructions = compareSymbol?.count ?? 0;

            const increaseInstructions = compareInstructions - instructions;
            const increasePercentage = calculatePercentageWithFixed(increaseInstructions, instructions);

            dataItems.push({
              stepId,
              name: symbol, // 使用符号名作为name
              category: categoryName,
              instructions,
              compareInstructions,
              increaseInstructions,
              increasePercentage: Number(increasePercentage.toFixed(2)),
              file: fileName // 添加文件信息
            });
          });
        });
      });
    });
  });

  return dataItems;
}



/**
 * 收集 data 中指令数为 0 但 compareData 中指令数不为 0 的符号层级信息
 * @param data JSONData 数据源
 * @param compareData 对比数据源
 * @returns 符合条件的符号层级 SymbolDataItem 数组
 */
function collectZeroToNonZeroSymbols(
  data: JSONData,
  compareData: JSONData
): SymbolDataItem[] {
  const dataItems: SymbolDataItem[] = [];

  // 构建主数据源的符号映射（stepId-category-subDataName-file-symbol → 指令数）
  const primarySymbolMap = buildSymbolInstructionMap(data);

  // 遍历对比数据源的所有符号
  compareData.steps.forEach(step => {
    step.data.forEach(dataItem => {
      const categoryName = compareData.categories[dataItem.category] || `category_${dataItem.category}`;

      dataItem.subData.forEach(subData => {
        subData.files.forEach(file => {
          file.symbols.forEach(symbol => {
            // 构建符号唯一标识
            const symbolKey = `${step.step_id}-${dataItem.category}-${subData.name}-${file.file}-${symbol.symbol}`;

            // 获取对比数据源中符号的指令数
            const compareInstructions = symbol.count;

            // 跳过对比数据源中指令数为0的符号
            if (compareInstructions === 0) return;

            // 获取主数据源中该符号的指令数
            const instructions = primarySymbolMap.get(symbolKey) || 0;

            // 仅收集主数据源中指令数为0，对比数据源中不为0的符号
            if (instructions === 0) {
              dataItems.push({
                stepId: step.step_id,
                name: symbol.symbol,
                category: categoryName,
                instructions: compareInstructions,
                compareInstructions,
                increaseInstructions: compareInstructions, // 增长值等于对比值
                increasePercentage: Infinity, // 无限增长（从0到非0）
                file: file.file // 保留文件信息
              });
            }
          });
        });
      });
    });
  });

  return dataItems;
}

/**
 * 构建符号指令数映射
 */
function buildSymbolInstructionMap(data: JSONData): Map<string, number> {
  const symbolMap = new Map<string, number>();

  data.steps.forEach(step => {
    step.data.forEach(dataItem => {
      dataItem.subData.forEach(subData => {
        subData.files.forEach(file => {
          file.symbols.forEach(symbol => {
            const symbolKey = `${step.step_id}-${dataItem.category}-${subData.name}-${file.file}-${symbol.symbol}`;
            symbolMap.set(symbolKey, symbol.count);
          });
        });
      });
    });
  });

  return symbolMap;
}












const performanceData = ref({
  rom_version: json!.rom_version,
  id: json!.app_id,
  name: json!.app_name,
  version: json!.app_version,
  scene: json!.scene,
  instructions: json!.steps.flatMap((step) =>
    step.data.flatMap((item) =>
      item.subData.flatMap((subItem) =>
        subItem.files.flatMap((file) =>
          file.symbols.map((symbol) =>
          ({
            stepId: step.step_id,
            instructions: symbol.count!,
            compareInstructions: 0,
            increaseInstructions: 0,
            increasePercentage: 0,
            name: symbol.symbol,
            file: file.file,
            category: compareJson!.categories[item.category],
          })
          )
        )
      )
    )
  ),
});

const comparePerformanceData = ref({
  rom_version: compareJson!.rom_version,
  id: compareJson!.app_id,
  name: compareJson!.app_name,
  version: compareJson!.app_version,
  scene: compareJson!.scene,
  instructions: compareJson!.steps.flatMap((step) =>
    step.data.flatMap((item) =>
      item.subData.flatMap((subItem) =>
        subItem.files.flatMap((file) =>
          file.symbols.map((symbol) =>
          ({
            stepId: step.step_id,
            instructions: symbol.count!,
            compareInstructions: 0,
            increaseInstructions: 0,
            increasePercentage: 0,
            name: symbol.symbol,
            file: file.file,
            category: compareJson!.categories[item.category],
          })
          )
        )
      )
    )
  ),
});

// 场景负载对比折线图
const compareSceneLineChartData = ref();
compareSceneLineChartData.value = selectJSONData(mergeSteps(json!), mergeSteps(compareJson!));

// 场景负载饼状图
const scenePieData = ref();
const compareScenePieData = ref();
scenePieData.value = processJSONData(json);
compareScenePieData.value = processJSONData(compareJson);
// 场景负载增长卡片
const sceneDiff = ref();
sceneDiff.value = calculateCategoryCountDifference(compareSceneLineChartData.value);



//测试步骤导航卡片
const testSteps = ref(
  json!.steps.map((step, index) => ({
    //从1开始
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }))
);

// 全部步骤负载总数 
const getTotalTestStepsCount = (testSteps: any[]) => {
  let total = 0;

  testSteps.forEach((step) => {
    total += step.count;
  });
  return total;
};

// 格式化持续时间的方法
const formatDuration = (milliseconds: any) => {
  return `指令数：${milliseconds}`;
};

// 处理步骤点击事件的方法，切换步骤，更新数据
const handleStepClick = (stepId: any) => {
  currentStepIndex.value = stepId;
  stepPieData.value = processJSONData(json);
  compareStepPieData.value = processJSONData(compareJson);
  compareLineChartData.value = currentStepIndex.value === 0 ? compareSceneLineChartData.value : selectJSONData(json!, compareJson!);
  stepDiff.value = calculateCategoryCountDifference(compareLineChartData.value);
};

// 性能对比区域
// 基线步骤饼图
const stepPieData = ref();
stepPieData.value = processJSONData(json);
// 对比步骤饼图
const compareStepPieData = ref();
compareStepPieData.value = processJSONData(compareJson);
// 步骤负载对比折线图
const compareLineChartData = ref();
compareLineChartData.value = currentStepIndex.value === 0 ? compareSceneLineChartData.value : selectJSONData(json!, compareJson!);
//步骤负载增长卡片
const stepDiff = ref();
stepDiff.value = calculateCategoryCountDifference(compareLineChartData.value);


// 文件负载表格
const filteredFilesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return fileDataItem.sort((a, b) => b.instructions - a.instructions);
  }
  return fileDataItem
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
// 函数负载表格
const filteredSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return symbolDataItem.sort((a, b) => b.instructions - a.instructions);
  }
  return symbolDataItem
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

// 新增文件负载表格
const increaseFilesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return increaseFile.sort((a, b) => b.instructions - a.instructions);
  }
  return increaseFile
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
// 新增函数负载表格
const increaseSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return increaseSymbol.sort((a, b) => b.instructions - a.instructions);
  }
  return increaseSymbol
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
// 基线函数负载top10表格
const filteredBaseSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return performanceData.value.instructions.sort((a, b) => b.instructions - a.instructions);
  }
  return performanceData.value.instructions
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
// 对比函数负载top10表格
const filteredCompareSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return comparePerformanceData.value.instructions.sort((a, b) => b.instructions - a.instructions);
  }
  return comparePerformanceData.value.instructions
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});


// 处理 JSON 数据生成steps饼状图所需数据
function processJSONData(data: JSONData | null) {
  if (data === null) {
    return { legendData: [], seriesData: [] };
  }
  const { categories, steps } = data;
  const categoryCountMap = new Map<string, number>();

  // 初始化每个分类的计数为 0
  categories.forEach((category) => {
    categoryCountMap.set(category, 0);
  });

  // 遍历所有步骤中的数据，累加每个分类的计数
  steps.forEach((step) => {
    if (currentStepIndex.value === 0) {
      step.data.forEach((item) => {
        const categoryName = categories[item.category];
        const currentCount = categoryCountMap.get(categoryName) || 0;
        categoryCountMap.set(categoryName, currentCount + item.count);
      });
    } else {
      if (step.step_id === currentStepIndex.value) {
        step.data.forEach((item) => {
          const categoryName = categories[item.category];
          const currentCount = categoryCountMap.get(categoryName) || 0;
          categoryCountMap.set(categoryName, currentCount + item.count);
        });
      }
    }
  });

  const legendData: string[] = [];
  const seriesData: { name: string; value: number }[] = [];

  // 将分类名称和对应的计数转换为饼状图所需的数据格式
  categoryCountMap.forEach((count, category) => {
    legendData.push(category);
    if (count != 0) {
      seriesData.push({ name: category, value: count });
    }
  });

  return { legendData: legendData, seriesData: seriesData };
}

function mergeSteps(data: JSONData): JSONData {
  if (data.steps.length === 0) {
    return {
      ...data,
      steps: []
    };
  }

  const mergedStep: JSONData['steps'][0] = {
    step_name: '',
    step_id: 0,
    count: 0,
    round: -1,
    perf_data_path: '',
    data: []
  };

  // 合并 step_id 和 count
  data.steps.forEach(step => {
    mergedStep.step_id += step.step_id;
    mergedStep.count += step.count;
  });

  // 合并 data
  const categoryMap = new Map<number, typeof mergedStep.data[0]>();
  data.steps.forEach(step => {
    step.data.forEach(item => {
      if (categoryMap.has(item.category)) {
        const existingItem = categoryMap.get(item.category)!;
        existingItem.count += item.count;

        // 合并 subData
        const subDataMap = new Map<string, typeof existingItem.subData[0]>();
        existingItem.subData.forEach(sub => subDataMap.set(sub.name, sub));
        item.subData.forEach(sub => {
          if (subDataMap.has(sub.name)) {
            subDataMap.get(sub.name)!.count += sub.count;

            // 合并 files
            const fileMap = new Map<string, typeof sub.files[0]>();
            subDataMap.get(sub.name)!.files.forEach(file => fileMap.set(file.file, file));
            sub.files.forEach(file => {
              if (fileMap.has(file.file)) {
                fileMap.get(file.file)!.count += file.count;

                // 合并 symbols
                const symbolMap = new Map<string, typeof file.symbols[0]>();
                fileMap.get(file.file)!.symbols.forEach(symbol => symbolMap.set(symbol.symbol, symbol));
                file.symbols.forEach(symbol => {
                  if (symbolMap.has(symbol.symbol)) {
                    symbolMap.get(symbol.symbol)!.count += symbol.count;
                  } else {
                    fileMap.get(file.file)!.symbols.push({ ...symbol });
                  }
                });
              } else {
                subDataMap.get(sub.name)!.files.push({ ...file });
              }
            });
          } else {
            existingItem.subData.push({ ...sub });
          }
        });
      } else {
        categoryMap.set(item.category, { ...item });
      }
    });
  });

  mergedStep.data = Array.from(categoryMap.values());

  return {
    ...data,
    steps: [mergedStep]
  };
}

// 合并基线和对比数据，根据步骤选择对比内容
function selectJSONData(data1: JSONData, data2: JSONData): JSONData {
  // if(currentStepIndex.value === 0){
  //   return compareSceneLineChartData.value;
  // }
  // 合并 steps 数组
  let mergedSteps = [...data1.steps, ...data2.steps];
  // 对 steps 数组按照 step_id 排序
  mergedSteps.sort((a, b) => a.step_id - b.step_id);
  if (currentStepIndex.value !== 0) {
    mergedSteps = mergedSteps.filter((item) => item.step_id === currentStepIndex.value)
  }

  let isBase = true;
  // 处理每个 step 中的 data 数组
  mergedSteps.forEach(step => {
    if (isBase) {
      if (!step.step_name.includes('基线：')) {
        step.step_name = '基线：' + step.step_name;
      }
      isBase = false;
    } else {
      if (!step.step_name.includes('对比：')) {
        step.step_name = '对比：' + step.step_name;
      }
    }
    const dataMap = new Map<number, typeof step.data[0]>();
    step.data.forEach(dataItem => {
      const existingItem = dataMap.get(dataItem.category);
      if (existingItem) {
        existingItem.count += dataItem.count;
      } else {
        dataMap.set(dataItem.category, { ...dataItem });
      }
    });
    step.data = Array.from(dataMap.values());
    // 对 data 数组按照 category 排序
    step.data.sort((a, b) => a.category - b.category);

    // 处理每个 data 中的 subData 数组
    step.data.forEach(dataItem => {
      const subDataMap = new Map<string, typeof dataItem.subData[0]>();
      dataItem.subData.forEach(subDataItem => {
        const existingSubData = subDataMap.get(subDataItem.name);
        if (existingSubData) {
          existingSubData.count += subDataItem.count;
        } else {
          subDataMap.set(subDataItem.name, { ...subDataItem });
        }
      });
      dataItem.subData = Array.from(subDataMap.values());
      // 对 subData 数组按照 name 排序
      dataItem.subData.sort((a, b) => a.name.localeCompare(b.name));

      // 处理每个 subData 中的 files 数组
      dataItem.subData.forEach(subDataItem => {
        const fileMap = new Map<string, typeof subDataItem.files[0]>();
        subDataItem.files.forEach(fileItem => {
          const existingFile = fileMap.get(fileItem.file);
          if (existingFile) {
            existingFile.count += fileItem.count;
          } else {
            fileMap.set(fileItem.file, { ...fileItem });
          }
        });
        subDataItem.files = Array.from(fileMap.values());
        // 对 files 数组按照 file 排序
        subDataItem.files.sort((a, b) => a.file.localeCompare(b.file));

        // 处理每个 file 中的 symbols 数组
        subDataItem.files.forEach(fileItem => {
          const symbolMap = new Map<string, typeof fileItem.symbols[0]>();
          fileItem.symbols.forEach(symbolItem => {
            const existingSymbol = symbolMap.get(symbolItem.symbol);
            if (existingSymbol) {
              existingSymbol.count += symbolItem.count;
            } else {
              symbolMap.set(symbolItem.symbol, { ...symbolItem });
            }
          });
          fileItem.symbols = Array.from(symbolMap.values());
          // 对 symbols 数组按照 symbol 排序
          fileItem.symbols.sort((a, b) => a.symbol.localeCompare(b.symbol));
        });
      });
    });
  });

  return {
    ...data1,
    steps: mergedSteps
  };
}


function calculateCategoryCountDifference(data: JSONData): SceneLoadDiff[] {
  if (data === undefined) {
    return [];
  }
  // 检查 steps 长度是否至少为 2
  if (data.steps.length < 2) {
    throw new Error('至少需要 2 个 step 才能计算差值');
  }

  const step1 = data.steps[0];
  const step2 = data.steps[1];

  // 构建两个 Map：category -> count
  const categoryMap1 = new Map<number, number>();
  step1.data.forEach(item => categoryMap1.set(item.category, item.count));

  const categoryMap2 = new Map<number, number>();
  step2.data.forEach(item => categoryMap2.set(item.category, item.count));

  const difference: SceneLoadDiff[] = [];

  // 合并所有存在的 category（包括两个 Map 中的所有键）
  const allCategories = new Set([...categoryMap1.keys(), ...categoryMap2.keys()]);
  let baseCount = 0;
  let compareCount = 0;
  allCategories.forEach(category => {
    const count1 = categoryMap1.get(category) || 0; // 不存在时默认 0
    const count2 = categoryMap2.get(category) || 0;
    let diff: SceneLoadDiff = { category: '', diff: 0, percentage: '' };
    diff.category = data.categories[category];
    diff.diff = count2 - count1;
    diff.percentage = calculatePercentageWithFixed(count2 - count1, count1) + '%';
    difference.push(diff);
    baseCount += count1;
    compareCount += count2;
  });

  difference.splice(0, 0, { category: '总值', diff: compareCount - baseCount, percentage: calculatePercentageWithFixed(compareCount - baseCount, baseCount) + '%' });

  return difference;
}

function calculatePercentageWithFixed(part: number, total: number, decimalPlaces: number = 2): number {
  if (total === 0) {
    //throw new Error('总值不能为零');
    total = 1;
  }
  const percentage = (part / total) * 100;
  return Number.parseFloat(percentage.toFixed(decimalPlaces));
}
</script>

<style scoped>
.performance-comparison {
  padding: 20px;
  background: #f5f7fa;
}

/* 步骤导航样式 */
.step-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
  position: sticky;
  top: 0;
  z-index: 9999;
  /* 固定在页面顶部 */
  background-color: white;
  /* 设置背景颜色，避免内容透过 */
}

.step-item {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }

  &.active {
    border: 2px solid #2196f3;
  }
}

.step-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.9em;
}

.step-order {
  color: #2196f3;
  font-weight: bold;
}

.step-duration {
  color: #757575;
}

.step-duration-compare {
  color: #d81b60;
}

.step-name {
  font-weight: 500;
  margin-bottom: 12px;
  white-space: nowrap;
  /* 禁止文本换行 */
  overflow: hidden;
  /* 隐藏超出部分 */
  text-overflow: ellipsis;
  /* 显示省略号 */
}

/* 对比区域样式 */
.comparison-container {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 32px;
}

.data-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px 0;
}

.version-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;

  .data-panel:nth-child(1) & {
    background: #e3f2fd;
    color: #1976d2;
  }

  .data-panel:nth-child(3) & {
    background: #fce4ec;
    color: #d81b60;
  }
}

/* 差异指示器 */
.indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.diff-box {
  width: 120px;
  height: 120px;
  border: 2px solid;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.diff-value {
  font-size: 24px;
  font-weight: bold;
}

.diff-label {
  font-size: 12px;
  color: #757575;
}

.time-diff {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #757575;
}

.beautified-descriptions {
  /* 设置容器的背景颜色和边框 */
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 10px;
}

/* 标题样式 */
.beautified-descriptions .el-descriptions__title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

/* 描述项容器样式 */
.beautified-descriptions .el-descriptions__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 描述项标签样式 */
.beautified-descriptions .el-descriptions__label {
  font-size: 16px;
  font-weight: 500;
  color: #666;
}

/* 描述项内容样式 */
.beautified-descriptions .el-descriptions__content {
  font-size: 16px;
  color: #333;
}

.info-box {
  background-color: #e7f3fe;
  border-left: 6px solid #2196F3;
  padding: 12px;
  margin-bottom: 9px;
  font-family: Arial, sans-serif;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.info-box p {
  margin: 0;
  color: #333;
}

/* 设置卡片容器的样式 */
.card-container {
  display: flex;
  flex-wrap: nowrap;
  /* 禁止换行 */
  gap: 16px;
  /* 卡片之间的间距 */
}

/* 设置卡片的样式 */
.category-card {
  flex-basis: 0;
  /* 初始大小为 0 */
  flex-grow: 1;
  /* 允许卡片根据可用空间扩展 */
}
</style>