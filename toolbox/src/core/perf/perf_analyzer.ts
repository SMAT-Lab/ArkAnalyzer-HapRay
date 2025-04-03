import path from 'path';
import fs from 'fs';
import initSqlJs, { Database } from 'sql.js';
import writeXlsxFile from 'write-excel-file/node';
import { createHash } from 'crypto';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ComponentCategory, OriginKind, getComponentCategories } from '../component';
import {
    CYCLES_EVENT,
    INSTRUCTION_EVENT,
    PerfAnalyzerBase,
    PerfComponent,
    PerfEvent,
    PerfStepSum,
    PerfSum,
    PerfSymbolDetailData,
    TestSceneInfo,
} from './perf_analyzer_base';
import { PerfDatabase } from './perf_database';
import { PROJECT_ROOT } from '../project';
import { getConfig } from '../../config';


const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * perf_sample 表
 */
interface PerfSample {
    id: number;
    callchain_id: number;
    thread_id: number;
    event_count: number;
    cpu_id: number;
    event_name: string;
    timestamp: number;
}

/**
 * perf_thread 表
 */
interface PerfThread {
    thread_id: number;
    process_id: number;
    thread_name: string;
}

interface FileClassification {
    file: string;
    category: ComponentCategory; // 组件大类
    subCategory: string; // 小类
    originKind: OriginKind; // 来源，开源
}

interface PerfCall {
    depth: number;
    fileId: number;
    symbolId: number;
    classification: FileClassification;
}

interface PerfCallchain {
    callchainId: number;
    selfEvent: number; // 标记取selfEvent位置
    totalEvents: number[]; // 标记取totalEvent位置
    stack: PerfCall[]; // 调用栈
}

export interface TestStep {
    id: number;
    name: string;
    start: number;
    end: number;
}

export const DEFAULT_PERF_DB = 'perf.db';
// 应用相关进程存在5种场景 :appBundleName, :appBundleName|| ':ui', :appBundleName || ':render', :appBundleName || ':background', :appBundleName|| 'service:ui'
const PERF_PROCESS_STEP_SAMPLE_SQL = `
SELECT
    perf_sample.id,
    perf_sample.callchain_id,
    perf_sample.thread_id,
    perf_sample.event_count,
    perf_sample.cpu_id,
    perf_report.report_value AS event_name,
    perf_sample.timestamp_trace AS timestamp
FROM
    perf_report
    INNER JOIN perf_sample ON perf_report.id = perf_sample.event_type_id
WHERE
    perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired')
    AND perf_sample.thread_id IN (
        SELECT
            child.thread_id
        FROM
            perf_thread parent
            INNER JOIN perf_thread child ON child.process_id = parent.thread_id
        WHERE
            parent.thread_id = parent.process_id
            AND parent.thread_name IN (:appBundleName, :appBundleName|| ':ui', :appBundleName || ':render', :appBundleName || ':background', :appBundleName|| 'service:ui'))
    AND perf_sample.timestamp_trace >= :stepStart
    AND perf_sample.timestamp_trace <= :stepEnd
`;
const PERF_PROCESS_CALLCHAIN_SQL = `
SELECT
    callchain_id, depth, file_id, name as symbol_id FROM perf_callchain
WHERE
    callchain_id IN (
        SELECT 
            perf_sample.callchain_id
        FROM
            perf_report
            INNER JOIN perf_sample ON perf_report.id = perf_sample.event_type_id
        WHERE
            perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired')
            AND perf_sample.thread_id IN (
                SELECT
            child.thread_id
        FROM
            perf_thread parent
            INNER JOIN perf_thread child ON child.process_id = parent.thread_id
        WHERE
            parent.thread_id = parent.process_id
            AND parent.thread_name IN (:appBundleName, :appBundleName|| ':ui', :appBundleName || ':render', :appBundleName || ':background', :appBundleName|| 'service:ui'))
    )
ORDER BY callchain_id, depth desc
`;

// Test Step timestamp
const TEST_STEP_TIMESTAMPS = `
SELECT
    callstack.name,
    callstack.ts,
    callstack.dur
FROM
    process
    INNER JOIN thread ON process.ipid = thread.ipid
    INNER JOIN callstack ON thread.itid = callstack.callid
WHERE
    process.pid = 66666
ORDER BY ts
`;

class PerfStepSample {
    testStep: TestStep;
    commonData: PerfCommonData;
    threadsEventMap: Map<string, number>; // 线程统计事件数 key = `${thread_id}-${PerfEvent}`
    processEventMap: Map<string, number>; // 进程统计事件数 key = `${thread_id}-${PerfEvent}`
    samples: PerfSample[]; // 原始采样
    details: PerfSymbolDetailData[]; // 计算symbol负载
    statistics: PerfStepSum;

    constructor(testStep: TestStep, samples: PerfSample[], commonData: PerfCommonData) {
        this.testStep = testStep;
        this.commonData = commonData;
        this.threadsEventMap = new Map();
        this.processEventMap = new Map();
        this.samples = [];
        this.details = [];
        this.statistics = {
            stepIdx: testStep.id,
            components: [],
            categoriesSum: [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            categoriesTotal: [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            total: [0, 0],
        };

        this.samples = samples;
        for (const threadEvent of samples) {
            let event = PerfEvent.CYCLES_EVENT;
            if (CYCLES_EVENT.has(threadEvent.event_name)) {
                event = PerfEvent.CYCLES_EVENT;
            } else if (INSTRUCTION_EVENT.has(threadEvent.event_name)) {
                event = PerfEvent.INSTRUCTION_EVENT;
            } else {
                continue;
            }

            this.threadsEventMap.set(`${threadEvent.thread_id}-${event}`, threadEvent.event_count);
            let thread = this.commonData.threadsMap.get(threadEvent.thread_id)!;
            let count = this.processEventMap.get(`${thread.process_id}-${event}`) || 0;
            count += threadEvent.event_count;
            this.processEventMap.set(`${thread.process_id}-${event}`, count);
        }
    }

    /**
     * 计算符号负载
     * @param classifyThread
     */
    public calcSymbolData(classifyThread: (threadName: string) => FileClassification | undefined): void {
        let resultMaps: Map<string, PerfSymbolDetailData> = new Map();
        let fileEventMaps: Map<string, number> = new Map();

        for (const sample of this.samples) {
            let event = PerfEvent.CYCLES_EVENT;
            if (CYCLES_EVENT.has(sample.event_name)) {
                event = PerfEvent.CYCLES_EVENT;
            } else if (INSTRUCTION_EVENT.has(sample.event_name)) {
                event = PerfEvent.INSTRUCTION_EVENT;
            } else {
                continue;
            }

            let thread = this.commonData.threadsMap.get(sample.thread_id)!;
            let process = this.commonData.threadsMap.get(thread.process_id)!;
            let threadComponent = classifyThread(thread?.thread_name);
            let callchain = this.commonData.callchainsMap.get(sample.callchain_id)!;

            // 忽略找不到符号的负载
            if (callchain.stack[callchain.selfEvent].classification.category === ComponentCategory.UNKNOWN) {
                continue;
            }

            let totalSet = new Set(callchain.totalEvents);
            for (let i = callchain.selfEvent; i < callchain.stack.length; i++) {
                let call = callchain.stack[i];

                let data: PerfSymbolDetailData = {
                    stepIdx: this.testStep.id,
                    eventType: event,
                    pid: process.process_id,
                    processName: process.thread_name,
                    processEvents: this.processEventMap.get(`${process.process_id}-${event}`) || 0,
                    tid: thread.thread_id,
                    threadEvents: this.threadsEventMap.get(`${thread.thread_id}-${event}`) || 0,
                    threadName: thread.thread_name,
                    file: call.classification.file,
                    fileEvents: 0,
                    symbol: this.commonData.symbolsMap.get(call.symbolId) || '',
                    symbolEvents: i === callchain.selfEvent ? sample.event_count : 0,
                    symbolTotalEvents: totalSet.has(i) ? sample.event_count : 0,
                    originKind: call.classification.originKind,
                    componentCategory: call.classification.category,
                    componentName: call.classification.subCategory,
                };

                // 忽略找不到符号的负载
                if (call.classification.category === ComponentCategory.UNKNOWN) {
                    continue;
                }

                // 根据线程名直接分类
                if (threadComponent !== undefined) {
                    data.componentName = threadComponent.subCategory;
                    data.componentCategory = threadComponent.category;
                    data.originKind = threadComponent.originKind;
                }

                logger.debug(data);

                let key = `${event}_${data.tid}_${call.symbolId}`;
                if (resultMaps.has(key)) {
                    let value = resultMaps.get(key)!;
                    value.symbolEvents += data.symbolEvents;
                    value.symbolTotalEvents += data.symbolTotalEvents;
                } else {
                    resultMaps.set(key, data);
                }

                // files
                let fileKey = `${data.eventType}_${data.tid}_${data.file}`;
                if (fileEventMaps.has(fileKey)) {
                    let value = fileEventMaps.get(fileKey)!;
                    fileEventMaps.set(fileKey, value + data.symbolEvents);
                } else {
                    fileEventMaps.set(fileKey, data.symbolEvents);
                }
            }
        }

        for (const [_, data] of resultMaps) {
            let fileKey = `${data.eventType}_${data.tid}_${data.file}`;
            data.fileEvents = fileEventMaps.get(fileKey)!;
        }

        this.details = Array.from(resultMaps.values());
    }

    public calcComponentsData(): void {
        let pkgPerfMap: Map<string, PerfComponent> = new Map();

        for (const data of this.details) {
            if (data.componentCategory === ComponentCategory.UNKNOWN) {
                continue;
            }

            this.statistics.categoriesSum[data.eventType][data.componentCategory] += data.symbolEvents;
            this.statistics.categoriesTotal[data.eventType][data.componentCategory] += data.symbolTotalEvents;
            this.statistics.total[data.eventType] += data.symbolEvents;
            let key = `${data.componentCategory}-${data.componentName}-${data.originKind}`;
            if (!pkgPerfMap.has(key)) {
                pkgPerfMap.set(key, {
                    name: data.componentName || '',
                    cycles: data.eventType === PerfEvent.CYCLES_EVENT ? data.symbolEvents : 0,
                    totalCycles: data.eventType === PerfEvent.CYCLES_EVENT ? data.symbolTotalEvents : 0,
                    instructions: data.eventType === PerfEvent.INSTRUCTION_EVENT ? data.symbolEvents : 0,
                    totalInstructions: data.eventType === PerfEvent.INSTRUCTION_EVENT ? data.symbolTotalEvents : 0,
                    category: data.componentCategory!,
                    originKind: data.originKind,
                });
            } else {
                let existComponent = pkgPerfMap.get(key)!;
                if (data.eventType === PerfEvent.CYCLES_EVENT) {
                    existComponent.cycles += data.symbolEvents;
                    existComponent.totalCycles += data.symbolTotalEvents;
                } else if (data.eventType === PerfEvent.INSTRUCTION_EVENT) {
                    existComponent.instructions += data.symbolEvents;
                    existComponent.totalInstructions += data.symbolTotalEvents;
                }
            }
        }

        this.statistics.components = Array.from(pkgPerfMap.values());
    }
}

// 不同场景共享的数据
interface PerfCommonData {
    threadsMap: Map<number, PerfThread>; // 线程表
    filesClassificationMap: Map<number, FileClassification>; // 文件分类表
    symbolsMap: Map<number, string>; // 符号表
    symbolsClassificationMap: Map<number, FileClassification>; // ets 需要按照符号进一步分类
    callchainsMap: Map<number, PerfCallchain>; // 调用链表
}

export class PerfAnalyzer extends PerfAnalyzerBase {
    protected commonData: PerfCommonData;
    protected callchainIds: Set<number>;
    protected testSteps: TestStep[];
    protected stepsSample: PerfStepSample[];

    constructor(workspace: string) {
        super(workspace);
        this.commonData = {
            threadsMap: new Map(),
            filesClassificationMap: new Map(),
            symbolsMap: new Map(),
            symbolsClassificationMap: new Map(),
            callchainsMap: new Map(),
        };

        this.callchainIds = new Set<number>();
        this.testSteps = [];
        this.stepsSample = [];
    }

    async analyze(dbPath: string, testInfo: TestSceneInfo, output: string): Promise<PerfSum> {
        const fileBuffer = fs.readFileSync(dbPath);
        const fileHash = createHash('sha256').update(fileBuffer).digest('hex');

        // 读取数据并统计
        await this.loadDbAndStatistics(dbPath, testInfo.packageName);

        let perf: PerfSum = {
            scene: testInfo.scene,
            osVersion: testInfo.osVersion,
            perfPath: path.resolve(dbPath),
            perfId: fileHash,
            timestamp: testInfo.timestamp,
            steps: this.stepsSample.map((value) => value.statistics),
            categories: getComponentCategories(),
        };

        let now = new Date().getTime();
        if (getConfig().inDbtools) {
            await this.saveDbtoolsXlsx(
                perf,
                path.join(output, `ecol_load_perf_${testInfo.packageName}_${testInfo.scene}_${now}.xlsx`)
            );
        } else {
            await this.saveSqlite(perf, path.join(this.getProjectRoot(), path.basename(dbPath)));
        }

        // for debug
        if (getConfig().save.callchain) {
            await this.saveCallchainXlsx(
                path.join(output, `callchain_${testInfo.packageName}_${testInfo.scene}_${now}.xlsx`)
            );
        }

        return perf;
    }

    private async saveSqlite(perf: PerfSum, outputFileName: string): Promise<void> {
        const db = new PerfDatabase(outputFileName);
        let database = await db.initialize();

        for (const step of this.stepsSample) {
            await db.insertRecords(database, perf.osVersion, perf.scene, step.details);
        }
        db.insertTestSteps(database, this.testSteps);
        db.close(database);
        let name = path.basename(outputFileName).replace(path.extname(outputFileName), '');
        fs.writeFileSync(
            path.join(this.getWorkspace(), `${name}_负载拆解.hpr`),
            JSON.stringify({ id: 'perf', path: path.join(PROJECT_ROOT, path.basename(outputFileName)) })
        );
    }

    /**
     * 另存为dbtools 导入Excel
     * @param perf 
     * @param outputFileName 
     */
    public async saveDbtoolsXlsx(perf: PerfSum, outputFileName: string): Promise<void> {
        let symbolPerfData: { type?: any; value: any }[][] = [];
        symbolPerfData.push([
            { value: '版本' },
            { value: '测试模型' },
            { value: '测试时间' },
            { value: '测试设备SN' },
            { value: 'trace文件路径' },
            { value: '测试场景' },
            { value: '场景执行id' },
            { value: '场景步骤id' },
            { value: '应用版本唯一标识' },
            { value: 'htrace文件唯一标识' },
            { value: '进程id' },
            { value: '进程名' },
            { value: '进程cycle数' },
            { value: '进程指令数' },
            { value: '线程id' },
            { value: '线程名' },
            { value: '线程cycle数' },
            { value: '线程指令数' },
            { value: '文件' },
            { value: '文件cycle数' },
            { value: '文件指令数' },
            { value: '符号Symbol' },
            { value: 'cycle数' },
            { value: 'Total cycle数' },
            { value: '指令数' },
            { value: 'Total指令数' },
            { value: '组件大类' },
            { value: '组件小类' },
            { value: '组件来源' },
        ]);

        symbolPerfData.push([
            { value: 'test_version' },
            { value: 'test_model' },
            { value: 'test_date' },
            { value: 'test_sn' },
            { value: 'trace_path' },
            { value: 'test_scene_name' },
            { value: 'test_scene_trial_id' },
            { value: 'step_id' },
            { value: 'app_version_id' },
            { value: 'hiperf_id' },
            { value: 'process_id' },
            { value: 'process_name' },
            { value: 'process_cycles' },
            { value: 'process_instructions' },
            { value: 'thread_id' },
            { value: 'thread_name' },
            { value: 'thread_cycles' },
            { value: 'thread_instructions' },
            { value: 'file' },
            { value: 'file_cycles' },
            { value: 'file_instructions' },
            { value: 'symbol' },
            { value: 'cpu_cycles' },
            { value: 'cpu_cycles_tree' },
            { value: 'cpu_instructions' },
            { value: 'cpu_instructions_tree' },
            { value: 'component_type' },
            { value: 'component_name' },
            { value: 'origin_kind' },
        ]);

        let symbolDetailsMap = new Map<string, PerfSymbolDetailData[]>();
        for (const step of this.stepsSample) {
            for (const data of step.details) {
                if (data.componentCategory === ComponentCategory.UNKNOWN) {
                    continue;
                }

                let row: PerfSymbolDetailData[] = [
                    {
                        stepIdx: step.testStep.id,
                        eventType: PerfEvent.CYCLES_EVENT,
                        pid: data.pid,
                        processName: data.processName,
                        processEvents: step.processEventMap.get(`${data.pid}-${PerfEvent.CYCLES_EVENT}`) || 0,
                        tid: data.tid,
                        threadEvents: step.threadsEventMap.get(`${data.tid}-${PerfEvent.CYCLES_EVENT}`) || 0,
                        threadName: data.threadName,
                        file: data.file,
                        fileEvents: 0,
                        symbol: data.symbol,
                        symbolEvents: 0,
                        symbolTotalEvents: 0,
                        componentName: data.componentName,
                        componentCategory: data.componentCategory,
                        originKind: data.originKind,
                    },
                    {
                        stepIdx: step.testStep.id,
                        eventType: PerfEvent.INSTRUCTION_EVENT,
                        pid: data.pid,
                        processName: data.processName,
                        processEvents: step.processEventMap.get(`${data.pid}-${PerfEvent.INSTRUCTION_EVENT}`) || 0,
                        tid: data.tid,
                        threadEvents: step.threadsEventMap.get(`${data.tid}-${PerfEvent.INSTRUCTION_EVENT}`) || 0,
                        threadName: data.threadName,
                        file: data.file,
                        fileEvents: 0,
                        symbol: data.symbol,
                        symbolEvents: 0,
                        symbolTotalEvents: 0,
                        componentName: data.componentName,
                        componentCategory: data.componentCategory,
                        originKind: data.originKind,
                    },
                ];

                let key = `${step.testStep.id}_${data.pid}_${data.tid}_${data.file}_${data.symbol}`;
                if (!symbolDetailsMap.has(key)) {
                    symbolDetailsMap.set(key, row);
                }

                row = symbolDetailsMap.get(key)!;
                row[data.eventType].processEvents = data.processEvents;
                row[data.eventType].threadEvents = data.threadEvents;
                row[data.eventType].fileEvents = data.fileEvents;
                row[data.eventType].symbolEvents = data.symbolEvents;
                row[data.eventType].symbolTotalEvents = data.symbolTotalEvents;
            }
        }

        for (const [_, data] of symbolDetailsMap) {
            let row = [
                { value: perf.osVersion, type: String },
                { value: 'Hapray', type: String },
                { value: this.dateCustomFormatting(perf.timestamp), type: String },
                { value: 'Hapray', type: String },
                { value: perf.perfPath, type: String },
                { value: perf.scene, type: String },
                { value: 'Hapray', type: String },
                { value: data[0].stepIdx, type: Number }, // step

                { value: this.project.versionId, type: String },
                { value: perf.perfId, type: String },

                { value: data[0].pid, type: Number },
                { value: data[0].processName, type: String },
                { value: data[0].processEvents, type: Number },
                { value: data[1].processEvents, type: Number },

                { value: data[0].tid, type: Number },
                { value: data[0].threadName, type: String },
                { value: data[0].threadEvents, type: Number },
                { value: data[1].threadEvents, type: Number },

                { value: data[0].file, type: String },
                { value: data[0].fileEvents, type: Number },
                { value: data[1].fileEvents, type: Number },

                { value: data[0].symbol.substring(0, 2048), type: String },
                { value: data[0].symbolEvents, type: Number },
                { value: data[0].symbolTotalEvents, type: Number },
                { value: data[1].symbolEvents, type: Number },
                { value: data[1].symbolTotalEvents, type: Number },

                { value: data[0].componentCategory, type: Number },
                { value: data[0].componentName, type: String },
                { value: data[0].originKind, type: Number },
            ];

            symbolPerfData.push(row);
        }

        let sceneStepData: { type?: any; value: any }[][] = [];
        sceneStepData.push([
            { value: '版本' },
            { value: '测试模型' },
            { value: '测试时间' },
            { value: '测试设备SN' },
            { value: 'trace文件路径' },
            { value: '测试场景' },
            { value: '场景执行id' },
            { value: '场景步骤id' },

            { value: 'htrace文件唯一标识' },
            { value: '步骤名称' },
        ]);

        sceneStepData.push([
            { value: 'test_version' },
            { value: 'test_model' },
            { value: 'test_date' },
            { value: 'test_sn' },
            { value: 'trace_path' },
            { value: 'test_scene_name' },
            { value: 'test_scene_trial_id' },
            { value: 'step_id' },

            { value: 'hiperf_id' },
            { value: 'step_name' },
        ]);

        for (const step of this.testSteps) {
            let row = [
                { value: perf.osVersion, type: String },
                { value: 'Hapray', type: String },
                { value: this.dateCustomFormatting(perf.timestamp), type: String },
                { value: 'Hapray', type: String },
                { value: perf.perfPath, type: String },
                { value: perf.scene, type: String },
                { value: 'Hapray', type: String },
                { value: step.id, type: Number }, // step

                { value: perf.perfId, type: String },
                { value: step.name, type: String },
            ];

            sceneStepData.push(row);
        }

        await writeXlsxFile([symbolPerfData, sceneStepData], {
            sheets: ['ecol_load_hiperf_detail', 'ecol_load_step'],
            filePath: outputFileName,
        });
    }

    private dateCustomFormatting(timestamp: number): string {
        let date = new Date(timestamp);
        const padStart = (value: number): string => value.toString().padStart(2, '0');
        return `${date.getFullYear()}-${padStart(date.getMonth() + 1)}-${padStart(date.getDate())} ${padStart(
            date.getHours()
        )}:${padStart(date.getMinutes())}:${padStart(date.getSeconds())}`;
    }

    private async loadDbAndStatistics(dbPath: string, processName: string): Promise<void> {
        let SQL = await initSqlJs();
        const db = new SQL.Database(fs.readFileSync(dbPath));

        try {
            // 读取所有线程信息
            await this.queryThreads(db);
            // 读取所有文件信息
            await this.queryFiles(db);
            // 读取所有符号信息
            await this.querySymbols(db);
            // 预处理调用链信息
            await this.queryCallchain(db, processName);
            this.disassembleCallchainLoad();
            // 读取测试步骤时间戳
            await this.queryTestStepTimestamps(db);
            // 读取样本数据
            await this.queryProcessSample(db, processName);
        } finally {
            await db.close();
        }
    }

    private async queryTestStepTimestamps(db: Database): Promise<void> {
        const results = db.exec(TEST_STEP_TIMESTAMPS);
        let steps: { name: string; ts: number; dur: number }[] = [];
        if (results.length > 0) {
            results[0].values.map((row) => {
                steps.push({ name: row[0] as string, ts: row[1] as number, dur: row[2] as number });
            });
        }

        if (steps.length > 1) {
            for (let i = 0; i < steps.length - 1; i += 2) {
                const lastIndex = steps[i].name.lastIndexOf('&');
                let step: TestStep = {
                    id: Math.floor(i / 2),
                    start: steps[i].ts + steps[i].dur,
                    end: steps[i + 1].ts,
                    name: lastIndex !== -1 ? steps[i].name.substring(lastIndex + 1) : '',
                };
                this.testSteps.push(step);
            }
        } else {
            const results = db.exec(
                'SELECT MAX(perf_sample.timestamp_trace) as end, MIN(perf_sample.timestamp_trace) as start from perf_sample'
            );
            if (results.length > 0) {
                results[0].values.map((row) => {
                    this.testSteps.push({ id: 0, name: '', start: row[1] as number, end: row[0] as number });
                });
            } else {
                this.testSteps.push({ id: 0, name: '', start: 0, end: Number.MAX_SAFE_INTEGER });
            }
        }
    }

    /**
     * read all thread from perf_thread table, save into threadsMap
     * @param db 
     * @returns 
     */
    private queryThreads(db: Database): void {
        const results = db.exec('SELECT thread_id, process_id, thread_name FROM perf_thread');
        if (results.length === 0) {
            return;
        }

        results[0].values.map((row) => {
            let thread: PerfThread = {
                thread_id: row[0] as number,
                process_id: row[1] as number,
                thread_name: row[2] as string,
            };
            this.commonData.threadsMap.set(thread.thread_id, thread);
        });
    }

    /**
     * read all files from perf_files table, then use FileClassifier to classify the files.
     * @param db 
     * @returns 
     */
    private async queryFiles(db: Database): Promise<void> {
        const results = db.exec('SELECT file_id, path FROM perf_files GROUP BY path ORDER BY file_id');
        if (results.length === 0) {
            return;
        }

        this.commonData.filesClassificationMap.set(-1, {
            file: 'UNKNOWN',
            category: ComponentCategory.UNKNOWN,
            subCategory: '',
            originKind: OriginKind.UNKNOWN,
        });
        results[0].values.map((row) => {
            let file = row[1] as string;
            // pid 替换成'{pid}, 方便版本间比较
            const pidMatch = file.match(/\/proc\/(\d+)\//);
            if (pidMatch) {
                file = file.replace(`/${pidMatch[1]}/`, '/{pid}/');
            }
            this.commonData.filesClassificationMap.set(row[0] as number, this.classifyFile(file));
        });
    }

    /**
     * read all symbol from data_dict table
     * @param db 
     * @returns 
     */
    private async querySymbols(db: Database): Promise<void> {
        const results = db.exec('SELECT id, data FROM data_dict');
        if (results.length === 0) {
            return;
        }
        results[0].values.map((row) => {
            this.commonData.symbolsMap.set(row[0] as number, row[1] as string);
        });
    }

    /**
     * read all callchain from perf_callchain, then use file and symbol info to classify
     * @param db 
     * @param processName 
     * @returns 
     */
    private async queryCallchain(db: Database, processName: string): Promise<void> {
        const results = db.exec(PERF_PROCESS_CALLCHAIN_SQL, [processName]);
        if (results.length === 0) {
            return;
        }
        results[0].values.map((row) => {
            let call: PerfCall = {
                depth: row[1] as number,
                fileId: row[2] as number,
                symbolId: row[3] as number,
                classification: this.commonData.filesClassificationMap.get(row[2] as number)!,
            };

            // ets 需要基于symbol 进一步分类
            if (call.classification.category === ComponentCategory.ABC_APP) {
                call.classification = this.classifySymbol(call.symbolId, call.classification);
            }

            let callchain = this.commonData.callchainsMap.get(row[0] as number) || {
                callchainId: row[0] as number,
                selfEvent: 0,
                totalEvents: [],
                stack: [],
            };
            callchain.stack.push(call);
            this.commonData.callchainsMap.set(callchain.callchainId, callchain);
        });
    }

    /**
     * 拆解callchain负载
     */
    private disassembleCallchainLoad(): void {
        for (const [_, callchain] of this.commonData.callchainsMap) {
            // 从栈顶往下找到第一个不是计算的符号，标记为selfEvent, 如果整个栈都是计算则栈顶0标记为selfEvent
            callchain.selfEvent = 0;
            for (let i = 0; i < callchain.stack.length; i++) {
                if (!this.isPureCompute(callchain.stack[i])) {
                    callchain.selfEvent = i;
                    break;
                }
            }

            let totalEventClassifySet = new Set<number>();
            totalEventClassifySet.add(callchain.stack[callchain.selfEvent].classification.category);

            // 计算symbolTotalEvents, 从栈顶至栈底赋给每个分类第一次出现的符号
            for (let i = callchain.selfEvent + 1; i < callchain.stack.length; i++) {
                let category = callchain.stack[i].classification.category;
                if (!totalEventClassifySet.has(category)) {
                    callchain.totalEvents.push(i);
                    totalEventClassifySet.add(category);
                }
            }
        }
    }

    private isPureCompute(call: PerfCall): boolean {
        const pureComputingSet = new Set<string>([
            '/system/lib64/module/arkcompiler/stub.an',
            '/system/lib64/platformsdk/libark_jsruntime.so',
            '/system/lib64/platformsdk/libace_napi.z.so',
            '/system/lib64/libark_jsoptimizer.so',
            '/system/lib64/libc++.so',
            '/system/lib/ld-musl-aarch64.so.1',
            '/system/etc/abc/framework/stateMgmt.abc',
            'sysmgr.elf',
            '[kernel.kallsyms]',
        ]);

        return (
            pureComputingSet.has(call.classification.file) || call.classification.category === ComponentCategory.UNKNOWN
        );
    }

    private async saveCallchainXlsx(outputFileName: string): Promise<void> {
        let callchainData: { type?: any; value: any }[][] = [];
        callchainData.push([
            { value: 'callchain_id' },
            { value: 'depth' },
            { value: 'file' },
            { value: 'symbol' },
            { value: '组件大类' },
            { value: '组件小类' },
            { value: '库来源' },
            { value: '负载划分' },
        ]);

        for (const [id, chain] of this.commonData.callchainsMap) {
            if (!this.callchainIds.has(id)) {
                continue;
            }
            const totalSet = new Set(chain.totalEvents);
            for (let i = 0; i < chain.stack.length; i++) {
                const call = chain.stack[i];
                let event = '';
                if (i === chain.selfEvent) {
                    event = 'Self';
                } else if (totalSet.has(i)) {
                    event = 'Total';
                }
                callchainData.push([
                    { value: chain.callchainId, type: Number },
                    { value: call.depth, type: Number },
                    { value: call.classification.file, type: String },
                    { value: this.commonData.symbolsMap.get(call.symbolId), type: String },
                    { value: ComponentCategory[call.classification.category!], type: String },
                    { value: call.classification.subCategory, type: String },
                    { value: OriginKind[call.classification.originKind!], type: String },
                    { value: event, type: String },
                ]);
            }
        }

        await writeXlsxFile([callchainData], { sheets: ['callchain'], filePath: outputFileName });
    }

    /**
     * query app process samples by appBundleName
     * @param db 
     * @param appBundleName 
     */
    private async queryProcessSample(db: Database, appBundleName: string): Promise<void> {
        for (const testStep of this.testSteps) {
            const results = db.exec(PERF_PROCESS_STEP_SAMPLE_SQL, [appBundleName, testStep.start, testStep.end]);
            if (results.length === 0) {
                this.createStepSample(testStep, []);
                continue;
            }
            let samples: PerfSample[] = [];
            results[0].values.map((row) => {
                this.callchainIds.add(row[1] as number);
                samples.push({
                    id: row[0] as number,
                    callchain_id: row[1] as number,
                    thread_id: row[2] as number,
                    event_count: row[3] as number,
                    cpu_id: row[4] as number,
                    event_name: row[5] as string,
                    timestamp: row[6] as number,
                });
            });
            this.createStepSample(testStep, samples);
        }
    }

    private createStepSample(testStep: TestStep, samples: PerfSample[]): void {
        let step = new PerfStepSample(testStep, samples, this.commonData);
        step.calcSymbolData((threadName) => this.classifyThread(threadName));
        step.calcComponentsData();
        this.stepsSample.push(step);
    }

    private classifyFile(file: string): FileClassification {
        let fileClassify: FileClassification = {
            file: file,
            category: ComponentCategory.SYS_Other,
            subCategory: path.basename(file),
            originKind: OriginKind.UNKNOWN,
        };

        if (this.cfgFileComponent.has(file)) {
            let component = this.cfgFileComponent.get(file)!;
            fileClassify.category = component.category;
            fileClassify.subCategory = component.name;

            return fileClassify;
        }

        for (const [key, component] of this.cfgRegexComponent) {
            let matched = file.match(key);
            if (matched) {
                fileClassify.category = component.category;
                fileClassify.subCategory = component.name;
                return fileClassify;
            }
        }

        /**
         * bundle so file
         * /proc/8836/root/data/storage/el1/bundle/libs/arm64/libalog.so
         */
        let regex = new RegExp('/proc/.*/data/storage/.*/bundle/.*');
        if (file.match(regex)) {
            let name = path.basename(file);
            if (name.endsWith('.so') || file.indexOf('/bundle/libs/') >= 0) {
                fileClassify.category = ComponentCategory.ABC_SO;
                if (this.soOrigins.has(path.basename(file))) {
                    let origin = this.soOrigins.get(name)!.broad_category;
                    if (origin === 'THIRD_PARTY') {
                        fileClassify.originKind = OriginKind.THIRD_PARTY;
                        fileClassify.subCategory = this.soOrigins.get(name)!.specific_origin;
                    } else if (origin === 'OPENSOURCE') {
                        fileClassify.originKind = OriginKind.OPEN_SOURCE;
                        fileClassify.subCategory = this.soOrigins.get(name)!.specific_origin;
                    } else if (origin === 'FIRST_PARTY') {
                        fileClassify.originKind = OriginKind.FIRST_PARTY;
                    }
                }

                return fileClassify;
            }

            fileClassify.category = ComponentCategory.ABC_APP;
            return fileClassify;
        }

        if (this.cfgFileComponent.has(path.basename(file))) {
            let component = this.cfgFileComponent.get(path.basename(file))!;
            fileClassify.category = component.category;
            fileClassify.subCategory = component.name;

            return fileClassify;
        }

        return fileClassify;
    }

    private classifySymbol(symbolId: number, fileClassification: FileClassification): FileClassification {
        if (this.commonData.symbolsClassificationMap.has(symbolId)) {
            return this.commonData.symbolsClassificationMap.get(symbolId)!;
        }

        const symbol = this.commonData.symbolsMap.get(symbolId) || '';
        /**
         * ets symbol
         * xx: [url:entry|@aaa/bbb|1.0.0|src/main/ets/i9/l9.ts:12:1]
         */
        let regex = /([^:]+):\[url:([^:\|]+)\|([^|]+)\|(\d+(?:\.\d+){2})\|([^\|\]]*)\]/;
        let matches = symbol.match(regex);
        if (matches) {
            let symbolClassification: FileClassification = {
                file: fileClassification.file,
                originKind: fileClassification.originKind,
                category: fileClassification.category,
                subCategory: matches[3],
            };

            if (this.hapComponents.has(matches[3])) {
                symbolClassification.category = this.hapComponents.get(matches[3])!.kind;
            }

            this.commonData.symbolsClassificationMap.set(symbolId, symbolClassification);
            return symbolClassification;
        }

        return fileClassification;
    }

    private classifyThread(threadName: string): FileClassification | undefined {
        if (this.cfgThreadComponent.has(threadName)) {
            let component = this.cfgThreadComponent.get(threadName)!;
            return {
                file: '',
                originKind: OriginKind.UNKNOWN,
                category: component.category,
                subCategory: component.name,
            };
        }

        return undefined;
    }
}
