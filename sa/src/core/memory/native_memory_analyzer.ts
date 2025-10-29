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

import fs from 'fs';
import path from 'path';
import type { Database } from 'sql.js';
import initSqlJs from 'sql.js';
import writeXlsxFile from 'write-excel-file/node';
import type { SheetData } from 'write-excel-file';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ComponentCategory } from '../../types/component';
import { getConfig } from '../../config';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * Native Hook 事件记录
 */
export interface NativeHookEvent {
    id: number;
    callchain_id: number;
    ipid: number;
    itid: number;
    event_type: string;
    sub_type_id: number;
    start_ts: number;
    end_ts: number;
    dur: number;
    addr: number;
    heap_size: number;
    all_heap_size: number;
    current_size_dur: number;
    last_lib_id: number;
    last_symbol_id: number;
}

/**
 * 进程信息
 */
export interface ProcessInfo {
    id: number;
    ipid: number;
    pid: number;
    name: string;
}

/**
 * 线程信息
 */
export interface ThreadInfo {
    id: number;
    itid: number;
    tid: number;
    name: string;
    ipid: number;
}

export enum EventType {
    AllocEvent = 'AllocEvent',
    FreeEvent = 'FreeEvent',
    MmapEvent = 'MmapEvent',
    MunmapEvent = 'MunmapEvent',
}

/**
 * Native Hook 调用栈帧
 */
export interface NativeHookFrame {
    id: number;
    callchain_id: number;
    depth: number;
    ip: number;
    symbol_id: number;
    symbol: string;
    file_id: number;
    file: string;
    offset: number;
    symbol_offset: number;
    vaddr: string;
}

/**
 * 平铺的 Native Memory 数据记录
 *
 * 新的数据结构：每条记录代表一个原始事件，不再聚合
 * 前端会根据不同维度的 key 进行独立计算
 */
export interface NativeMemoryRecord {
    stepIdx: number;
    // 进程维度信息
    pid: number;
    process: string;
    // 线程维度信息
    tid: number | null;
    thread: string | null;
    // 文件维度信息
    fileId: number | null;
    file: string | null;
    // 符号维度信息
    symbolId: number | null;
    symbol: string | null;
    // 事件信息
    eventType: string;
    subEventType: string;
    // 内存大小（单次分配/释放的大小）
    heapSize: number;
    // 相对时间戳（相对于 trace 开始时间）
    allHeapSize: number;
    relativeTs: number;
    // 分类信息 - 大类
    componentCategory: ComponentCategory;
    // 分类信息 - 小类
    componentName: string;
    categoryName: string;
    subCategoryName: string;
}

/**
 * 分类配置接口
 */
interface ClassifyCategory {
    category: ComponentCategory;
    categoryName: string;
    subCategoryName: string;
}

/**
 * 文件分类结果
 */
interface FileClassification {
    file: string;
    category: ComponentCategory;
    categoryName: string;
    subCategoryName: string;
}

/**
 * Native Memory 分析器
 * 参考 PerfAnalyzer 的结构，使用清晰的分析流程
 * 
 * 关键优化：
 * 1. 使用 heap_size 而不是 all_heap_size
 * 2. 一条调用链上的内存都归到栈顶（depth=0），其他帧信息不记录
 * 3. 按照 (stepIdx, tid, file, symbol) 作为唯一键聚合数据
 * 4. 计算每个维度的统计信息：进程、线程、文件、符号
 */
export class NativeMemoryAnalyzer {
    private dbPath: string;

    // 缓存数据
    private events: Array<NativeHookEvent> = [];
    private processes: Array<ProcessInfo> = [];
    private threads: Array<ThreadInfo> = [];
    private processMap: Map<number, ProcessInfo> = new Map();
    private threadMap: Map<number, ThreadInfo> = new Map();
    private subTypeNameMap: Map<number, string> = new Map(); // sub_type_id 到名称的映射
    private dataDictMap: Map<number, string> = new Map(); // data_dict id 到 data 的映射
    private traceStartTs = 0; // trace_range 的 start_ts，用于时间换算

    // 分类配置
    private fileClassifyCfg: Map<string, ClassifyCategory> = new Map();
    private fileRegexClassifyCfg: Map<RegExp, ClassifyCategory> = new Map();

    constructor(dbPath: string, _packageName?: string) {
        this.dbPath = dbPath;
        this.loadPerfKindCfg();
    }

    /**
     * 从配置文件加载分类规则
     * 参考 PerfAnalyzerBase 的 loadPerfKindCfg 方法
     */
    private loadPerfKindCfg(): void {
        for (const componentConfig of getConfig().perf.kinds) {
            for (const sub of componentConfig.components) {
                for (const file of sub.files) {
                    if (this.hasRegexChart(file)) {
                        this.fileRegexClassifyCfg.set(new RegExp(file), {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name ?? 'unknown',
                        });
                    } else {
                        this.fileClassifyCfg.set(file, {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name ?? 'unknown',
                        });
                    }
                }
            }
        }
    }

    /**
     * 检查字符串是否包含正则表达式字符
     */
    private hasRegexChart(symbol: string): boolean {
        if (
            symbol.indexOf('$') >= 0 ||
            symbol.indexOf('d+') >= 0 ||
            symbol.indexOf('.*') >= 0 ||
            symbol.indexOf('.+') >= 0
        ) {
            return true;
        }
        return false;
    }

    /**
     * 加载数据库中的所有数据
     */
    private async loadData(db: Database): Promise<void> {
        this.events = this.queryNativeHookEvents(db);
        this.processes = this.queryProcesses(db);
        this.threads = this.queryThreads(db);
        this.subTypeNameMap = this.querySubTypeNames(db);
        this.dataDictMap = this.queryDataDict(db); // 查询 data_dict 表，用于获取符号和文件名称
        this.traceStartTs = this.queryTraceStartTs(db); // 查询 trace_range 的 start_ts，用于时间换算

        // 构建映射
        this.processes.forEach(p => this.processMap.set(p.id, p));
        this.threads.forEach(t => this.threadMap.set(t.id, t));

    }

    /**
     * 执行分析，直接返回平铺数据
     * 参考 PerfAnalyzer 的 calcSymbolData 方法
     */
    async analyze(stepIdx = 1): Promise<Array<NativeMemoryRecord>> {
        logger.info(`Starting Native Memory analysis for ${this.dbPath}`);

        const SQL = await initSqlJs();
        let db: Database | null = null;

        try {
            const buffer = fs.readFileSync(this.dbPath);
            db = new SQL.Database(buffer);

            // 加载所有数据
            await this.loadData(db);
            logger.info(`Loaded ${this.events.length} events, ${this.processes.length} processes, ${this.threads.length} threads`);

            // 导出事件和调用栈数据到 Excel
            await this.exportToExcel(db, stepIdx);

            // 直接生成平铺数据
            const records = this.generateMemoryRecords(stepIdx);
            logger.info(`Native Memory analysis completed, generated ${records.length} records`);
            return records;

        } catch (error) {
            logger.error(`Error analyzing native memory: ${error}`);
            throw error;
        } finally {
            if (db) {
                db.close();
            }
        }
    }

    /**
     * 计算内存统计信息（峰值、平均值、持续时间）
     */
    calculateMemoryStats(): { peak_memory_size: number; peak_memory_duration: number; average_memory_size: number } {
        if (this.events.length === 0) {
            return {
                peak_memory_size: 0,
                peak_memory_duration: 0,
                average_memory_size: 0,
            };
        }

        let peakMemorySize = 0;
        let peakMemoryDuration = 0;
        let totalMemory = 0;
        let memoryCount = 0;

        // 遍历所有事件，计算峰值和平均值
        this.events.forEach((event) => {
            const currentSize = event.all_heap_size || 0;
            if (currentSize > peakMemorySize) {
                peakMemorySize = currentSize;
                peakMemoryDuration = event.current_size_dur || 0;
            }
            totalMemory += currentSize;
            memoryCount++;
        });

        const averageMemorySize = memoryCount > 0 ? totalMemory / memoryCount : 0;

        return {
            peak_memory_size: peakMemorySize,
            peak_memory_duration: peakMemoryDuration,
            average_memory_size: averageMemorySize,
        };
    }

    /**
     * 生成平铺的内存记录
     *
     * 新逻辑：
     * 1. 为每个事件生成一条记录，不再聚合
     * 2. 每条记录包含所有 4 个维度的信息（pid, tid, fileId, symbolId）
     * 3. 如果某个维度没有信息，则设为 null
     * 4. 记录包含 heapSize（单次分配/释放大小）和 relativeTs（相对时间戳）
     * 5. 根据文件、符号、线程进行分类，获取大类和小类信息
     * 6. 前端根据不同维度的 key 进行独立计算
     */
    private generateMemoryRecords(stepIdx: number): Array<NativeMemoryRecord> {
        const records: Array<NativeMemoryRecord> = [];

        // 遍历所有事件，为每个事件生成一条记录
        for (const event of this.events) {
            const process = this.processMap.get(event.ipid);
            if (!process) {continue;}

            const thread = this.threadMap.get(event.itid);

            // 获取文件和符号信息
            let filePath: string | null = null;
            let symbolName: string | null = null;
            let fileId: number | null = null;
            let symbolId: number | null = null;

            // 获取文件信息 - 直接从 data_dict 表中查询
            if (event.last_lib_id && event.last_lib_id > 0) {
                fileId = event.last_lib_id;
                filePath = this.dataDictMap.get(event.last_lib_id) ?? 'unknown';
            }

            // 获取符号信息 - 直接从 data_dict 表中查询
            if (event.last_symbol_id && event.last_symbol_id > 0) {
                symbolId = event.last_symbol_id;
                symbolName = this.dataDictMap.get(event.last_symbol_id) ?? 'unknown';
            }

            // 1. 先对文件进行分类
            const fileClassification = this.classifyFile(filePath ?? 'unknown');

            // 2. 再对符号进行分类（如果有符号信息）
            let symbolClassification = fileClassification;
            if (symbolName && symbolName !== 'unknown') {
                symbolClassification = this.classifySymbol(symbolName, fileClassification);
            }

            // 3. 对线程进行分类（如果有线程信息）
            const threadClassification = this.classifyThread(thread?.name ?? null);

            // 4. 确定最终的分类信息
            // 优先级：符号 > 文件 > 线程 > 进程
            let finalCategoryName = symbolClassification.categoryName;
            let finalSubCategoryName = symbolClassification.subCategoryName;
            let finalComponentName = symbolName ?? filePath ?? thread?.name ?? process.name;

            // 如果符号分类没有返回有效的小类，使用线程分类
            if (!finalSubCategoryName && thread?.name) {
                finalSubCategoryName = threadClassification.subCategoryName;
            }

            // 创建记录
            const record: NativeMemoryRecord = {
                stepIdx,
                pid: process.pid,
                process: process.name,
                tid: thread?.tid ?? null,
                thread: thread?.name ?? null,
                fileId: fileId,
                file: filePath,
                symbolId: symbolId,
                symbol: symbolName,
                eventType: event.event_type,
                subEventType: this.subTypeNameMap.get(event.sub_type_id) ?? '',
                heapSize: event.heap_size,
                allHeapSize: event.all_heap_size, // 当前时间点的累积内存值
                relativeTs: event.start_ts - this.traceStartTs,
                // 分类信息
                componentName: finalComponentName,
                componentCategory: symbolClassification.category,
                categoryName: finalCategoryName,
                subCategoryName: finalSubCategoryName,
            };

            records.push(record);
        }

        return records;
    }

    /**
     * 查询sub_type_id对应的名称
     */
    private querySubTypeNames(db: Database): Map<number, string> {
        const subTypeNameMap = new Map<number, string>();
        try {
            const sql = `SELECT id, data FROM data_dict WHERE id IN (
                SELECT DISTINCT sub_type_id FROM native_hook
            )`;
            const result = db.exec(sql);
            if (result.length > 0) {
                for (const row of result[0].values) {
                    subTypeNameMap.set(row[0] as number, row[1] as string);
                }
            }
        } catch (error) {
            logger.warn(`Failed to query sub_type_id names: ${error}`);
        }
        return subTypeNameMap;
    }

    /**
     * 查询 data_dict 表中的所有数据
     * 用于获取 symbol_id 和 file_id 对应的名称
     */
    private queryDataDict(db: Database): Map<number, string> {
        const dataDictMap = new Map<number, string>();
        try {
            const sql = 'SELECT id, data FROM data_dict';
            const result = db.exec(sql);
            if (result.length > 0) {
                for (const row of result[0].values) {
                    dataDictMap.set(row[0] as number, row[1] as string);
                }
            }
        } catch (error) {
            logger.warn(`Failed to query data_dict: ${error}`);
        }
        return dataDictMap;
    }



    /**
     * 查询所有native hook事件
     */
    private queryNativeHookEvents(db: Database): Array<NativeHookEvent> {
        const sql = `
            SELECT
                id, callchain_id, ipid, itid, event_type, sub_type_id,
                start_ts, end_ts, dur, addr, heap_size, all_heap_size,
                current_size_dur, last_lib_id, last_symbol_id
            FROM native_hook
            ORDER BY start_ts
        `;

        const result = db.exec(sql);
        if (result.length === 0) {
            return [];
        }

        const events: Array<NativeHookEvent> = [];
        const rows = result[0].values;

        for (const row of rows) {
            events.push({
                id: row[0] as number,
                callchain_id: row[1] as number,
                ipid: row[2] as number,
                itid: row[3] as number,
                event_type: row[4] as string,
                sub_type_id: row[5] as number,
                start_ts: row[6] as number,
                end_ts: row[7] as number,
                dur: row[8] as number,
                addr: row[9] as number,
                heap_size: row[10] as number,
                all_heap_size: row[11] as number,
                current_size_dur: row[12] as number,
                last_lib_id: row[13] as number,
                last_symbol_id: row[14] as number,
            });
        }

        return events;
    }



    /**
     * 查询进程信息
     */
    private queryProcesses(db: Database): Array<ProcessInfo> {
        const sql = 'SELECT id, ipid, pid, name FROM process';
        const result = db.exec(sql);
        if (result.length === 0) {
            return [];
        }

        const processes: Array<ProcessInfo> = [];
        const rows = result[0].values;

        for (const row of rows) {
            processes.push({
                id: row[0] as number,
                ipid: row[1] as number,
                pid: row[2] as number,
                name: row[3] as string,
            });
        }

        return processes;
    }

    /**
     * 查询线程信息
     */
    private queryThreads(db: Database): Array<ThreadInfo> {
        const sql = 'SELECT id, itid, tid, name, ipid FROM thread';
        const result = db.exec(sql);
        if (result.length === 0) {
            return [];
        }

        const threads: Array<ThreadInfo> = [];
        const rows = result[0].values;

        for (const row of rows) {
            threads.push({
                id: row[0] as number,
                itid: row[1] as number,
                tid: row[2] as number,
                name: row[3] as string,
                ipid: row[4] as number,
            });
        }

        return threads;
    }

    /**
     * 查询 trace_range 表的 start_ts，用于时间换算
     */
    private queryTraceStartTs(db: Database): number {
        try {
            // 尝试从 trace_range 表查询
            const sql = 'SELECT start_ts FROM trace_range LIMIT 1';
            const result = db.exec(sql);

            if (result.length > 0 && result[0].values.length > 0) {
                const startTs = result[0].values[0][0] as number;
                logger.info(`Loaded trace_range start_ts: ${startTs}`);
                return startTs;
            }
        } catch (error) {
            logger.warn(`Failed to query trace_range: ${error}`);
        }

        // 如果 trace_range 表不存在或为空，使用 native_hook 表的最小时间戳
        try {
            const sql = 'SELECT MIN(start_ts) FROM native_hook';
            const result = db.exec(sql);

            if (result.length > 0 && result[0].values.length > 0) {
                const rawMinTs = result[0].values[0][0];
                if (rawMinTs !== null) {
                    const minTs = Number(rawMinTs);
                    logger.info(`Using native_hook min start_ts as baseline: ${minTs}`);
                    return minTs;
                }
            }
        } catch (error) {
            logger.warn(`Failed to query native_hook min start_ts: ${error}`);
        }

        logger.warn('Could not determine trace start timestamp, using 0');
        return 0;
    }

    /**
     * 分类文件
     * 参考 PerfAnalyzerBase 的分类逻辑，但针对 Native Memory 数据进行优化
     *
     * 分类优先级：
     * 1. 精确路径匹配（配置中的完整路径）
     * 2. 正则表达式匹配（配置中的正则规则）
     * 3. 应用 Bundle 文件检测（proc 目录下的 bundle 路径）
     * 4. 文件名匹配（配置中的文件名）
     * 5. 默认分类（系统库）
     */
    private classifyFile(filePath: string): FileClassification {
        const fileName = path.basename(filePath);

        // 处理 unknown 或空文件路径
        if (!filePath || filePath === 'unknown' || filePath.toLowerCase() === 'unknown') {
            return {
                file: filePath,
                category: ComponentCategory.UNKNOWN,
                categoryName: 'UNKNOWN',
                subCategoryName: 'unknown',
            };
        }

        // 1. 精确路径匹配（最高优先级）
        if (this.fileClassifyCfg.has(filePath)) {
            const component = this.fileClassifyCfg.get(filePath)!;
            return {
                file: filePath,
                category: component.category,
                categoryName: component.categoryName,
                subCategoryName: component.subCategoryName,
            };
        }

        // 2. 正则表达式匹配
        for (const [regex, component] of this.fileRegexClassifyCfg) {
            if (filePath.match(regex)) {
                return {
                    file: filePath,
                    category: component.category,
                    categoryName: component.categoryName,
                    subCategoryName: component.subCategoryName,
                };
            }
        }

        // 3. 应用 Bundle 文件检测（参考 PerfAnalyzerBase 的逻辑）
        const bundleRegex = new RegExp('/proc/.*/data/storage/.*/bundle/.*');
        if (filePath.match(bundleRegex)) {
            // Bundle 中的 .so 文件
            if (fileName.endsWith('.so') || filePath.includes('/bundle/libs/')) {
                return {
                    file: filePath,
                    category: ComponentCategory.APP_SO,
                    categoryName: 'APP_SO',
                    subCategoryName: fileName,
                };
            }
            // Bundle 中的 .abc 文件
            if (fileName.endsWith('.abc')) {
                return {
                    file: filePath,
                    category: ComponentCategory.APP_ABC,
                    categoryName: 'APP_ABC',
                    subCategoryName: fileName,
                };
            }
        }

        // 4. 文件名匹配（作为后备方案）
        if (this.fileClassifyCfg.has(fileName)) {
            const component = this.fileClassifyCfg.get(fileName)!;
            return {
                file: filePath,
                category: component.category,
                categoryName: component.categoryName,
                subCategoryName: component.subCategoryName,
            };
        }

        // 5. 默认分类：系统库
        return {
            file: filePath,
            category: ComponentCategory.SYS_SDK,
            categoryName: 'SYS_SDK',
            subCategoryName: fileName,
        };
    }

    /**
     * 分类符号
     * 参考 PerfAnalyzerBase 的分类逻辑
     * 对于 APP_ABC 类型的符号，提取包名作为小类
     * 对于 KMP 类型的符号，提取包名作为小类
     */
    private classifySymbol(symbolName: string | null, fileClassification: FileClassification): FileClassification {
        if (!symbolName || symbolName === 'unknown') {
            return fileClassification;
        }

        // 对于 APP_ABC 类型的符号，提取包名
        if (fileClassification.category === ComponentCategory.APP_ABC) {
            // ETS 符号格式：functionName: [url:entry|@package/module|version|path:line:column]
            const regex = /([^:]+):\[url:([^:\|]+)\|([^|]+)\|([^:\|]+)\|([^\|\]]*):(\d+):(\d+)\]$/;
            const matches = symbolName.match(regex);
            if (matches) {
                 
                const [_, _functionName, _entry, packageName, version, filePath, _line, _column] = matches;
                return {
                    file: `${packageName}/${version}/${filePath}`,
                    category: fileClassification.category,
                    categoryName: fileClassification.categoryName,
                    subCategoryName: packageName, // 使用包名作为小类
                };
            }
        }

        // 对于 KMP 类型的符号，提取包名
        if (fileClassification.category === ComponentCategory.KMP && symbolName.startsWith('kfun')) {
            // KMP 符号格式：kfun:package.class.function
            const parts = symbolName.split('.');
            if (parts.length > 1) {
                const packageName = parts[0].replace('kfun:', '');
                return {
                    file: `${packageName}.${parts[1]}`,
                    category: fileClassification.category,
                    categoryName: fileClassification.categoryName,
                    subCategoryName: packageName, // 使用包名作为小类
                };
            }
        }

        return fileClassification;
    }

    /**
     * 分类线程
     * 参考 PerfAnalyzerBase 的分类逻辑
     * 根据线程名称进行分类
     */
    private classifyThread(threadName: string | null): FileClassification {
        if (!threadName) {
            return {
                file: 'unknown',
                category: ComponentCategory.UNKNOWN,
                categoryName: 'UNKNOWN',
                subCategoryName: 'UNKNOWN'
            };
        }

        // 对于 Native Memory，直接使用线程名称作为小类
        // 如果需要更复杂的线程分类，可以在这里添加规则
        return {
            file: threadName,
            category: ComponentCategory.UNKNOWN,
            categoryName: 'Thread',
            subCategoryName: threadName
        };
    }

    /**
     * 导出事件和调用栈数据到 Excel
     */
    private async exportToExcel(db: Database, stepIdx: number): Promise<void> {
        try {
            // 获取数据库文件所在目录
            const dbDir = path.dirname(this.dbPath);

            // 查询调用栈帧数据（从数据库直接查询所有数据）
            const frames = this.queryAllNativeHookFrames(db);
            logger.info(`Queried ${frames.length} callchain frames from database`);

            // 构建事件到 last_lib_id 和 last_symbol_id 的映射
            const eventSelectionMap = new Map<number, { last_lib_id: number; last_symbol_id: number }>();
            for (const event of this.events) {
                eventSelectionMap.set(event.callchain_id, {
                    last_lib_id: event.last_lib_id,
                    last_symbol_id: event.last_symbol_id,
                });
            }

            // 构建事件数据表格
            const eventsSheetData: SheetData = [];

            // 事件表头
            eventsSheetData.push([
                { value: 'id', fontWeight: 'bold' as const },
                { value: 'callchain_id', fontWeight: 'bold' as const },
                { value: 'ipid', fontWeight: 'bold' as const },
                { value: 'itid', fontWeight: 'bold' as const },
                { value: 'event_type', fontWeight: 'bold' as const },
                { value: 'sub_type_id', fontWeight: 'bold' as const },
                { value: 'start_ts', fontWeight: 'bold' as const },
                { value: 'end_ts', fontWeight: 'bold' as const },
                { value: 'dur', fontWeight: 'bold' as const },
                { value: 'addr', fontWeight: 'bold' as const },
                { value: 'heap_size', fontWeight: 'bold' as const },
                { value: 'all_heap_size', fontWeight: 'bold' as const },
                { value: 'current_size_dur', fontWeight: 'bold' as const },
                { value: 'last_lib_id', fontWeight: 'bold' as const },
                { value: 'last_symbol_id', fontWeight: 'bold' as const },
            ]);

            // 事件数据行
            for (const event of this.events) {
                eventsSheetData.push([
                    { value: event.id, type: Number },
                    { value: event.callchain_id, type: Number },
                    { value: event.ipid, type: Number },
                    { value: event.itid, type: Number },
                    { value: event.event_type, type: String },
                    { value: event.sub_type_id, type: Number },
                    { value: event.start_ts, type: Number },
                    { value: event.end_ts, type: Number },
                    { value: event.dur, type: Number },
                    { value: event.addr, type: Number },
                    { value: event.heap_size, type: Number },
                    { value: event.all_heap_size, type: Number },
                    { value: event.current_size_dur, type: Number },
                    { value: event.last_lib_id, type: Number },
                    { value: event.last_symbol_id, type: Number },
                ]);
            }

            // 第一步：识别哪些 callchain_id 至少有一个 selected 为 YES 的帧
            const validCallchainIds = new Set<number>();
            for (const frame of frames) {
                const selection = eventSelectionMap.get(frame.callchain_id);
                const isSelected = selection &&
                    frame.file_id === selection.last_lib_id &&
                    frame.symbol_id === selection.last_symbol_id;

                if (isSelected) {
                    validCallchainIds.add(frame.callchain_id);
                }
            }

            logger.info(`Found ${validCallchainIds.size} callchain_ids with at least one selected frame`);

            // 第二步：只保留有效 callchain_id 的帧
            const filteredFrames = frames.filter(frame => validCallchainIds.has(frame.callchain_id));
            logger.info(`Filtered frames: ${frames.length} -> ${filteredFrames.length} (reduced ${frames.length - filteredFrames.length} frames)`);

            // 构建调用栈帧数据表格
            const framesSheetData: SheetData = [];

            // 调用栈帧表头（添加 selected 列）
            framesSheetData.push([
                { value: 'id', fontWeight: 'bold' as const },
                { value: 'callchain_id', fontWeight: 'bold' as const },
                { value: 'depth', fontWeight: 'bold' as const },
                { value: 'ip', fontWeight: 'bold' as const },
                { value: 'symbol_id', fontWeight: 'bold' as const },
                { value: 'symbol', fontWeight: 'bold' as const },
                { value: 'file_id', fontWeight: 'bold' as const },
                { value: 'file', fontWeight: 'bold' as const },
                { value: 'selected', fontWeight: 'bold' as const }, // 新增：标记是否被选中
            ]);

            // 调用栈帧数据行（只包含有效的 callchain_id）
            for (const frame of filteredFrames) {
                // 判断该帧是否被选中
                // 选中条件：该帧的 file_id 匹配事件的 last_lib_id，且 symbol_id 匹配事件的 last_symbol_id
                const selection = eventSelectionMap.get(frame.callchain_id);
                const isSelected = selection &&
                    frame.file_id === selection.last_lib_id &&
                    frame.symbol_id === selection.last_symbol_id;

                framesSheetData.push([
                    { value: frame.id, type: Number },
                    { value: frame.callchain_id, type: Number },
                    { value: frame.depth, type: Number },
                    { value: frame.ip, type: Number },
                    { value: frame.symbol_id, type: Number },
                    { value: frame.symbol, type: String },
                    { value: frame.file_id, type: Number },
                    { value: frame.file, type: String },
                    { value: isSelected ? 'YES' : 'NO', type: String }, // 标记是否被选中
                ]);
            }

            // 写入 Excel 文件
            const outputPath = path.join(dbDir, `native_memory_step${stepIdx}.xlsx`);

            // 确保目录存在
            if (!fs.existsSync(dbDir)) {
                fs.mkdirSync(dbDir, { recursive: true });
            }

            await writeXlsxFile([
                eventsSheetData,
                framesSheetData,
            ], {
                sheets: ['NativeHookEvents', 'NativeHookFrames'],
                filePath: outputPath,
            });

            logger.info(`Excel file exported to: ${outputPath}`);
            logger.info(`  - NativeHookEvents: ${this.events.length} rows`);
            logger.info(`  - NativeHookFrames: ${filteredFrames.length} rows (filtered from ${frames.length})`);
        } catch (error) {
            logger.error(`Failed to export Excel: ${error}`);
        }
    }

    /**
     * 查询所有调用栈帧（从数据库直接查询，不过滤）
     */
    private queryAllNativeHookFrames(db: Database): Array<NativeHookFrame> {
        const sql = `
            SELECT
                id, callchain_id, depth, ip, symbol_id, file_id,
                offset, symbol_offset, vaddr
            FROM native_hook_frame
            ORDER BY callchain_id, depth
        `;

        const result = db.exec(sql);
        if (result.length === 0) {
            return [];
        }

        const frames: Array<NativeHookFrame> = [];
        const rows = result[0].values;

        for (const row of rows) {
            const symbolId = row[4] as number;
            const fileId = row[5] as number;

            frames.push({
                id: row[0] as number,
                callchain_id: row[1] as number,
                depth: row[2] as number,
                ip: row[3] as number,
                symbol_id: symbolId,
                symbol: this.dataDictMap.get(symbolId) ?? 'unknown',
                file_id: fileId,
                file: this.dataDictMap.get(fileId) ?? 'unknown',
                offset: row[6] as number,
                symbol_offset: row[7] as number,
                vaddr: row[8] as string,
            });
        }

        return frames;
    }

}

