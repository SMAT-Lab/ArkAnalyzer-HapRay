/**
 * 内容匹配器
 */

import type { ContentRule, FileInfo, RuleMatchResult } from '../types';

/**
 * 内容匹配器
 */
export class ContentMatcher {
    /**
     * 匹配内容规则
     */
    public async match(rule: ContentRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        if (!fileInfo.content) {
            return {
                matched: false,
                confidence: 0
            };
        }

        const contentStr = fileInfo.content.toString('utf-8');

        for (const pattern of rule.patterns) {
            try {
                // 尝试作为正则表达式
                const regex = new RegExp(pattern);
                if (regex.test(contentStr)) {
                    return {
                        matched: true,
                        confidence: 1.0
                    };
                }
            } catch {
                // 如果不是有效的正则表达式，作为普通字符串搜索
                if (contentStr.includes(pattern)) {
                    return {
                        matched: true,
                        confidence: 1.0
                    };
                }
            }
        }

        return {
            matched: false,
            confidence: 0
        };
    }
}

