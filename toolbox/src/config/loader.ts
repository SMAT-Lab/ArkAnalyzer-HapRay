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
import { z } from 'zod';
import type { ComponentConfig, GlobalConfig, Ohpm, ProcessClassify, SoOriginal, SymbolSplit } from './types';

const ConfigSchema = z.object({
    analysis: z.object({
        onlineIdentifyThirdPart: z.boolean().default(false),
        reSo: z.boolean().default(false),
        reAbc: z.boolean().default(false),
        ohpm: z.array(
            z.object({
                name: z.string(),
                version: z.string(),
                versions: z.array(z.string()),
                files: z.array(z.string()).optional(),
            })
        ),
        npm: z.array(
            z.object({
                name: z.string(),
                version: z.string(),
                versions: z.array(z.string()),
                files: z.array(z.string()).optional(),
            })
        ),
        invalidNpm: z.array(z.string()).default([]),
    }),
    perf: z.object({
        kinds: z
            .array(
                z.object({
                    name: z.string(),
                    kind: z.number(),
                    components: z.array(
                        z.object({
                            name: z.string().optional(),
                            files: z.array(z.string()),
                            threads: z.array(z.string()).optional(),
                        })
                    ),
                })
            )
            .default([]),
        symbolSplitRules: z
            .array(
                z.object({
                    source_file: z.string(),
                    new_file: z.string(),
                    filter_symbols: z.array(z.string()),
                })
            )
            .default([]),
        soOrigins: z
            .map(
                z.string(),
                z.object({
                    specific_origin: z.string(),
                    broad_category: z.string(),
                    sdk_category: z.string(),
                })
            )
            .default(new Map()),
        classify: z.object({
            dfx_symbols: z.array(z.string()).default([]),
            compute_files: z.array(z.string()).default([]),
            process: z.record(
                z.string(),
                z.record(
                    z.string(),
                    z.record(
                        z.string(),
                        z.object({
                            Android_Process: z.array(z.string()),
                            Harmony_Process: z.array(z.string()),
                            IOS_Process: z.array(z.string()),
                        })
                    )
                )
            ),
            process_special: z
                .record(
                    z.string(),
                    z.record(
                        z.string(),
                        z.record(
                            z.string(),
                            z.object({
                                scene: z.string(),
                                Android_Process: z.array(z.string()),
                                Harmony_Process: z.array(z.string()),
                                IOS_Process: z.array(z.string()),
                            })
                        )
                    )
                )
                .default({}),
        }),
    }),
    save: z.object({
        callchain: z.boolean().default(false),
    }),
    inDbtools: z.boolean().default(false),
    jobs: z.number().default(4),
    input: z.string().default(''),
    fuzzy: z.array(z.string()).default([]),
    output: z.string().default('output'),
    extToolsPath: z.string(),
    osPlatform: z.number().default(0),
    soDir: z.string().default(''),
    choose: z.boolean().default(false),
    checkTraceDb: z.boolean().default(false),
    compatibility: z.boolean().default(false),
    ut: z.boolean().default(false),
});

function getExtToolsRoot(): string {
    let root = path.join(__dirname, 'third-party');
    if (!fs.existsSync(root)) {
        root = path.join(__dirname, '../../../third-party');
    }
    if (fs.existsSync(root)) {
        return path.resolve(root);
    }
    throw new Error('not found ext_tools');
}

function loadResCfg(): Partial<GlobalConfig> {
    let res = path.join(__dirname, 'res');
    if (!fs.existsSync(res)) {
        res = path.join(__dirname, '../../res');
    }

    const config: GlobalConfig = {
        analysis: {
            onlineIdentifyThirdPart: false,
            reSo: false,
            reAbc: false,
            ohpm: [],
            npm: [],
            invalidNpm: [],
        },
        perf: {
            kinds: [],
            symbolSplitRules: [],
            soOrigins: new Map(),
            classify: {
                process: {},
                process_special: {},
                dfx_symbols: [],
                compute_files: [],
            },
        },
        save: {
            callchain: false,
        },
        inDbtools: false,
        jobs: 4,
        input: '',
        fuzzy: [],
        output: 'output',
        extToolsPath: '',
        osPlatform: 0,
        soDir: '',
        choose: false,
        checkTraceDb: false,
        compatibility: false,
        ut: false
    };
    let perfKind = path.join(res, 'perf/kind.json');
    config.perf.kinds = JSON.parse(fs.readFileSync(perfKind, { encoding: 'utf-8' })) as Array<ComponentConfig>;
    config.perf.symbolSplitRules = JSON.parse(
        fs.readFileSync(path.join(res, 'perf/symbol_split.json'), { encoding: 'utf-8' })
    ) as Array<SymbolSplit>;
    let soOriginCfg = path.join(res, 'so/standardized_origins.json');
    if (fs.existsSync(soOriginCfg)) {
        config.perf.soOrigins = new Map(
            Object.entries(
                JSON.parse(fs.readFileSync(soOriginCfg, { encoding: 'utf-8' })) as Record<string, SoOriginal>
            )
        );
    }

    let classifyCfg = path.join(res, 'perf/classify.json');
    if (fs.existsSync(classifyCfg)) {
        config.perf.classify = JSON.parse(fs.readFileSync(classifyCfg, { encoding: 'utf-8' })) as ProcessClassify;
    }

    let ohpmCfg = path.join(res, 'ohpm/ohpm.json');
    let npmCfg = path.join(res, 'ohpm/npm.json');
    let invalidNpmCfg = path.join(res, 'ohpm/invalid_npm.json');

    if (fs.existsSync(ohpmCfg)) {
        config['analysis']['ohpm'] = JSON.parse(fs.readFileSync(ohpmCfg, { encoding: 'utf-8' })) as Array<Ohpm>;
    }

    if (fs.existsSync(npmCfg)) {
        config['analysis']['npm'] = JSON.parse(fs.readFileSync(npmCfg, { encoding: 'utf-8' })) as Array<Ohpm>;
    }

    if (fs.existsSync(invalidNpmCfg)) {
        config['analysis']['invalidNpm'] = JSON.parse(
            fs.readFileSync(invalidNpmCfg, { encoding: 'utf-8' })
        ) as Array<string>;
    }

    config['extToolsPath'] = getExtToolsRoot();

    return config;
}

export function loadConfig(cliArgs: Partial<GlobalConfig>): GlobalConfig {
    return ConfigSchema.parse({ ...loadResCfg(), ...cliArgs });
}
