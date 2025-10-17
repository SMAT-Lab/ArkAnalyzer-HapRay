/**
 * 技术栈检测模块 - 统一导出
 */

// 类型定义
export * from './types';

// 配置加载
export { TechStackConfigLoader, getTechStackConfigLoader, loadTechStackConfig } from '../../config/techstack_config_loader';

// 检测引擎
export { DetectorEngine, getDetectorEngine } from './detector/detector-engine';

// 规则匹配器
export { FileRuleMatcher } from './rules/file-rule-matcher';
export { MetadataExtractor } from './rules/metadata-extractor';
export { CustomExtractorRegistry } from './rules/custom-extractors';

// Matchers
export { BaseMatcher, IMatcher } from './matchers/base-matcher';
export { FilenameMatcher } from './matchers/filename-matcher';
export { PathMatcher } from './matchers/path-matcher';
export { ExtensionMatcher } from './matchers/extension-matcher';
export { MagicMatcher } from './matchers/magic-matcher';
export { ContentMatcher } from './matchers/content-matcher';
export { CombinedMatcher } from './matchers/combined-matcher';

// 并行执行器
export { ParallelExecutor } from './detector/parallel-executor';

// 适配器
export { ResultAdapter } from './adapter/result-adapter';
export { HapFileScanner } from './adapter/hap-file-scanner';

