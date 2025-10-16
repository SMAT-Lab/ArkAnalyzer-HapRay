/**
 * 内容匹配器
 */

import type { FileRule, FileInfo, ContentPattern } from '../types';
import { BaseMatcher } from './base-matcher';

/**
 * 内容匹配结果
 */
export interface ContentMatchResult {
    matched: boolean;
    confidence?: number; // 匹配的置信度
    matchedPatterns?: Array<string>; // 匹配到的模式
}

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
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<ContentMatchResult> => {
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
            let confidence = 0.5; // 默认置信度

            // 判断是字符串还是 ContentPattern 对象
            if (typeof patternItem === 'string') {
                pattern = patternItem;
            } else {
                pattern = (patternItem as ContentPattern).pattern;
                confidence = (patternItem as ContentPattern).confidence ?? 0.5;
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
            confidence: maxConfidence,
            matchedPatterns
        };
    };
}

