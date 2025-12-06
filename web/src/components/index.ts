/**
 * Components 统一导出文件
 * 方便其他模块导入组件
 */

// ==================== 通用组件 ====================
export { default as AppNavigation } from './common/AppNavigation.vue';
export { default as UploadHtml } from './common/UploadHtml.vue';

// 图表组件
export { default as BarChart } from './common/charts/BarChart.vue';
export { default as LineChart } from './common/charts/LineChart.vue';
export { default as PieChart } from './common/charts/PieChart.vue';
export { default as TrendChart } from './common/charts/TrendChart.vue';

// ==================== 单版本分析 ====================

// 负载总览
export { default as PerfLoadOverview } from './single-analysis/overview/PerfLoadOverview.vue';

// 步骤负载分析
export { default as PerfStepLoad } from './single-analysis/step/load/PerfStepLoad.vue';
export { default as PerfLoadAnalysis } from './single-analysis/step/load/PerfLoadAnalysis.vue';
export { default as PerfSingle } from './single-analysis/step/load/PerfSingle.vue';

// 负载分析表格
export { default as PerfProcessTable } from './single-analysis/step/load/tables/PerfProcessTable.vue';
export { default as PerfThreadTable } from './single-analysis/step/load/tables/PerfThreadTable.vue';
export { default as PerfFileTable } from './single-analysis/step/load/tables/PerfFileTable.vue';
export { default as PerfSymbolTable } from './single-analysis/step/load/tables/PerfSymbolTable.vue';

// 帧分析
export { default as FrameAnalysis } from './single-analysis/step/frame/FrameAnalysis.vue';
export { default as PerfFrameAnalysis } from './single-analysis/step/frame/PerfFrameAnalysis.vue';

// 故障树分析
export { default as FaultTreeAnalysis } from './single-analysis/step/fault-tree/FaultTreeAnalysis.vue';

// 火焰图分析
export { default as FlameGraph } from './single-analysis/step/flame/FlameGraph.vue';

// Memory分析
export { default as NativeMemory } from './single-analysis/step/memory/NativeMemory.vue';
export { default as NativeMemoryTable } from './single-analysis/step/memory/NativeMemoryTable.vue';
export { default as MemoryTimelineChart } from './single-analysis/step/memory/MemoryTimelineChart.vue';
export { default as MemoryFlameGraph } from './single-analysis/step/memory/MemoryFlameGraph.vue';
export { default as MemoryOutstandingFlameGraph } from './single-analysis/step/memory/MemoryOutstandingFlameGraph.vue';

// UI动画分析
export { default as PerfUIAnimate } from './single-analysis/step/ui-animate/PerfUIAnimate.vue';
export { default as UIAnimatePhaseAnalysis } from './single-analysis/step/ui-animate/UIAnimatePhaseAnalysis.vue';

// 依赖分析
export { default as ComponentsDeps } from './single-analysis/deps/ComponentsDeps.vue';

// ==================== 版本对比 ====================
export { default as PerfCompare } from './compare/PerfCompare.vue';
export { default as CompareOverview } from './compare/CompareOverview.vue';
export { default as CompareStepLoad } from './compare/CompareStepLoad.vue';
export { default as StepLoadCompare } from './compare/StepLoadCompare.vue';
export { default as DetailDataCompare } from './compare/DetailDataCompare.vue';
export { default as NewDataAnalysis } from './compare/NewDataAnalysis.vue';
export { default as Top10DataCompare } from './compare/Top10DataCompare.vue';
export { default as FaultTreeCompare } from './compare/FaultTreeCompare.vue';
export { default as SceneLoadCompare } from './compare/SceneLoadCompare.vue';

// ==================== 多版本趋势 ====================
export { default as PerfMulti } from './multi-version/PerfMulti.vue';

