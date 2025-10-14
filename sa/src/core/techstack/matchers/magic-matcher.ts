/**
 * 魔术字匹配器
 */

import type { MagicRule, FileInfo, RuleMatchResult } from '../types';

/**
 * 魔术字匹配器
 */
export class MagicMatcher {
    /**
     * 匹配魔术字规则
     */
    public async match(rule: MagicRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        if (!fileInfo.content) {
            return {
                matched: false,
                confidence: 0
            };
        }

        const offset = rule.offset ?? 0;
        const magicBytes = Buffer.from(rule.magicBytes);

        // 检查文件是否足够长
        if (fileInfo.content.length < offset + magicBytes.length) {
            return {
                matched: false,
                confidence: 0
            };
        }

        // 比较魔术字
        for (let i = 0; i < magicBytes.length; i++) {
            if (fileInfo.content[offset + i] !== magicBytes[i]) {
                return {
                    matched: false,
                    confidence: 0
                };
            }
        }

        return {
            matched: true,
            confidence: 1.0
        };
    }
}

