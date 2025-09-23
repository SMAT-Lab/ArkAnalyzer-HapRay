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

export enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3
}

export interface LoggerConfig {
    logFile?: string;
    consoleLevel: LogLevel;
    fileLevel: LogLevel;
    enableConsole: boolean;
    enableFile: boolean;
}

/**
 * 简化的日志系统，参考toolbox的Logger实现
 */
export class Logger {
    private static instance: Logger;
    private config: LoggerConfig;
    private logStream?: fs.WriteStream;

    private constructor(config?: Partial<LoggerConfig>) {
        this.config = {
            consoleLevel: LogLevel.INFO,
            fileLevel: LogLevel.DEBUG,
            enableConsole: true,
            enableFile: false,
            ...config
        };

        if (this.config.enableFile && this.config.logFile) {
            this.initLogFile();
        }
    }

    public static getInstance(config?: Partial<LoggerConfig>): Logger {
        if (!Logger.instance) {
            Logger.instance = new Logger(config);
        }
        return Logger.instance;
    }

    public static configure(logFile?: string, fileLevel: LogLevel = LogLevel.DEBUG, consoleLevel: LogLevel = LogLevel.INFO, enableConsole: boolean = true): void {
        Logger.instance = new Logger({
            logFile,
            fileLevel,
            consoleLevel,
            enableConsole,
            enableFile: !!logFile
        });
    }

    private initLogFile(): void {
        if (!this.config.logFile) return;

        const logDir = path.dirname(this.config.logFile);
        if (!fs.existsSync(logDir)) {
            fs.mkdirSync(logDir, { recursive: true });
        }

        this.logStream = fs.createWriteStream(this.config.logFile, { flags: 'a' });
    }

    private formatMessage(level: LogLevel, message: string, ...args: unknown[]): string {
        const timestamp = new Date().toISOString();
        const levelName = LogLevel[level];
        const formattedArgs = args.length > 0 ? ' ' + args.map(arg => 
            typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
        ).join(' ') : '';
        
        return `[${timestamp}] [${levelName}] ${message}${formattedArgs}`;
    }

    private log(level: LogLevel, message: string, ...args: unknown[]): void {
        const formattedMessage = this.formatMessage(level, message, ...args);

        // 控制台输出
        if (this.config.enableConsole && level >= this.config.consoleLevel) {
            switch (level) {
                case LogLevel.DEBUG:
                    console.debug(formattedMessage);
                    break;
                case LogLevel.INFO:
                    console.info(formattedMessage);
                    break;
                case LogLevel.WARN:
                    console.warn(formattedMessage);
                    break;
                case LogLevel.ERROR:
                    console.error(formattedMessage);
                    break;
            }
        }

        // 文件输出
        if (this.config.enableFile && this.logStream && level >= this.config.fileLevel) {
            this.logStream.write(formattedMessage + '\n');
        }
    }

    public debug(message: string, ...args: unknown[]): void {
        this.log(LogLevel.DEBUG, message, ...args);
    }

    public info(message: string, ...args: unknown[]): void {
        this.log(LogLevel.INFO, message, ...args);
    }

    public warn(message: string, ...args: unknown[]): void {
        this.log(LogLevel.WARN, message, ...args);
    }

    public error(message: string, ...args: unknown[]): void {
        this.log(LogLevel.ERROR, message, ...args);
    }

    public close(): void {
        if (this.logStream) {
            this.logStream.end();
        }
    }
}
