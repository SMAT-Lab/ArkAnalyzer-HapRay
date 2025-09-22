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
import type { Component, ComponentCategoryType } from '../component';
import { ComponentCategory, OriginKind } from '../component';
import { AnalyzerProjectBase, PROJECT_ROOT } from '../project';
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

export interface ClassifyCategory {
    category: number; // 组件大类
    categoryName: string; //组件名
    subCategoryName?: string; // 小类
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
    protected threadClassifyCfg: Map<RegExp, ClassifyCategory>;
    protected fileClassifyCfg: Map<string, ClassifyCategory>;
    protected fileRegexClassifyCfg: Map<RegExp, ClassifyCategory>;
    protected soOriginsClassifyCfg: Map<string, SoOriginal>;
    protected hapComponents: Map<string, Component>;
    protected symbolsSplitRulesCfg: Array<SymbolSplitRule>;

    // classify result
    protected filesClassifyMap: Map<number, FileClassification>;
    protected symbolsClassifyMap: Map<number, FileClassification>;
    protected symbolsMap: Map<number, string>;

    // KMP方案标记
    protected hasKmpScheme = false;

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
        this.threadClassifyCfg = new Map();
        this.fileClassifyCfg = new Map();
        this.fileRegexClassifyCfg = new Map();
        this.soOriginsClassifyCfg = getConfig().perf.soOrigins;
        this.symbolsSplitRulesCfg = [];

        this.filesClassifyMap = new Map();
        this.symbolsClassifyMap = new Map();
        this.symbolsMap = new Map();
        this.hasKmpScheme = false;

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
        if (
            file.match(regex) ||
            (this.project.bundleName === 'com.ohos.sceneboard' && file.startsWith('/system/app/SceneBoard/')) ||
            (this.project.bundleName === 'com.huawei.hmos.photos' && file.startsWith('/system/app/PhotosHm/'))
        ) {
            let name = path.basename(file);
            if (name.endsWith('.so') || file.indexOf('/bundle/libs/') >= 0) {
                fileClassify.category = ComponentCategory.APP_SO;
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

                // 特殊处理compose符号
                if (packageName === 'compose') {
                    symbolClassification.category = ComponentCategory.KMP;
                    symbolClassification.categoryName = 'KMP';
                    symbolClassification.subCategoryName = 'compose';
                }

                if (this.hapComponents.has(matches[3])) {
                    symbolClassification.category = this.hapComponents.get(matches[3])!.kind;
                }

                this.symbolsClassifyMap.set(symbolId, symbolClassification);
                return symbolClassification;
            }
        } else if (fileClassification.category === ComponentCategory.KMP && symbol.startsWith('kfun')) {
            let kmpSymbol = this.parseKmpSymbol(symbol);
            this.symbolsMap.set(symbolId, kmpSymbol.fullFunctionName);
            let symbolClassification: FileClassification = {
                file: `${kmpSymbol.packageName}.${kmpSymbol.className}`,
                originKind: fileClassification.originKind,
                category: fileClassification.category,
                categoryName: fileClassification.categoryName,
                subCategoryName: kmpSymbol.packageName,
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

    public classifySoOrigins(file: string): { originKind: OriginKind; subCategoryName?: string } | undefined {
        let name = path.basename(file);
        if (!this.soOriginsClassifyCfg.has(name)) {
            return undefined;
        }

        let soOriginalCfg = this.soOriginsClassifyCfg.get(name)!;
        let result = {
            originKind: OriginKind.FIRST_PARTY,
            subCategoryName: this.soOriginsClassifyCfg.get(name)!.sdk_category,
        };

        if (soOriginalCfg.broad_category === 'THIRD_PARTY') {
            result.originKind = OriginKind.THIRD_PARTY;
        } else if (soOriginalCfg.broad_category === 'OPENSOURCE') {
            result.originKind = OriginKind.OPEN_SOURCE;
        } else if (soOriginalCfg.broad_category === 'FIRST_PARTY') {
            result.originKind = OriginKind.FIRST_PARTY;
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
            { value: '组件大类' },
            { value: '组件小类' },
            { value: '组件来源' },
            { value: '是否主应用' },
            { value: '业务领域' },
            { value: '子系统' },
            { value: '部件' },
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
            { value: 'is_main_app' },
            { value: 'sys_domain' },
            { value: 'sys_subsystem' },
            { value: 'sys_component' },
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
                    componentName: data.componentName,
                    componentCategory: data.componentCategory,
                    originKind: data.originKind,
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

                { value: data[0].componentCategory, type: Number },
                { value: data[0].componentName, type: String },
                { value: data[0].originKind, type: Number },
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
            await saveJsonArray([jsonObject], outputFileName);
        }
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
