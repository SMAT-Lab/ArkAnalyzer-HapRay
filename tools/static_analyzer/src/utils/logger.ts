/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import log4js from 'log4js';

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
