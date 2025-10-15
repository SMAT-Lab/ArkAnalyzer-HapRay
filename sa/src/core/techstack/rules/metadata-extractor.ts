/**
 * 元数据提取器
 */

import type { MetadataRule, MetadataPattern, FileInfo } from '../types';
import { CustomExtractorRegistry } from './custom-extractors';

/**
 * 元数据提取器
 */
export class MetadataExtractor {
    private customExtractorRegistry: CustomExtractorRegistry;

    constructor() {
        this.customExtractorRegistry = CustomExtractorRegistry.getInstance();
    }

    /**
     * 提取元数据
     */
    public async extractMetadata(
        rules: Array<MetadataRule> | undefined,
        fileInfo: FileInfo
    ): Promise<Record<string, unknown>> {
        if (!rules || rules.length === 0) {
            return {};
        }

        const metadata: Record<string, unknown> = {};

        for (const rule of rules) {
            const value = await this.extractField(rule, fileInfo);
            if (value !== null && value !== undefined) {
                metadata[rule.field] = value;
            }
        }

        return metadata;
    }

    /**
     * 提取单个字段
     */
    private async extractField(rule: MetadataRule, fileInfo: FileInfo): Promise<unknown> {
        // 如果指定了自定义提取器，使用自定义提取器
        if (rule.extractor) {
            return await this.extractFromCustomExtractor(rule.extractor, fileInfo);
        }

        // 否则使用正则模式提取
        if (!rule.patterns || rule.patterns.length === 0) {
            return null;
        }

        const values: Array<unknown> = [];

        for (const pattern of rule.patterns) {
            const value = await this.extractFromPattern(pattern, fileInfo);
            if (value !== null && value !== undefined) {
                if (Array.isArray(value)) {
                    // Type assertion: we know value is an array of unknown
                    values.push(...(value as Array<unknown>));
                } else {
                    values.push(value);
                }
            }
        }

        // 如果只有一个值，返回单个值；否则返回数组
        if (values.length === 0) {
            return null;
        } else if (values.length === 1) {
            return values[0];
        } else {
            return values;
        }
    }

    /**
     * 使用自定义提取器提取数据
     */
    private async extractFromCustomExtractor(extractorName: string, fileInfo: FileInfo): Promise<unknown> {
        const extractor = this.customExtractorRegistry.get(extractorName);
        if (!extractor) {
            console.warn(`Custom extractor not found: ${extractorName}`);
            return null;
        }

        try {
            const result = await extractor(fileInfo);
            return result;
        } catch (error) {
            console.error(`Error in custom extractor ${extractorName}:`, error);
            return null;
        }
    }

    /**
     * 从模式中提取值
     */
    private async extractFromPattern(pattern: MetadataPattern, fileInfo: FileInfo): Promise<unknown> {
        // 如果有自定义提取器，使用自定义提取器
        if (pattern.custom) {
            const extractor = this.customExtractorRegistry.get(pattern.custom);
            if (extractor) {
                return await extractor(fileInfo, pattern);
            }
        }

        // 获取源数据
        const source = this.getSource(pattern.source, fileInfo);
        if (!source) {
            return null;
        }

        // 使用正则表达式提取
        try {
            const regex = new RegExp(pattern.pattern, 'g');
            const matches: Array<string> = [];

            let match;
            while ((match = regex.exec(source)) !== null) {
                const captureGroup = pattern.captureGroup ?? 0;
                const value = match[captureGroup];
                if (value) {
                    const transformed = this.transform(value, pattern.transform);
                    matches.push(transformed);
                }
            }

            return matches.length > 0 ? matches : null;
        } catch (error) {
            console.warn(`Failed to extract metadata with pattern: ${pattern.pattern}`, error);
            return null;
        }
    }

    /**
     * 获取源数据
     */
    private getSource(source: 'content' | 'path' | 'filename', fileInfo: FileInfo): string | null {
        switch (source) {
            case 'content':
                return fileInfo.content ? fileInfo.content.toString('utf-8') : null;
            case 'path':
                return fileInfo.path;
            case 'filename':
                return fileInfo.file;
            default:
                return null;
        }
    }

    /**
     * 转换值
     */
    private transform(value: string, transform?: 'trim' | 'lowercase' | 'uppercase'): string {
        if (!transform) {
            return value;
        }

        switch (transform) {
            case 'trim':
                return value.trim();
            case 'lowercase':
                return value.toLowerCase();
            case 'uppercase':
                return value.toUpperCase();
            default:
                return value;
        }
    }
}

