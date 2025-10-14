/**
 * 文件名匹配器
 */

import type { FilenameRule, FileInfo, RuleMatchResult } from '../types';

/**
 * 文件名匹配器
 */
export class FilenameMatcher {
    /**
     * 匹配文件名规则
     */
    public async match(rule: FilenameRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        const filename = fileInfo.file;

        for (const pattern of rule.patterns) {
            try {
                const regex = new RegExp(pattern);
                if (regex.test(filename)) {
                    return {
                        matched: true,
                        confidence: 1.0
                    };
                }
            } catch (error) {
                console.warn(`Invalid regex pattern: ${pattern}`, error);
            }
        }

        return {
            matched: false,
            confidence: 0
        };
    }
}

