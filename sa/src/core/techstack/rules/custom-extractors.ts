/**
 * 自定义提取器注册表
 */

import type { CustomExtractor, FileInfo, MetadataPattern } from '../types';
import fs from 'fs';
import path from 'path';
import { ElfAnalyzer } from '../../elf/elf_analyzer';

/**
 * 自定义提取器注册表（单例）
 */
export class CustomExtractorRegistry {
    private static instance: CustomExtractorRegistry | null = null;
    private extractors: Map<string, CustomExtractor>;

    private constructor() {
        this.extractors = new Map();
        this.registerBuiltinExtractors();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(): CustomExtractorRegistry {
        if (!CustomExtractorRegistry.instance) {
            CustomExtractorRegistry.instance = new CustomExtractorRegistry();
        }
        return CustomExtractorRegistry.instance;
    }

    /**
     * 注册提取器
     */
    public register(name: string, extractor: CustomExtractor): void {
        this.extractors.set(name, extractor);
    }

    /**
     * 获取提取器
     */
    public get(name: string): CustomExtractor | undefined {
        return this.extractors.get(name);
    }

    /**
     * 注册内置提取器
     */
    private registerBuiltinExtractors(): void {
        // Flutter Dart 包提取器
        this.register('extractDartPackages', extractDartPackages);
        this.register('extractPubDevPackages', extractPubDevPackages);

        // Flutter 版本提取器
        this.register('extractFlutterVersion', extractFlutterVersion);
        this.register('extractFlutterHex40', extractFlutterHex40);
        this.register('extractFlutterVersionLastModified', extractFlutterVersionLastModified);
        this.register('extractDartVersion', extractDartVersion);

        // KMP Kotlin 签名提取器
        this.register('extractKotlinSignatures', extractKotlinSignatures);

        // 文件元数据提取器
        this.register('extractLastModified', extractLastModified);
    }
}

/**
 * 提取 Dart 包（从 libapp.so）
 * 原始逻辑来自 FlutterAnalyzer.analyzeDartPackages
 *
 * 注意：这个方法返回的是 pub.dev 上的开源包（排除自研包）
 */
async function extractDartPackages(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<Array<string>> {
    if (!fileInfo.content) {
        return [];
    }

    try {
        // 使用 ELF 分析器提取字符串
        const elfAnalyzer = await ElfAnalyzer.getInstance();

        // 创建临时文件
        const tempDir = path.join(process.cwd(), '.temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `temp_${Date.now()}.so`);
        fs.writeFileSync(tempFilePath, fileInfo.content);

        try {
            const strings = await elfAnalyzer.strings(tempFilePath);

            // 匹配 package 字符串的正则表达式（支持版本号）
            const packageRegex = /package:([a-zA-Z0-9_]+)(?:@([0-9]+\.[0-9]+\.[0-9]+))?/g;
            const packages = new Set<string>();

            for (const str of strings) {
                let match;
                while ((match = packageRegex.exec(str)) !== null) {
                    const packageName = match[1];
                    packages.add(packageName);
                }
            }

            // 加载 pub.dev 包列表，只保留开源包
            try {
                const resPath = path.join(__dirname, '../../../../res/pub_dev_packages.json');
                const data = fs.readFileSync(resPath, 'utf-8');
                const jsonData = JSON.parse(data) as { packages: Array<string> };
                const pubDevPackages = new Set(jsonData.packages);

                // 只保留在 pub.dev 上的包（开源包），排除自研包
                const openSourcePackages = Array.from(packages).filter(name => pubDevPackages.has(name));
                return openSourcePackages;
            } catch (error) {
                console.warn('Failed to load pub.dev packages, returning all packages:', error);
                return Array.from(packages);
            }
        } finally {
            // 清理临时文件
            if (fs.existsSync(tempFilePath)) {
                fs.unlinkSync(tempFilePath);
            }
        }
    } catch (error) {
        console.warn('Failed to extract Dart packages:', error);
        return [];
    }
}

/**
 * 提取 Dart 版本（从 libflutter.so）
 * 原始逻辑：从 strings 中匹配 Dart 版本字符串
 * 注意：这个方法实际上提取的是 Dart 版本，不是 Flutter 版本
 */
async function extractFlutterVersion(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<string | null> {
    if (!fileInfo.content) {
        return null;
    }

    try {
        // 使用 ELF 分析器提取字符串
        const elfAnalyzer = await ElfAnalyzer.getInstance();

        // 创建临时文件
        const tempDir = path.join(process.cwd(), '.temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `temp_${Date.now()}.so`);
        fs.writeFileSync(tempFilePath, fileInfo.content);

        try {
            const strings = await elfAnalyzer.strings(tempFilePath);

            // 匹配 Dart 版本字符串（格式：2.19.6 (stable)）
            const dartVersionRegex = /^(\d+\.\d+\.\d+) \(stable\)/;

            for (const str of strings) {
                const match = str.match(dartVersionRegex);
                if (match) {
                    return match[1]; // 返回版本号部分，如 "2.19.6"
                }
            }

            return null;
        } finally {
            // 清理临时文件
            if (fs.existsSync(tempFilePath)) {
                fs.unlinkSync(tempFilePath);
            }
        }
    } catch (error) {
        console.warn('Failed to extract Dart version:', error);
        return null;
    }
}

/**
 * 提取 Kotlin 签名（使用 ELF 分析器）
 */
async function extractKotlinSignatures(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<Array<string>> {
    if (!fileInfo.content) {
        return [];
    }

    try {
        // 使用 ELF 分析器提取字符串
        const elfAnalyzer = await ElfAnalyzer.getInstance();

        // 创建临时文件
        const tempDir = path.join(process.cwd(), '.temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `temp_kmp_${Date.now()}.so`);
        fs.writeFileSync(tempFilePath, fileInfo.content);

        try {
            const strings = await elfAnalyzer.strings(tempFilePath);

            const signatures = new Set<string>();
            const kotlinPatterns = ['kfun:', 'Kotlin', 'kotlin', 'KOTLIN_NATIVE'];

            for (const str of strings) {
                for (const pattern of kotlinPatterns) {
                    if (str.includes(pattern)) {
                        signatures.add(pattern);
                    }
                }
            }

            return Array.from(signatures);
        } finally {
            // 清理临时文件
            if (fs.existsSync(tempFilePath)) {
                fs.unlinkSync(tempFilePath);
            }
        }
    } catch (error) {
        console.warn('Failed to extract Kotlin signatures:', error);
        return [];
    }
}

/**
 * 提取自研 Dart 包（不在 pub.dev 上的包）
 */
async function extractPubDevPackages(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<Array<string>> {
    if (!fileInfo.content) {
        return [];
    }

    try {
        // 使用 ELF 分析器提取字符串
        const elfAnalyzer = await ElfAnalyzer.getInstance();

        // 创建临时文件
        const tempDir = path.join(process.cwd(), '.temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `temp_${Date.now()}.so`);
        fs.writeFileSync(tempFilePath, fileInfo.content);

        try {
            const strings = await elfAnalyzer.strings(tempFilePath);

            // 匹配 package 字符串的正则表达式（支持版本号）
            const packageRegex = /package:([a-zA-Z0-9_]+)(?:@([0-9]+\.[0-9]+\.[0-9]+))?/g;
            const packages = new Set<string>();

            for (const str of strings) {
                let match;
                while ((match = packageRegex.exec(str)) !== null) {
                    const packageName = match[1];
                    packages.add(packageName);
                }
            }

            // 加载 pub.dev 包列表，只保留自研包
            try {
                const resPath = path.join(__dirname, '../../../../res/pub_dev_packages.json');
                const data = fs.readFileSync(resPath, 'utf-8');
                const jsonData = JSON.parse(data) as { packages: Array<string> };
                const pubDevPackages = new Set(jsonData.packages);

                // 只保留不在 pub.dev 上的包（自研包）
                const customPackages = Array.from(packages).filter(name => !pubDevPackages.has(name));
                return customPackages;
            } catch (error) {
                console.warn('Failed to load pub.dev packages, returning all packages:', error);
                return Array.from(packages);
            }
        } finally {
            // 清理临时文件
            if (fs.existsSync(tempFilePath)) {
                fs.unlinkSync(tempFilePath);
            }
        }
    } catch (error) {
        console.warn('Failed to extract custom Dart packages:', error);
        return [];
    }
}

/**
 * 提取 Flutter 40位 Hex 字符串（从 libflutter.so）
 */
async function extractFlutterHex40(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<string | null> {
    if (!fileInfo.content) {
        return null;
    }

    try {
        // 使用 ELF 分析器提取字符串
        const elfAnalyzer = await ElfAnalyzer.getInstance();

        // 创建临时文件
        const tempDir = path.join(process.cwd(), '.temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `temp_hex_${Date.now()}.so`);
        fs.writeFileSync(tempFilePath, fileInfo.content);

        try {
            const strings = await elfAnalyzer.strings(tempFilePath);

            // 匹配 40 位 Hex 字符串的正则表达式
            const hex40Regex = /^[0-9a-fA-F]{40}$/;
            const hex40Strings: Array<string> = [];

            // 收集所有 40 位 hex 字符串
            for (const str of strings) {
                if (hex40Regex.test(str)) {
                    hex40Strings.push(str);
                }
            }

            if (hex40Strings.length === 0) {
                return null;
            }

            // 加载 Flutter 版本映射
            const flutterVersions = await getFlutterVersions();

            // 找到匹配的版本
            for (const hex40 of hex40Strings) {
                const versionInfo = flutterVersions.get(hex40);
                if (versionInfo) {
                    // 找到匹配的版本，返回 hex40
                    return hex40;
                }
            }

            // 如果没有找到匹配的版本，返回第一个 hex40 字符串
            return hex40Strings[0];
        } finally {
            // 清理临时文件
            if (fs.existsSync(tempFilePath)) {
                fs.unlinkSync(tempFilePath);
            }
        }
    } catch (error) {
        console.warn('Failed to extract Flutter hex40:', error);
        return null;
    }
}

/**
 * 获取 Flutter 版本映射
 * 从 res/flutter_versions.json 加载
 */
async function getFlutterVersions(): Promise<Map<string, { lastModified: string }>> {
    try {
        // 从本地资源文件读取版本映射
        const resPath = path.join(__dirname, '../../../../res/flutter_versions.json');
        if (fs.existsSync(resPath)) {
            const data = fs.readFileSync(resPath, 'utf-8');
            const versionsData = JSON.parse(data) as Record<string, { lastModified: string }>;
            const versions = new Map<string, { lastModified: string }>();

            for (const [hex40, info] of Object.entries(versionsData)) {
                versions.set(hex40, info);
            }

            return versions;
        } else {
            console.warn('flutter_versions.json not found in res directory, using empty map');
            return new Map();
        }
    } catch (error) {
        console.warn('Failed to load Flutter versions from local file:', error);
        return new Map();
    }
}

/**
 * 提取 Flutter 版本的最后修改时间
 * 从 flutter_versions.json 中根据 hex40 查找对应的 lastModified
 */
async function extractFlutterVersionLastModified(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<string | null> {
    // 首先提取 hex40
    const hex40 = await extractFlutterHex40(fileInfo, pattern);
    if (!hex40) {
        return null;
    }

    try {
        // 加载 Flutter 版本映射
        const flutterVersions = await getFlutterVersions();
        const versionInfo = flutterVersions.get(hex40);

        if (versionInfo && versionInfo.lastModified) {
            return versionInfo.lastModified;
        }

        return null;
    } catch (error) {
        console.warn('Failed to extract Flutter version lastModified:', error);
        return null;
    }
}

/**
 * 提取 Dart 版本（从 libflutter.so）
 */
async function extractDartVersion(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<string | null> {
    // 复用 extractFlutterVersion
    return extractFlutterVersion(fileInfo, pattern);
}

/**
 * 提取文件最后修改时间
 */
async function extractLastModified(fileInfo: FileInfo, pattern?: MetadataPattern): Promise<string | null> {
    if (!fileInfo.lastModified) {
        return null;
    }

    // 返回 ISO 格式的时间字符串
    return fileInfo.lastModified.toISOString();
}

