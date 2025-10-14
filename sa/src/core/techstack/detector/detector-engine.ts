/**
 * 技术栈检测引擎
 */

import type { TechStackConfig, FileInfo, FileDetectionResult, ExcludeRule } from '../types';
import { TechStackConfigLoader } from '../../../config/techstack_config_loader';
import { ParallelExecutor } from './parallel-executor';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * 检测引擎（单例）
 */
export class DetectorEngine {
    private static instance: DetectorEngine | null = null;
    private config: TechStackConfig | null = null;
    private parallelExecutor: ParallelExecutor;

    private constructor() {
        this.parallelExecutor = new ParallelExecutor();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(): DetectorEngine {
        if (!DetectorEngine.instance) {
            DetectorEngine.instance = new DetectorEngine();
        }
        return DetectorEngine.instance;
    }

    /**
     * 初始化（加载配置）
     */
    public initialize(configPath?: string): void {
        const configLoader = TechStackConfigLoader.getInstance();
        if (configPath) {
            configLoader.setConfigPath(configPath);
        }
        this.config = configLoader.loadConfig();
    }

    /**
     * 检测文件
     */
    public async detectFile(fileInfo: FileInfo): Promise<FileDetectionResult> {
        if (!this.config) {
            throw new Error('DetectorEngine not initialized. Call initialize() first.');
        }

        // 1. 检查排除规则
        if (this.shouldExclude(fileInfo)) {
            return {
                folder: fileInfo.folder,
                file: fileInfo.file,
                size: fileInfo.size,
                detections: []
            };
        }

        // 2. 并行执行所有检测规则
        const detections = await this.parallelExecutor.executeRules(this.config.detections, fileInfo);

        // 3. 按置信度排序
        detections.sort((a, b) => b.confidence - a.confidence);

        return {
            folder: fileInfo.folder,
            file: fileInfo.file,
            size: fileInfo.size,
            detections
        };
    }

    /**
     * 批量检测文件
     */
    public async detectFiles(fileInfos: Array<FileInfo>): Promise<Array<FileDetectionResult>> {
        const promises = fileInfos.map(fileInfo => this.detectFile(fileInfo));
        return await Promise.all(promises);
    }

    /**
     * 检查是否应该排除文件
     */
    private shouldExclude(fileInfo: FileInfo): boolean {
        if (!this.config || !this.config.excludes) {
            return false;
        }

        for (const exclude of this.config.excludes) {
            if (this.matchExcludeRule(exclude, fileInfo)) {
                logger.debug(`File excluded by rule: ${exclude.type} - ${exclude.pattern}`);
                return true;
            }
        }

        return false;
    }

    /**
     * 匹配排除规则
     */
    private matchExcludeRule(rule: ExcludeRule, fileInfo: FileInfo): boolean {
        try {
            const regex = new RegExp(rule.pattern);

            switch (rule.type) {
                case 'path':
                    return regex.test(fileInfo.path);
                case 'filename':
                    return regex.test(fileInfo.file);
                default:
                    return false;
            }
        } catch (error) {
            console.warn(`Invalid exclude rule pattern: ${rule.pattern}`, error);
            return false;
        }
    }
}

/**
 * 获取检测引擎实例（便捷方法）
 */
export function getDetectorEngine(): DetectorEngine {
    return DetectorEngine.getInstance();
}

