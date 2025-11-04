/**
 * 基础匹配器抽象类
 */

import type { FileRule, FileInfo } from '../types';

/**
 * 匹配结果（带置信度）
 */
export interface MatchResult {
    matched: boolean;
    confidence?: number; // 匹配的置信度（可选）
}

/**
 * 匹配器接口
 */
export interface IMatcher {
    /**
     * 匹配规则
     * @param rule 文件规则
     * @param fileInfo 文件信息
     * @returns 是否匹配
     */
    match: (rule: FileRule, fileInfo: FileInfo) => Promise<boolean>;

    /**
     * 匹配规则（带置信度）
     * @param rule 文件规则
     * @param fileInfo 文件信息
     * @returns 匹配结果和置信度
     */
    matchWithConfidence: (rule: FileRule, fileInfo: FileInfo) => Promise<MatchResult>;

    /**
     * 获取匹配器类型
     */
    getType: () => string;
}

/**
 * 基础匹配器抽象类
 * 所有具体的匹配器都应该继承此类
 */
export abstract class BaseMatcher implements IMatcher {
    /**
     * 匹配规则 - 子类必须实现
     */
    abstract match: (rule: FileRule, fileInfo: FileInfo) => Promise<boolean>;

    /**
     * 匹配规则（带置信度）- 子类必须实现
     */
    abstract matchWithConfidence: (rule: FileRule, fileInfo: FileInfo) => Promise<MatchResult>;

    /**
     * 获取匹配器类型
     */
    abstract getType: () => string;
}

