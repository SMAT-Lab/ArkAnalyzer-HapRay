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
export enum OSPlatform {
    HarmonyOS = 0,
    Android = 1,
    IOS = 2,
}

export const OSPlatformMap: Map<string, OSPlatform> = new Map([
    ['HarmonyOS', OSPlatform.HarmonyOS],
    ['Android', OSPlatform.Android],
    ['IOS', OSPlatform.IOS],
]);

export interface Ohpm {
    name: string;
    version: string;
    versions: Array<string>;
    main?: string;
    module?: string;
    types?: string;
    files?: Array<string>;
    so?: Array<string>;
    filesSet?: Set<string>;
}

export interface KotlinModule {
    name: string;
    namespace: string;
}

export interface SubComponentConfig {
    name?: string;
    files: Array<string>;
    threads?: Array<string>;
}

export interface ComponentConfig {
    name: string;
    kind: number;
    components: Array<SubComponentConfig>;
}

export interface SoOriginal {
    specific_origin: string;
    broad_category: string;
    sdk_category: string;
    confidence?: number;
    original?: string;
    feature?: string;
    reasoning?: string;
}

export interface SymbolSplit {
    source_file: string;
    new_file: string;
    filter_symbols: Array<string>;
}

export interface ProcessClassify {
    dfx_symbols: Array<string>;
    compute_files: Array<[string, string]>;
    process: Record<
        string, // domain
        Record<
            string, // subSystem
            Record<
                string, // component
                {
                    Android_Process: Array<string>;
                    Harmony_Process: Array<string>;
                    IOS_Process: Array<string>;
                }
            >
        >
    >;
    process_special: Record<
        string, // domain
        Record<
            string, // subSystem
            Record<
                string, // component
                {
                    scene: string;
                    Android_Process: Array<string>;
                    Harmony_Process: Array<string>;
                    IOS_Process: Array<string>;
                }
            >
        >
    >;
}

export interface GlobalConfig {
    analysis: {
        onlineIdentifyThirdPart: boolean;
        reSo: boolean;
        reAbc: boolean;
        ohpm: Array<Ohpm>;
        npm: Array<Ohpm>;
        invalidNpm: Array<string>;
    };

    perf: {
        kinds: Array<ComponentConfig>;
        symbolSplitRules: Array<SymbolSplit>;
        soOrigins: Map<string, SoOriginal>;
        classify: ProcessClassify;
        kotlinModules: Array<KotlinModule>;
    };

    save: {
        callchain: boolean;
    };
    inDbtools: boolean;
    jobs: number;
    input: string;
    fuzzy: Array<string>;
    output: string;
    extToolsPath: string;
    soDir: string;
    osPlatform: OSPlatform;
    choose: boolean;
    checkTraceDb: boolean;
    compatibility: boolean;
    ut: boolean;
}



/**
 * 技术栈框架类型
 */
export enum FrameworkType {
    RN = 'RN',
    Flutter = 'Flutter',
    Hermes = 'Hermes',
    KMP = 'KMP',
    CMP = 'CMP',
    Lynx = 'Lynx',
    Qt = 'Qt',
    Unity = 'Unity',
    Taro = 'Taro',
    Weex = 'Weex',
    System = 'System',
    Unknown = 'Unknown'
}

/**
 * 框架类型的类型定义
 */
export type FrameworkTypeKey = keyof typeof FrameworkType;

/**
 * SO文件分析结果
 */
/**
 * KMP 框架分析详情
 */
export interface KmpAnalysisDetail {
    /** 是否检测到 KMP */
    isKmp: boolean;
    /** 匹配到的特征符号列表 */
    matchedSignatures: Array<string>;
    /** 检测方法 */
    detectionMethod: 'pattern' | 'deep';
}

export interface TechStackDetection {
    /** 文件夹路径 */
    folder: string;
    /** 文件名 */
    file: string;
    /** 文件大小（字节） */
    size: number;
    /** 技术栈类型 */
    techStack: string;
    /** 文件类型 */
    fileType?: string;
    /** 置信度 */
    confidence?: number;
    /** 元数据（包含所有提取的信息） */
    metadata: {
        /** 版本信息 */
        version?: string;
        /** 最后修改时间 */
        lastModified?: string;
        /** Dart 版本 */
        dartVersion?: string;
        /** Flutter 40位版本 */
        flutterHex40?: string;
        /** Dart 包列表 */
        dartPackages?: Array<string>;
        /** Kotlin 签名列表 */
        kotlinSignatures?: Array<string>;
        /** 其他自定义字段 */
        [key: string]: unknown;
    };
}

/**
 * 文件类型枚举
 */
export type FileType = string;

/**
 * 魔术字定义
 */
export interface MagicNumber {
    type: FileType;
    signature: Array<number>;
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
    nestedFiles?: Array<ResourceFileInfo>;
    /** 嵌套的压缩文件 */
    nestedArchives?: Array<ArchiveFileInfo>;
}

/**
 * JavaScript文件信息
 */
export interface JsFileInfo extends ResourceFileInfo {
    /** 是否为压缩代码 */
    isMinified: boolean;
    /** 代码行数（估算） */
    estimatedLines: number;
    /** 美化后的文件路径（如果已美化） */
    beautifiedPath?: string;
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
 * Flutter 分析结果
 */
export interface FlutterVersionInfo {
    hex40?: string;
    lastModified?: string;
    dartVersion?: string;
}

export interface FlutterPackageInfo {
    name: string;
    version?: string;
}

export interface FlutterAnalysisResult {
    isFlutter: boolean;
    dartPackages: Array<FlutterPackageInfo>;
    flutterVersion?: FlutterVersionInfo;
}

/**
 * 资源文件分析结果
 */
export interface ResourceAnalysisResult {
    /** 总文件数（包括嵌套文件） */
    totalFiles: number;
    /** 按类型分组的文件（包括嵌套文件） */
    filesByType: Map<FileType, Array<ResourceFileInfo>>;
    /** 压缩文件列表 */
    archiveFiles: Array<ArchiveFileInfo>;
    /** JavaScript文件列表（包括嵌套文件） */
    jsFiles: Array<JsFileInfo>;
    /** Hermes字节码文件列表（包括嵌套文件） */
    hermesFiles: Array<HermesFileInfo>;
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
        detectedFrameworks: Array<string>;
        /** SO文件详情 */
        techStackDetections: Array<TechStackDetection>;
        /** 总SO文件数 */
        totalSoFiles: number;
    };
    /** 资源文件分析结果 */
    resourceAnalysis: ResourceAnalysisResult;
    /** 分析时间戳 */
    timestamp: Date;
}



