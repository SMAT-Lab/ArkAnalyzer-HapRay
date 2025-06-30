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

export enum OSPlatform {
    HarmonyOS = 0,
    Android = 1,
    IOS = 2,
}

export const OSPlatformMap: Map<string, OSPlatform> = new Map([
    ['HarmonyOS', OSPlatform.HarmonyOS],
    ['Android', OSPlatform.Android],
    ['IOS', OSPlatform.IOS],
]);

export interface Ohpm {
    name: string;
    version: string;
    versions: string[];
    main?: string;
    module?: string;
    types?: string;
    files?: string[];
    so?: string[];
    filesSet?: Set<string>;
}

export interface SubComponentConfig {
    name?: string;
    files: string[];
    threads?: string[];
}

export interface ComponentConfig {
    name: string;
    kind: number;
    components: SubComponentConfig[];
}

export interface SoOriginal {
    specific_origin: string;
    broad_category: string;
    sdk_category: string;
    confidence?: number;
    original?: string;
    feature?: string;
    reasoning?: string;
}

export interface SymbolSplit {
    source_file: string;
    new_file: string;
    filter_symbols: string[];
}

export interface GlobalConfig {
    analysis: {
        onlineIdentifyThirdPart: boolean;
        reSo: boolean;
        reAbc: boolean;
        ohpm: Ohpm[];
        npm: Ohpm[];
        invalidNpm: string[];
    };

    perf: {
        kinds: ComponentConfig[];
        symbolSplitRules: SymbolSplit[];
        soOrigins: Map<string, SoOriginal>;
        classify: {
            dfx_symbols: string[];
            compute_files: string[];
            process: Record<
                string, // domain
                Record<
                    string, // subSystem
                    Record<
                        string, // component
                        {
                            Android_Process: string[];
                            Harmony_Process: string[];
                            IOS_Process: string[];
                        }
                    >
                >
            >;
            process_special: Record<
                string, // domain
                Record<
                    string, // subSystem
                    Record<
                        string, // component
                        {
                            scene: string;
                            Android_Process: string[];
                            Harmony_Process: string[];
                            IOS_Process: string[];
                        }
                    >
                >
            >;
        };
    };

    save: {
        callchain: boolean;
    };
    inDbtools: boolean;
    jobs: number;
    input: string;
    fuzzy: string[];
    output: string;
    extToolsPath: string;
    soDir: string;
    osPlatform: OSPlatform;
    choose: boolean;
    checkTraceDb: boolean;
}
