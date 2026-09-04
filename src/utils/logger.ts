/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import log4js, { type Configuration } from 'log4js';
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
    // HAPRAY_WORKSPACE 落点（对齐 hapray-core path_utils / symbol_recovery config.py）：
    //   - 根 = HAPRAY_WORKSPACE（已设且目录存在）否则 cwd；不再写 ~/ArkAnalyzer-HapRay 家目录。
    //   - reports/logs 落根顶层；其余 scratch（runtime/static_analyzer/…）进 .hapray/<subdir>。
    private static readonly WORKSPACE_TOP_LEVEL_SUBDIRS = ['reports', 'logs'];

    private static resolveWorkspaceRoot(): string {
        const raw = (process.env.HAPRAY_WORKSPACE ?? '').trim();
        if (!raw) {
            return process.cwd();
        }
        try {
            if (!fs.existsSync(raw)) {
                return process.cwd();
            }
            return path.resolve(raw);
        } catch {
            return process.cwd();
        }
    }

    private static resolveDataRoot(subdir: string): string {
        const root = Logger.resolveWorkspaceRoot();
        return Logger.WORKSPACE_TOP_LEVEL_SUBDIRS.includes(subdir)
            ? path.join(root, subdir)
            : path.join(root, '.hapray', subdir);
    }

    private static isDirWritable(dir: string): boolean {
        try {
            fs.accessSync(dir, fs.constants.W_OK);
            return true;
        } catch {
            return false;
        }
    }

    static resolveDefaultRuntimeDir(dirName = 'runtime'): string {
        // 临时目录落到 HAPRAY_WORKSPACE 下的可写 runtime 目录（对齐 symbol_recovery）。
        const dir = Logger.resolveDataRoot(dirName);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    static resolveUserDataDir(dirName: string): string {
        const dir = Logger.resolveDataRoot(dirName);
        fs.mkdirSync(dir, { recursive: true });
        return dir;
    }

    /**
     * 将输出路径统一映射到 HAPRAY_WORKSPACE 下的可写目录，避免只读 cwd 写入失败。
     * 映射为 <HAPRAY_WORKSPACE>/.hapray/static_analyzer/<subdir>/<basename(outputPath)>
     */
    static mapOutputPath(subdir: string, outputPath: string): string {
        const root = path.join(Logger.resolveUserDataDir('static_analyzer'), subdir);
        fs.mkdirSync(root, { recursive: true });
        return path.join(root, path.basename(outputPath));
    }

    /**
     * cwd 不可写时（如打包资源只读目录）切到 HAPRAY_WORKSPACE 下的可写 runtime 目录，
     * 避免相对路径写盘触发 EROFS（对齐 symbol_recovery _ensure_writable_cwd）。
     * cwd 可写时保持原状，不切。全平台一致，不再按平台区分。
     */
    static ensureWritableCwd(): void {
        if (Logger.isDirWritable(process.cwd())) {
            return;
        }
        try {
            process.chdir(Logger.resolveDefaultRuntimeDir('runtime'));
        } catch {
            // 保持现状，由后续 IO 显式报错
        }
    }

    static resolveDefaultLogPath(logFileName: string): string {
        // 日志写到 HAPRAY_WORKSPACE 顶层 logs 目录。
        const dir = Logger.resolveDataRoot('logs');
        try {
            fs.mkdirSync(dir, { recursive: true });
            return path.join(dir, logFileName);
        } catch {
            // 如果目标目录不可写，退回不写文件（让调用方只走 console appender）
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
