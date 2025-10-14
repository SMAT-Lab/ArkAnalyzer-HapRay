/**
 * 路径匹配器
 */

import type { PathRule, FileInfo, RuleMatchResult } from '../types';

/**
 * 路径匹配器
 */
export class PathMatcher {
    /**
     * 匹配路径规则
     */
    public async match(rule: PathRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        const filePath = fileInfo.path;

        for (const pattern of rule.patterns) {
            try {
                const regex = new RegExp(pattern);
                if (regex.test(filePath)) {
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

