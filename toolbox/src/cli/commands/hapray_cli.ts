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

import { Command } from 'commander';
import type { GlobalConfig } from '../../config/types';
import { initConfig, updateKindConfig } from '../../config';
import { main } from '../../services/report/test_report';

interface HapAnalyzerOptions {
    input: string;
    output: string;
    choose: boolean;
    disableDbtools: boolean;
    kindConfig?: string;
    compatibility: boolean;
}

export const DbtoolsCli = new Command('dbtools')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--choose', 'choose one from rounds', false)
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-s, --soDir <string>', '--So_dir soDir', '')
    .option('-k, --kind-config <string>', 'custom kind configuration in JSON format')
    .option('--compatibility', 'start compatibility mode', false)
    .action(async (options: HapAnalyzerOptions) => {
        let cliArgs: Partial<GlobalConfig> = { ...options };
        initConfig(cliArgs, (config) => {
            config.choose = options.choose;
            config.inDbtools = !options.disableDbtools;
            if (options.kindConfig) {
                updateKindConfig(config, options.kindConfig);
            }
            config.compatibility = options.compatibility;
        });

        await main(options.input);
    });
