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
 * 匹配结果（带置信度）
 */
export interface MatchResult {
    matched: boolean;
    confidence?: number; // 匹配的置信度（可选）
}

/**
 * 文件规则匹配器
 * 使用 Map 动态管理所有匹配器，消除 switch-case
 */
export class FileRuleMatcher {
    private matchers: Map<string, BaseMatcher>;
    private contentMatcher: ContentMatcher;

    constructor() {
        // 使用 Map 存储所有匹配器，通过类型动态查找
        this.matchers = new Map<string, BaseMatcher>();
        this.contentMatcher = new ContentMatcher();
        this.registerMatcher(new FilenameMatcher());
        this.registerMatcher(new PathMatcher());
        this.registerMatcher(new MagicMatcher());
        this.registerMatcher(new ExtensionMatcher());
        this.registerMatcher(this.contentMatcher);
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
        const result = await this.matchRulesWithConfidence(rules, fileInfo);
        return result.matched;
    }

    /**
     * 匹配文件规则列表（OR 关系，带置信度）
     */
    public async matchRulesWithConfidence(rules: Array<FileRule>, fileInfo: FileInfo): Promise<MatchResult> {
        for (const rule of rules) {
            const result = await this.matchRuleWithConfidence(rule, fileInfo);
            // 如果已经匹配成功，可以提前返回（优化）
            if (result.matched) {
                return result;
            }
        }

        // 如果没有任何规则匹配，返回失败
        return { matched: false };
    }

    /**
     * 匹配单个文件规则
     * 使用动态查找，现在类型安全
     */
    public async matchRule(rule: FileRule, fileInfo: FileInfo): Promise<boolean> {
        const result = await this.matchRuleWithConfidence(rule, fileInfo);
        return result.matched;
    }

    /**
     * 匹配单个文件规则（带置信度）
     */
    public async matchRuleWithConfidence(rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> {
        const matcher = this.matchers.get(rule.type);
        if (!matcher) {
            console.warn(`Unknown matcher type: ${rule.type}`);
            return { matched: false };
        }

        // 特殊处理 ContentMatcher，获取置信度
        if (rule.type === 'content' && matcher instanceof ContentMatcher) {
            return await matcher.matchWithConfidence(rule, fileInfo);
        }

        // 其他匹配器只返回布尔值
        const matched = await matcher.match(rule, fileInfo);
        return { matched, confidence: matched ? 1.0 : undefined };
    }
}

