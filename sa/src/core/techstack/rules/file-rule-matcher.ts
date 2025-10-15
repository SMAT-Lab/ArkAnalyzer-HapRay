/**
 * 文件规则匹配器
 */

import type { FileRule, FileInfo } from '../types';
import type { BaseMatcher } from '../matchers/base-matcher';
import { FilenameMatcher } from '../matchers/filename-matcher';
import { PathMatcher } from '../matchers/path-matcher';
import { MagicMatcher } from '../matchers/magic-matcher';
import { ExtensionMatcher } from '../matchers/extension-matcher';
import { ContentMatcher } from '../matchers/content-matcher';
import { CombinedMatcher } from '../matchers/combined-matcher';

/**
 * 文件规则匹配器
 * 使用 Map 动态管理所有匹配器，消除 switch-case
 */
export class FileRuleMatcher {
    private matchers: Map<string, BaseMatcher>;

    constructor() {
        // 使用 Map 存储所有匹配器，通过类型动态查找
        this.matchers = new Map<string, BaseMatcher>();
        this.registerMatcher(new FilenameMatcher());
        this.registerMatcher(new PathMatcher());
        this.registerMatcher(new MagicMatcher());
        this.registerMatcher(new ExtensionMatcher());
        this.registerMatcher(new ContentMatcher());
        this.registerMatcher(new CombinedMatcher());
    }

    /**
     * 注册匹配器
     */
    private registerMatcher(matcher: BaseMatcher): void {
        this.matchers.set(matcher.getType(), matcher);
    }

    /**
     * 匹配文件规则列表（OR 关系）
     */
    public async matchRules(rules: Array<FileRule>, fileInfo: FileInfo): Promise<boolean> {
        for (const rule of rules) {
            const matched = await this.matchRule(rule, fileInfo);
            // 如果已经匹配成功，可以提前返回（优化）
            if (matched) {
                return true;
            }
        }

        // 如果没有任何规则匹配，返回失败
        return false;
    }

    /**
     * 匹配单个文件规则
     * 使用动态查找，现在类型安全
     */
    public async matchRule(rule: FileRule, fileInfo: FileInfo): Promise<boolean> {
        const matcher = this.matchers.get(rule.type);
        if (!matcher) {
            console.warn(`Unknown matcher type: ${rule.type}`);
            return false;
        }

        // 现在类型安全，因为所有匹配器都接受 FileRule 类型
        return await matcher.match(rule, fileInfo);
    }
}

