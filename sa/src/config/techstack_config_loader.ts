/**
 * 技术栈检测配置加载器
 */

import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import type { TechStackConfig } from '../core/techstack/types';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * 配置加载器（单例）
 */
export class TechStackConfigLoader {
    private static instance: TechStackConfigLoader | null = null;
    private config: TechStackConfig | null = null;
    private configPath: string;

    private constructor() {
        // 使用与 loadFrameworkConfig 相同的路径查找策略
        // 先尝试当前目录，再尝试上级目录
        let resDir = path.join(__dirname, 'res');
        if (!fs.existsSync(resDir)) {
            resDir = path.join(__dirname, '../../res');
        }

        this.configPath = path.join(resDir, 'techstack-config.yaml');

        // 如果还是找不到，尝试从当前工作目录查找
        if (!fs.existsSync(this.configPath)) {
            const cwdPath = path.join(process.cwd(), 'res/techstack-config.yaml');
            if (fs.existsSync(cwdPath)) {
                this.configPath = cwdPath;
            }
        }
    }

    /**
     * 获取单例实例
     */
    public static getInstance(): TechStackConfigLoader {
        if (!TechStackConfigLoader.instance) {
            TechStackConfigLoader.instance = new TechStackConfigLoader();
        }
        return TechStackConfigLoader.instance;
    }

    /**
     * 设置配置文件路径
     */
    public setConfigPath(configPath: string): void {
        this.configPath = configPath;
        this.config = null; // 重置缓存
    }

    /**
     * 加载配置
     */
    public loadConfig(): TechStackConfig {
        if (this.config) {
            return this.config;
        }

        try {
            if (!fs.existsSync(this.configPath)) {
                throw new Error(`Config file not found: ${this.configPath}`);
            }

            const content = fs.readFileSync(this.configPath, 'utf-8');
            this.config = yaml.load(content) as TechStackConfig;

            // 验证配置
            this.validateConfig(this.config);

            logger.info(`✅ 技术栈配置加载成功：${this.config.detections.length} 个检测规则`);

            return this.config;
        } catch (error) {
            logger.error(`❌ 加载技术栈配置失败：${error}`);
            throw new Error(`Failed to load techstack config from ${this.configPath}: ${error}`);
        }
    }

    /**
     * 获取配置（如果未加载则自动加载）
     */
    public getConfig(): TechStackConfig {
        return this.loadConfig();
    }

    /**
     * 验证配置格式
     */
    private validateConfig(config: TechStackConfig): void {
        if (!config || typeof config !== 'object') {
            throw new Error('配置文件格式错误：根对象无效');
        }

        if (!config.version || typeof config.version !== 'string') {
            throw new Error('配置文件格式错误：缺少 version 字段');
        }

        if (!config.detections || !Array.isArray(config.detections)) {
            throw new Error('配置文件格式错误：缺少 detections 字段或格式错误');
        }

        // 验证每个检测规则
        for (const detection of config.detections) {
            this.validateDetectionRule(detection);
        }
    }

    /**
     * 验证检测规则
     */
    private validateDetectionRule(detection: any): void {
        if (!detection.id || typeof detection.id !== 'string') {
            throw new Error('检测规则缺少 id 字段');
        }

        if (!detection.name || typeof detection.name !== 'string') {
            throw new Error(`检测规则 ${detection.id} 缺少 name 字段`);
        }

        if (!detection.type || typeof detection.type !== 'string') {
            throw new Error(`检测规则 ${detection.id} 缺少 type 字段`);
        }

        if (typeof detection.confidence !== 'number' || detection.confidence < 0 || detection.confidence > 1) {
            throw new Error(`检测规则 ${detection.id} 的 confidence 字段无效（应为 0-1 之间的数字）`);
        }

        if (!detection.fileRules || !Array.isArray(detection.fileRules)) {
            throw new Error(`检测规则 ${detection.id} 缺少 fileRules 字段或格式错误`);
        }

        if (detection.fileRules.length === 0) {
            throw new Error(`检测规则 ${detection.id} 的 fileRules 不能为空`);
        }
    }

    /**
     * 重置配置（用于测试）
     */
    public reset(): void {
        this.config = null;
    }
}

/**
 * 获取配置加载器实例（便捷方法）
 */
export function getTechStackConfigLoader(): TechStackConfigLoader {
    return TechStackConfigLoader.getInstance();
}

/**
 * 加载技术栈配置（便捷方法）
 */
export function loadTechStackConfig(): TechStackConfig {
    return TechStackConfigLoader.getInstance().loadConfig();
}

