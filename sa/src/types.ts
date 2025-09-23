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

import { createFrameworkTypeEnum, createFileTypeEnum } from './config/types-config';

/**
 * 技术栈框架类型 - 从配置文件动态生成
 */
export const FrameworkType = createFrameworkTypeEnum();

/**
 * 框架类型的类型定义
 */
export type FrameworkTypeKey = keyof typeof FrameworkType;

/**
 * SO文件分析结果
 */
export interface SoAnalysisResult {
    /** SO文件路径 */
    filePath: string;
    /** 文件名 */
    fileName: string;
    /** 识别到的框架类型 */
    frameworks: FrameworkTypeKey[];
    /** 文件大小 */
    fileSize: number;
    /** 是否为系统库 */
    isSystemLib: boolean;
}

/**
 * 文件类型枚举 - 从配置文件动态生成
 */
export const FileType = createFileTypeEnum();

/**
 * 文件类型的类型定义
 */
// eslint-disable-next-line no-redeclare
export type FileType = keyof typeof FileType;

/**
 * 魔术字定义
 */
export interface MagicNumber {
    type: FileType;
    signature: number[];
    offset: number;
    description: string;
}

/**
 * 资源文件信息
 */
export interface ResourceFileInfo {
    /** 文件路径 */
    filePath: string;
    /** 文件名 */
    fileName: string;
    /** 文件类型 */
    fileType: FileType;
    /** 文件大小 */
    fileSize: number;
    /** MIME类型 */
    mimeType: string;
    /** 是否为文本文件 */
    isTextFile: boolean;
}

/**
 * 压缩文件信息
 */
export interface ArchiveFileInfo extends ResourceFileInfo {
    /** 压缩文件内的文件数量 */
    entryCount: number;
    /** 是否已解压分析 */
    extracted: boolean;
    /** 解压深度 */
    extractionDepth: number;
    /** 嵌套文件列表 */
    nestedFiles?: ResourceFileInfo[];
    /** 嵌套的压缩文件 */
    nestedArchives?: ArchiveFileInfo[];
}

/**
 * JavaScript文件信息
 */
export interface JsFileInfo extends ResourceFileInfo {
    /** 是否为压缩代码 */
    isMinified: boolean;
    /** 代码行数（估算） */
    estimatedLines: number;
}

/**
 * Hermes字节码文件信息
 */
export interface HermesFileInfo extends ResourceFileInfo {
    /** 字节码版本 */
    version?: string;
    /** 是否为有效的Hermes字节码 */
    isValidHermes: boolean;
}

/**
 * 资源文件分析结果
 */
export interface ResourceAnalysisResult {
    /** 总文件数（包括嵌套文件） */
    totalFiles: number;
    /** 按类型分组的文件（包括嵌套文件） */
    filesByType: Map<FileType, ResourceFileInfo[]>;
    /** 压缩文件列表 */
    archiveFiles: ArchiveFileInfo[];
    /** JavaScript文件列表（包括嵌套文件） */
    jsFiles: JsFileInfo[];
    /** Hermes字节码文件列表（包括嵌套文件） */
    hermesFiles: HermesFileInfo[];
    /** 总文件大小（包括嵌套文件） */
    totalSize: number;
    /** 最大解压深度 */
    maxExtractionDepth: number;
    /** 解压的压缩文件数量 */
    extractedArchiveCount: number;
}

/**
 * HAP包静态分析结果
 */
export interface HapStaticAnalysisResult {
    /** HAP包路径 */
    hapPath: string;
    /** SO文件分析结果 */
    soAnalysis: {
        /** 检测到的框架 */
        detectedFrameworks: FrameworkTypeKey[];
        /** SO文件详情 */
        soFiles: SoAnalysisResult[];
        /** 总SO文件数 */
        totalSoFiles: number;
    };
    /** 资源文件分析结果 */
    resourceAnalysis: ResourceAnalysisResult;
    /** 分析时间戳 */
    timestamp: Date;
}


