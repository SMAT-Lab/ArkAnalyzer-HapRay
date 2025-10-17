/**
 * 技术栈检测 - 类型定义
 */

/**
 * 检测配置
 */
export interface TechStackConfig {
    version: string;
    description: string;
    excludes: Array<ExcludeRule>;
    detections: Array<DetectionRule>;
}

/**
 * 排除规则
 */
export interface ExcludeRule {
    type: 'path' | 'filename';
    pattern: string;
}

/**
 * 检测规则
 */
export interface DetectionRule {
    id: string;
    name: string;
    type: string; // 技术栈类型
    confidence: number; // 置信度 0-1
    fileRules: Array<FileRule>;
    metadataRules?: Array<MetadataRule>;
}

/**
 * 文件规则（联合类型）
 */
export type FileRule =
    | FilenameRule
    | PathRule
    | MagicRule
    | ExtensionRule
    | ContentRule
    | CombinedRule;

/**
 * 文件名规则
 */
export interface FilenameRule {
    type: 'filename';
    patterns: Array<string>; // 正则表达式
}

/**
 * 路径规则
 */
export interface PathRule {
    type: 'path';
    patterns: Array<string>; // 正则表达式
}

/**
 * 魔术字规则
 */
export interface MagicRule {
    type: 'magic';
    magicBytes: Array<number>;
    offset?: number;
}

/**
 * 扩展名规则
 */
export interface ExtensionRule {
    type: 'extension';
    extensions: Array<string>;
}

/**
 * 内容规则
 */
export interface ContentRule {
    type: 'content';
    patterns: Array<string | ContentPattern>; // 正则表达式或字符串，或带置信度的模式
}

/**
 * 内容模式（支持置信度）
 */
export interface ContentPattern {
    pattern: string; // 正则表达式或字符串
    confidence?: number; // 可选的置信度 0-1
}

/**
 * 组合规则
 */
export interface CombinedRule {
    type: 'combined';
    operator: 'and' | 'or' | 'not';
    rules: Array<FileRule>;
}

/**
 * 元数据提取规则
 */
export interface MetadataRule {
    field: string; // 提取字段名
    patterns?: Array<MetadataPattern>; // 正则模式（可选）
    extractor?: string; // 自定义提取器名称（可选）
}

/**
 * 元数据模式
 */
export interface MetadataPattern {
    source: 'content' | 'path' | 'filename';
    pattern: string; // 正则表达式
    captureGroup?: number; // 捕获组索引
    transform?: 'trim' | 'lowercase' | 'uppercase';
    custom?: string; // 自定义提取器名称
}

/**
 * 文件信息
 */
export interface FileInfo {
    folder: string;
    file: string;
    path: string; // 完整路径
    size: number;
    content?: Buffer; // 文件内容（按需加载）
    lastModified?: Date; // 最后修改时间
}

/**
 * 检测结果
 */
export interface DetectionResult {
    techStack: string;
    confidence: number;
    ruleId: string;
    ruleName: string;
    metadata: Record<string, unknown>;
}

/**
 * 文件检测结果
 */
export interface FileDetectionResult {
    folder: string;
    file: string;
    size: number;
    detections: Array<DetectionResult>;
}

/**
 * 自定义提取器函数类型
 */
export type CustomExtractor = (
    fileInfo: FileInfo,
    pattern?: MetadataPattern
) => Promise<unknown>;

