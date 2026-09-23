/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import log4js, { type Configuration } from 'log4js';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import {
    resolveLogPath,
    resolveOutputPath,
    resolveRuntimeDir,
    resolveUserDataDir,
    type RuntimePathContext,
} from './runtime_paths';

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
    private static isDirectoryWritable(dir: string): boolean {
        const probePath = path.join(
            dir,
            `.hapray-write-test-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        );
        let fd: number | undefined;
        try {
            fd = fs.openSync(probePath, 'wx');
            return true;
        } catch {
            return false;
        } finally {
            if (fd !== undefined) {
                fs.closeSync(fd);
            }
            try {
                fs.unlinkSync(probePath);
            } catch {
                // The probe may not have been created.
            }
        }
    }

    private static runtimePathContext(): RuntimePathContext {
        const cwd = process.cwd();
        return {
            platform: process.platform,
            cwd,
            homeDir: os.homedir(),
            env: process.env,
            cwdWritable: Logger.isDirectoryWritable(cwd),
        };
    }

    static resolveDefaultRuntimeDir(
        dirName = 'runtime',
        context = Logger.runtimePathContext(),
    ): string {
        const dir = resolveRuntimeDir(dirName, context);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    static resolveUserDataDir(
        dirName: string,
        context = Logger.runtimePathContext(),
    ): string {
        const dir = resolveUserDataDir(dirName, context);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    /**
     * Preserve explicit output paths. Relative paths are redirected only when
     * a workspace override is configured or the current directory is read-only.
     */
    static mapOutputPath(
        subdir: string,
        outputPath: string,
        context = Logger.runtimePathContext(),
    ): string {
        return resolveOutputPath(subdir, outputPath, context);
    }

    static ensureWritableCwd(
        context = Logger.runtimePathContext(),
    ): RuntimePathContext {
        if (context.cwdWritable) {
            return context;
        }
        try {
            const runtimeDir = Logger.resolveDefaultRuntimeDir('runtime', context);
            process.chdir(runtimeDir);
        } catch {
            // 保持现状，由后续 IO 显式报错
        }
        return context;
    }

    static resolveDefaultLogPath(
        logFileName: string,
        context = Logger.runtimePathContext(),
    ): string {
        const logPath = resolveLogPath(logFileName, context);
        if (logPath === logFileName) {
            return logFileName;
        }
        try {
            fs.mkdirSync(path.dirname(logPath), { recursive: true });
            return logPath;
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

    /**
     * 将控制台日志改到 stderr，便于 stdout 仅输出 --machine-json 的 JSON 行。
     * 需在子命令（如 hap）解析到 --machine-json 后、业务日志输出前调用。
     */
    static reconfigureForMachineJson(): void {
        log4js.shutdown();
        const logFilePath = Logger.resolveDefaultLogPath('HapRay.log');
        const appendersTypes: Array<string> = [];
        if (logFilePath) {
            appendersTypes.push('file');
        }
        appendersTypes.push('stderrConsole');

        const appenders: NonNullable<Configuration['appenders']> = {
            stderrConsole: {
                type: 'stderr',
                layout: {
                    type: 'pattern',
                    pattern: '[%d] [%p] [%z] [%X{module}] - [%X{tag}] %m',
                },
            },
        };
        if (logFilePath) {
            appenders.file = {
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
            };
        }

        const cfg: Configuration = {
            appenders,
            categories: {
                default: {
                    appenders: ['stderrConsole'],
                    level: 'info',
                    enableCallStack: false,
                },
                ArkAnalyzer: {
                    appenders: appendersTypes,
                    level: LOG_LEVEL.ERROR,
                    enableCallStack: true,
                },
                Tool: {
                    appenders: appendersTypes,
                    level: LOG_LEVEL.INFO,
                    enableCallStack: true,
                },
            },
        };
        log4js.configure(cfg);
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
