/**
 * 组合匹配器
 */

import type { FileInfo, FileRule } from '../types';
import { BaseMatcher, type MatchResult } from './base-matcher';
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
    private contentMatcher: ContentMatcher;

    constructor() {
        super();
        // 使用 Map 存储所有匹配器，通过类型动态查找
        this.matchers = new Map<string, BaseMatcher>();
        this.contentMatcher = new ContentMatcher();
        this.registerMatcher(new FilenameMatcher());
        this.registerMatcher(new PathMatcher());
        this.registerMatcher(new MagicMatcher());
        this.registerMatcher(new ExtensionMatcher());
        this.registerMatcher(this.contentMatcher);
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
        const result = await this.matchWithConfidence(rule, fileInfo);
        return result.matched;
    };

    /**
     * 匹配组合规则（带置信度）
     */
    public matchWithConfidence = async (rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> => {
        if (rule.type !== 'combined') {
            return { matched: false };
        }
        const results: Array<boolean> = [];
        const confidences: Array<number> = [];

        // 递归匹配所有子规则
        for (const subRule of rule.rules) {
            const result = await this.matchFileRuleWithConfidence(subRule, fileInfo);
            results.push(result.matched);
            if (result.confidence !== undefined) {
                confidences.push(result.confidence);
            }
        }

        // 根据操作符计算最终结果
        let matched = false;
        switch (rule.operator) {
            case 'and':
                // AND: 所有规则都必须匹配
                matched = results.every(r => r);
                break;
            case 'or':
                // OR: 至少一个规则匹配
                matched = results.some(r => r);
                break;
            case 'not': {
                // NOT: 第一个规则匹配，但后续规则都不匹配
                if (results.length === 0) {
                    matched = false;
                } else {
                    const firstMatched = results[0];
                    const othersMatched = results.slice(1).some(r => r);
                    matched = firstMatched && !othersMatched;
                }
                break;
            }
        }

        // 计算置信度：优先使用配置文件中的置信度，否则取子规则的最高置信度
        let confidence: number | undefined;
        if (rule.confidence !== undefined) {
            confidence = rule.confidence;
        } else if (confidences.length > 0) {
            confidence = Math.max(...confidences);
        }

        return { matched, confidence };
    };

    /**
     * 匹配单个文件规则（带置信度）
     */
    private async matchFileRuleWithConfidence(rule: FileRule, fileInfo: FileInfo): Promise<MatchResult> {
        const matcher = this.matchers.get(rule.type);
        if (!matcher) {
            console.warn(`Unknown matcher type: ${rule.type}`);
            return { matched: false };
        }

        // 所有匹配器现在都支持置信度
        return await matcher.matchWithConfidence(rule, fileInfo);
    }
}

