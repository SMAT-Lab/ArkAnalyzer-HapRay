/**
 * 组合匹配器
 */

import type { FileInfo, FileRule } from '../types';
import { BaseMatcher } from './base-matcher';
import { FilenameMatcher } from './filename-matcher';
import { PathMatcher } from './path-matcher';
import { MagicMatcher } from './magic-matcher';
import { ExtensionMatcher } from './extension-matcher';
import { ContentMatcher } from './content-matcher';

/**
 * 组合匹配器
 */
export class CombinedMatcher extends BaseMatcher {
    private matchers: Map<string, BaseMatcher>;

    constructor() {
        super();
        // 使用 Map 存储所有匹配器，通过类型动态查找
        this.matchers = new Map<string, BaseMatcher>();
        this.registerMatcher(new FilenameMatcher());
        this.registerMatcher(new PathMatcher());
        this.registerMatcher(new MagicMatcher());
        this.registerMatcher(new ExtensionMatcher());
        this.registerMatcher(new ContentMatcher());
        this.registerMatcher(this); // 支持嵌套的 combined 规则
    }

    /**
     * 获取匹配器类型
     */
    public getType = (): string => {
        return 'combined';
    };

    /**
     * 注册匹配器
     */
    private registerMatcher(matcher: BaseMatcher): void {
        this.matchers.set(matcher.getType(), matcher);
    }

    /**
     * 匹配组合规则
     */
    public match = async (rule: FileRule, fileInfo: FileInfo): Promise<boolean> => {
        if (rule.type !== 'combined') {
            return false;
        }
        const results: Array<boolean> = [];

        // 递归匹配所有子规则
        for (const subRule of rule.rules) {
            const result = await this.matchFileRule(subRule, fileInfo);
            results.push(result);
        }

        // 根据操作符计算最终结果
        switch (rule.operator) {
            case 'and':
                // AND: 所有规则都必须匹配
                return results.every(r => r);
            case 'or':
                // OR: 至少一个规则匹配
                return results.some(r => r);
            case 'not': {
                // NOT: 第一个规则匹配，但后续规则都不匹配
                if (results.length === 0) {
                    return false;
                }
                const firstMatched = results[0];
                const othersMatched = results.slice(1).some(r => r);
                return firstMatched && !othersMatched;
            }
        }
    };

    /**
     * 匹配单个文件规则
     * 使用动态查找，现在类型安全
     */
    private async matchFileRule(rule: FileRule, fileInfo: FileInfo): Promise<boolean> {
        const matcher = this.matchers.get(rule.type);
        if (!matcher) {
            console.warn(`Unknown matcher type: ${rule.type}`);
            return false;
        }

        // 现在类型安全，因为所有匹配器都接受 FileRule 类型
        return await matcher.match(rule, fileInfo);
    }
}

