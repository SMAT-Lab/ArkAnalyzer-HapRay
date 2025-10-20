/**
 * 内容匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher, type MatchResult } from './base-matcher';

/**
 * 内容匹配器
 */
export class ContentMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'content';
    };

    /**
     * 匹配内容规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        const result = await this.matchWithConfidence(rule, fileInfo);
        return result.matched;
    };

    /**
     * 匹配内容规则（带置信度）
     */
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> => {
        if (rule.type !== 'content') {
            return { matched: false };
        }
        if (!fileInfo.content) {
            return { matched: false };
        }

        const contentStr = fileInfo.content.toString('utf-8');
        const matchedPatterns: Array<string> = [];
        const confidences: Array<number> = [];

        for (const patternItem of rule.patterns) {
            let pattern: string;
            let confidence = rule.confidence ?? 1.0; // 使用配置文件中的置信度，如果没有设置则使用默认值1.0

            // 判断是字符串还是 ContentPattern 对象
            if (typeof patternItem === 'string') {
                pattern = patternItem;
            } else {
                pattern = (patternItem).pattern;
                // 如果 ContentPattern 中有置信度，则使用它；否则使用规则级别的置信度
                confidence = (patternItem).confidence ?? rule.confidence ?? 1.0;
            }

            try {
                // 尝试作为正则表达式
                const regex = new RegExp(pattern);
                if (regex.test(contentStr)) {
                    matchedPatterns.push(pattern);
                    confidences.push(confidence);
                }
            } catch {
                // 如果不是有效的正则表达式，作为普通字符串搜索
                if (contentStr.includes(pattern)) {
                    matchedPatterns.push(pattern);
                    confidences.push(confidence);
                }
            }
        }

        if (matchedPatterns.length === 0) {
            return { matched: false };
        }

        // 计算加权平均置信度（取最高置信度）
        const maxConfidence = Math.max(...confidences);

        return {
            matched: true,
            confidence: maxConfidence
        };
    };
}

