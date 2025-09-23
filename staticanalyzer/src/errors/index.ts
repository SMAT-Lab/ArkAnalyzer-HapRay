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

/**
 * 分析错误基类
 */
export class AnalysisError extends Error {
    public readonly code: string;
    public readonly originalError?: Error;
    public readonly context?: Record<string, unknown>;

    constructor(
        message: string,
        code: string,
        originalError?: Error,
        context?: Record<string, unknown>
    ) {
        super(message);
        this.name = 'AnalysisError';
        this.code = code;
        this.originalError = originalError;
        this.context = context;

        // 保持原始错误的堆栈跟踪
        if (originalError && originalError.stack) {
            this.stack = `${this.stack}\nCaused by: ${originalError.stack}`;
        }

        // 确保错误对象的原型链正确
        Object.setPrototypeOf(this, AnalysisError.prototype);
    }

    /**
     * 获取完整的错误信息，包括上下文
     */
    public getFullMessage(): string {
        let fullMessage = `[${this.code}] ${this.message}`;
        
        if (this.context && Object.keys(this.context).length > 0) {
            fullMessage += `\nContext: ${JSON.stringify(this.context, null, 2)}`;
        }
        
        if (this.originalError) {
            fullMessage += `\nOriginal error: ${this.originalError.message}`;
        }
        
        return fullMessage;
    }

    /**
     * 转换为JSON格式
     */
    public toJSON(): Record<string, unknown> {
        return {
            name: this.name,
            message: this.message,
            code: this.code,
            context: this.context,
            originalError: this.originalError ? {
                name: this.originalError.name,
                message: this.originalError.message,
                stack: this.originalError.stack
            } : undefined,
            stack: this.stack
        };
    }
}

/**
 * HAP文件相关错误
 */
export class HapFileError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'HAP_FILE_ERROR', originalError, context);
        this.name = 'HapFileError';
        Object.setPrototypeOf(this, HapFileError.prototype);
    }
}

/**
 * ZIP解析错误
 */
export class ZipParsingError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'ZIP_PARSING_ERROR', originalError, context);
        this.name = 'ZipParsingError';
        Object.setPrototypeOf(this, ZipParsingError.prototype);
    }
}

/**
 * SO分析错误
 */
export class SoAnalysisError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'SO_ANALYSIS_ERROR', originalError, context);
        this.name = 'SoAnalysisError';
        Object.setPrototypeOf(this, SoAnalysisError.prototype);
    }
}

/**
 * 资源分析错误
 */
export class ResourceAnalysisError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'RESOURCE_ANALYSIS_ERROR', originalError, context);
        this.name = 'ResourceAnalysisError';
        Object.setPrototypeOf(this, ResourceAnalysisError.prototype);
    }
}

/**
 * 配置错误
 */
export class ConfigurationError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'CONFIGURATION_ERROR', originalError, context);
        this.name = 'ConfigurationError';
        Object.setPrototypeOf(this, ConfigurationError.prototype);
    }
}

/**
 * 内存不足错误
 */
export class OutOfMemoryError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'OUT_OF_MEMORY_ERROR', originalError, context);
        this.name = 'OutOfMemoryError';
        Object.setPrototypeOf(this, OutOfMemoryError.prototype);
    }
}

/**
 * 文件大小限制错误
 */
export class FileSizeLimitError extends AnalysisError {
    constructor(message: string, originalError?: Error, context?: Record<string, unknown>) {
        super(message, 'FILE_SIZE_LIMIT_ERROR', originalError, context);
        this.name = 'FileSizeLimitError';
        Object.setPrototypeOf(this, FileSizeLimitError.prototype);
    }
}

/**
 * 错误工厂函数
 */
export class ErrorFactory {
    /**
     * 创建HAP文件错误
     */
    static createHapFileError(message: string, hapPath?: string, originalError?: Error): HapFileError {
        return new HapFileError(message, originalError, { hapPath });
    }

    /**
     * 创建ZIP解析错误
     */
    static createZipParsingError(message: string, filePath?: string, originalError?: Error): ZipParsingError {
        return new ZipParsingError(message, originalError, { filePath });
    }

    /**
     * 创建SO分析错误
     */
    static createSoAnalysisError(message: string, soPath?: string, originalError?: Error): SoAnalysisError {
        return new SoAnalysisError(message, originalError, { soPath });
    }

    /**
     * 创建资源分析错误
     */
    static createResourceAnalysisError(message: string, resourcePath?: string, originalError?: Error): ResourceAnalysisError {
        return new ResourceAnalysisError(message, originalError, { resourcePath });
    }

    /**
     * 创建配置错误
     */
    static createConfigurationError(message: string, configPath?: string, originalError?: Error): ConfigurationError {
        return new ConfigurationError(message, originalError, { configPath });
    }

    /**
     * 创建内存不足错误
     */
    static createOutOfMemoryError(message: string, fileSize?: number, originalError?: Error): OutOfMemoryError {
        return new OutOfMemoryError(message, originalError, { fileSize });
    }

    /**
     * 创建文件大小限制错误
     */
    static createFileSizeLimitError(message: string, fileSize: number, limit: number, filePath?: string): FileSizeLimitError {
        return new FileSizeLimitError(message, undefined, { fileSize, limit, filePath });
    }
}

/**
 * 错误处理工具函数
 */
export class ErrorUtils {
    /**
     * 判断是否为分析错误
     */
    static isAnalysisError(error: unknown): error is AnalysisError {
        return error instanceof AnalysisError;
    }

    /**
     * 判断是否为内存相关错误
     */
    static isMemoryError(error: unknown): boolean {
        if (error instanceof OutOfMemoryError || error instanceof FileSizeLimitError) {
            return true;
        }
        
        const message = (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string')
            ? error.message.toLowerCase()
            : '';
        return message.includes('out of memory') ||
               message.includes('heap') ||
               message.includes('maximum call stack');
    }

    /**
     * 从任意错误创建分析错误
     */
    static fromError(error: unknown, code: string = 'UNKNOWN_ERROR', context?: Record<string, unknown>): AnalysisError {
        if (error instanceof AnalysisError) {
            return error;
        }

        const message = (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string')
            ? error.message
            : String(error);
        const originalError = error instanceof Error ? error : new Error(String(error));
        
        return new AnalysisError(message, code, originalError, context);
    }

    /**
     * 安全地获取错误消息
     */
    static getErrorMessage(error: unknown): string {
        if (error instanceof AnalysisError) {
            return error.getFullMessage();
        }
        
        if (error instanceof Error) {
            return error.message;
        }
        
        return String(error);
    }
}
