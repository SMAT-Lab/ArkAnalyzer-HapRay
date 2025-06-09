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

import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';
import { loadConfig } from './loader';
import { GlobalConfig } from './types';
const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

let _config: GlobalConfig | null = null;

export function initConfig(cliArgs: Partial<GlobalConfig>, afterLoad: (cfg: GlobalConfig) => void): void {
    _config = loadConfig(cliArgs);
    afterLoad(_config);
    _config = Object.freeze(_config);
}

export function getConfig(): GlobalConfig {
    if (!_config) {
        _config = Object.freeze(loadConfig({}));
    }

    return _config;
}

export function updateKindConfig(config: GlobalConfig, kindsJson: string): void {
    try {
        const kinds = JSON.parse(kindsJson);
        config.perf.kinds.push(...kinds);
    } catch (error: any) {
        logger.error(`Invalid kind configuration: ${error.message} ${kindsJson}`);
    }
}
