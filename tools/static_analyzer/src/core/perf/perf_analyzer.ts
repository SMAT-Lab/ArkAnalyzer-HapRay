/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import path from 'path';
import fs from 'fs';
import type { Database } from 'sql.js';
import initSqlJs from 'sql.js';
import writeXlsxFile from 'write-excel-file/node';
import { createHash } from 'crypto';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ComponentCategory, getComponentCategories, type ClassifyCategory } from '../../types/component';
import type {
    FileClassification,
    PerfComponent,
    PerfStepSum,
    PerfSum,
    PerfSymbolDetailData,
    ProcessClassifyCategory,
    SummaryInfo,
    TestReportInfo,
    TestSceneInfo,
    TestStep
} from './perf_analyzer_base';
import {
    CYCLES_EVENT,
    INSTRUCTION_EVENT,
    PerfAnalyzerBase,
    PerfEvent,
    UNKNOWN_STR,
} from './perf_analyzer_base';
import { getConfig } from '../../config';
import type { SheetData } from 'write-excel-file';
import { saveJsonArray } from '../../utils/json_utils';

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
    name: string;
    processId: number;
    threadId: number;
    systemClassifyCategory: ProcessClassifyCategory;
    classification: ClassifyCategory;
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
    totalEvents: Array<number>; // 标记取totalEvent位置
    stack: Array<PerfCall>; // 调用栈
}

// 定义单个 step 的结构
export interface Step {
    name: string;
    stepIdx: number;
    description: string;
}

// 定义时间范围接口
export interface TimeRange {
    startTime: number;
    endTime: number;
}

export const DEFAULT_PERF_DB = 'perf.db';
// 应用相关进程存在5种场景 :appBundleName, :appBundleName|| ':ui', :appBundleName || ':render', :appBundleName || ':background', :appBundleName|| 'service:ui'
const PERF_PROCESS_SAMPLE_SQL = `
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
    perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired', 'hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles')
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
            perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired', 'hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles')
            AND perf_sample.thread_id IN (
                SELECT
            child.thread_id
        FROM
            perf_thread parent
            INNER JOIN perf_thread child ON child.process_id = parent.thread_id
        WHERE
            parent.thread_id = parent.process_id
        )
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

const PERF_PROCESS_TOTAL_SQL = `
SELECT
    SUM(perf_sample.event_count)
FROM
    perf_sample
    INNER JOIN perf_report ON perf_report.id = perf_sample.event_type_id
WHERE
    perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired', 'hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles')
`;

const PERF_PROCESS_SWAPPER_SQL = `
SELECT
    SUM(perf_sample.event_count)
FROM
    perf_sample
    INNER JOIN perf_report ON perf_report.id = perf_sample.event_type_id
WHERE
    perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired', 'hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles')
    and perf_sample.thread_id = 0
`;

export class PerfAnalyzer extends PerfAnalyzerBase {
    protected threadsMap: Map<number, PerfThread>; // 线程表
    protected callchainsMap: Map<number, PerfCallchain>; // 调用链表
    protected callchainIds: Set<number>;
    protected testSteps: Array<TestStep>;
    protected samples: Array<PerfSample>;

    constructor(workspace: string) {
        super(workspace);

        this.threadsMap = new Map();
        this.callchainsMap = new Map();
        this.callchainIds = new Set<number>();
        this.testSteps = [];
        this.samples = [];
    }

    public async calcPerfDbTotalInstruction(dbfile: string): Promise<number> {
        let total = 0;
        if (dbfile === '') {
            return 0;
        }

        let SQL = await initSqlJs();

        logger.info(`calcTotalInstruction ${dbfile} start`);
        let db: Database | null = null;
        try {
            db = new SQL.Database(fs.readFileSync(dbfile));
            // 读取样本数据
            total = this.queryProcessTotal(db);
        } catch (err) {
            logger.error(`${err} ${dbfile}`);
        } finally {
            if (db) {
                db.close();
            }
        }
        logger.info(`calcTotalInstruction ${dbfile} done`);

        return total;
    }

    /**
     * 纯分析方法，不产生输出文件，用于轮次选择等场景
     * @param testInfo 测试场景信息
     * @param timeRange 可选的时间范围过滤，格式为 {startTime: number, endTime: number}
     */
    async analyzeOnly(testInfo: TestSceneInfo, timeRange?: TimeRange): Promise<PerfSum> {
        let hash = createHash('sha256');
        testInfo.rounds[testInfo.chooseRound].steps.map((value) => {
            if (value.dbfile) {
                const fileBuffer = fs.readFileSync(value.dbfile);
                hash.update(fileBuffer);
            }
        });
        const fileHash = hash.digest('hex');

        if (this.project.versionId.length === 0) {
            this.setProjectInfo(testInfo.packageName, testInfo.appVersion);
        }

        // 读取数据并统计
        await this.loadDbAndStatisticsOnly(testInfo, testInfo.packageName, timeRange);
        let perfPath = '';
        let isFirstPerfPath = true;
        for (const step of testInfo.rounds[testInfo.chooseRound].steps) {
            if (isFirstPerfPath) {
                perfPath = path.resolve(step.dbfile!);
                isFirstPerfPath = false;
            } else {
                perfPath = perfPath + ',' + step.dbfile!.replace(path.dirname(step.reportRoot), '');
            }
        }

        let perf: PerfSum = {
            scene: testInfo.scene,
            osVersion: testInfo.osVersion,
            perfPath: perfPath,
            perfId: fileHash,
            timestamp: testInfo.timestamp,
            steps: Array.from(this.stepSumMap.values()),
            categories: getComponentCategories(),
        };

        return perf;
    }

    /**
     * 完整分析方法，包含输出文件生成
     * @param testInfo 测试场景信息
     * @param output 输出路径
     * @param timeRange 可选的时间范围过滤，格式为 {startTime: number, endTime: number}
     */
    async analyze(testInfo: TestSceneInfo, output: string, timeRange?: TimeRange): Promise<PerfSum> {
        // 先执行纯分析
        const perf = await this.analyzeOnly(testInfo, timeRange);

        // 然后生成输出文件
        await this.generateOutputFiles(testInfo, perf, output);

        return perf;
    }

    /**
     * 生成输出文件
     */
    private async generateOutputFiles(testInfo: TestSceneInfo, perf: PerfSum, output: string): Promise<void> {
        let now = new Date().getTime();

        // 生成主要输出文件
        if (getConfig().inDbtools) {
            await this.saveDbtoolsXlsx(
                testInfo,
                perf,
                path.join(output, `ecol_load_perf_${testInfo.packageName}_${testInfo.scene}_${now}.xlsx`)
            );
        } else {
            await this.saveSqlite(
                perf,
                path.join(this.getProjectRoot(), path.basename(testInfo.rounds[testInfo.chooseRound].steps[0].dbfile!))
            );
        }

        // 生成调试输出文件
        if (getConfig().save.callchain) {
            await this.saveCallchainXlsx(
                path.join(output, `callchain_${testInfo.packageName}_${testInfo.scene}`)
            );
        }
    }

    /**
     * 仅加载数据库和统计信息，不产生输出文件
     */
    private async loadDbAndStatisticsOnly(testInfo: TestSceneInfo, packageName: string, timeRange?: TimeRange): Promise<void> {
        let SQL = await initSqlJs();
        for (const stepGroup of testInfo.rounds[testInfo.chooseRound].steps) {
            logger.info(`loadDbAndStatisticsOnly groupId=${stepGroup.groupId} parse dbfile ${stepGroup.dbfile}`);
            const db = new SQL.Database(fs.readFileSync(stepGroup.dbfile!));

            try {
                // 统计信息
                this.loadStatistics(db, packageName, testInfo.scene, stepGroup.groupId, timeRange);
            } catch (error) {
                let err = error as Error;
                logger.error(`loadDbAndStatisticsOnly ${err}, ${err.stack} ${stepGroup.dbfile}`);
            } finally {
                // 清空过程缓存map
                this.callchainIds.clear();
                this.filesClassifyMap.clear();
                this.symbolsMap.clear();
                this.symbolsClassifyMap.clear();
                this.callchainsMap.clear();
                this.threadsMap.clear();
                this.samples = [];
                db.close();
            }
        }
    }

    private loadStatistics(db: Database, packageName: string, scene: string, groupId: number, timeRange?: TimeRange): number {
        // 读取所有线程信息
        this.queryThreads(db, packageName, scene);
        // 读取所有文件信息
        this.queryFiles(db);
        // 读取所有符号信息
        this.querySymbols(db);
        // 预处理调用链信息
        this.queryCallchain(db);
        this.disassembleCallchainLoad();
        // 读取测试步骤时间戳
        this.queryTestStepTimestamps(db, groupId);
        // 读取样本数据
        const sampleCount = this.queryProcessSample(db, groupId, timeRange);
        // 计算符号数据并构建 PerfStepSum
        this.calcSymbolData(groupId, packageName);
        return sampleCount;
    }

    private queryTestStepTimestamps(db: Database, groupId: number): void {
        const results = db.exec(TEST_STEP_TIMESTAMPS);
        let steps: Array<{ name: string; ts: number; dur: number }> = [];
        if (results.length > 0) {
            results[0].values.map((row) => {
                steps.push({ name: row[0] as string, ts: row[1] as number, dur: row[2] as number });
            });
        }

        if (steps.length > 1) {
            for (let i = 0; i < steps.length - 1; i += 2) {
                let lastIndex = steps[i].name.lastIndexOf('&');
                if (lastIndex === -1) {
                    lastIndex = steps[i].name.lastIndexOf('#');
                }

                let step: TestStep = {
                    id: this.testSteps.length,
                    groupId: groupId,
                    start: steps[i].ts + steps[i].dur,
                    end: steps[i + 1].ts,
                    name: lastIndex !== -1 ? steps[i].name.substring(lastIndex + 1) : steps[i].name,
                };
                this.testSteps.push(step);
            }
        } else {
            const results = db.exec(
                'SELECT MAX(perf_sample.timestamp_trace) as end, MIN(perf_sample.timestamp_trace) as start from perf_sample'
            );
            if (results.length > 0) {
                results[0].values.map((row) => {
                    this.testSteps.push({
                        id: this.testSteps.length,
                        groupId: groupId,
                        name: '',
                        start: row[1] as number,
                        end: row[0] as number,
                    });
                });
            } else {
                this.testSteps.push({
                    id: this.testSteps.length,
                    groupId: groupId,
                    name: '',
                    start: 0,
                    end: Number.MAX_SAFE_INTEGER,
                });
            }
        }
    }

    /**
     * read all thread from perf_thread table, save into threadsMap
     * @param db
     * @returns
     */
    private queryThreads(db: Database, packageName: string, scene: string): void {
        let processesMap: Map<number, ProcessClassifyCategory> = new Map();
        let results = db.exec('SELECT process_id, thread_name FROM perf_thread where thread_id = process_id');
        if (results.length === 0) {
            return;
        }

        results[0].values.map((row) => {
            let processName = row[1] as string || null;
            processesMap.set(row[0] as number, this.classifyProcess(processName ?? undefined, packageName, scene));
        });

        results = db.exec('SELECT thread_id, process_id, thread_name FROM perf_thread');
        if (results.length === 0) {
            return;
        }

        results[0].values.map((row) => {
            let processClassify = processesMap.get(row[1] as number)!;
            let threadClassify = this.classifyThread(row[2] as string);
            let name = row[2] as string;
            if (!name || name.length === 0) {
                name = UNKNOWN_STR;
            }
            let thread: PerfThread = {
                threadId: row[0] as number,
                processId: row[1] as number,
                name: name,
                systemClassifyCategory: processClassify,
                classification: threadClassify,
            };
            this.threadsMap.set(thread.threadId, thread);
        });
    }

    /**
     * read all files from perf_files table, then use FileClassifier to classify the files.
     * @param db
     * @param packageName
     * @returns
     */
    private queryFiles(db: Database): void {
        const results = db.exec('SELECT file_id, path FROM perf_files GROUP BY path ORDER BY file_id');
        if (results.length === 0) {
            return;
        }

        this.filesClassifyMap.set(-1, {
            file: UNKNOWN_STR,
            category: ComponentCategory.UNKNOWN,
            categoryName: UNKNOWN_STR,
            subCategoryName: '',
        });

        // 先检查是否存在KMP方案标识文件
        const hasKmpScheme = this.checkKmpScheme(db);

        // 然后进行文件分类
        results[0].values.map((row) => {
            let file = row[1] as string;
            // pid 替换成'{pid}, 方便版本间比较
            const pidMatch = file.match(/\/proc\/(\d+)\//);
            if (pidMatch) {
                file = file.replace(`/${pidMatch[1]}/`, '/{pid}/');
            }

            let fileClassify = this.classifyFile(file);

            if (fileClassify.category === ComponentCategory.APP && fileClassify.subCategoryName === 'APP_SO') {
                // 特殊处理KMP相关文件：当检测到KMP方案时，将libskia.so和libskikobridge.so归类为KMP
                if (hasKmpScheme &&
                    (file.match(/\/proc\/.*\/bundle\/libs\/arm64\/libskia\.so$/))) {
                    fileClassify.category = ComponentCategory.KMP;
                    fileClassify.categoryName = 'KMP';
                    fileClassify.subCategoryName = 'CMP';
                }
            }

            this.filesClassifyMap.set(row[0] as number, fileClassify);
        });
    }

    /**
     * 检查是否存在KMP方案标识文件
     */
    private checkKmpScheme(db: Database): boolean {
        const results = db.exec("SELECT COUNT(*) as count FROM perf_files WHERE path LIKE '%/proc/%/bundle/libs/arm64/libkn.so'");
        if (results.length > 0 && results[0].values.length > 0) {
            const count = results[0].values[0][0] as number;
            return count > 0;
        }
        return false;
    }

    /**
     * read all symbol from data_dict table
     * @param db
     * @returns
     */
    private querySymbols(db: Database): void {
        const results = db.exec('SELECT id, data FROM data_dict');
        if (results.length === 0) {
            return;
        }
        results[0].values.map((row) => {
            this.symbolsMap.set(row[0] as number, row[1] as string);
        });
    }

    /**
     * read all callchain from perf_callchain, then use file and symbol info to classify
     * @param db
     * @param processName
     * @returns
     */
    private queryCallchain(db: Database): void {
        const results = db.exec(PERF_PROCESS_CALLCHAIN_SQL);
        if (results.length === 0) {
            return;
        }
        results[0].values.map((row) => {
            let call: PerfCall = {
                depth: row[1] as number,
                fileId: row[2] as number,
                symbolId: row[3] as number,
                classification: this.filesClassifyMap.get(row[2] as number)!,
            };

            // ets 需要基于symbol 进一步分类
            call.classification = this.classifySymbol(call.symbolId, call.classification);

            let callchain = this.callchainsMap.get(row[0] as number) ?? {
                callchainId: row[0] as number,
                selfEvent: 0,
                totalEvents: [],
                stack: [],
            };
            callchain.stack.push(call);
            this.callchainsMap.set(callchain.callchainId, callchain);
        });
    }

    /**
     * 拆解callchain负载
     */
    private disassembleCallchainLoad(): void {
        for (const [key, callchain] of this.callchainsMap) {
            if (this.isSkipSymbol(this.symbolsMap.get(callchain.stack[0].symbolId) ?? '')) {
                logger.debug(`delete dfx callchain id ${key}`);
                this.callchainsMap.delete(key);
                continue;
            }
            // 从栈顶往下找到第一个不是计算的符号，标记为selfEvent, 如果整个栈都是计算则栈标记为selfEvent
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
        return (
            this.isPureComputeSymbol(call.classification.file, this.symbolsMap.get(call.symbolId) ?? '') || call.classification.category === ComponentCategory.UNKNOWN
        );
    }

    private async saveCallchainXlsx(outputFileName: string): Promise<void> {
        const MAX_SIZE = 500000;
        const header = [
            { value: 'callchain_id' },
            { value: 'depth' },
            { value: 'file' },
            { value: 'symbol' },
            { value: '组件大类' },
            { value: '组件小类' },
            { value: '库来源' },
            { value: '负载划分' },
        ];
        const now = new Date().getTime();
        let order = 1;

        let callchainData: SheetData = [];
        callchainData.push(header);

        for (const [id, chain] of this.callchainsMap) {
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
                    { value: this.symbolsMap.get(call.symbolId) ?? '', type: String },
                    { value: ComponentCategory[call.classification.category], type: String },
                    { value: call.classification.subCategoryName ?? '', type: String },
                    { value: call.classification.thirdCategoryName ?? '', type: String },
                    { value: event, type: String },
                ]);
            }

            if (callchainData.length > MAX_SIZE) {
                await writeXlsxFile([callchainData], {
                    sheets: ['callchain'],
                    filePath: `${outputFileName}_${order}_${now}.xlsx`,
                });
                callchainData = [];
                callchainData.push(header);
                order++;
            }
        }

        await writeXlsxFile([callchainData], {
            sheets: ['callchain'],
            filePath: `${outputFileName}_${order}_${now}.xlsx`,
        });
    }

    /**
     * query app process samples by appBundleName
     * @param db
     * @param appBundleName
     */
    private queryProcessSample(db: Database, groupId: number, timeRange?: TimeRange): number {
        const total = this.queryProcessTotal(db);
        const swapper = this.queryStepSwapper(db);

        // swapper进程按比例分摊到其他符号
        const scale = total === swapper ? 1 : 1 + swapper / (total - swapper);

        // 构建带时间过滤的 SQL 查询
        let sql = PERF_PROCESS_SAMPLE_SQL;
        if (timeRange) {
            sql += ` AND perf_sample.timestamp_trace >= ${timeRange.startTime} AND perf_sample.timestamp_trace <= ${timeRange.endTime}`;
        }

        const results = db.exec(sql);
        if (results.length === 0) {
            return 0;
        }

        results[0].values.map((row) => {
            this.callchainIds.add(row[1] as number);
            if ((row[2] as number) === 0) {
                return;
            }

            this.samples.push({
                id: row[0] as number,
                callchain_id: row[1] as number,
                thread_id: row[2] as number,
                event_count: Math.round((row[3] as number) * scale),
                cpu_id: row[4] as number,
                event_name: row[5] as string,
                timestamp: row[6] as number,
            });
        });

        return results[0].values.length;
    }

    private queryProcessTotal(db: Database, timeRange?: TimeRange): number {
        let total = 0;

        // 构建带时间过滤的 SQL 查询
        let sql = PERF_PROCESS_TOTAL_SQL;
        if (timeRange) {
            sql += ` AND perf_sample.timestamp_trace >= ${timeRange.startTime} AND perf_sample.timestamp_trace <= ${timeRange.endTime}`;
        }

        const results = db.exec(sql);
        if (results.length === 0) {
            return total;
        }

        results[0].values.map((row) => {
            total += row[0] as number;
        });
        return total;
    }

    private queryStepSwapper(db: Database, timeRange?: TimeRange): number {
        let total = 0;

        // 构建带时间过滤的 SQL 查询
        let sql = PERF_PROCESS_SWAPPER_SQL;
        if (timeRange) {
            sql += ` AND perf_sample.timestamp_trace >= ${timeRange.startTime} AND perf_sample.timestamp_trace <= ${timeRange.endTime}`;
        }

        const results = db.exec(sql);
        if (results.length === 0) {
            return total;
        }

        results[0].values.map((row) => {
            total += row[0] as number;
        });
        return total;
    }

    /**
     * 计算符号负载
     * @param groupId 组ID
     * @param packageName 包名，用于区分应用负载
     */
    public calcSymbolData(groupId: number, packageName?: string): number {
        let resultMaps: Map<string, PerfSymbolDetailData> = new Map();
        let fileEventMaps: Map<string, number> = new Map();
        let threadsEventMap: Map<string, number> = new Map(); // 线程统计事件数
        let processEventMap: Map<string, number> = new Map(); // 进程统计事件数
        let skipDfxEvents = 0;

        for (const sample of this.samples) {
            let event = this.getEventType(sample.event_name);
            if (event === null) {
                continue;
            }

            if (!this.callchainsMap.has(sample.callchain_id)) {
                logger.debug('calcSymbolData callchain_id %s not found', sample.callchain_id);
                skipDfxEvents += sample.event_count;
                continue;
            }

            let thread = this.threadsMap.get(sample.thread_id);
            if (!thread) {
                thread = {
                    name: UNKNOWN_STR,
                    processId: sample.thread_id,
                    threadId: sample.thread_id,
                    systemClassifyCategory: this.classifyProcess(undefined, '', ''),
                    classification: {
                        category: ComponentCategory.UNKNOWN,
                        categoryName: UNKNOWN_STR,
                        subCategoryName: UNKNOWN_STR,
                    },
                };
                this.threadsMap.set(sample.thread_id, thread);
            }
            let process = this.threadsMap.get(thread.processId);
            if (!process) {
                logger.error(`calcSymbolData process ${thread.processId} not found`);
                continue;
            }

            const callchain = this.callchainsMap.get(sample.callchain_id)!;
            const call = callchain.stack[callchain.selfEvent];

            // 优先使用symbolsClassifyMap中的特殊处理结果，如果没有则使用call.classification
            // 创建副本以避免修改callchainsMap中的原始对象
            const sourceClassification = this.symbolsClassifyMap.get(call.symbolId) ?? call.classification;
            const finalClassification: FileClassification = {
                file: sourceClassification.file,
                category: sourceClassification.category,
                categoryName: sourceClassification.categoryName,
                subCategoryName: sourceClassification.subCategoryName,
                thirdCategoryName: sourceClassification.thirdCategoryName,
            };

            let data: PerfSymbolDetailData = {
                stepIdx: groupId,
                eventType: event,
                pid: process.processId,
                processName: process.name,
                processEvents: 0,
                tid: thread.threadId,
                threadEvents: 0,
                threadName: thread.name,
                file: finalClassification.file,
                fileEvents: 0,
                symbol: this.symbolsMap.get(call.symbolId) ?? '',
                symbolEvents: sample.event_count,
                symbolTotalEvents: 0,
                componentCategory: finalClassification,
                isMainApp: process.systemClassifyCategory.isMainApp,
                sysDomain: process.systemClassifyCategory.domain,
                sysSubSystem: process.systemClassifyCategory.subSystem,
                sysComponent: process.systemClassifyCategory.component,
            };

            let threadEventCount = threadsEventMap.get(this.getThreadKey(data)) ?? 0;
            threadsEventMap.set(this.getThreadKey(data), threadEventCount + sample.event_count);

            let processEventCount = processEventMap.get(this.getProcessKey(data)) ?? 0;
            processEventMap.set(this.getProcessKey(data), processEventCount + sample.event_count);

            // 根据线程名直接分类
            if (thread.classification.category !== ComponentCategory.UNKNOWN) {
                if (thread.classification.subCategoryName) {
                    data.componentCategory.subCategoryName = thread.classification.subCategoryName;
                } else {
                    data.componentCategory.subCategoryName = path.basename(finalClassification.file);
                }

                data.componentCategory.category = thread.classification.category;
                data.componentCategory.categoryName = thread.classification.categoryName;
            }

            if (data.sysDomain === 'DFX' || data.sysDomain === 'Test') {
                skipDfxEvents += sample.event_count;
                continue;
            }

            if (data.componentCategory.category === ComponentCategory.SYS_SDK && data.componentCategory.subCategoryName === 'Other') {
                if (path.basename(data.processName) === path.basename(data.file)) {
                    data.componentCategory.subCategoryName = data.sysDomain;
                }
            }

            let key = this.getSymbolKey(data);
            if (resultMaps.has(key)) {
                let value = resultMaps.get(key)!;
                value.symbolEvents += data.symbolEvents;
                value.symbolTotalEvents += data.symbolTotalEvents;
            } else {
                resultMaps.set(key, data);
            }

            // files
            let fileKey = this.getFileKey(data);
            if (fileEventMaps.has(fileKey)) {
                let value = fileEventMaps.get(fileKey)!;
                fileEventMaps.set(fileKey, value + data.symbolEvents);
            } else {
                fileEventMaps.set(fileKey, data.symbolEvents);
            }

        }

        for (const [_, data] of resultMaps) {
            data.fileEvents = fileEventMaps.get(this.getFileKey(data))!;
            data.threadEvents = threadsEventMap.get(this.getThreadKey(data))!;
            data.processEvents = processEventMap.get(this.getProcessKey(data))!;
        }

        let groupData = Array.from(resultMaps.values()).sort((a, b) => {
            if (a.pid < b.pid) {
                return -1;
            } else if (a.pid > b.pid) {
                return 1;
            }

            if (a.tid < b.tid) {
                return -1;
            } else if (a.tid > b.tid) {
                return 1;
            }

            if (a.file !== b.file) {
                return a.file.localeCompare(b.file);
            }
            return a.symbol.localeCompare(b.symbol);
        });

        this.details.push(...groupData);

        // 构建 PerfStepSum 对象
        const stepSum = this.buildPerfStepSum(groupId, groupData, packageName);
        this.stepSumMap.set(groupId, stepSum);

        return skipDfxEvents;
    }

    private getEventType(eventName: string): PerfEvent | null {
        if (CYCLES_EVENT.has(eventName)) {
            return PerfEvent.CYCLES_EVENT;
        }
        if (INSTRUCTION_EVENT.has(eventName)) {
            return PerfEvent.INSTRUCTION_EVENT;
        }
        return null;
    }

    private getSymbolKey(data: PerfSymbolDetailData): string {
        return `${data.eventType}_${data.stepIdx}_${data.tid}_${data.file}_${data.symbol}`;
    }

    private getFileKey(data: PerfSymbolDetailData): string {
        return `${data.eventType}_${data.stepIdx}_${data.tid}_${data.file}`;
    }

    private getThreadKey(data: PerfSymbolDetailData): string {
        return `${data.eventType}_${data.stepIdx}_${data.tid}`;
    }

    private getProcessKey(data: PerfSymbolDetailData): string {
        return `${data.eventType}_${data.stepIdx}_${data.pid}`;
    }

    /**
     * 构建 PerfStepSum 对象，统计负载信息
     */
    private buildPerfStepSum(groupId: number, groupData: Array<PerfSymbolDetailData>, packageName?: string): PerfStepSum {
        // 按组件名称统计负载
        const componentMap = new Map<string, PerfComponent>();

        // 按大类统计负载 [category][eventType] = count
        const categoriesSum = new Array<Array<number>>();
        const categoriesTotal = new Array<Array<number>>();

        // 总值统计 [0] = cycles, [1] = instructions
        const total = [0, 0];

        // 负载计数统计
        let count = 0; // 总负载数
        let app_count = 0; // 应用负载数

        // 初始化大类统计数组
        // ComponentCategory 枚举值: APP_ABC=0, APP_SO=1, ..., UNKNOWN=-1
        // 我们需要为所有正值和UNKNOWN(-1)创建索引
        const maxCategoryValue = Math.max(...Object.values(ComponentCategory).filter(v => typeof v === 'number' && v >= 0) as Array<number>);
        const categoryCount = maxCategoryValue + 2; // +1 for 0-based index, +1 for UNKNOWN

        for (let i = 0; i < categoryCount; i++) {
            categoriesSum[i] = [0, 0]; // [cycles, instructions]
            categoriesTotal[i] = [0, 0]; // [cycles, instructions]
        }

        // 遍历所有符号数据进行统计
        for (const data of groupData) {
            const componentKey = `${data.componentCategory.category}_${data.componentCategory.subCategoryName}`;
            const eventIndex = data.eventType; // 0: cycles, 1: instructions
            // 将 UNKNOWN(-1) 映射到最后一个索引
            const categoryIndex = data.componentCategory.category >= 0 ? data.componentCategory.category : categoryCount - 1;

            // 统计负载计数
            count += data.symbolEvents;

            // 判断是否为应用负载：processName 或 threadName 包含 packageName
            if (packageName && data.processName.includes(packageName)) {
                app_count += data.symbolEvents;
            }

            // 统计组件负载
            if (!componentMap.has(componentKey)) {
                componentMap.set(componentKey, {
                    name: data.componentCategory.categoryName,
                    cycles: 0,
                    totalCycles: 0,
                    instructions: 0,
                    totalInstructions: 0,
                    category: data.componentCategory,
                });
            }

            const component = componentMap.get(componentKey)!;
            if (eventIndex === PerfEvent.CYCLES_EVENT) {
                component.cycles += data.symbolEvents;
                component.totalCycles += data.symbolTotalEvents;
            } else {
                // Must be INSTRUCTION_EVENT since there are only two enum values
                component.instructions += data.symbolEvents;
                component.totalInstructions += data.symbolTotalEvents;
            }

            // 统计大类负载
            if (categoryIndex >= 0 && categoryIndex < categoryCount) {
                categoriesSum[categoryIndex][eventIndex] += data.symbolEvents;
                categoriesTotal[categoryIndex][eventIndex] += data.symbolTotalEvents;
            }

            // 统计总值
            total[eventIndex] += data.symbolEvents;
        }

        return {
            stepIdx: groupId,
            components: Array.from(componentMap.values()),
            categoriesSum,
            categoriesTotal,
            total,
            count,
            app_count,
        };
    }

    /**
     * 生成 summary_info.json，使用已统计的 count 和 app_count 值
     */
    async generateSummaryInfoJson(
        input: string,
        testInfo: TestReportInfo,
        steps: Array<Step>
    ): Promise<void> {
        const outputDir = path.join(input, 'report');
        let summaryJsonObject: Array<SummaryInfo> = [];

        steps.forEach((step) => {
            // 从已统计的 stepSumMap 中获取数据
            const stepSum = this.stepSumMap.get(step.stepIdx);
            if (!stepSum) {
                logger.warn(`未找到步骤 ${step.stepIdx} 的统计信息`);
                return;
            }

            const summaryObject: SummaryInfo = {
                rom_version: testInfo.rom_version,
                app_version: testInfo.app_version,
                scene: testInfo.scene,
                step_name: step.description,
                step_id: step.stepIdx,
                count: stepSum.count, // 使用已统计的总负载数
                app_count: stepSum.app_count, // 使用已统计的应用负载数
            };
            summaryJsonObject.push(summaryObject);
        });

        await saveJsonArray(summaryJsonObject, path.join(outputDir, 'summary_info.json'));
        logger.info(`已生成 summary_info.json，包含 ${summaryJsonObject.length} 个步骤的汇总信息`);
    }
}
