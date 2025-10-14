/**
 * 文件规则匹配器
 */

import type { FileRule, FileInfo, RuleMatchResult } from '../types';
import { FilenameMatcher } from '../matchers/filename-matcher';
import { PathMatcher } from '../matchers/path-matcher';
import { MagicMatcher } from '../matchers/magic-matcher';
import { ExtensionMatcher } from '../matchers/extension-matcher';
import { ContentMatcher } from '../matchers/content-matcher';
import { CombinedMatcher } from '../matchers/combined-matcher';

/**
 * 文件规则匹配器
 */
export class FileRuleMatcher {
    private filenameMatcher: FilenameMatcher;
    private pathMatcher: PathMatcher;
    private magicMatcher: MagicMatcher;
    private extensionMatcher: ExtensionMatcher;
    private contentMatcher: ContentMatcher;
    private combinedMatcher: CombinedMatcher;

    constructor() {
        this.filenameMatcher = new FilenameMatcher();
        this.pathMatcher = new PathMatcher();
        this.magicMatcher = new MagicMatcher();
        this.extensionMatcher = new ExtensionMatcher();
        this.contentMatcher = new ContentMatcher();
        this.combinedMatcher = new CombinedMatcher();
    }

    /**
     * 匹配文件规则列表（OR 关系）
     */
    public async matchRules(rules: Array<FileRule>, fileInfo: FileInfo): Promise<RuleMatchResult> {
        const results: Array<RuleMatchResult> = [];

        for (const rule of rules) {
            const result = await this.matchRule(rule, fileInfo);
            results.push(result);

            // 如果已经匹配成功，可以提前返回（优化）
            if (result.matched) {
                return result;
            }
        }

        // 如果没有任何规则匹配，返回失败
        return {
            matched: false,
            confidence: 0
        };
    }

    /**
     * 匹配单个文件规则
     */
    public async matchRule(rule: FileRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        switch (rule.type) {
            case 'filename':
                return this.filenameMatcher.match(rule, fileInfo);
            case 'path':
                return this.pathMatcher.match(rule, fileInfo);
            case 'magic':
                return this.magicMatcher.match(rule, fileInfo);
            case 'extension':
                return this.extensionMatcher.match(rule, fileInfo);
            case 'content':
                return this.contentMatcher.match(rule, fileInfo);
            case 'combined':
                return this.combinedMatcher.match(rule, fileInfo);
            default:
                return {
                    matched: false,
                    confidence: 0
                };
        }
    }
}

