/**
 * 扩展名匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher } from './base-matcher';

/**
 * 扩展名匹配器
 */
export class ExtensionMatcher extends BaseMatcher {
    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'extension';
    };

    /**
     * 匹配扩展名规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        if (rule.type !== 'extension') {
            return false;
        }
        const filename = fileInfo.file;
        const ext = filename.toLowerCase().split('.').pop();

        if (!ext) {
            return false;
        }

        for (const extension of rule.extensions) {
            if (ext === extension.toLowerCase()) {
                return true;
            }
        }

        return false;
    };
}

