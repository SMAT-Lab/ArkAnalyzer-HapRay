/**
 * 文件名匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher } from './base-matcher';

/**
 * 文件名匹配器
 */
export class FilenameMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'filename';
    };

    /**
     * 匹配文件名规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        if (rule.type !== 'filename') {
            return false;
        }
        const filename = fileInfo.file;

        for (const pattern of rule.patterns) {
            try {
                const regex = new RegExp(pattern);
                if (regex.test(filename)) {
                    return true;
                }
            } catch (error) {
                console.warn(`Invalid regex pattern: ${pattern}`, error);
            }
        }

        return false;
    };
}

