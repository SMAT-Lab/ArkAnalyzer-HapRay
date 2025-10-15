/**
 * 内容匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher } from './base-matcher';

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
        if (rule.type !== 'content') {
            return false;
        }
        if (!fileInfo.content) {
            return false;
        }

        const contentStr = fileInfo.content.toString('utf-8');

        for (const pattern of rule.patterns) {
            try {
                // 尝试作为正则表达式
                const regex = new RegExp(pattern);
                if (regex.test(contentStr)) {
                    return true;
                }
            } catch {
                // 如果不是有效的正则表达式，作为普通字符串搜索
                if (contentStr.includes(pattern)) {
                    return true;
                }
            }
        }

        return false;
    };
}

