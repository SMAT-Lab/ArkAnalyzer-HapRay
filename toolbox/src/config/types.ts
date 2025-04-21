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

export interface GlobalConfig {
    analysis: {
        onlineIdentifyThirdPart: boolean;
        reSo: boolean;
        reAbc: boolean;
        ohpm: Ohpm[];
    };

    perf: {
        kinds: ComponentConfig[];
    };

    save: {
        callchain: boolean;
    };
    inDbtools: boolean;
    jobs: number;
    input: string;
    output: string;
}
