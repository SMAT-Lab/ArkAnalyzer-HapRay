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
        if (frameworks.includes('Unknown') && this.deepDetectionConfig.enableKmp) {
            const isKmp = await this.detectKmpFramework(fileName, zipEntry, zip);
            if (isKmp) {
                frameworks = frameworks.filter(f => f !== 'Unknown');
                frameworks.push('KMP');
                detectionMethod = 'deep';
                logger.info(`[Framework Detection] Detected KMP framework in: ${fileName}`);
            }
        }
        
        return {
            frameworks,
            detectionMethod
        };
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
     * @returns 是否为KMP框架
     */
    private async detectKmpFramework(
        fileName: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance
    ): Promise<boolean> {
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
            return false;
        }
    }
    
    /**
     * 在小文件中检测Kotlin特征
     */
    private async detectInSmallFile(
        zipEntry: ZipEntry,
        patterns: Array<Buffer>,
        fileName: string
    ): Promise<boolean> {
        try {
            const buffer = await zipEntry.async('nodebuffer');
            
            for (const pattern of patterns) {
                if (buffer.indexOf(pattern) !== -1) {
                    return true;
                }
            }
            return false;
        } catch (error) {
            console.warn(`KMP detection failed for ${fileName}:`, error);
            return false;
        }
    }
    
    /**
     * 在大文件中检测Kotlin特征（分块搜索）
     */
    private async detectInLargeFile(
        zipEntry: ZipEntry,
        patterns: Array<Buffer>,
        fileName: string
    ): Promise<boolean> {
        try {
            const buffer = await zipEntry.async('nodebuffer');
            const chunkSize = 1 * 1024 * 1024; // 1MB
            const maxChunks = this.deepDetectionConfig.maxChunksForLargeFile;
            const totalChunks = Math.min(Math.ceil(buffer.length / chunkSize), maxChunks);
            
            // 分块搜索
            for (let i = 0; i < totalChunks; i++) {
                const start = i * chunkSize;
                const end = Math.min(start + chunkSize, buffer.length);
                const chunk = buffer.subarray(start, end);
                
                // 在当前块中搜索
                for (const pattern of patterns) {
                    if (chunk.indexOf(pattern) !== -1) {
                        return true; // 早期退出
                    }
                }
                
                // 检查跨块边界
                if (i < totalChunks - 1) {
                    const foundAtBoundary = this.checkChunkBoundary(
                        buffer,
                        start,
                        end,
                        patterns
                    );
                    if (foundAtBoundary) {
                        return true;
                    }
                }
            }
            
            return false;
        } catch (error) {
            console.warn(`KMP detection failed for ${fileName}:`, error);
            return false;
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
    ): boolean {
        const maxPatternLength = Math.max(...patterns.map(p => p.length));
        const overlap = buffer.subarray(Math.max(start, end - maxPatternLength), end);
        const nextChunkStart = buffer.subarray(end, Math.min(end + maxPatternLength, buffer.length));
        const boundary = Buffer.concat([overlap, nextChunkStart]);
        
        for (const pattern of patterns) {
            if (boundary.indexOf(pattern) !== -1) {
                return true;
            }
        }
        
        return false;
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

