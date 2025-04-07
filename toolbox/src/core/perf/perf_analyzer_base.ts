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
// import { Component, ComponentCategory, ComponentCategoryType, OriginKind, SoOriginal } from '../component';
import { Component, ComponentCategory, ComponentCategoryType, OriginKind } from '../component';
import { AnalyzerProjectBase } from '../project';
// import { getConfig } from '../../config';

export interface TestSceneInfo {
    packageName: string; // 应用包名
    scene: string; // 测试场景名
    osVersion: string; // 操作系统版本
    timestamp: number; // 测试开始时间戳
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
    components: PerfComponent[]; // 计算统计组件负载
    categoriesSum: number[][]; // 大类统计值
    categoriesTotal: number[][]; // 大类Total值
    total: number[]; // 总值, 0 circles, 1 instructions
}

export interface PerfSum {
    scene: string;
    osVersion: string;
    timestamp: number;
    perfPath: string;
    perfId: string;
    steps: PerfStepSum[];
    categories: ComponentCategoryType[];
}

export class PerfAnalyzerBase extends AnalyzerProjectBase {
    protected hapComponents: Map<string, Component>;
    protected cfgThreadComponent: Map<string, { name: string; category: ComponentCategory }>;
    protected cfgFileComponent: Map<string, { name: string; category: ComponentCategory }>;
    protected cfgRegexComponent: Map<RegExp, { name: string; category: ComponentCategory }>;
    // protected soOrigins: Map<string, SoOriginal>;

    constructor(workspace: string) {
        super(workspace);

        this.hapComponents = new Map();
        this.cfgThreadComponent = new Map();
        this.cfgFileComponent = new Map();
        this.cfgRegexComponent = new Map();
        // this.soOrigins = getConfig().perf.soOrigins as Map<string, SoOriginal>;

        this.loadHapComponents();
        // this.loadPerfKindCfg();
    }

    private loadHapComponents(): void {
        const componentFile = path.join(this.projectRoot, 'modules.json');
        if (fs.existsSync(componentFile)) {
            let info = JSON.parse(fs.readFileSync(componentFile, { encoding: 'utf-8' }));
            for (const node of info) {
                for (const component of node.components) {
                    this.hapComponents.set(component.name, component);
                }
            }
        }
    }

    // private loadPerfKindCfg(): void {
    //     for (const kit of getConfig().perf.kinds) {
    //         if (kit.threads) {
    //             for (const thread of kit.threads) {
    //                 this.cfgThreadComponent.set(thread, { name: kit.name, category: kit.kind });
    //             }
    //         }

    //         if (kit.files) {
    //             for (const file of kit.files) {
    //                 if (file.indexOf('*') >= 0) {
    //                     this.cfgRegexComponent.set(new RegExp(file), { name: kit.name, category: kit.kind });
    //                 } else {
    //                     this.cfgFileComponent.set(file, { name: kit.name, category: kit.kind });
    //                 }
    //             }
    //         }
    //     }
    // }
}
