/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import * as fs from 'fs';
import * as path from 'path';
import { Logger, LOG_MODULE_TYPE } from 'arkanalyzer';
import { ElfAnalyzer } from '../../elf/elf_analyzer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export interface DartPackage {
    name: string;
    version?: string;
}

export interface FlutterVersionInfo {
    hex40: string;
    lastModified: string;
}

export interface FlutterAnalysisResult {
    isFlutter: boolean;
    dartPackages: DartPackage[];
    flutterVersion?: FlutterVersionInfo;
}

export class FlutterAnalyzer {
    private static instance: FlutterAnalyzer | undefined;
    private elfAnalyzer: ElfAnalyzer;
    private pubDevPackages: Set<string> | null = null;

    private constructor() {
        this.elfAnalyzer = ElfAnalyzer.getInstance();
    }

    public static getInstance(): FlutterAnalyzer {
        return (this.instance ??= new FlutterAnalyzer());
    }

    /**
     * 分析Flutter应用
     * @param soPath 当前SO文件路径（可为libapp.so或libflutter.so或其他Flutter相关SO）
     * @param libflutterSoPath libflutter.so文件路径（可选；若当前文件即为libflutter.so，可传同一路径）
     * @returns Flutter分析结果
     */
    public async analyzeFlutter(
        soPath: string,
        libflutterSoPath?: string
    ): Promise<FlutterAnalysisResult> {
        const result: FlutterAnalysisResult = {
            isFlutter: false,
            dartPackages: []
        };

        try {
            // 1. 检查当前SO是否存在
            if (!fs.existsSync(soPath)) {
                logger.warn(`SO not found: ${soPath}`);
                return result;
            }

            // 2. 分析Dart包（对当前SO进行分析）
            const dartPackages = await this.analyzeDartPackages(soPath);
            result.dartPackages = dartPackages;

            // 3. 如果有自研包，则认为是Flutter应用
            const pubDevPackages = await this.getPubDevPackages();
            const customPackages = dartPackages.filter(pkg => !pubDevPackages.has(pkg.name));
            
            if (customPackages.length > 0) {
                result.isFlutter = true;
                logger.info(`Detected Flutter app with ${customPackages.length} custom packages`);
            }

            // 4. 分析Flutter版本（如果提供了libflutter.so；若当前即为libflutter.so，可传当前路径）
            if (libflutterSoPath && fs.existsSync(libflutterSoPath)) {
                const flutterVersion = await this.analyzeFlutterVersion(libflutterSoPath);
                if (flutterVersion) {
                    result.flutterVersion = flutterVersion;
                    result.isFlutter = true; // 如果找到Flutter版本，则确认是Flutter应用
                }
            }

            return result;
        } catch (error) {
            logger.error(`Failed to analyze Flutter: ${(error as Error).message}`);
            return result;
        }
    }

    /**
     * 从给定SO中分析Dart包（可为libapp.so / libflutter.so / 其他Flutter相关SO）
     * @param soPath SO文件路径
     * @returns Dart包列表
     */
    private async analyzeDartPackages(soPath: string): Promise<DartPackage[]> {
        try {
            // 使用ELF分析器的strings方法提取字符串
            const strings = await this.elfAnalyzer.strings(soPath);
            
            // 匹配package字符串的正则表达式
            const packageRegex = /package:([a-zA-Z0-9_]+)(?:@([0-9]+\.[0-9]+\.[0-9]+))?/g;
            const packages: DartPackage[] = [];
            const seenPackages = new Set<string>();

            for (const str of strings) {
                let match;
                while ((match = packageRegex.exec(str)) !== null) {
                    const packageName = match[1];
                    const version = match[2];

                    // 避免重复添加相同的包
                    const packageKey = `${packageName}@${version || 'unknown'}`;
                    if (!seenPackages.has(packageKey)) {
                        seenPackages.add(packageKey);
                        packages.push({
                            name: packageName,
                            version: version
                        });
                        logger.debug(`Found Dart package: ${packageName}@${version || 'unknown'} from string: ${str.substring(0, 100)}...`);
                    } else {
                        logger.debug(`Duplicate Dart package skipped: ${packageName}@${version || 'unknown'} from string: ${str.substring(0, 100)}...`);
                    }
                }
            }

            logger.info(`Found ${packages.length} Dart packages in ${path.basename(soPath)}`);
            return packages;
        } catch (error) {
            logger.error(`Failed to analyze Dart packages: ${(error as Error).message}`);
            return [];
        }
    }

    /**
     * 从libflutter.so中分析Flutter版本
     * @param libflutterSoPath libflutter.so文件路径
     * @returns Flutter版本信息
     */
    public async analyzeFlutterVersion(libflutterSoPath: string): Promise<FlutterVersionInfo | null> {
        try {
            // 使用ELF分析器的strings方法提取字符串
            const strings = await this.elfAnalyzer.strings(libflutterSoPath);
            
            // 匹配40位Hex字符串的正则表达式
            const hex40Regex = /^[0-9a-fA-F]{40}$/;
            const hex40Strings: string[] = [];

            for (const str of strings) {
                if (hex40Regex.test(str)) {
                    hex40Strings.push(str);
                }
            }

            if (hex40Strings.length === 0) {
                logger.warn(`No 40-character hex strings found in ${path.basename(libflutterSoPath)}`);
                return null;
            }

            // 获取Flutter版本映射
            const flutterVersions = await this.getFlutterVersions();
            
            // 优先返回映射中存在的版本；否则回退到首个hex并使用文件修改时间
            for (const hex40 of hex40Strings) {
                const versionInfo = flutterVersions.get(hex40);
                if (versionInfo) {
                    logger.info(`Found Flutter version: ${hex40}, last modified: ${versionInfo.lastModified}`);
                    return {
                        hex40,
                        lastModified: versionInfo.lastModified
                    };
                }
            }

            // 回退：使用检测到的首个40位Hex，修改时间取自文件mtime
            const fallbackHex = hex40Strings[0];
            let mtime = '';
            try {
                const stat = fs.statSync(libflutterSoPath);
                mtime = new Date(stat.mtimeMs).toISOString();
            } catch (e) {
                logger.warn(`Failed to read mtime for ${libflutterSoPath}: ${(e as Error).message}`);
            }
            logger.warn(`No matching Flutter version found in map, fallback to hex ${fallbackHex} with mtime ${mtime || 'unknown'}`);
            return {
                hex40: fallbackHex,
                lastModified: mtime
            };
        } catch (error) {
            logger.error(`Failed to analyze Flutter version: ${(error as Error).message}`);
            return null;
        }
    }

    /**
     * 获取pub.dev上的Flutter/Dart包列表
     * @returns pub.dev包名集合
     */
    private async getPubDevPackages(): Promise<Set<string>> {
        if (this.pubDevPackages !== null) {
            return this.pubDevPackages;
        }

        try {
            // 从本地资源文件读取包列表
            const resPath = path.join(__dirname, '../../../../res/pub_dev_packages.json');
            if (fs.existsSync(resPath)) {
                const data = fs.readFileSync(resPath, 'utf-8');
                const packages = JSON.parse(data) as string[];
                this.pubDevPackages = new Set(packages);
                logger.info(`Loaded ${packages.length} packages from local resource file`);
                return this.pubDevPackages;
            } else {
                logger.warn('pub_dev_packages.json not found in res directory, using empty set');
                this.pubDevPackages = new Set();
                return this.pubDevPackages;
            }
        } catch (error) {
            logger.error(`Failed to load pub.dev packages from local file: ${(error as Error).message}`);
            this.pubDevPackages = new Set();
            return this.pubDevPackages;
        }
    }

    /**
     * 获取Flutter版本映射
     * @returns Flutter版本映射表
     */
    private async getFlutterVersions(): Promise<Map<string, { lastModified: string }>> {
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
                
                logger.info(`Loaded ${versions.size} Flutter versions from local resource file`);
                return versions;
            } else {
                logger.warn('flutter_versions.json not found in res directory, using empty map');
                return new Map();
            }
        } catch (error) {
            logger.error(`Failed to load Flutter versions from local file: ${(error as Error).message}`);
            return new Map();
        }
    }
}
