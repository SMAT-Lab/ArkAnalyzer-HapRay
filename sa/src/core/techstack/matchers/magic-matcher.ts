/**
 * 魔术字匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher, type MatchResult } from './base-matcher';

/**
 * 魔术字匹配器
 */
export class MagicMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'magic';
    };

    /**
     * 匹配魔术字规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        const result = await this.matchWithConfidence(rule, fileInfo);
        return result.matched;
    };

    /**
     * 匹配魔术字规则（带置信度）
     */
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> => {
        if (rule.type !== 'magic') {
            return { matched: false };
        }
        if (!fileInfo.content) {
            return { matched: false };
        }

        const offset = rule.offset ?? 0;
        const magicBytes = Buffer.from(rule.magicBytes);

        // 检查文件是否足够长
        if (fileInfo.content.length < offset + magicBytes.length) {
            return { matched: false };
        }

        // 比较魔术字
        for (let i = 0; i < magicBytes.length; i++) {
            if (fileInfo.content[offset + i] !== magicBytes[i]) {
                return { matched: false };
            }
        }

        // 使用配置文件中的置信度，如果没有设置则使用默认值1.0
        return { matched: true, confidence: rule.confidence ?? 1.0 };
    };
}

