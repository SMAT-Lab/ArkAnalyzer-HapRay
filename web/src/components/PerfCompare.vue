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
        <!-- 进程负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程负载</span>
          </h3>
          <PerfProcessTable :stepId="currentStepIndex" :data="filteredProcessesPerformanceData"
            :hideColumn="isHidden" />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="24">
        <!-- 线程负载表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">线程负载</span>
          </h3>
          <PerfThreadTable :stepId="currentStepIndex" :data="filteredThreadsPerformanceData" :hideColumn="isHidden" />
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
          <PerfFileTable :stepId="currentStepIndex" :data="filteredFilesPerformanceData" :hideColumn="isHidden" />
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
          <PerfFileTable :stepId="currentStepIndex" :data="increaseFilesPerformanceData" :hideColumn="hidden" />
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
import PerfProcessTable, { type ProcessDataItem } from './PerfProcessTable.vue';
import PerfThreadTable, { type ThreadDataItem } from './PerfThreadTable.vue';
import PerfFileTable, { type FileDataItem } from './PerfFileTable.vue';
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
const json = replaceThreadNulls(jsonDataStore.jsonData!);
const compareJson = replaceThreadNulls(jsonDataStore.compareJsonData!);

/**
 * 校验并替换JSON对象中所有key为'thread'且值为null的项为'unknown'
 * @param data - 待处理的JSON对象或数组
 * @returns 处理后的新对象（原对象不会被修改）
 */
function replaceThreadNulls<T extends object | any[]>(data: T): T {
  // 处理数组类型
  if (Array.isArray(data)) {
    return data.map(item => 
      typeof item === 'object' && item !== null 
        ? replaceThreadNulls(item) 
        : item
    ) as T;
  }

  // 处理普通对象类型
  if (typeof data === 'object' && data !== null) {
    const result: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(data)) {
      // 如果key是'thread'且值为null，替换为'unknown'
      if (key === 'thread' && value === null) {
        result[key] = 'unknown';
      } 
      // 否则递归处理嵌套对象
      else if (typeof value === 'object' && value !== null) {
        result[key] = replaceThreadNulls(value);
      } 
      // 基本类型直接赋值
      else {
        result[key] = value;
      }
    }
    
    return result as T;
  }

  // 非对象类型直接返回
  return data;
}

const mergedJson = mergeJSONData(json!, compareJson!);


/**
 * 创建对象映射，提高查找效率
 * @param items 数组项
 * @param keySelector 键选择器函数
 * @returns 映射表
 */
function createMap<T, K extends string | number>(items: T[] | undefined, keySelector: (item: T) => K): Map<K, T> {
  const map = new Map<K, T>();
  items?.forEach(item => map.set(keySelector(item), item));
  return map;
}

/**
 * 合并两个数组，生成包含count和compareCount的新结构
 * @param array1 第一个数组
 * @param array2 第二个数组
 * @param keySelector 键选择器函数
 * @param mergeItem 合并单个项的函数
 * @returns 合并后的数组
 */
function mergeArrays<T1, T2, R>(
  array1: T1[] | undefined,
  array2: T2[] | undefined,
  keySelector: (item: T1 | T2) => string | number,
  mergeItem: (item1: T1 | undefined, item2: T2 | undefined) => R
): R[] {
  const map1 = createMap(array1, keySelector as (item: T1) => string | number);
  const map2 = createMap(array2, keySelector as (item: T2) => string | number);

  const allKeys = [...new Set([...map1.keys(), ...map2.keys()])];

  return allKeys.map(key => {
    const item1 = map1.get(key);
    const item2 = map2.get(key);
    return mergeItem(item1, item2);
  });
}

/**
 * 合并两个JSONData类型的数据
 * @param data1 第一个数据
 * @param data2 第二个数据
 * @returns 合并后的数据
 */
function mergeJSONData(data1: JSONData, data2: JSONData): MergeJSONData {
  return {
    app_id: data1.app_id,
    app_name: data1.app_name,
    app_version: data1.app_version,
    scene: data1.scene,
    timestamp: data1.timestamp,
    perfDataPath: [...new Set([...data1.perfDataPath, ...data2.perfDataPath])],
    perfDbPath: [...new Set([...data1.perfDbPath, ...data2.perfDbPath])],
    htracePath: [...new Set([...data1.htracePath, ...data2.htracePath])],
    categories: [...new Set([...data1.categories, ...data2.categories])],
    steps: mergeArrays(
      data1.steps,
      data2.steps,
      step => step.step_id,
      (step1, step2) => ({
        step_name: step1?.step_name || step2?.step_name || '',
        step_id: step1?.step_id || step2!.step_id,
        count: step1?.count || -1,
        compareCount: step2?.count || -1,
        round: step1?.round || step2?.round || 0,
        perf_data_path: step1?.perf_data_path || step2?.perf_data_path || '',
        data: mergeArrays(
          step1?.data,
          step2?.data,
          data => data.category,
          (data1, data2) => ({
            category: data1?.category || data2!.category,
            count: data1?.count || -1,
            compareCount: data2?.count || -1,
            processes: mergeArrays(
              data1?.processes,
              data2?.processes,
              process => process.process,
              (process1, process2) => ({
                process: process1?.process || process2!.process,
                count: process1?.count || -1,
                compareCount: process2?.count || -1,
                threads: mergeArrays(
                  process1?.threads,
                  process2?.threads,
                  thread => thread.thread,
                  (thread1, thread2) => ({
                    thread: thread1?.thread || thread2!.thread,
                    count: thread1?.count || -1,
                    compareCount: thread2?.count || -1,
                    files: mergeArrays(
                      thread1?.files,
                      thread2?.files,
                      file => file.file,
                      (file1, file2) => ({
                        file: file1?.file || file2!.file,
                        count: file1?.count || -1,
                        compareCount: file2?.count || -1,
                        symbols: mergeArrays(
                          file1?.symbols,
                          file2?.symbols,
                          symbol => symbol.symbol,
                          (symbol1, symbol2) => ({
                            symbol: symbol1?.symbol || symbol2!.symbol,
                            count: symbol1?.count || -1,
                            compareCount: symbol2?.count || -1
                          })
                        )
                      })
                    )
                  })
                )
              })
            )
          })
        )
      })
    )
  };
}


const processDataItem: ProcessDataItem[] = convertToProcessDataItems(mergedJson);
const threadDataItem: ThreadDataItem[] = convertToThreadDataItems(mergedJson);
const fileDataItem: FileDataItem[] = convertToFileDataItems(mergedJson);
const symbolDataItem: SymbolDataItem[] = convertToSymbolDataItems(mergedJson);

const increaseFile: FileDataItem[] = fileDataItem.filter((item) => (item.instructions === 0 || item.instructions === -1) && item.compareInstructions !== 0).map((item) => ({
  stepId: item.stepId,
  category: item.category,
  instructions: item.compareInstructions,
  compareInstructions: 0,
  increaseInstructions: 0,
  increasePercentage: 0,
  file: item.file,
  thread: item.thread,
  process: item.process
}));
const increaseSymbol: SymbolDataItem[] = symbolDataItem.filter((item) => (item.instructions === 0 || item.instructions === -1) && item.compareInstructions !== 0).map((item) => ({
  stepId: item.stepId,
  category: item.category,
  instructions: item.compareInstructions,
  compareInstructions: 0,
  increaseInstructions: 0,
  increasePercentage: 0,
  symbol: item.symbol,
  file: item.file,
  thread: item.thread,
  process: item.process
}));


/**
 * 将MergeJSONData类型数据转换为ProcessDataItem数组
 * @param mergedData 合并后的JSON数据
 * @returns ProcessDataItem数组
 */
function convertToProcessDataItems(mergedData: MergeJSONData): ProcessDataItem[] {
  const processDataMap = new Map<string, ProcessDataItem>();

  // 遍历所有步骤
  mergedData.steps.forEach(step => {
    // 遍历步骤中的所有数据类别
    step.data.forEach(data => {

      // 遍历子数据中的所有进程
      data.processes.forEach(process => {
        // 生成唯一键（步骤ID + 类别 + 进程名 + 线程名 + 文件名）
        const key = `${step.step_id}-${data.category}-${process.process}`;

        // 累加文件层级的count
        const existingItem = processDataMap.get(key);

        if (existingItem) {
          // 如果已存在，累加instructions和compareInstructions
          existingItem.instructions += process.count;
          existingItem.compareInstructions += process.compareCount;
        } else {
          // 如果不存在，创建新的FileDataItem
          processDataMap.set(key, {
            stepId: step.step_id,
            category: mergedData.categories[data.category],
            instructions: process.count,
            compareInstructions: process.compareCount,
            increaseInstructions: 0, // 初始化为0，后续计算
            increasePercentage: 0,   // 初始化为0，后续计算
            process: process.process
          });
        }
      });

    });
  });

  // 计算increaseInstructions和increasePercentage
  const processDataItems = Array.from(processDataMap.values());
  processDataItems.forEach(item => {
    // 计算增加的指令数
    item.increaseInstructions = item.compareInstructions - item.instructions;

    // 计算增加的百分比，避免除以零的情况
    if (item.instructions !== 0) {
      let percentage = (item.increaseInstructions / item.instructions) * 100;
      if (item.instructions === -1) {
        percentage = (item.increaseInstructions - 1) * 100;
      }
      item.increasePercentage = Number.parseFloat(percentage.toFixed(2))
    } else {
      // 如果instructions为0，根据compareInstructions的值设置百分比
      item.increasePercentage = item.compareInstructions > 0 ? Infinity : 0;
    }
  });

  return processDataItems;
}


/**
 * 将MergeJSONData类型数据转换为ThreadDataItem数组
 * @param mergedData 合并后的JSON数据
 * @returns ThreadDataItem数组
 */
function convertToThreadDataItems(mergedData: MergeJSONData): ThreadDataItem[] {
  const threadDataMap = new Map<string, ThreadDataItem>();

  // 遍历所有步骤
  mergedData.steps.forEach(step => {
    // 遍历步骤中的所有数据类别
    step.data.forEach(data => {

      // 遍历子数据中的所有进程
      data.processes.forEach(process => {
        // 遍历进程中的所有线程
        process.threads.forEach(thread => {
          // 生成唯一键（步骤ID + 类别 + 进程名 + 线程名 + 文件名）
          const key = `${step.step_id}-${data.category}-${process.process}-${thread.thread}`;

          // 累加文件层级的count
          const existingItem = threadDataMap.get(key);

          if (existingItem) {
            // 如果已存在，累加instructions和compareInstructions
            existingItem.instructions += thread.count;
            existingItem.compareInstructions += thread.compareCount;
          } else {
            // 如果不存在，创建新的FileDataItem
            threadDataMap.set(key, {
              stepId: step.step_id,
              category: mergedData.categories[data.category],
              instructions: thread.count,
              compareInstructions: thread.compareCount,
              increaseInstructions: 0, // 初始化为0，后续计算
              increasePercentage: 0,   // 初始化为0，后续计算
              thread: thread.thread,
              process: process.process
            });
          }

        });
      });

    });
  });

  // 计算increaseInstructions和increasePercentage
  const threadDataItems = Array.from(threadDataMap.values());
  threadDataItems.forEach(item => {
    // 计算增加的指令数
    item.increaseInstructions = item.compareInstructions - item.instructions;

    // 计算增加的百分比，避免除以零的情况
    if (item.instructions !== 0) {
      let percentage = (item.increaseInstructions / item.instructions) * 100;
      if (item.instructions === -1) {
        percentage = (item.increaseInstructions - 1) * 100;
      }
      item.increasePercentage = Number.parseFloat(percentage.toFixed(2))
    } else {
      // 如果instructions为0，根据compareInstructions的值设置百分比
      item.increasePercentage = item.compareInstructions > 0 ? Infinity : 0;
    }
  });

  return threadDataItems;
}

/**
 * 将MergeJSONData类型数据转换为FileDataItem数组
 * @param mergedData 合并后的JSON数据
 * @returns FileDataItem数组
 */
function convertToFileDataItems(mergedData: MergeJSONData): FileDataItem[] {
  const fileDataMap = new Map<string, FileDataItem>();

  // 遍历所有步骤
  mergedData.steps.forEach(step => {
    // 遍历步骤中的所有数据类别
    step.data.forEach(data => {

      // 遍历子数据中的所有进程
      data.processes.forEach(process => {
        // 遍历进程中的所有线程
        process.threads.forEach(thread => {
          // 遍历线程中的所有文件
          thread.files.forEach(file => {
            // 生成唯一键（步骤ID + 类别 + 进程名 + 线程名 + 文件名）
            const key = `${step.step_id}-${data.category}-${process.process}-${thread.thread}-${file.file}`;

            // 累加文件层级的count
            const existingItem = fileDataMap.get(key);

            if (existingItem) {
              // 如果已存在，累加instructions和compareInstructions
              existingItem.instructions += file.count;
              existingItem.compareInstructions += file.compareCount;
            } else {
              // 如果不存在，创建新的FileDataItem
              fileDataMap.set(key, {
                stepId: step.step_id,
                category: mergedData.categories[data.category],
                instructions: file.count,
                compareInstructions: file.compareCount,
                increaseInstructions: 0, // 初始化为0，后续计算
                increasePercentage: 0,   // 初始化为0，后续计算
                file: file.file,
                thread: thread.thread,
                process: process.process
              });
            }
          });
        });
      });

    });
  });

  // 计算increaseInstructions和increasePercentage
  const fileDataItems = Array.from(fileDataMap.values());
  fileDataItems.forEach(item => {
    // 计算增加的指令数
    item.increaseInstructions = item.compareInstructions - item.instructions;

    // 计算增加的百分比，避免除以零的情况
    if (item.instructions !== 0) {
      let percentage = (item.increaseInstructions / item.instructions) * 100;
      if (item.instructions === -1) {
        percentage = (item.increaseInstructions - 1) * 100;
      }
      item.increasePercentage = Number.parseFloat(percentage.toFixed(2))
    } else {
      // 如果instructions为0，根据compareInstructions的值设置百分比
      item.increasePercentage = item.compareInstructions > 0 ? Infinity : 0;
    }
  });

  return fileDataItems;
}



/**
 * 将MergeJSONData类型数据转换为SymbolDataItem数组
 * @param mergedData 合并后的JSON数据
 * @returns FileDataItem数组
 */
function convertToSymbolDataItems(mergedData: MergeJSONData): SymbolDataItem[] {
  const symbolDataMap = new Map<string, SymbolDataItem>();

  // 遍历所有步骤
  mergedData.steps.forEach(step => {
    // 遍历步骤中的所有数据类别
    step.data.forEach(data => {

      // 遍历子数据中的所有进程
      data.processes.forEach(process => {
        // 遍历进程中的所有线程
        process.threads.forEach(thread => {
          // 遍历线程中的所有文件
          thread.files.forEach(file => {
            //遍历文件中的所有符号
            file.symbols.forEach(symbol => {
              // 生成唯一键（步骤ID + 类别 + 进程名 + 线程名 + 文件名 + 符号名）
              const key = `${step.step_id}-${data.category}-${process.process}-${thread.thread}-${file.file}-${symbol.symbol}`;

              // 累加文件层级的count
              const existingItem = symbolDataMap.get(key);

              if (existingItem) {
                // 如果已存在，累加instructions和compareInstructions
                existingItem.instructions += symbol.count;
                existingItem.compareInstructions += symbol.compareCount;
              } else {
                // 如果不存在，创建新的FileDataItem
                symbolDataMap.set(key, {
                  stepId: step.step_id,
                  category: mergedData.categories[data.category],
                  instructions: symbol.count,
                  compareInstructions: symbol.compareCount,
                  increaseInstructions: 0, // 初始化为0，后续计算
                  increasePercentage: 0,   // 初始化为0，后续计算
                  symbol: symbol.symbol,
                  file: file.file,
                  thread: thread.thread,
                  process: process.process
                });
              }
            });
          });
        });
      });

    });
  });
  // 计算increaseInstructions和increasePercentage
  const symbolDataItems = Array.from(symbolDataMap.values());
  symbolDataItems.forEach(item => {
    // 计算增加的指令数
    item.increaseInstructions = item.compareInstructions - item.instructions;

    // 计算增加的百分比，避免除以零的情况
    if (item.instructions !== 0) {
      let percentage = (item.increaseInstructions / item.instructions) * 100;
      if (item.instructions === -1) {
        percentage = (item.increaseInstructions - 1) * 100;
      }
      item.increasePercentage = Number.parseFloat(percentage.toFixed(2))
    } else {
      // 如果instructions为0，根据compareInstructions的值设置百分比
      item.increasePercentage = item.compareInstructions > 0 ? Infinity : 0;
    }
  });

  return symbolDataItems;

}

const performanceData = ref({
  rom_version: json!.rom_version,
  id: json!.app_id,
  name: json!.app_name,
  version: json!.app_version,
  scene: json!.scene,
  instructions: json!.steps.flatMap((step) =>
    step.data.flatMap((item) =>
      item.processes.flatMap((process) =>
        process.threads.flatMap((thread) =>
          thread.files.flatMap((file) =>
            file.symbols.map((symbol) => ({
              stepId: step.step_id,
              instructions: symbol.count,
              compareInstructions: 0,
              increaseInstructions: 0,
              increasePercentage: 0,
              symbol: symbol.symbol,
              file: file.file,
              thread: thread.thread,
              process: process.process,
              category: json!.categories[item.category],
            })
            )
          )
        )
      )
    )
  )
});

const comparePerformanceData = ref({
  rom_version: compareJson!.rom_version,
  id: compareJson!.app_id,
  name: compareJson!.app_name,
  version: compareJson!.app_version,
  scene: compareJson!.scene,
  instructions: compareJson!.steps.flatMap((step) =>
    step.data.flatMap((item) =>
      item.processes.flatMap((process) =>
        process.threads.flatMap((thread) =>
          thread.files.flatMap((file) =>
            file.symbols.map((symbol) => ({
              stepId: step.step_id,
              instructions: symbol.count,
              compareInstructions: 0,
              increaseInstructions: 0,
              increasePercentage: 0,
              symbol: symbol.symbol,
              file: file.file,
              thread: thread.thread,
              process: process.process,
              category: json!.categories[item.category],
            })
            )
          )
        )
      )
    )
  )
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


// 进程负载表格
const filteredProcessesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return processDataItem.sort((a, b) => b.instructions - a.instructions);
  }
  return processDataItem
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
// 线程负载表格
const filteredThreadsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return threadDataItem.sort((a, b) => b.instructions - a.instructions);
  }
  return threadDataItem
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});
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

        // 合并 processes
        const processesDataMap = new Map<string, typeof existingItem.processes[0]>();
        existingItem.processes.forEach(process => processesDataMap.set(process.process, process));
        item.processes.forEach(process => {
          if (processesDataMap.has(process.process)) {
            processesDataMap.get(process.process)!.count += process.count;

            // 合并 threads
            const threadsDataMap = new Map<string, typeof process.threads[0]>();
            processesDataMap.get(process.process)!.threads.forEach(thread => threadsDataMap.set(thread.thread, thread));
            process.threads.forEach(thread => {
              if (threadsDataMap.has(thread.thread)) {
                threadsDataMap.get(thread.thread)!.count += thread.count;

                // 合并 files
                const filesMap = new Map<string, typeof thread.files[0]>();
                threadsDataMap.get(thread.thread)!.files.forEach(file => filesMap.set(file.file, file));
                thread.files.forEach(file => {
                  if (filesMap.has(file.file)) {
                    filesMap.get(file.file)!.count += file.count;
                  } else {
                    threadsDataMap.get(thread.thread)!.files.push({ ...file });
                  }
                });
              } else {
                processesDataMap.get(process.process)!.threads.push({ ...thread });
              }
            });
          } else {
            existingItem.processes.push({ ...process });
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

    // 处理每个 data 中的 processes 数组
    step.data.forEach(dataItem => {
      const processesDataMap = new Map<string, typeof dataItem.processes[0]>();
      dataItem.processes.forEach(process => {
        const existingSubData = processesDataMap.get(process.process);
        if (existingSubData) {
          existingSubData.count += process.count;
        } else {
          processesDataMap.set(process.process, { ...process });
        }
      });
      dataItem.processes = Array.from(processesDataMap.values());
      // 对 processes 数组按照 name 排序
      dataItem.processes.sort((a, b) => a.process.localeCompare(b.process));

      // 处理每个 processes 中的 threads 数组
      dataItem.processes.forEach(process => {
        const threadsMap = new Map<string, typeof process.threads[0]>();
        process.threads.forEach(thread => {
          const existingFile = threadsMap.get(thread.thread);
          if (existingFile) {
            existingFile.count += thread.count;
          } else {
            threadsMap.set(thread.thread, { ...thread });
          }
        });
        process.threads = Array.from(threadsMap.values());
        // 对 threads 数组按照 thread 排序
        process.threads.sort((a, b) => a.thread.localeCompare(b.thread));

        // 处理每个 threads 中的 files 数组
        process.threads.forEach(thread => {
          const filesMap = new Map<string, typeof thread.files[0]>();
          thread.files.forEach(file => {
            const existingSymbol = filesMap.get(file.file);
            if (existingSymbol) {
              existingSymbol.count += file.count;
            } else {
              filesMap.set(file.file, { ...file });
            }
          });
          thread.files = Array.from(filesMap.values());
          // 对 symbols 数组按照 symbol 排序
          thread.files.sort((a, b) => a.file.localeCompare(b.file));
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