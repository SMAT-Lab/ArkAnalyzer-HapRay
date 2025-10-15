/**
 * 并行执行器
 */

import type { DetectionRule, FileInfo, DetectionResult } from '../types';
import { FileRuleMatcher } from '../rules/file-rule-matcher';
import { MetadataExtractor } from '../rules/metadata-extractor';

/**
 * 并行执行器
 */
export class ParallelExecutor {
    private fileRuleMatcher: FileRuleMatcher;
    private metadataExtractor: MetadataExtractor;

    constructor() {
        this.fileRuleMatcher = new FileRuleMatcher();
        this.metadataExtractor = new MetadataExtractor();
    }

    /**
     * 并行执行所有检测规则
     */
    public async executeRules(
        rules: Array<DetectionRule>,
        fileInfo: FileInfo
    ): Promise<Array<DetectionResult>> {
        // 并行执行所有规则
        const promises = rules.map(rule => this.executeRule(rule, fileInfo));
        const results = await Promise.all(promises);

        // 过滤掉未匹配的结果
        return results.filter((result): result is DetectionResult => result !== null);
    }

    /**
     * 执行单个检测规则
     */
    private async executeRule(
        rule: DetectionRule,
        fileInfo: FileInfo
    ): Promise<DetectionResult | null> {
        try {
            // 1. 匹配文件规则
            const matchResult = await this.fileRuleMatcher.matchRules(rule.fileRules, fileInfo);

            if (!matchResult.matched) {
                return null;
            }

            // 2. 提取元数据
            const metadata = await this.metadataExtractor.extractMetadata(rule.metadataRules, fileInfo);

            // 3. 计算最终置信度（规则置信度 * 匹配置信度）
            const confidence = rule.confidence * matchResult.confidence;

            // 4. 返回检测结果
            return {
                techStack: rule.type,
                confidence,
                ruleId: rule.id,
                ruleName: rule.name,
                metadata
            };
        } catch (error) {
            console.warn(`Failed to execute rule ${rule.id}:`, error);
            return null;
        }
    }
}

