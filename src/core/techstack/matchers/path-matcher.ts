/**
 * 路径匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher, type MatchResult } from './base-matcher';

/**
 * 路径匹配器
 */
export class PathMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'path';
    };

    /**
     * 匹配路径规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        const result = await this.matchWithConfidence(rule, fileInfo);
        return result.matched;
    };

    /**
     * 匹配路径规则（带置信度）
     */
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> => {
        if (rule.type !== 'path') {
            return { matched: false };
        }
        const filePath = fileInfo.path;

        for (const pattern of rule.patterns) {
            try {
                const regex = new RegExp(pattern);
                if (regex.test(filePath)) {
                    // 使用配置文件中的置信度，如果没有设置则使用默认值1.0
                    return { matched: true, confidence: rule.confidence ?? 1.0 };
                }
            } catch (error) {
                console.warn(`Invalid regex pattern: ${pattern}`, error);
            }
        }

        return { matched: false };
    };
}

