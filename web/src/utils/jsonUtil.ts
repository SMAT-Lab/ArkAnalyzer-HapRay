import type { FileDataItem } from "@/components/PerfFileTable.vue";
import type { ProcessDataItem } from "@/components/PerfProcessTable.vue";
import type { SymbolDataItem } from "@/components/PerfSymbolTable.vue";
import type { ThreadDataItem } from "@/components/PerfThreadTable.vue";
import { ComponentCategory, type JSONData } from "@/stores/jsonDataStore";
import pako from 'pako';


// 处理 JSON 数据生成steps饼状图所需数据
export function processJson2PieChartData(jsonData: JSONData, currentStepIndex: number) {
    if (!jsonData) {
        return { legendData: [], seriesData: [] };
    }

    const categoryMap = new Map<ComponentCategory, number>();

    // 处理数据并累加 symbolEvents
    jsonData.steps.forEach(step => {
        if (currentStepIndex === 0 || step.step_id === currentStepIndex) {
            step.data.forEach(item => {
                const category = item.componentCategory;
                const events = item.symbolEvents;
                categoryMap.set(category, (categoryMap.get(category) || 0) + events);
            });
        }
    });

    // 准备按枚举值排序的数据
    const sortedEntries = Array.from(categoryMap.entries())
        .filter(([_, value]) => value !== 0) // 过滤掉值为零的分类
        .sort(([catA], [catB]) => {
            // 按枚举值升序排序
            if (catA < catB) return -1;
            if (catA > catB) return 1;
            return 0;
        });

    // 获取排序后的枚举键（按数值升序）
    const sortedCategories = sortedEntries.map(([category]) => category);

    // 创建图例数据（按排序后的顺序）
    const legendData = sortedCategories.map(category =>
        ComponentCategory[category] || "UNKNOWN"
    );

    // 创建系列数据（按排序后的顺序）
    const seriesData = sortedEntries.map(([category, value]) => ({
        name: ComponentCategory[category] || "UNKNOWN",
        value
    }));

    return { legendData, seriesData };
}

// 处理 JSON 数据生成进程负载饼状图所需数据
export function processJson2ProcessPieChartData(jsonData: JSONData, currentStepIndex: number) {
    if (!jsonData) {
        return { legendData: [], seriesData: [] };
    }

    // 使用进程名作为键，累加该进程下所有线程的 symbolEvents
    const processMap = new Map<string, number>();

    // 处理数据并累加进程负载
    jsonData.steps.forEach(step => {
        if (currentStepIndex === 0 || step.step_id === currentStepIndex) {
            step.data.forEach(item => {
                const processName = item.processName || "Unknown Process";
                const currentTotal = processMap.get(processName) || 0;
                // 累加该进程下所有线程的 symbolEvents
                processMap.set(processName, currentTotal + item.symbolEvents);
            });
        }
    });

    // 转换为数组并过滤零值
    const processEntries = Array.from(processMap.entries())
        .filter(([_, value]) => value > 0); // 过滤掉负载为零的进程

    // 按负载值降序排序（展示负载最高的进程在前）
    processEntries.sort((a, b) => b[1] - a[1]);

    // 提取图例数据（进程名）
    const legendData = processEntries.map(([processName]) => processName);

    // 提取系列数据（进程名和负载值）
    const seriesData = processEntries.map(([processName, totalEvents]) => ({
        name: processName,
        value: totalEvents
    }));

    return { legendData, seriesData };
}

// 定义键生成策略
type KeyGenerator = (item: any, stepId: number) => string;

// 定义结果创建策略
type ResultCreator<T> = (keyParts: string[], instructions: number, compareInstructions: number,
    increaseInstructions: number, increasePercentage: number) => T;

// 通用比较函数
function compareJsonDataByLevel<T>(
    baseData: JSONData,
    compareData: JSONData | null,
    keyGenerator: KeyGenerator,
    resultCreator: ResultCreator<T>
): T[] {
    // 处理单个JSON数据
    const processData = (data: JSONData): Map<string, number> => {
        const map = new Map<string, number>();

        for (const step of data.steps) {
            for (const item of step.data) {
                const key = keyGenerator(item, step.step_id);
                const current = map.get(key) || 0;
                map.set(key, current + item.symbolEvents);
            }
        }

        return map;
    };

    // 处理基准数据
    const baseMap = processData(baseData);

    // 处理对比数据
    const compareMap = compareData ? processData(compareData) : new Map<string, number>();

    // 合并所有键
    const allKeys = new Set<string>([...baseMap.keys(), ...compareMap.keys()]);
    const results: T[] = [];

    // 处理每个键
    for (const key of allKeys) {
        const keyParts = key.split('|');

        // 获取基准值
        const instructions = baseMap.get(key) ?? -1;

        // 获取对比值
        const compareInstructions = compareMap.get(key) ?? -1;

        // 计算增量
        let increaseInstructions = (compareInstructions === -1 ? 0 : compareInstructions) - (instructions === -1 ? 0 : instructions);

        // 计算增量百分比
        let increasePercentage = NaN;
        if (instructions !== 0) {
            increasePercentage = parseFloat(
                ((increaseInstructions / instructions) * 100).toFixed(2)
            );
        } else {
            increasePercentage = parseFloat(
                ((increaseInstructions / 1) * 100).toFixed(2)
            );
        }

        // 创建结果项
        results.push(resultCreator(keyParts, instructions, compareInstructions,
            increaseInstructions, increasePercentage));
    }

    return results;
}

//process-thread-file-symbol
// 进程级别比较
export function calculateProcessData(
    baseData: JSONData,
    compareData: JSONData | null
): ProcessDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${item.processName}`;

    const resultCreator: ResultCreator<ProcessDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: keyParts[1],
            category: "",
            componentName: "",
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 线程级别比较
export function calculateThreadData(
    baseData: JSONData,
    compareData: JSONData | null
): ThreadDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${item.processName}|${item.threadName}`;

    const resultCreator: ResultCreator<ThreadDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: keyParts[1],
            category: "",
            componentName: "",
            thread: keyParts[2],
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 文件级别比较
export function calculateFileData(
    baseData: JSONData,
    compareData: JSONData | null
): FileDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${item.processName}|${item.threadName}|${item.file}`;

    const resultCreator: ResultCreator<FileDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: keyParts[1],
            category: "",
            componentName: "",
            thread: keyParts[2],
            file: keyParts[3],
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 符号级别比较
export function calculateSymbolData(
    baseData: JSONData,
    compareData: JSONData | null
): SymbolDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${item.processName}|${item.threadName}|${item.file}|${item.symbol}`;

    const resultCreator: ResultCreator<SymbolDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: keyParts[1],
            category: "",
            componentName: "",
            thread: keyParts[2],
            file: keyParts[3],
            symbol: keyParts[4],
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

//category-componentName-file-symbol
// 大分类级别比较
export function calculateCategorysData(
    baseData: JSONData,
    compareData: JSONData | null
): ProcessDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${ComponentCategory[item.componentCategory]}`;

    const resultCreator: ResultCreator<ProcessDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: "",
            category: keyParts[1],
            componentName: "",
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 小分类级别比较
export function calculateComponentNameData(
    baseData: JSONData,
    compareData: JSONData | null
): ThreadDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${ComponentCategory[item.componentCategory]}|${item.componentName}`;

    const resultCreator: ResultCreator<ThreadDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: "",
            category: keyParts[1],
            componentName: keyParts[2],
            thread: "",
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 文件级别比较
export function calculateFileData1(
    baseData: JSONData,
    compareData: JSONData | null
): FileDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${ComponentCategory[item.componentCategory]}|${item.componentName}|${item.file}`;

    const resultCreator: ResultCreator<FileDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: "",
            category: keyParts[1],
            componentName: keyParts[2],
            thread: "",
            file: keyParts[3],
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}

// 符号级别比较
export function calculateSymbolData1(
    baseData: JSONData,
    compareData: JSONData | null
): SymbolDataItem[] {
    const keyGenerator: KeyGenerator = (item, stepId) =>
        `${stepId}|${ComponentCategory[item.componentCategory]}|${item.componentName}|${item.file}|${item.symbol}`;

    const resultCreator: ResultCreator<SymbolDataItem> = (keyParts, instructions, compareInstructions,
        increaseInstructions, increasePercentage) => ({
            stepId: parseInt(keyParts[0], 10),
            process: "",
            category: keyParts[1],
            componentName: keyParts[2],
            thread: "",
            file: keyParts[3],
            symbol: keyParts[4],
            instructions,
            compareInstructions,
            increaseInstructions,
            increasePercentage,
        });

    return compareJsonDataByLevel(baseData, compareData, keyGenerator, resultCreator);
}


export function changeBase64Str2Json(base64String:string) {
    if(base64String=='/tempCompareJsonData/'){
        return '/tempCompareJsonData/';
    }
    const compressed = atob(base64String);
    const uint8Array = new Uint8Array([...compressed].map(c => c.charCodeAt(0)));
    const jsonString = pako.inflate(uint8Array, { to: 'string' });
    const jsonData = JSON.parse(jsonString);
    return jsonData;
}
