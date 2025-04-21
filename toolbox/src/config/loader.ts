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
import { GlobalConfig, Ohpm } from './types';

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
            })
        ),
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
    }),
    save: z.object({
        callchain: z.boolean().default(false),
    }),
    inDbtools: z.boolean().default(false),
    jobs: z.number().default(4),
    input: z.string().default(''),
    output: z.string().default('output'),
});

function loadResCfg(): Partial<GlobalConfig> {
    let res = path.join(__dirname, 'res');
    if (!fs.existsSync(res)) {
        res = path.join(__dirname, '../../res');
    }

    const config: Record<string, any> = {
        analysis: { reSo: false, reAbc: false },
        perf: {},
        save: {},
    };
    let perfKind = path.join(res, 'perf/kind.json');
    config['perf']['kinds'] = JSON.parse(fs.readFileSync(perfKind, { encoding: 'utf-8' }));
    let ohpmCfg = path.join(res, 'ohpm/ohpm.json');

    if (fs.existsSync(ohpmCfg)) {
        config['analysis']['ohpm'] = JSON.parse(fs.readFileSync(ohpmCfg, { encoding: 'utf-8' })) as Array<Ohpm>;
    }

    return config;
}

export function loadConfig(cliArgs: Partial<GlobalConfig>): GlobalConfig {
    return ConfigSchema.parse({ ...loadResCfg(), ...cliArgs });
}
