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

import { spawn, spawnSync } from 'child_process';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export function runCommandSync(
    command: string,
    args: Array<string>,
    allowNonZeroExit = true,
    env?: NodeJS.ProcessEnv
): string {
    let result = spawnSync(command, args, { encoding: 'utf-8', shell: true, env: env });
    logger.info(`runCommandSync ${command} ${args.join(' ')}`);
    if (result.stderr.trim()) {
        logger.error(`runCommandSync: ${command} ${args.join(' ')} ${result.stderr}`);
        if (!allowNonZeroExit) {
            throw new Error(`${result.stderr}`);
        }
    }
    logger.info(`runCommandSync ${result.stdout}`);
    return result.stdout;
}

export async function runCommand(command: string, args: Array<string>, env?: NodeJS.ProcessEnv): Promise<string> {
    return new Promise((resolve) => {
        let output: Array<string> = [];
        let cmdProcess = spawn(command, args, { shell: true, env: env });
        logger.info(`runCommand ${command} ${args.join(' ')}`);
        cmdProcess.stdout.on('data', (data: Buffer) => {
            logger.info(`runCommand ${data.toString()}`);
            output.push(data.toString());
        });

        cmdProcess.stderr.on('data', (data: Buffer) => {
            logger.debug(`runCommand stderr: ${data.toString()}`);
            output.push(data.toString());
        });

        cmdProcess.on('close', (code) => {
            if (code !== 0) {
                logger.debug(`runCommand process exited with code ${code}`);
            }
            resolve(output.join('\n'));
        });
    });
}
