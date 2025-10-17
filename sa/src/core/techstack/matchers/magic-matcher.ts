/**
 * 魔术字匹配器
 */

import type { FileRule, FileInfo } from '../types';
import { BaseMatcher } from './base-matcher';

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
        if (rule.type !== 'magic') {
            return false;
        }
        if (!fileInfo.content) {
            return false;
        }

        const offset = rule.offset ?? 0;
        const magicBytes = Buffer.from(rule.magicBytes);

        // 检查文件是否足够长
        if (fileInfo.content.length < offset + magicBytes.length) {
            return false;
        }

        // 比较魔术字
        for (let i = 0; i < magicBytes.length; i++) {
            if (fileInfo.content[offset + i] !== magicBytes[i]) {
                return false;
            }
        }

        return true;
    };
}

