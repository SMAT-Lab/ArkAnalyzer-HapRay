/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import log4js from 'log4js';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';

export const LOG_LEVEL = {
    ERROR: 'ERROR',
    WARN: 'WARN',
    INFO: 'INFO',
    DEBUG: 'DEBUG',
    TRACE: 'TRACE',
} as const;

export const LOG_MODULE_TYPE = {
    DEFAULT: 'default',
    TOOL: 'sa-cmd',
} as const;

type LogLevel = (typeof LOG_LEVEL)[keyof typeof LOG_LEVEL];
type LogModuleType = (typeof LOG_MODULE_TYPE)[keyof typeof LOG_MODULE_TYPE];

class Logger {
    static resolveDefaultRuntimeDir(dirName = 'runtime'): string {
        // 仅在 macOS App 打包场景下，cwd 可能落在只读目录；这里统一把临时目录放到用户目录
        // Windows/Linux 保持原行为（相对当前工作目录即可）。
        if (process.platform !== 'darwin') {
            return path.join(process.cwd(), dirName);
        }
        const dir = path.join(os.homedir(), 'ArkAnalyzer-HapRay', dirName);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    static ensureWritableCwd(): void {
        if (process.platform !== 'darwin') {
            return;
        }
        try {
            const runtimeDir = Logger.resolveDefaultRuntimeDir('runtime');
            process.chdir(runtimeDir);
        } catch {
            // 保持现状，由后续 IO 显式报错
        }
    }

    static resolveDefaultLogPath(logFileName: string): string {
        // 仅在 macOS App 打包场景下，cwd 可能落在只读目录；这里统一把日志写到用户目录
        // Windows/Linux 保持原行为（相对路径即可）。
        if (process.platform !== 'darwin') {
            return logFileName;
        }
        const dir = path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'logs');
        try {
            fs.mkdirSync(dir, { recursive: true });
            return path.join(dir, logFileName);
        } catch {
            // 如果用户目录不可写，退回不写文件（让调用方只走 console appender）
            return '';
        }
    }

    static configure(
        logFilePath: string,
        arkanalyzerLevel: LogLevel = LOG_LEVEL.ERROR,
        toolLevel: LogLevel = LOG_LEVEL.INFO,
        useConsole = false,
    ): void {
        const appendersTypes: Array<string> = [];
        if (logFilePath) {
            appendersTypes.push('file');
        }
        if (!appendersTypes.length || useConsole) {
            appendersTypes.push('console');
        }

        log4js.configure({
            appenders: {
                file: {
                    type: 'fileSync',
                    filename: logFilePath,
                    maxLogSize: 5 * 1024 * 1024,
                    backups: 5,
                    compress: true,
                    encoding: 'utf-8',
                    layout: {
                        type: 'pattern',
                        pattern: '[%d] [%p] [%z] [%X{module}] - [%X{tag}] %m',
                    },
                },
                console: {
                    type: 'console',
                    layout: {
                        type: 'pattern',
                        pattern: '[%d] [%p] [%z] [%X{module}] - [%X{tag}] %m',
                    },
                },
            },
            categories: {
                default: {
                    appenders: ['console'],
                    level: 'info',
                    enableCallStack: false,
                },
                ArkAnalyzer: {
                    appenders: appendersTypes,
                    level: arkanalyzerLevel,
                    enableCallStack: true,
                },
                Tool: {
                    appenders: appendersTypes,
                    level: toolLevel,
                    enableCallStack: true,
                },
            },
        });
    }

    static getLogger(logType: LogModuleType, tag = '-'): log4js.Logger {
        const category =
      logType === LOG_MODULE_TYPE.DEFAULT
          ? logType
          : LOG_MODULE_TYPE.TOOL;
        const logger = log4js.getLogger(category);
        logger.addContext('module', logType);
        logger.addContext('tag', tag);
        return logger;
    }
}

export default Logger;
