/**
 * 组合匹配器
 */

import type { CombinedRule, FileInfo, RuleMatchResult, FileRule } from '../types';
import { FilenameMatcher } from './filename-matcher';
import { PathMatcher } from './path-matcher';
import { MagicMatcher } from './magic-matcher';
import { ExtensionMatcher } from './extension-matcher';
import { ContentMatcher } from './content-matcher';

/**
 * 组合匹配器
 */
export class CombinedMatcher {
    private filenameMatcher: FilenameMatcher;
    private pathMatcher: PathMatcher;
    private magicMatcher: MagicMatcher;
    private extensionMatcher: ExtensionMatcher;
    private contentMatcher: ContentMatcher;

    constructor() {
        this.filenameMatcher = new FilenameMatcher();
        this.pathMatcher = new PathMatcher();
        this.magicMatcher = new MagicMatcher();
        this.extensionMatcher = new ExtensionMatcher();
        this.contentMatcher = new ContentMatcher();
    }

    /**
     * 匹配组合规则
     */
    public async match(rule: CombinedRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
        const results: Array<RuleMatchResult> = [];

        // 递归匹配所有子规则
        for (const subRule of rule.rules) {
            const result = await this.matchFileRule(subRule, fileInfo);
            results.push(result);
        }

        // 根据操作符计算最终结果
        if (rule.operator === 'and') {
            // AND: 所有规则都必须匹配
            const allMatched = results.every(r => r.matched);
            const avgConfidence = allMatched
                ? results.reduce((sum, r) => sum + r.confidence, 0) / results.length
                : 0;

            return {
                matched: allMatched,
                confidence: avgConfidence
            };
        } else if (rule.operator === 'or') {
            // OR: 至少一个规则匹配
            const anyMatched = results.some(r => r.matched);
            const maxConfidence = anyMatched
                ? Math.max(...results.map(r => r.confidence))
                : 0;

            return {
                matched: anyMatched,
                confidence: maxConfidence
            };
        } else if (rule.operator === 'not') {
            // NOT: 第一个规则匹配，但后续规则都不匹配
            if (results.length === 0) {
                return { matched: false, confidence: 0 };
            }

            const firstMatched = results[0].matched;
            const othersMatched = results.slice(1).some(r => r.matched);

            return {
                matched: firstMatched && !othersMatched,
                confidence: firstMatched && !othersMatched ? results[0].confidence : 0
            };
        } else {
            return {
                matched: false,
                confidence: 0
            };
        }
    }

    /**
     * 匹配单个文件规则
     */
    private async matchFileRule(rule: FileRule, fileInfo: FileInfo): Promise<RuleMatchResult> {
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
                return this.match(rule, fileInfo);
            default:
                return {
                    matched: false,
                    confidence: 0
                };
        }
    }
}

