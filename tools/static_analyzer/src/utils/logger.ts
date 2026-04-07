/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import log4js, { type Configuration } from 'log4js';
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

    static resolveUserDataDir(dirName: string): string {
        if (process.platform !== 'darwin') {
            return path.join(process.cwd(), dirName);
        }
        const dir = path.join(os.homedir(), 'ArkAnalyzer-HapRay', dirName);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    /**
     * macOS 下将输出路径统一映射到用户目录，避免只读目录写入失败。
     * - Windows/Linux：保持用户传入路径不变
     * - macOS：映射为 ~/ArkAnalyzer-HapRay/static_analyzer/<subdir>/<basename(outputPath)>
     */
    static mapOutputPath(subdir: string, outputPath: string): string {
        if (process.platform !== 'darwin') {
            return outputPath;
        }
        const root = path.join(Logger.resolveUserDataDir('static_analyzer'), subdir);
        fs.mkdirSync(root, { recursive: true });
        return path.join(root, path.basename(outputPath));
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
