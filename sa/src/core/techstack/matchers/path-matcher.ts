/**
 * 路径匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher } from './base-matcher';

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
        if (rule.type !== 'path') {
            return false;
        }
        const filePath = fileInfo.path;

        for (const pattern of rule.patterns) {
            try {
                const regex = new RegExp(pattern);
                if (regex.test(filePath)) {
                    return true;
                }
            } catch (error) {
                console.warn(`Invalid regex pattern: ${pattern}`, error);
            }
        }

        return false;
    };
}

