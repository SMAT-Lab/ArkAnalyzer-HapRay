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
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { runCommand, runCommandSync } from '../../utils/exe_utils';
import { getConfig } from '../../config';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

function initTools(): string {
    let toolName = '';
    if (process.platform === 'win32') {
        toolName = 'trace_streamer_windows.exe';
    } else if (process.platform === 'linux') {
        toolName = 'trace_streamer_linux';
    } else if (process.platform === 'darwin') {
        toolName = 'trace_streamer_mac';
    } else {
        logger.error('os not support');
        throw new Error('os not support');
    }

    let toolCmd = path.join(getConfig().extToolsPath, 'trace_streamer_binary', toolName);
    if (fs.existsSync(toolCmd)) {
        if (process.platform === 'linux' || process.platform === 'darwin') {
            runCommandSync('chmod', ['+x', toolCmd]);
        }
    }
    return toolCmd;
}

export async function traceStreamerCmd(htraceFile: string, outDbFile: string): Promise<string> {
    let _traceStreamer = initTools();

    if (!fs.existsSync(_traceStreamer)) {
        logger.error('not found trace_streamer_binary');
        throw new Error('not found trace_streamer_binary');
    }

    if (getConfig().soDir !== '') {
        return await runCommand(_traceStreamer, [htraceFile, '-e', outDbFile, '--So_dir', getConfig().soDir]);
    } else {
        return await runCommand(_traceStreamer, [htraceFile, '-e', outDbFile]);
    }
}
