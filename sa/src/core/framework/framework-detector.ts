/**
 * 框架检测器 - 统一的框架识别和深度检测逻辑
 *
 * 职责：
 * 1. 基于文件名的快速模式匹配
 * 2. 基于文件内容的深度检测（KMP等）
 * 3. 提供清晰的检测策略和扩展点
 */

import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getFrameworkPatterns, matchSoPattern } from '../../config/framework-patterns';
import type { ZipEntry, ZipInstance } from '../../types/zip-types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * 框架检测结果
 */
export interface FrameworkDetectionResult {
    /** 检测到的框架列表 */
    frameworks: Array<string>;
    /** 检测方法：'pattern' | 'deep' */
    detectionMethod: 'pattern' | 'deep';
    /** KMP 匹配到的特征符号（仅当检测到 KMP 时） */
    kmpMatchedSignatures?: Array<string>;
}

/**
 * 深度检测配置
 */
export interface DeepDetectionConfig {
    /** 是否启用KMP检测 */
    enableKmp?: boolean;
    /** 小文件阈值（MB） */
    smallFileThreshold?: number;
    /** 大文件最大扫描块数 */
    maxChunksForLargeFile?: number;
}

/**
 * 框架检测器类
 */
export class FrameworkDetector {
    private static instance: FrameworkDetector | undefined;
    
    private readonly deepDetectionConfig: Required<DeepDetectionConfig>;
    
    private constructor(config: DeepDetectionConfig = {}) {
        this.deepDetectionConfig = {
            enableKmp: config.enableKmp ?? true,
            smallFileThreshold: config.smallFileThreshold ?? 10, // 10MB
            maxChunksForLargeFile: config.maxChunksForLargeFile ?? 50
        };
    }
    
    /**
     * 获取单例实例
     */
    public static getInstance(config?: DeepDetectionConfig): FrameworkDetector {
        FrameworkDetector.instance ??= new FrameworkDetector(config);
        return FrameworkDetector.instance;
    }

    /**
     * 识别框架（快速模式匹配）
     *
     * @param fileName SO文件名
     * @returns 框架列表，未识别时返回 ['Unknown']
     */
    public identifyFrameworksByPattern(fileName: string): Array<string> {
        try {
            const frameworkPatterns = getFrameworkPatterns();
            const detected: Array<string> = [];

            for (const [frameworkType, patterns] of Object.entries(frameworkPatterns)) {
                for (const pattern of patterns) {
                    if (matchSoPattern(fileName, pattern)) {
                        if (!detected.includes(frameworkType)) {
                            detected.push(frameworkType);
                        }
                        break;
                    }
                }
            }

            return detected.length > 0 ? detected : ['Unknown'];
        } catch {
            return ['Unknown'];
        }
    }
    
    /**
     * 完整的框架检测（模式匹配 + 深度检测）
     * 
     * @param fileName SO文件名
     * @param zipEntry ZIP条目
     * @param zip ZIP实例
     * @returns 框架检测结果
     */
    public async detectFrameworks(
        fileName: string,
        zipEntry: ZipEntry,
        zip: ZipInstance
    ): Promise<FrameworkDetectionResult> {
        // 第一步：模式匹配
        let frameworks = this.identifyFrameworksByPattern(fileName);
        let detectionMethod: 'pattern' | 'deep' = 'pattern';

        // 第二步：如果是Unknown，尝试深度检测
        let kmpMatchedSignatures: Array<string> | undefined;
        if (frameworks.includes('Unknown')) {
            // 尝试 Flutter 深度检测
            const flutterResult = await this.detectFlutterFramework(fileName, zipEntry, zip);
            if (flutterResult.isFlutter) {
                frameworks = frameworks.filter(f => f !== 'Unknown');
                frameworks.push('Flutter');
                detectionMethod = 'deep';
                logger.info(`[Framework Detection] Detected Flutter framework in: ${fileName}, found ${flutterResult.dartPackageCount} Dart packages`);
            }

            // 尝试 KMP 深度检测
            if (frameworks.includes('Unknown') && this.deepDetectionConfig.enableKmp) {
                const kmpResult = await this.detectKmpFramework(fileName, zipEntry, zip);
                if (kmpResult.isKmp) {
                    frameworks = frameworks.filter(f => f !== 'Unknown');
                    frameworks.push('KMP');
                    detectionMethod = 'deep';
                    kmpMatchedSignatures = kmpResult.matchedSignatures;
                    logger.info(`[Framework Detection] Detected KMP framework in: ${fileName}, matched: ${kmpResult.matchedSignatures.join(', ')}`);
                }
            }
        }

        return {
            frameworks,
            detectionMethod,
            kmpMatchedSignatures
        };
    }

    /**
     * Flutter框架深度检测
     *
     * 策略：
     * - 检测 Dart 包特征：package:xxx
     * - 如果找到 Dart 包，则认为是 Flutter 应用
     *
     * @param fileName 文件名
     * @param zipEntry ZIP条目
     * @param zip ZIP实例
     * @returns Flutter检测结果（是否为Flutter + Dart包数量）
     */
    private async detectFlutterFramework(
        fileName: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance
    ): Promise<{ isFlutter: boolean; dartPackageCount: number }> {
        try {
            // Dart包特征模式：package:
            const dartPackagePattern = Buffer.from('package:', 'utf8');

            const fileSize = zipEntry.uncompressedSize ?? zipEntry.compressedSize;
            const smallFileThreshold = this.deepDetectionConfig.smallFileThreshold * 1024 * 1024;

            // 读取文件内容
            const buffer = await zipEntry.async('nodebuffer');

            // 搜索 Dart 包特征
            let dartPackageCount = 0;
            let searchStart = 0;

            // 限制搜索次数，避免在大文件中搜索过久
            const maxSearchCount = fileSize < smallFileThreshold ? 1000 : 100;

            while (searchStart < buffer.length && dartPackageCount < maxSearchCount) {
                const index = buffer.indexOf(dartPackagePattern, searchStart);
                if (index === -1) {
                    break;
                }

                dartPackageCount++;
                searchStart = index + dartPackagePattern.length;
            }

            // 如果找到至少 1 个 Dart 包特征，则认为是 Flutter
            const isFlutter = dartPackageCount > 0;

            return {
                isFlutter,
                dartPackageCount
            };
        } catch (error) {
            console.warn(`Flutter framework detection failed for ${fileName}:`, error);
            return { isFlutter: false, dartPackageCount: 0 };
        }
    }

    /**
     * KMP框架深度检测
     *
     * 策略：
     * - 小文件（<10MB）：直接读取全部内容搜索
     * - 大文件（>=10MB）：分块搜索，找到特征后立即返回
     * - 跨块边界检查：避免特征被分割
     *
     * @param fileName 文件名
     * @param zipEntry ZIP条目
     * @param zip ZIP实例
     * @returns KMP检测结果（是否为KMP + 匹配的特征）
     */
    private async detectKmpFramework(
        fileName: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance
    ): Promise<{ isKmp: boolean; matchedSignatures: Array<string> }> {
        try {
            // Kotlin特征模式
            const kotlinPatterns = [
                Buffer.from('Kotlin', 'utf8'),
                Buffer.from('kotlin', 'utf8'),
                Buffer.from('kfun:', 'utf8'),
                Buffer.from('KOTLIN_NATIVE', 'utf8')
            ];
            
            const fileSize = zipEntry.uncompressedSize ?? zipEntry.compressedSize;
            const smallFileThreshold = this.deepDetectionConfig.smallFileThreshold * 1024 * 1024;
            
            // 小文件策略：直接读取全部
            if (fileSize < smallFileThreshold) {
                return await this.detectInSmallFile(zipEntry, kotlinPatterns, fileName);
            }

            // 大文件策略：分块搜索
            return await this.detectInLargeFile(zipEntry, kotlinPatterns, fileName);

        } catch (error) {
            console.warn(`KMP framework detection failed for ${fileName}:`, error);
            return { isKmp: false, matchedSignatures: [] };
        }
    }

    /**
     * 在小文件中检测Kotlin特征
     */
    private async detectInSmallFile(
        zipEntry: ZipEntry,
        patterns: Array<Buffer>,
        fileName: string
    ): Promise<{ isKmp: boolean; matchedSignatures: Array<string> }> {
        try {
            const buffer = await zipEntry.async('nodebuffer');
            const matchedSignatures: Array<string> = [];

            for (const pattern of patterns) {
                if (buffer.indexOf(pattern) !== -1) {
                    matchedSignatures.push(pattern.toString('utf8'));
                }
            }

            return {
                isKmp: matchedSignatures.length > 0,
                matchedSignatures
            };
        } catch (error) {
            console.warn(`KMP detection failed for ${fileName}:`, error);
            return { isKmp: false, matchedSignatures: [] };
        }
    }
    
    /**
     * 在大文件中检测Kotlin特征（分块搜索）
     */
    private async detectInLargeFile(
        zipEntry: ZipEntry,
        patterns: Array<Buffer>,
        fileName: string
    ): Promise<{ isKmp: boolean; matchedSignatures: Array<string> }> {
        try {
            const buffer = await zipEntry.async('nodebuffer');
            const chunkSize = 1 * 1024 * 1024; // 1MB
            const maxChunks = this.deepDetectionConfig.maxChunksForLargeFile;
            const totalChunks = Math.min(Math.ceil(buffer.length / chunkSize), maxChunks);
            const matchedSignatures: Array<string> = [];

            // 分块搜索
            for (let i = 0; i < totalChunks; i++) {
                const start = i * chunkSize;
                const end = Math.min(start + chunkSize, buffer.length);
                const chunk = buffer.subarray(start, end);

                // 在当前块中搜索
                for (const pattern of patterns) {
                    if (chunk.indexOf(pattern) !== -1) {
                        const signature = pattern.toString('utf8');
                        if (!matchedSignatures.includes(signature)) {
                            matchedSignatures.push(signature);
                        }
                    }
                }

                // 检查跨块边界
                if (i < totalChunks - 1) {
                    const boundaryMatches = this.checkChunkBoundary(
                        buffer,
                        start,
                        end,
                        patterns
                    );
                    for (const match of boundaryMatches) {
                        if (!matchedSignatures.includes(match)) {
                            matchedSignatures.push(match);
                        }
                    }
                }
            }

            return {
                isKmp: matchedSignatures.length > 0,
                matchedSignatures
            };
        } catch (error) {
            console.warn(`KMP detection failed for ${fileName}:`, error);
            return { isKmp: false, matchedSignatures: [] };
        }
    }
    
    /**
     * 检查块边界处的特征
     */
    private checkChunkBoundary(
        buffer: Buffer,
        start: number,
        end: number,
        patterns: Array<Buffer>
    ): Array<string> {
        const maxPatternLength = Math.max(...patterns.map(p => p.length));
        const overlap = buffer.subarray(Math.max(start, end - maxPatternLength), end);
        const nextChunkStart = buffer.subarray(end, Math.min(end + maxPatternLength, buffer.length));
        const boundary = Buffer.concat([overlap, nextChunkStart]);
        const matches: Array<string> = [];

        for (const pattern of patterns) {
            if (boundary.indexOf(pattern) !== -1) {
                matches.push(pattern.toString('utf8'));
            }
        }

        return matches;
    }
}

/**
 * 便捷函数：识别框架（仅模式匹配）
 */
export function identifyFrameworks(fileName: string): Array<string> {
    return FrameworkDetector.getInstance().identifyFrameworksByPattern(fileName);
}

/**
 * 便捷函数：完整框架检测（模式 + 深度）
 */
export async function detectFrameworks(
    fileName: string,
    zipEntry: ZipEntry,
    zip: ZipInstance
): Promise<FrameworkDetectionResult> {
    return FrameworkDetector.getInstance().detectFrameworks(fileName, zipEntry, zip);
}

