/**
 * 扩展名匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher, type MatchResult } from './base-matcher';

/**
 * 扩展名匹配器
 */
export class ExtensionMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'extension';
    };

    /**
     * 匹配扩展名规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        const result = await this.matchWithConfidence(rule, fileInfo);
        return result.matched;
    };

    /**
     * 匹配扩展名规则（带置信度）
     */
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> => {
        if (rule.type !== 'extension') {
            return { matched: false };
        }
        const filename = fileInfo.file;
        const ext = filename.toLowerCase().split('.').pop();

        if (!ext) {
            return { matched: false };
        }

        for (const extension of rule.extensions) {
            if (ext === extension.toLowerCase()) {
                // 使用配置文件中的置信度，如果没有设置则使用默认值1.0
                return { matched: true, confidence: rule.confidence ?? 1.0 };
            }
        }

        return { matched: false };
    };
}

