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
import initSqlJs, { Database } from 'sql.js';
import writeXlsxFile from 'write-excel-file/node';
import { createHash } from 'crypto';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ComponentCategory, OriginKind, getComponentCategories } from '../component';
import {
    ClassifyCategory,
    CYCLES_EVENT,
    FileClassification,
    INSTRUCTION_EVENT,
    PerfAnalyzerBase,
    PerfEvent,
    PerfSum,
    PerfSymbolDetailData,
    TestSceneInfo,
    TestStep,
    UNKNOWN_STR,
} from './perf_analyzer_base';
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
    name: string;
    processId: number;
    threadId: number;
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
    totalEvents: number[]; // 标记取totalEvent位置
    stack: PerfCall[]; // 调用栈
}

// 定义单个 step 的结构
export interface Step {
    name: string;
    stepIdx: number;
    description: string;
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
    AND perf_sample.thread_id IN (
        SELECT
            child.thread_id
        FROM
            perf_thread parent
            INNER JOIN perf_thread child ON child.process_id = parent.thread_id
        WHERE
            parent.thread_id = parent.process_id
            AND parent.thread_name IN (:appBundleName, :appBundleName|| ':ui', :appBundleName || ':render', :appBundleName || ':background', :appBundleName|| 'service:ui'))
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

const PERF_PROCESS_TOTAL_SQL = `
SELECT
    SUM(perf_sample.event_count)
FROM
    perf_sample
    INNER JOIN perf_report ON perf_report.id = perf_sample.event_type_id
WHERE
    perf_report.report_value IN ('hw-instructions', 'instructions', 'raw-instruction-retired', 'hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles')
`;

export class PerfAnalyzer extends PerfAnalyzerBase {
    protected threadsMap: Map<number, PerfThread>; // 线程表
    protected callchainsMap: Map<number, PerfCallchain>; // 调用链表
    protected callchainIds: Set<number>;
    protected testSteps: TestStep[];
    protected samples: PerfSample[];

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
            db = new SQL.Database(fs.readFileSync(dbfile!));
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

    async analyze(testInfo: TestSceneInfo, output: string): Promise<PerfSum> {
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
        await this.loadDbAndStatistics(testInfo, output, testInfo.packageName);
        let perfPath = '';
        let isFirstPerfPath = true;
        for (const step of testInfo.rounds[testInfo.chooseRound].steps!) {
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

        let now = new Date().getTime();
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

        return perf;
    }

    private async loadDbAndStatistics(testInfo: TestSceneInfo, output: string, packageName: string): Promise<void> {
        let SQL = await initSqlJs();
        for (const stepGroup of testInfo.rounds[testInfo.chooseRound].steps) {
            logger.info(`loadDbAndStatistics groupId=${stepGroup.groupId} parse dbfile ${stepGroup.dbfile}`);
            const db = new SQL.Database(fs.readFileSync(stepGroup.dbfile!));

            try {
                // 统计信息
                this.loadStatistics(db, packageName, testInfo.scene, stepGroup.groupId);
                // for debug
                if (getConfig().save.callchain) {
                    await this.saveCallchainXlsx(
                        path.join(output, `callchain_${testInfo.packageName}_${testInfo.scene}`)
                    );
                }
            } catch (error) {
                let err = error as Error;
                logger.error(`loadDbAndStatistics ${err}, ${err.stack} ${stepGroup.dbfile}`);
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

    private loadStatistics(db: Database, packageName: string, scene: string, groupId: number): number {
        // 读取所有线程信息
        this.queryThreads(db, packageName, scene);
        // 读取所有文件信息
        this.queryFiles(db);
        // 读取所有符号信息
        this.querySymbols(db);
        // 预处理调用链信息
        this.queryCallchain(db, packageName);
        this.disassembleCallchainLoad();
        // 读取测试步骤时间戳
        this.queryTestStepTimestamps(db, groupId);
        // 读取样本数据
        return this.queryProcessSample(db, packageName, groupId);
    }

    private queryTestStepTimestamps(db: Database, groupId: number): void {
        const results = db.exec(TEST_STEP_TIMESTAMPS);
        let steps: { name: string; ts: number; dur: number }[] = [];
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
        const results = db.exec('SELECT thread_id, process_id, thread_name FROM perf_thread');
        if (results.length === 0) {
            return;
        }

        results[0].values.map((row) => {
            let threadClassify = this.classifyThread(row[2] as string);
            let name = row[2] as string;
            if (!name || name.length === 0) {
                name = UNKNOWN_STR;
            }
            let thread: PerfThread = {
                threadId: row[0] as number,
                processId: row[1] as number,
                name: name,
                classification: threadClassify,
            };
            this.threadsMap.set(thread.threadId, thread);
        });
    }

    /**
     * read all files from perf_files table, then use FileClassifier to classify the files.
     * @param db
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
            originKind: OriginKind.UNKNOWN,
        });
        results[0].values.map((row) => {
            let file = row[1] as string;
            // pid 替换成'{pid}, 方便版本间比较
            const pidMatch = file.match(/\/proc\/(\d+)\//);
            if (pidMatch) {
                file = file.replace(`/${pidMatch[1]}/`, '/{pid}/');
            }
            let fileClassify = this.classifyFile(file);
            this.filesClassifyMap.set(row[0] as number, fileClassify);
        });
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
    private queryCallchain(db: Database, processName: string): void {
        const results = db.exec(PERF_PROCESS_CALLCHAIN_SQL, [processName]);
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
            
            let callchain = this.callchainsMap.get(row[0] as number) || {
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
        for (const [_, callchain] of this.callchainsMap) {
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

        let callchainData: { type?: any; value: any }[][] = [];
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
                    { value: call.classification.file || '', type: String },
                    { value: this.symbolsMap.get(call.symbolId) || '', type: String },
                    { value: ComponentCategory[call.classification.category!], type: String },
                    { value: call.classification.subCategoryName || '', type: String },
                    { value: OriginKind[call.classification.originKind!], type: String },
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
    private queryProcessSample(db: Database, appBundleName: string, groupId: number): number {
        const results = db.exec(PERF_PROCESS_SAMPLE_SQL, [appBundleName]);
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
                event_count: row[3] as number,
                cpu_id: row[4] as number,
                event_name: row[5] as string,
                timestamp: row[6] as number,
            });
        });

        return this.calcSymbolData(groupId);
    }

    private queryProcessTotal(db: Database): number {
        let total = 0;
        const results = db.exec(PERF_PROCESS_TOTAL_SQL);
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
     * @param classifyThread
     */
    public calcSymbolData(groupId: number): number {
        let resultMaps: Map<string, PerfSymbolDetailData> = new Map();
        let fileEventMaps: Map<string, number> = new Map();
        let threadsEventMap: Map<string, number> = new Map(); // 线程统计事件数
        let processEventMap: Map<string, number> = new Map(); // 进程统计事件数

        for (const sample of this.samples) {
            let event = this.getEventType(sample.event_name);
            if (event === null) {
                continue;
            }

            let thread = this.threadsMap.get(sample.thread_id);
            if (!thread) {
                thread = {
                    name: UNKNOWN_STR,
                    processId: sample.thread_id,
                    threadId: sample.thread_id,
                    classification: {
                        category: ComponentCategory.UNKNOWN,
                        categoryName: UNKNOWN_STR,
                        subCategoryName: UNKNOWN_STR,
                    },
                };
                this.threadsMap.set(sample.thread_id, thread);
            }
            let process = this.threadsMap.get(thread.processId)!;
            if (!process) {
                logger.error(`calcSymbolData process ${thread.processId} not found`);
                continue;
            }

            let callchain = this.callchainsMap.get(sample.callchain_id)!;
            let call = callchain.stack[callchain.selfEvent];
            let data: PerfSymbolDetailData = {
                stepIdx: groupId,
                eventType: event,
                pid: process.processId,
                processName: process.name,
                processEvents: 0,
                tid: thread.threadId,
                threadEvents: 0,
                threadName: thread.name,
                file: call.classification.file,
                fileEvents: 0,
                symbol: this.symbolsMap.get(call.symbolId) || '',
                symbolEvents: sample.event_count,
                symbolTotalEvents: 0,
                originKind: call.classification.originKind,
                componentCategory: call.classification.category,
                componentName: call.classification.subCategoryName,
            };

            let threadEventCount = threadsEventMap.get(this.getThreadKey(data)) || 0;
            threadsEventMap.set(this.getThreadKey(data), threadEventCount + sample.event_count);

            let processEventCount = processEventMap.get(this.getProcessKey(data)) || 0;
            processEventMap.set(this.getProcessKey(data), processEventCount + sample.event_count);

            // 根据线程名直接分类
            if (thread.classification.category !== ComponentCategory.UNKNOWN) {
                if (thread.classification.subCategoryName) {
                    data.componentName = thread.classification.subCategoryName;
                } else {
                    data.componentName = path.basename(call.classification.file);
                }

                data.componentCategory = thread.classification.category;
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
        return 0;
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
}
