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
import type { Component, ComponentCategoryType } from '../component';
import { ComponentCategory, OriginKind } from '../component';
import { AnalyzerProjectBase, PROJECT_ROOT } from '../project';
import { getConfig } from '../../config';
import writeXlsxFile from 'write-excel-file/node';
import { PerfDatabase } from './perf_database';
import { saveJsonArray } from '../../utils/json_utils';
import type { SheetData } from 'write-excel-file';

export const UNKNOWN_STR = 'unknown';

export interface StepJsonData {
    step_name: string;
    step_id: number;
    count: number;
    round: number;
    perf_data_path: string;
    data: Array<PerfSymbolDetailData>;
}

export interface TestStepGroup {
    reportRoot: string;
    groupId: number;
    groupName: string;
    dbfile?: string;
    perfReport?: string;
    traceFile?: string;
    perfFile?: string;
}

export interface Round {
    steps: Array<TestStepGroup>;
}

export interface TestSceneInfo {
    packageName: string; // 应用包名
    scene: string; // 测试场景名
    osVersion: string; // 操作系统版本
    timestamp: number; // 测试开始时间戳
    appName: string;
    appVersion: string;
    model?: string;
    sn?: string;
    rounds: Array<Round>;
    chooseRound: number;
}

export interface ClassifyCategory {
    category: number; // 组件大类
    categoryName: string; // 组件名
    subCategoryName?: string; // 小类
}

export interface FileClassification extends ClassifyCategory {
    file: string;
    originKind: OriginKind; // 来源，开源
}

export interface PerfComponent {
    name: string; // 组件名
    cycles: number;
    totalCycles: number;
    instructions: number;
    totalInstructions: number;

    category: ComponentCategory; // 大类
    originKind?: OriginKind; // 来源
}

export enum PerfEvent {
    CYCLES_EVENT = 0,
    INSTRUCTION_EVENT = 1,
}

export const CYCLES_EVENT: Set<string> = new Set(['hw-cpu-cycles', 'cpu-cycles', 'raw-cpu-cycles']);
export const INSTRUCTION_EVENT: Set<string> = new Set(['hw-instructions', 'instructions', 'raw-instruction-retired']);

export interface PerfSymbolDetailData {
    stepIdx: number;
    eventType: PerfEvent;
    pid: number;
    processName: string;
    processEvents: number;
    tid: number;
    threadName: string;
    threadEvents: number;
    file: string;
    fileEvents: number;
    symbol: string;
    symbolEvents: number;
    symbolTotalEvents: number;
    componentName?: string;
    componentCategory: ComponentCategory;
    originKind?: OriginKind;
}

export interface PerfStepSum {
    stepIdx: number; // 步骤编号
    components: Array<PerfComponent>; // 计算统计组件负载
    categoriesSum: Array<Array<number>>; // 大类统计值
    categoriesTotal: Array<Array<number>>; // 大类Total值
    total: Array<number>; // 总值, 0 circles, 1 instructions
}

export interface PerfSum {
    scene: string;
    osVersion: string;
    timestamp: number;
    perfPath: string;
    perfId: string;
    steps: Array<PerfStepSum>;
    categories: Array<ComponentCategoryType>;
}

export interface TestStep {
    id: number;
    groupId: number;
    name: string;
    start: number;
    end: number;
}

interface SymbolSplitRule {
    source: RegExp;
    dst: string;
    symbols: Array<RegExp>;
}

export class PerfAnalyzerBase extends AnalyzerProjectBase {
    // classify rule
    protected threadClassifyCfg: Map<RegExp, ClassifyCategory>;
    protected fileClassifyCfg: Map<string, ClassifyCategory>;
    protected fileRegexClassifyCfg: Map<RegExp, ClassifyCategory>;
    protected hapComponents: Map<string, Component>;
    protected symbolsSplitRulesCfg: Array<SymbolSplitRule>;

    // classify result
    protected filesClassifyMap: Map<number, FileClassification>;
    protected symbolsClassifyMap: Map<number, FileClassification>;
    protected symbolsMap: Map<number, string>;

    protected testSteps: Array<TestStep>;
    protected stepSumMap: Map<number, PerfStepSum>;
    protected details: Array<PerfSymbolDetailData>;

    constructor(workspace: string) {
        super(workspace);

        this.hapComponents = new Map();
        this.threadClassifyCfg = new Map();
        this.fileClassifyCfg = new Map();
        this.fileRegexClassifyCfg = new Map();
        this.symbolsSplitRulesCfg = [];

        this.filesClassifyMap = new Map();
        this.symbolsClassifyMap = new Map();
        this.symbolsMap = new Map();

        this.testSteps = [];
        this.stepSumMap = new Map();
        this.details = [];

        this.loadHapComponents();
        this.loadPerfKindCfg();
        this.loadSymbolSplitCfg();
    }

    private loadHapComponents(): void {
        const componentFile = path.join(this.projectRoot, 'modules.json');
        if (fs.existsSync(componentFile)) {
            let info = JSON.parse(fs.readFileSync(componentFile, { encoding: 'utf-8' })) as Array<{
                components: Array<Component>;
            }>;
            for (const node of info) {
                for (const component of node.components) {
                    this.hapComponents.set(component.name, component);
                }
            }
        }
        getConfig().analysis.ohpm.forEach((pkg) => {
            this.hapComponents.set(pkg.name, { name: pkg.name, kind: ComponentCategory.APP_LIB });
        });
        getConfig().analysis.npm.forEach((pkg) => {
            this.hapComponents.set(pkg.name, { name: pkg.name, kind: ComponentCategory.APP_LIB });
        });
    }

    private loadPerfKindCfg(): void {
        for (const componentConfig of getConfig().perf.kinds) {
            for (const sub of componentConfig.components) {
                if (sub.threads) {
                    for (const thread of sub.threads) {
                        this.threadClassifyCfg.set(new RegExp(thread), {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name,
                        });
                    }
                }

                for (const file of sub.files) {
                    if (this.hasRegexChart(file)) {
                        this.fileRegexClassifyCfg.set(new RegExp(file), {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name,
                        });
                    } else {
                        this.fileClassifyCfg.set(file, {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name,
                        });
                    }
                }
            }
        }
    }

    private loadSymbolSplitCfg(): void {
        for (const ruleCfg of getConfig().perf.symbolSplitRules) {
            let rule: SymbolSplitRule = {
                source: new RegExp(ruleCfg.source_file),
                dst: ruleCfg.new_file,
                symbols: [],
            };
            for (const symbol of ruleCfg.filter_symbols) {
                rule.symbols.push(new RegExp(symbol));
            }
            this.symbolsSplitRulesCfg.push(rule);
        }
    }

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

    public classifyFile(file: string): FileClassification {
        let fileClassify: FileClassification = {
            file: file,
            category: ComponentCategory.SYS_SDK,
            categoryName: 'SYS_SDK',
            subCategoryName: path.basename(file),
            originKind: OriginKind.UNKNOWN,
        };

        if (this.fileClassifyCfg.has(file)) {
            let component = this.fileClassifyCfg.get(file)!;
            fileClassify.category = component.category;
            fileClassify.categoryName = component.categoryName;
            if (component.subCategoryName) {
                fileClassify.subCategoryName = component.subCategoryName;
            }

            return fileClassify;
        }

        for (const [key, component] of this.fileRegexClassifyCfg) {
            let matched = file.match(key);
            if (matched) {
                fileClassify.category = component.category;
                fileClassify.categoryName = component.categoryName;
                if (component.subCategoryName) {
                    fileClassify.subCategoryName = component.subCategoryName;
                }
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
                fileClassify.category = ComponentCategory.APP_SO;
                // if (this.soOrigins.has(path.basename(file))) {
                //     let origin = this.soOrigins.get(name)!.broad_category;
                //     if (origin === 'THIRD_PARTY') {
                //         fileClassify.originKind = OriginKind.THIRD_PARTY;
                //         fileClassify.subCategory = this.soOrigins.get(name)!.specific_origin;
                //     } else if (origin === 'OPENSOURCE') {
                //         fileClassify.originKind = OriginKind.OPEN_SOURCE;
                //         fileClassify.subCategory = this.soOrigins.get(name)!.specific_origin;
                //     } else if (origin === 'FIRST_PARTY') {
                //         fileClassify.originKind = OriginKind.FIRST_PARTY;
                //     }
                // }

                return fileClassify;
            }

            fileClassify.category = ComponentCategory.APP_ABC;
            return fileClassify;
        }

        if (this.fileClassifyCfg.has(path.basename(file))) {
            let component = this.fileClassifyCfg.get(path.basename(file))!;
            fileClassify.category = component.category;
            fileClassify.categoryName = component.categoryName;
            if (component.subCategoryName) {
                fileClassify.subCategoryName = component.subCategoryName;
            }

            return fileClassify;
        }

        return fileClassify;
    }

    public classifySymbol(symbolId: number, fileClassification: FileClassification): FileClassification {
        if (this.symbolsClassifyMap.has(symbolId)) {
            return this.symbolsClassifyMap.get(symbolId)!;
        }

        const symbol = this.symbolsMap.get(symbolId) ?? '';
        if (fileClassification.category === ComponentCategory.APP_ABC) {
            /**
             * ets symbol
             * xx: [url:entry|@aaa/bbb|1.0.0|src/main/ets/i9/l9.ts:12:1]
             */
            let regex = /([^:]+):\[url:([^:\|]+)\|([^|]+)\|([^:\|]+)\|([^\|\]]*):(\d+):(\d+)\]$/;
            let matches = symbol.match(regex);
            if (matches) {
                const [_, functionName, _entry, packageName, version, filePath, _line, _column] = matches;
                this.symbolsMap.set(symbolId, functionName);

                let symbolClassification: FileClassification = {
                    file: `${packageName}/${version}/${filePath}`,
                    originKind: fileClassification.originKind,
                    category: fileClassification.category,
                    categoryName: fileClassification.categoryName,
                    subCategoryName: packageName,
                };

                if (this.hapComponents.has(matches[3])) {
                    symbolClassification.category = this.hapComponents.get(matches[3])!.kind;
                }

                this.symbolsClassifyMap.set(symbolId, symbolClassification);
                return symbolClassification;
            }
        }

        for (const rule of this.symbolsSplitRulesCfg) {
            if (!fileClassification.file.match(rule.source)) {
                continue;
            }
            for (const symbolRule of rule.symbols) {
                if (symbol.match(symbolRule)) {
                    let newClassification: FileClassification = {
                        file: rule.dst,
                        originKind: fileClassification.originKind,
                        category: fileClassification.category,
                        categoryName: fileClassification.categoryName,
                        subCategoryName: fileClassification.subCategoryName,
                    };
                    this.symbolsClassifyMap.set(symbolId, newClassification);
                    return newClassification;
                }
            }
        }

        return fileClassification;
    }

    public classifyThread(threadName: string | null): ClassifyCategory {
        const unknown = {
            category: ComponentCategory.UNKNOWN,
            categoryName: UNKNOWN_STR,
            subCategoryName: UNKNOWN_STR,
        };
        if (threadName === null) {
            return unknown;
        }

        for (const [reg, component] of this.threadClassifyCfg) {
            if (threadName.match(reg)) {
                return {
                    category: component.category,
                    categoryName: component.categoryName,
                    subCategoryName: component.subCategoryName,
                };
            }
        }

        return unknown;
    }

    protected async saveSqlite(perf: PerfSum, outputFileName: string): Promise<void> {
        const db = new PerfDatabase(outputFileName);
        let database = await db.initialize();

        await db.insertRecords(database, perf.osVersion, perf.scene, this.details);

        db.insertTestSteps(database, this.testSteps);
        await db.close(database);
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
    protected async saveDbtoolsXlsx(testInfo: TestSceneInfo, perf: PerfSum, outputFileName: string): Promise<void> {
        let symbolPerfData: SheetData = [];
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

        let symbolDetailsMap = new Map<string, Array<PerfSymbolDetailData>>();

        for (const data of this.details) {
            let row: Array<PerfSymbolDetailData> = [
                {
                    stepIdx: data.stepIdx,
                    eventType: PerfEvent.CYCLES_EVENT,
                    pid: data.pid,
                    processName: data.processName,
                    processEvents: 0,
                    tid: data.tid,
                    threadEvents: 0,
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
                    stepIdx: data.stepIdx,
                    eventType: PerfEvent.INSTRUCTION_EVENT,
                    pid: data.pid,
                    processName: data.processName,
                    processEvents: 0,
                    tid: data.tid,
                    threadEvents: 0,
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

            let key = `${data.stepIdx}_${data.pid}_${data.tid}_${data.file}_${data.symbol}`;
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

        for (const [_, data] of symbolDetailsMap) {
            if (data[0].symbolEvents + data[1].symbolEvents === 0) {
                continue;
            }
            let row = [
                { value: perf.osVersion, type: String },
                { value: testInfo.model, type: String },
                { value: this.dateCustomFormatting(perf.timestamp), type: String },
                { value: testInfo.sn, type: String },
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

                { value: this.excelSpecialTranscode(data[0].symbol), type: String },
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

        let sceneStepData: SheetData = [];
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
                { value: testInfo.model, type: String },
                { value: this.dateCustomFormatting(perf.timestamp), type: String },
                { value: testInfo.sn, type: String },
                { value: perf.perfPath, type: String },
                { value: perf.scene, type: String },
                { value: 'Hapray', type: String },
                { value: step.id, type: Number }, // step

                { value: perf.perfId, type: String },
                { value: step.name, type: String },
            ];

            sceneStepData.push(row);
        }
        if (!fs.existsSync(path.dirname(outputFileName))) {
            fs.mkdirSync(path.dirname(outputFileName), { recursive: true });
        }
        await writeXlsxFile([symbolPerfData, sceneStepData], {
            sheets: ['ecol_load_hiperf_detail', 'ecol_load_step'],
            filePath: outputFileName,
        });
    }

    private excelSpecialTranscode(content: string): string {
        if (content === 'toString') {
            return 'toString()';
        }
        return content.substring(0, 2048);
    }

    private dateCustomFormatting(timestamp: number): string {
        let date = new Date(timestamp);
        const padStart = (value: number): string => value.toString().padStart(2, '0');
        return `${date.getFullYear()}-${padStart(date.getMonth() + 1)}-${padStart(date.getDate())} ${padStart(
            date.getHours()
        )}:${padStart(date.getMinutes())}:${padStart(date.getSeconds())}`;
    }

    public async saveHiperfJson(testInfo: TestSceneInfo, outputFileName: string): Promise<void> {
        let harMap = new Map<string, { name: string; count: number }>();
        let stepMap = new Map<number, StepJsonData>();

        for (const data of this.details) {
            if (
                data.componentCategory === ComponentCategory.APP_ABC ||
                data.componentCategory === ComponentCategory.APP_LIB
            ) {
                if (harMap.has(data.componentName!)) {
                    let value = harMap.get(data.componentName!)!;
                    value.count += data.symbolEvents;
                } else {
                    harMap.set(data.componentName!, { name: data.componentName!, count: data.symbolEvents });
                }
            }

            if (stepMap.has(data.stepIdx)) {
                let value = stepMap.get(data.stepIdx)!;
                value.data.push(data);
                value.count += data.symbolEvents;
            } else {
                let step = this.getStepByGroupId(testInfo, data.stepIdx);
                let value: StepJsonData = {
                    step_name: step.groupName,
                    step_id: data.stepIdx,
                    count: data.symbolEvents,
                    round: testInfo.chooseRound,
                    perf_data_path: step.dbfile ?? '',
                    data: [data],
                };
                stepMap.set(data.stepIdx, value);
            }
        }

        let jsonObject = {
            rom_version: testInfo.osVersion,
            app_id: testInfo.packageName,
            app_name: testInfo.appName,
            app_version: testInfo.appVersion,
            scene: testInfo.scene,
            timestamp: testInfo.timestamp,
            perfDataPath: testInfo.rounds[testInfo.chooseRound].steps.map((step) => step.perfFile),
            perfDbPath: testInfo.rounds[testInfo.chooseRound].steps.map((step) => step.dbfile),
            htracePath: testInfo.rounds[testInfo.chooseRound].steps.map((step) => step.traceFile),
            steps: Array.from(stepMap.values()),
            har: Array.from(harMap.values()),
        };
        await saveJsonArray([jsonObject], outputFileName);
    }

    private getStepByGroupId(testInfo: TestSceneInfo, groupId: number): TestStepGroup {
        return testInfo.rounds[testInfo.chooseRound].steps.filter((step) => step.groupId === groupId)[0];
    }
}
