/**
 * 扩展名匹配器
 */

import type { ExtensionRule, FileInfo, RuleMatchResult } from '../types';

/**
 * 扩展名匹配器
 */
export class ExtensionMatcher {
    /**
     * 匹配扩展名规则
     */
    public async match(rule: ExtensionRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        const filename = fileInfo.file;
        const ext = filename.toLowerCase().split('.').pop();

        if (!ext) {
            return {
                matched: false,
                confidence: 0
            };
        }

        for (const extension of rule.extensions) {
            if (ext === extension.toLowerCase()) {
                return {
                    matched: true,
                    confidence: 1.0
                };
            }
        }

        return {
            matched: false,
            confidence: 0
        };
    }
}

