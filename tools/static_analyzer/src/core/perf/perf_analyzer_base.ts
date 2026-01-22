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
import { createHash } from 'crypto';
import type { Component, ComponentCategoryType, ClassifyCategory } from '../../types/component';
import { ComponentCategory, OriginKind, createLevel2Category } from '../../types/component';
import { AnalyzerProjectBase, PROJECT_ROOT } from './project';
import { getConfig } from '../../config';
import writeXlsxFile from 'write-excel-file/node';
import { PerfDatabase } from './perf_database';
import { saveJsonArray } from '../../utils/json_utils';
import type { SheetData } from 'write-excel-file';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import type { SoOriginal } from '../../config/types';
import { PackageMatcher } from './package_matcher';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export const UNKNOWN_STR = 'unknown';

export interface StepJsonData {
    step_name: string;
    step_id: number;
    count: number;
    round: number;
    perf_data_path: string;
    data: Array<PerfSymbolDetailData>;
    har?: Map<string, { name: string; count: number }>;
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

export interface ProcessClassifyCategory {
    isMainApp: boolean; //是否主应用
    domain: string; //业务领域
    subSystem: string; //子系统
    component: string; // 部件
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

export interface FileClassification extends ClassifyCategory {
    file: string;
}

export interface PerfComponent {
    name: string; // 组件名
    cycles: number;
    totalCycles: number;
    instructions: number;
    totalInstructions: number;

    category: ClassifyCategory; // 大类
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

    componentCategory: ClassifyCategory; 

    isMainApp: boolean;
    sysDomain: string;
    sysSubSystem: string;
    sysComponent: string;
}

export interface PerfStepSum {
    stepIdx: number; // 步骤编号
    components: Array<PerfComponent>; // 计算统计组件负载
    categoriesSum: Array<Array<number>>; // 大类统计值
    categoriesTotal: Array<Array<number>>; // 大类Total值
    total: Array<number>; // 总值, 0 circles, 1 instructions
    count: number; // 总负载数
    app_count: number; // 应用负载数
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

// ===================== Summary Info 相关类型定义 =====================
export interface TestReportInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
    rom_version: string;
    device_sn: string;
}

export interface SummaryInfo {
    rom_version: string;
    app_version: string;
    scene: string;
    step_name: string;
    step_id: number;
    count: number;
    app_count: number;
}

export interface RoundInfo {
    step_id: number;
    round: number;
    count: number;
}

export interface Step {
    stepIdx: number;
    description: string;
}

interface ParsedSymbol {
    packageName: string;
    className: string;
    fullFunctionName: string;
}

export class PerfAnalyzerBase extends AnalyzerProjectBase {
    processClassifyCfg: Map<RegExp, ProcessClassifyCategory>;
    specialProcessClassifyCfg: Map<RegExp, Map<RegExp, ProcessClassifyCategory>>;

    // classify rule
    protected threadClassifyCfg: Array<{ regex: RegExp; category: ClassifyCategory; priority: number }>;
    protected fileClassifyCfg: Map<string, ClassifyCategory>;
    protected fileRegexClassifyCfg: Array<{ regex: RegExp; category: ClassifyCategory; priority: number }>;
    protected soOriginsClassifyCfg: Map<string, SoOriginal>;
    protected hapComponents: Map<string, Component>;
    protected symbolsSplitRulesCfg: Array<SymbolSplitRule>;

    // classify result
    protected filesClassifyMap: Map<number, FileClassification>;
    protected symbolsClassifyMap: Map<number, FileClassification>;
    protected symbolsMap: Map<number, string>;

    protected testSteps: Array<TestStep>;
    protected stepSumMap: Map<number, PerfStepSum>;
    protected details: Array<PerfSymbolDetailData>;

    protected computeFilesRegexCfg: Map<RegExp, RegExp>;
    protected dfxSymbolsCfg: Set<string>;
    protected dfxRegexSymbolsCfg: Set<RegExp>;

    protected packageMatcher: PackageMatcher;

    constructor(workspace: string) {
        super(workspace);

        this.processClassifyCfg = new Map();
        this.specialProcessClassifyCfg = new Map();
        this.hapComponents = new Map();
        this.threadClassifyCfg = [];
        this.fileClassifyCfg = new Map();
        this.fileRegexClassifyCfg = [];
        this.soOriginsClassifyCfg = getConfig().perf.soOrigins;
        this.symbolsSplitRulesCfg = [];

        this.filesClassifyMap = new Map();
        this.symbolsClassifyMap = new Map();
        this.symbolsMap = new Map();

        this.testSteps = [];
        this.stepSumMap = new Map();
        this.details = [];

        this.computeFilesRegexCfg = new Map();
        this.dfxSymbolsCfg = new Set();
        this.dfxRegexSymbolsCfg = new Set();

        this.loadHapComponents();
        this.loadPerfKindCfg();
        this.loadSymbolSplitCfg();
        this.loadPerfClassify();
        this.packageMatcher = new PackageMatcher(getConfig().perf.kotlinModules);
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
            this.hapComponents.set(pkg.name, { name: pkg.name, kind: createLevel2Category(ComponentCategory.APP, 'APP', 1, 'APP_LIB') });
        });
        getConfig().analysis.npm.forEach((pkg) => {
            this.hapComponents.set(pkg.name, { name: pkg.name, kind: createLevel2Category(ComponentCategory.APP, 'APP', 1, 'APP_LIB') });
        });
    }

    private loadPerfKindCfg(): void {
        // 收集所有规则，包含优先级信息
        const threadRules: Array<{ regex: RegExp; category: ClassifyCategory; priority: number }> = [];
        const fileRegexRules: Array<{ regex: RegExp; category: ClassifyCategory; priority: number }> = [];

        for (const componentConfig of getConfig().perf.kinds) {
            for (const sub of componentConfig.components) {
                // 获取优先级，默认为 0（优先级越高，数字越大）
                const priority = sub.priority ?? 0;
                if (sub.threads) {
                    for (const thread of sub.threads) {
                        threadRules.push({
                            regex: new RegExp(thread),
                            category: {
                                category: componentConfig.kind,
                                categoryName: componentConfig.name,
                                subCategoryName: sub.name,
                            },
                            priority: priority,
                        });
                    }
                }

                for (const file of sub.files) {
                    if (this.hasRegexChart(file)) {
                        fileRegexRules.push({
                            regex: new RegExp(file),
                            category: {
                                category: componentConfig.kind,
                                categoryName: componentConfig.name,
                                subCategoryName: sub.name,
                            },
                            priority: priority,
                        });
                    } else {
                        // 精确匹配的文件规则使用 Map（key 是唯一的，通常不会有冲突）
                        // 如果确实有冲突，后加载的会覆盖先加载的
                        this.fileClassifyCfg.set(file, {
                            category: componentConfig.kind,
                            categoryName: componentConfig.name,
                            subCategoryName: sub.name,
                        });
                    }
                }
            }
        }

        // 按优先级从高到低排序（优先级高的先匹配）
        threadRules.sort((a, b) => b.priority - a.priority);
        fileRegexRules.sort((a, b) => b.priority - a.priority);

        this.threadClassifyCfg = threadRules;
        this.fileRegexClassifyCfg = fileRegexRules;
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

    private loadPerfClassify(): void {
        for (const file of getConfig().perf.classify.compute_files) {
            this.computeFilesRegexCfg.set(new RegExp(file[0]), new RegExp(file[1]));
        }
        for (const symbol of getConfig().perf.classify.dfx_symbols) {
            if (this.hasRegexChart(symbol)) {
                this.dfxRegexSymbolsCfg.add(new RegExp(symbol));
            } else {
                this.dfxSymbolsCfg.add(symbol);
            }
        }

        for (const [domain, subSystems] of Object.entries(getConfig().perf.classify.process)) {
            for (const [subSystem, components] of Object.entries(subSystems)) {
                for (const [component, cfg] of Object.entries(components)) {
                    for (const process of cfg.Harmony_Process) {
                        this.processClassifyCfg.set(new RegExp(process.toLowerCase()), {
                            isMainApp: false,
                            domain: domain,
                            subSystem: subSystem,
                            component: component,
                        });
                    }
                }
            }
        }

        for (const [domain, subSystems] of Object.entries(getConfig().perf.classify.process_special)) {
            for (const [subSystem, components] of Object.entries(subSystems)) {
                for (const [component, cfg] of Object.entries(components)) {
                    let map = new Map<RegExp, ProcessClassifyCategory>();
                    for (const process of cfg.Harmony_Process) {
                        map.set(new RegExp(process.toLowerCase()), {
                            isMainApp: false,
                            domain: domain,
                            subSystem: subSystem,
                            component: component,
                        });
                    }
                    this.specialProcessClassifyCfg.set(new RegExp(cfg.scene), map);
                }
            }
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
            thirdCategoryName: path.basename(file),
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

        // 按优先级顺序匹配（已排序，优先级高的在前）
        for (const rule of this.fileRegexClassifyCfg) {
            let matched = file.match(rule.regex);
            if (matched) {
                fileClassify.category = rule.category.category;
                fileClassify.categoryName = rule.category.categoryName;
                if (rule.category.subCategoryName) {
                    fileClassify.subCategoryName = rule.category.subCategoryName;
                }
                return fileClassify;
            }
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
        if (fileClassification.category === ComponentCategory.APP && fileClassification.subCategoryName === 'APP_ABC') {
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
                    category: fileClassification.category,
                    categoryName: fileClassification.categoryName,
                    subCategoryName: fileClassification.subCategoryName,
                    thirdCategoryName: packageName,
                };

                // 特殊处理compose符号
                if (packageName === 'compose') {
                    symbolClassification.category = ComponentCategory.KMP;
                    symbolClassification.categoryName = 'KMP';
                    symbolClassification.subCategoryName = 'CMP';
                }

                if (this.hapComponents.has(matches[3])) {
                    const componentKind = this.hapComponents.get(matches[3])!.kind;
                    symbolClassification.category = componentKind.category;
                    symbolClassification.categoryName = componentKind.categoryName;
                    if (componentKind.subCategoryName) {
                        symbolClassification.subCategoryName = componentKind.subCategoryName;
                    }
                    if (componentKind.thirdCategoryName) {
                        symbolClassification.thirdCategoryName = componentKind.thirdCategoryName;
                    }
                }

                this.symbolsClassifyMap.set(symbolId, symbolClassification);
                return symbolClassification;
            }
        } else if (fileClassification.category === ComponentCategory.KMP && symbol.startsWith('kfun')) {
            let kmpSymbol = this.parseKmpSymbol(symbol);
            this.symbolsMap.set(symbolId, kmpSymbol.fullFunctionName);
            let symbolClassification: FileClassification = {
                file: `${kmpSymbol.packageName}.${kmpSymbol.className}`,
                category: fileClassification.category,
                categoryName: fileClassification.categoryName,
                subCategoryName: 'KMP_LIB',
                thirdCategoryName: kmpSymbol.packageName,
            };

            this.symbolsClassifyMap.set(symbolId, symbolClassification);
            return symbolClassification;
        }

        for (const rule of this.symbolsSplitRulesCfg) {
            if (!fileClassification.file.match(rule.source)) {
                continue;
            }
            for (const symbolRule of rule.symbols) {
                if (symbol.match(symbolRule)) {
                    let newClassification: FileClassification = {
                        file: rule.dst,
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

        // 按优先级顺序匹配（已排序，优先级高的在前）
        for (const rule of this.threadClassifyCfg) {
            if (threadName.match(rule.regex)) {
                return {
                    category: rule.category.category,
                    categoryName: rule.category.categoryName,
                    subCategoryName: rule.category.subCategoryName,
                };
            }
        }

        return unknown;
    }

    public classifyProcess(
        processName: string | undefined,
        packageName: string,
        scene: string
    ): ProcessClassifyCategory {
        const UNKNOWN = { domain: '其他', subSystem: '其他', component: '其他', isMainApp: false };
        const MAINAPP = { domain: '主应用', subSystem: '主应用', component: '主应用', isMainApp: true };

        if (processName === undefined) {
            return UNKNOWN;
        }

        for (const [key, rules] of this.specialProcessClassifyCfg) {
            if (!key.test(scene)) {
                continue;
            }

            for (const [regex, domain] of rules) {
                if (regex.test(processName.toLowerCase()) || regex.test(path.basename(processName.toLowerCase()))) {
                    if (processName === packageName) {
                        domain.isMainApp = true;
                    }
                    return domain;
                }
            }
        }

        for (const [regex, domain] of this.processClassifyCfg) {
            if (regex.test(processName.toLowerCase()) || regex.test(path.basename(processName.toLowerCase()))) {
                if (processName === packageName) {
                    domain.isMainApp = true;
                }
                return domain;
            }
        }

        if (processName === packageName || (packageName.length > 0 && processName.startsWith(packageName))) {
            return MAINAPP;
        }

        return UNKNOWN;
    }

    public classifySoOrigins(file: string): { subCategoryName: string, thirdCategoryName?: string } | undefined {
        let name = path.basename(file);
        if (!this.soOriginsClassifyCfg.has(name)) {
            return undefined;
        }

        let soOriginalCfg = this.soOriginsClassifyCfg.get(name)!;
        let result = {
            subCategoryName: OriginKind.FIRST_PARTY,
            thirdCategoryName: this.soOriginsClassifyCfg.get(name)!.sdk_category,
        };

        if (soOriginalCfg.broad_category === 'THIRD_PARTY') {
            result.subCategoryName = OriginKind.THIRD_PARTY;
        } else if (soOriginalCfg.broad_category === 'OPENSOURCE') {
            result.subCategoryName = OriginKind.OPEN_SOURCE;
        } else if (soOriginalCfg.broad_category === 'FIRST_PARTY') {
            result.subCategoryName = OriginKind.FIRST_PARTY;
        }
    }

    public isSkipSymbol(symbol: string): boolean {
        if (this.dfxSymbolsCfg.has(symbol)) {
            return true;
        }

        for (const reg of this.dfxRegexSymbolsCfg) {
            let matched = symbol.match(reg);
            if (matched) {
                return true;
            }
        }
        return false;
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
            { value: '组件一级分类' },
            { value: '组件二级分类' },
            { value: '组件三级分类' },
            { value: '是否主应用' },
            { value: '业务领域' },
            { value: '子系统' },
            { value: '部件' },
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
                    componentCategory: data.componentCategory,
                    isMainApp: data.isMainApp,
                    sysDomain: data.sysDomain,
                    sysSubSystem: data.sysSubSystem,
                    sysComponent: data.sysComponent,
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
                    componentCategory: data.componentCategory,
                    isMainApp: data.isMainApp,
                    sysDomain: data.sysDomain,
                    sysSubSystem: data.sysSubSystem,
                    sysComponent: data.sysComponent,
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

                { value: data[0].componentCategory.category, type: Number },
                { value: data[0].componentCategory.subCategoryName, type: String },
                { value: data[0].componentCategory.thirdCategoryName, type: String },
                { value: data[0].isMainApp, type: Boolean },
                { value: data[0].sysDomain, type: String },
                { value: data[0].sysSubSystem, type: String },
                { value: data[0].sysComponent, type: String },
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

        // 生成技术栈数据表格
        await this.saveTechStackXlsx(testInfo, perf, outputFileName);
    }

    /**
     * 判断是否应该归类到ArkUI技术栈
     * ArkUI技术栈包含：
     * - kind=1的：APP_ABC, APP_LIB
     * - kind=2的：ArkUI
     * - kind=3的：Ability, ArkTS Runtime, ArkTS System LIB
     */
    private shouldClassifyAsArkUI(category: ComponentCategory, categoryName: string, subCategoryName: string | undefined): boolean {
        // kind=2的ArkUI
        if (category === ComponentCategory.ArkUI || categoryName === 'ArkUI') {
            return true;
        }
        
        // kind=1的APP_ABC, APP_LIB
        if (category === ComponentCategory.APP && subCategoryName) {
            if (subCategoryName === 'APP_ABC' || subCategoryName === 'APP_LIB') {
                return true;
            }
        }
        
        // kind=3的Ability, ArkTS Runtime, ArkTS System LIB
        if (category === ComponentCategory.OS_Runtime && subCategoryName) {
            if (subCategoryName === 'Ability' || 
                subCategoryName === 'ArkTS Runtime' || 
                subCategoryName === 'ArkTS System LIB') {
                return true;
            }
        }
        
        return false;
    }

    /**
     * 生成技术栈数据表格
     * 根据 techStackData 方法的逻辑，生成技术栈数据 Excel 文件
     */
    private async saveTechStackXlsx(testInfo: TestSceneInfo, perf: PerfSum, outputFileName: string): Promise<void> {
        // 需要排除的分类名称（对应 kind = 1, 3, 4, -1）
        const excludedCategories = ['APP', 'OS_Runtime', 'SYS_SDK', 'UNKNOWN'];

        // 统计所有主应用数据的总负载（包括被排除的分类），用于计算应用占比
        const stepTotalAppInstructionsMap = new Map<number, number>();

        // 按步骤分组统计技术栈数据
        const stepTechStackMap = new Map<number, {
            categoryMap: Map<string, { instructions: number }>;
            totalInstructions: number;
        }>();

        // 遍历所有详细数据，只统计指令数
        for (const data of this.details) {
            // 只统计指令数
            if (data.eventType !== PerfEvent.INSTRUCTION_EVENT) {
                continue;
            }

            // 只保留主应用的数据
            if (!data.isMainApp) {
                continue;
            }

            const stepIdx = data.stepIdx;

            const category = data.componentCategory.category;
            // 获取 categoryName，如果无法获取有效的分类名称，直接跳过
            const categoryName = data.componentCategory.categoryName || ComponentCategory[category];
            if (!categoryName || categoryName.toLowerCase() === UNKNOWN_STR.toLowerCase()) {
                continue;
            }
            const subCategoryName = data.componentCategory.subCategoryName;

            // 统计所有主应用数据的总负载（包括被排除的分类，但不包括UNKNOWN）
            stepTotalAppInstructionsMap.set(
                stepIdx,
                (stepTotalAppInstructionsMap.get(stepIdx) ?? 0) + data.symbolEvents
            );
            
            // 判断是否应该归类到ArkUI
            const isArkUI = this.shouldClassifyAsArkUI(category, categoryName, subCategoryName);
            
            // 确定最终的技术栈分类名称
            let finalCategoryName: string;
            if (isArkUI) {
                finalCategoryName = 'ArkUI';
            } else {
                // 排除指定的分类
                if (excludedCategories.includes(categoryName)) {
                    continue;
                }
                finalCategoryName = categoryName;
            }

            // 初始化步骤数据
            if (!stepTechStackMap.has(stepIdx)) {
                stepTechStackMap.set(stepIdx, {
                    categoryMap: new Map(),
                    totalInstructions: 0,
                });
            }

            const stepData = stepTechStackMap.get(stepIdx)!;

            // 统计大分类
            if (!stepData.categoryMap.has(finalCategoryName)) {
                stepData.categoryMap.set(finalCategoryName, {
                    instructions: 0,
                });
            }

            const categoryData = stepData.categoryMap.get(finalCategoryName)!;
            categoryData.instructions += data.symbolEvents;

            stepData.totalInstructions += data.symbolEvents;
        }

        // 如果没有技术栈数据，不生成文件
        if (stepTechStackMap.size === 0) {
            return;
        }

        // 从路径解析测试场景、步骤和轮次信息
        const pathInfo = this.parsePathInfo(outputFileName);
        
        // 优先使用 perf.scene，如果为空则使用从路径解析的测试场景
        const scene = perf.scene || (pathInfo.scene ?? '');
        
        // 获取输出目录
        const outputDir = path.dirname(outputFileName);
        
        // 优先使用从路径解析的轮次，如果无法解析则使用原有逻辑
        let roundNumber = pathInfo.round;
        if (roundNumber === null) {
            // 从Excel文件目录的父目录名称中提取最后一个数字作为轮次（兼容原有逻辑）
            const parentDirName = path.basename(outputDir);
            const lastNumberMatch = parentDirName.match(/(\d+)(?!.*\d)/);
            roundNumber = lastNumberMatch ? parseInt(lastNumberMatch[1], 10) : 0;
        }

        // 从测试场景中提取应用名（用下划线分割，取第二部分）
        const sceneParts = scene.split('_');
        const appName = sceneParts.length >= 2 ? sceneParts[1] : '';
        
        // 如果路径中解析出了步骤信息，使用路径中的步骤ID
        // 因为路径明确标识了这是哪个步骤的数据
        const pathStepId = pathInfo.step;

        // 生成技术栈数据表格
        const techStackData: SheetData = [];
        
        // 表头
        techStackData.push([
            { value: '轮次' },
            { value: '应用名' },
            { value: '测试场景' },
            { value: '步骤名称' },
            { value: '技术栈分类' },
            { value: '指令数' },
            { value: '相对占比(%)' },
            { value: '应用占比(%)' },
        ]);

        // 按步骤ID排序
        const sortedSteps = Array.from(stepTechStackMap.entries()).sort((a, b) => a[0] - b[0]);

        for (const [stepIdx, stepData] of sortedSteps) {
            // 如果路径中有步骤信息，且只有一个步骤的数据，使用路径中的步骤ID
            // 因为路径明确标识了这是哪个步骤的数据（如 _step2）
            // 如果有多个步骤，使用数据中的步骤ID，因为路径中的步骤ID可能只适用于第一个步骤
            const actualStepIdx = (pathStepId !== null && stepTechStackMap.size === 1) 
                ? pathStepId 
                : stepIdx;
            
            // 先尝试用实际步骤ID查找步骤，如果找不到再用数据中的步骤ID
            let step = this.testSteps.find(s => s.id === actualStepIdx);
            step ??= this.testSteps.find(s => s.id === stepIdx);
            const stepName = step?.name ?? `Step ${actualStepIdx}`;

            // 按指令数排序大分类
            const sortedCategories = Array.from(stepData.categoryMap.entries())
                .sort((a, b) => b[1].instructions - a[1].instructions);

            for (const [categoryName, categoryData] of sortedCategories) {
                // 相对占比：技术栈分类在所有技术栈中的占比（相对于所有技术栈数据的总和）
                const relativePercentage = stepData.totalInstructions > 0
                    ? Number(((categoryData.instructions / stepData.totalInstructions) * 100).toFixed(1))
                    : 0.0;
                
                // 应用占比：技术栈分类在所有主应用数据中的占比（包括被排除的分类）
                const totalAppInstructions = stepTotalAppInstructionsMap.get(stepIdx) ?? 0;
                const appPercentage = totalAppInstructions > 0
                    ? Number(((categoryData.instructions / totalAppInstructions) * 100).toFixed(1))
                    : 0.0;

                techStackData.push([
                    { value: roundNumber, type: Number },
                    { value: appName, type: String },
                    { value: scene, type: String },
                    { value: stepName, type: String },
                    { value: categoryName, type: String },
                    { value: categoryData.instructions, type: Number },
                    { value: relativePercentage, type: Number },
                    { value: appPercentage, type: Number },
                ]);
            }
        }

        // 生成技术栈数据 Excel 文件（与原文件同目录，文件名添加 _techstack 后缀）
        const outputBaseName = path.basename(outputFileName, path.extname(outputFileName));
        const techStackFileName = path.join(outputDir, `${outputBaseName}_techstack.xlsx`);

        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        await writeXlsxFile([techStackData], {
            sheets: ['技术栈数据'],
            filePath: techStackFileName,
        });

        logger.info(`技术栈数据表格已生成: ${techStackFileName}`);
    }

    /**
     * 从文件路径中解析轮次、测试场景和步骤信息
     * 
     * 支持的路径格式：
     * - _round2/PerfLoad_Douyin_0090_step3
     * - _r2/MemLoad_kuaishou+0020_step2
     * - 任何包含 _roundN 或 _rN 和 _stepN 的路径
     * 
     * @param filePath 文件路径
     * @returns 解析结果，包含轮次、测试场景和步骤ID
     */
    private parsePathInfo(filePath: string): { round: number | null; scene: string | null; step: number | null } {
        const pathStr = filePath;
        
        // 解析轮次：匹配 _roundN 或 _rN
        const roundMatch = pathStr.match(/_r(?:ound)?(\d+)/i);
        const roundNumber = roundMatch ? parseInt(roundMatch[1], 10) : null;
        
        // 解析步骤：匹配 _stepN
        const stepMatch = pathStr.match(/_step(\d+)/i);
        const stepNumber = stepMatch ? parseInt(stepMatch[1], 10) : null;
        
        // 解析测试场景：在轮次和步骤之间的部分
        // 例如：_round2/PerfLoad_Douyin_0090_step3 -> PerfLoad_Douyin_0090
        // 或者：_r2/MemLoad_kuaishou+0020_step2 -> MemLoad_kuaishou+0020
        let scene: string | null = null;
        
        // 尝试找到轮次和步骤之间的部分
        if (roundMatch && stepMatch) {
            // 找到轮次匹配后的位置
            const roundEnd = roundMatch.index! + roundMatch[0].length;
            // 找到步骤匹配前的位置
            const stepStart = stepMatch.index!;
            
            // 提取中间部分
            let middlePart = pathStr.substring(roundEnd, stepStart);
            // 去掉路径分隔符和多余的下划线
            middlePart = middlePart.replace(/^[/\\_]+|[/\\_]+$/g, '');
            
            // 如果中间部分不为空，且看起来像测试场景名称
            if (middlePart) {
                // 去掉目录分隔符，只保留场景名称部分
                // 如果包含路径分隔符，取最后一部分
                const parts = middlePart.replace(/\\/g, '/').split('/');
                const lastPart = parts[parts.length - 1];
                if (lastPart) {
                    scene = lastPart;
                }
            }
        }
        
        // 如果通过轮次和步骤无法解析，尝试直接匹配常见的测试场景模式
        if (!scene) {
            // 匹配类似 PerfLoad_Douyin_0090 或 MemLoad_kuaishou+0020 的模式
            // 模式：大写字母开头的单词，可能包含下划线、加号、数字
            const sceneMatch = pathStr.match(/([A-Z][A-Za-z0-9_+]+(?:_[A-Za-z0-9+]+)*)/);
            if (sceneMatch) {
                const potentialScene = sceneMatch[1];
                // 确保不是 step 或 round 相关的词
                if (!potentialScene.toLowerCase().includes('step') && 
                    !potentialScene.toLowerCase().includes('round')) {
                    scene = potentialScene;
                }
            }
        }
        
        return {
            round: roundNumber,
            scene: scene,
            step: stepNumber
        };
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

    public async saveHiperfJson(testInfo: TestSceneInfo, outputFileName: string): Promise<void | boolean> {
        let harMap = new Map<string, { name: string; count: number }>();
        let stepMap = new Map<number, StepJsonData>();

        // 首先使用已统计的 stepSumMap 初始化步骤数据，确保统计一致性
        for (const [stepId, stepSum] of this.stepSumMap) {
            let step = this.getStepByGroupId(testInfo, stepId);
            let value: StepJsonData = {
                step_name: step.groupName,
                step_id: stepId,
                count: stepSum.app_count, // 使用已统计的应用负载数，确保与 summary_info.json 一致
                round: testInfo.chooseRound,
                perf_data_path: step.dbfile ?? '',
                data: [],
            };
            stepMap.set(stepId, value);
        }

        // 然后遍历详细数据，收集 HAR 信息和详细数据
        for (const data of this.details) {
            // 正确逻辑：只有进程名包含包名时才是应用负载
            if (!data.processName.includes(testInfo.packageName)) {
                continue;
            }

            // 统计 HAR 组件数据
            if (
                (data.componentCategory.category === ComponentCategory.APP && data.componentCategory.subCategoryName === 'APP_ABC') ||
                (data.componentCategory.category === ComponentCategory.APP && data.componentCategory.subCategoryName === 'APP_LIB')
            ) {
                if (harMap.has(data.componentCategory.thirdCategoryName!)) {
                    let value = harMap.get(data.componentCategory.thirdCategoryName!)!;
                    value.count += data.symbolEvents;
                } else {
                    harMap.set(data.componentCategory.thirdCategoryName!, { name: data.componentCategory.thirdCategoryName!, count: data.symbolEvents });
                }
            }

            // 添加详细数据到对应步骤（不重新计算 count）
            let stepData = stepMap.get(data.stepIdx);
            if (stepData) {
                stepData.data.push(data);
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
        if (getConfig().ut) {
            const jsonString = JSON.stringify([jsonObject], null, 2);
            return this.isRight(jsonString, outputFileName);
        } else {
            await saveJsonArray(this.transformPerfData([jsonObject]), outputFileName);
        }
    }


    /**
     * 展开 componentCategory 对象到顶层
     * @param obj - 包含 componentCategory 的对象
     * @returns 展开后的对象
     */
    expandComponentCategory<T extends { componentCategory?: ClassifyCategory }>(obj: T): T & {
        componentName?: string;
        subCategoryName?: string;
        thirdCategoryName?: string;
        componentCategory?: ComponentCategory;
    } {
        if ('componentCategory' in obj && obj.componentCategory) {
            const componentCategory = obj.componentCategory;
            const { componentCategory: _, ...rest } = obj;
            return {
                ...rest,
                componentName: componentCategory.categoryName,
                subCategoryName: componentCategory.subCategoryName,
                thirdCategoryName: componentCategory.thirdCategoryName,
                componentCategory: componentCategory.category,
            } as T & {
                componentName?: string;
                subCategoryName?: string;
                thirdCategoryName?: string;
                componentCategory?: ComponentCategory;
            };
        }
        return obj as T & {
            componentName?: string;
            subCategoryName?: string;
            thirdCategoryName?: string;
            componentCategory?: ComponentCategory;
        };
    }

    /**
     * 处理 perf.steps[].data[].componentCategory 展开
     * @param data - 要处理的数据
     * @param transform - 可选的转换函数
     * @returns 处理后的数据
     */
    transformPerfData<T extends Record<string, unknown>>(data: Array<T>): Array<T> {
        if (!Array.isArray(data)) {
            return data;
        }

        return data.map((item) => {
            if ('steps' in item && Array.isArray(item.steps)) {
                const processedItem = { ...item } as T & { steps: Array<Record<string, unknown>> };
                const steps = item.steps as Array<Record<string, unknown>>;
                processedItem.steps = steps.map((step) => {
                    if ('data' in step && Array.isArray(step.data)) {
                        const processedStep = { ...step } as Record<string, unknown> & { data: Array<Record<string, unknown>> };
                        const dataArray = step.data as Array<Record<string, unknown>>;
                        processedStep.data = dataArray.map((dataItem) => {
                            // 然后展开 componentCategory
                            return this.expandComponentCategory(dataItem);
                        });
                        return processedStep;
                    }
                    return step;
                });
                return processedItem as T;
            }
            return item;
        });
    }

    private getStepByGroupId(testInfo: TestSceneInfo, groupId: number): TestStepGroup {
        return testInfo.rounds[testInfo.chooseRound].steps.filter((step) => step.groupId === groupId)[0];
    }

    private isRight(jsonString: string, outputFileName: string): boolean {
        // 将jsonObject转换成字符串并计算hash值

        const currentHash = createHash('sha256').update(jsonString).digest('hex');

        // 读取目标文件的内容并计算hash值
        const targetFilePath = outputFileName;

        try {
            if (fs.existsSync(targetFilePath)) {
                const targetFileContent = fs.readFileSync(targetFilePath, 'utf-8');
                const targetHash = createHash('sha256').update(targetFileContent).digest('hex');

                logger.log(`Current jsonObject hash: ${currentHash}`);
                logger.log(`expect file hash: ${targetHash}`);
                logger.log(`Hash values are equal: ${currentHash === targetHash}`);
                return currentHash === targetHash;
            } else {
                logger.log(`expect file not found: ${targetFilePath}`);
            }
        } catch (error) {
            logger.error(`Error reading expect file: ${error}`);
        }
        return false;
    }

    /**
     * 解析符号字符串，提取包名、类名和函数符号
     * @param symbol 输入的符号字符串，如"kfun:androidx.compose.ui.node.LayoutNodeLayoutDelegate#<get-measurePassDelegate>(){}androidx.compose.ui.node.LayoutNodeLayoutDelegate.MeasurePassDelegate"
     * @returns 解析后的对象，包含包名、类名和函数符号
     */
    parseKmpSymbol(symbol: string): ParsedSymbol {
        // 移除前缀"kfun:"
        const withoutPrefix = symbol.replace(/^kfun:/, '');

        // 分割类路径和函数部分
        const [classPath, _] = withoutPrefix.split('#');

        // 提取包名和类名
        const lastDotIndex = classPath.lastIndexOf('.');
        let packageName = lastDotIndex > 0 ? classPath : 'kotlin';
        if (lastDotIndex > 0) {
            let match = this.packageMatcher.findMostSpecificModule(classPath);
            if (match) {
                packageName = match;
            } else {
                packageName = classPath.split('.').slice(0, 4).join('.');
            }
        } else {
            packageName = 'kotlin';
        }

        const className = lastDotIndex > 0 ? classPath.substring(lastDotIndex + 1) : classPath;
        const fullFunctionName = symbol;
        return {
            packageName,
            className,
            fullFunctionName,
        };
    }

    protected isPureComputeSymbol(file: string, symbol: string): boolean {
        for (const [fileRegex, symbolRegex] of this.computeFilesRegexCfg) {
            if (file.match(fileRegex) && symbol.match(symbolRegex)) {
                return true;
            }
        }

        return false;
    }
}
