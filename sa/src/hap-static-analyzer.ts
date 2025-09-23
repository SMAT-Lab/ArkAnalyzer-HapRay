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

import path from 'path';
import JSZip from 'jszip';
import fs from 'fs';
import { HapStaticAnalysisResult } from './types';
import { SoAnalyzer } from './analyzers/so-analyzer';
import { ResourceAnalyzer } from './analyzers/resource-analyzer';
import { fileExists, ensureDirectoryExists } from './utils/file-utils';
import { createEnhancedZipAdapter, EnhancedJSZipAdapter } from './utils/zip-adapter';
import {
    ErrorFactory,
    ErrorUtils
} from './errors';

/**
 * HAP包静态分析器主类
 */
/* eslint-disable @typescript-eslint/no-unused-vars */
export class HapStaticAnalyzer {
    private soAnalyzer: SoAnalyzer;
    private resourceAnalyzer: ResourceAnalyzer;
    private verbose: boolean;

    constructor(verbose: boolean = false) {
        this.verbose = verbose;
        this.soAnalyzer = new SoAnalyzer();
        this.resourceAnalyzer = new ResourceAnalyzer();
    }

    /**
     * 分析HAP包
     * @param hapFilePath HAP包文件路径
     * @param outputDir 临时解压目录（可选，当前版本未使用）
     * @returns 分析结果
     */
    public async analyzeHap(hapFilePath: string, _outputDir?: string): Promise<HapStaticAnalysisResult> {
        // 验证HAP文件存在性
        if (!fileExists(hapFilePath)) {
            throw ErrorFactory.createHapFileError(
                `HAP file not found: ${hapFilePath}`,
                hapFilePath
            );
        }

        if (this.verbose) {
            console.log(`Starting analysis of HAP: ${hapFilePath}`);
        }

        let zipAdapter: EnhancedJSZipAdapter | null = null;

        try {
            // 读取HAP文件数据
            let hapData: Buffer;
            try {
                hapData = fs.readFileSync(hapFilePath);
            } catch (error) {
                throw ErrorFactory.createHapFileError(
                    `Failed to read HAP file: ${hapFilePath}`,
                    hapFilePath,
                    error instanceof Error ? error : new Error(String(error))
                );
            }

            // 解析ZIP数据
            try {
                zipAdapter = await createEnhancedZipAdapter(hapData);
            } catch (error) {
                throw ErrorFactory.createZipParsingError(
                    `Failed to parse HAP as ZIP: ${hapFilePath}`,
                    hapFilePath,
                    error instanceof Error ? error : new Error(String(error))
                );
            }

            if (this.verbose) {
                const fileCount = Object.keys(zipAdapter.files).length;
                console.log(`HAP loaded, found ${fileCount} files`);
                console.log(`Total uncompressed size: ${this.formatBytes(zipAdapter.getTotalUncompressedSize())}`);
                console.log(`Total compressed size: ${this.formatBytes(zipAdapter.getTotalCompressedSize())}`);
                console.log(`Overall compression ratio: ${(zipAdapter.getOverallCompressionRatio() * 100).toFixed(1)}%`);

                if (this.verbose) {
                    console.log('Files in HAP:');
                    Object.keys(zipAdapter.files).forEach(filePath => {
                        console.log(`  ${filePath}`);
                    });
                }
            }

            // 执行并行分析
            let soAnalysis, resourceAnalysis;
            try {
                [soAnalysis, resourceAnalysis] = await Promise.all([
                    this.soAnalyzer.analyzeSoFilesFromZip(zipAdapter),
                    this.resourceAnalyzer.analyzeResourcesFromZip(zipAdapter)
                ]);
            } catch (error) {
                if (ErrorUtils.isMemoryError(error)) {
                    throw ErrorFactory.createOutOfMemoryError(
                        `Analysis failed due to memory constraints: ${hapFilePath}`,
                        zipAdapter.getTotalUncompressedSize(),
                        error instanceof Error ? error : new Error(String(error))
                    );
                }
                throw error;
            }

            const result: HapStaticAnalysisResult = {
                hapPath: hapFilePath,
                soAnalysis,
                resourceAnalysis,
                timestamp: new Date()
            };

            if (this.verbose) {
                this.logAnalysisResults(result);
            }

            return result;

        } catch (error) {
            // 如果已经是我们的自定义错误，直接抛出
            if (ErrorUtils.isAnalysisError(error)) {
                throw error;
            }

            // 否则包装为通用分析错误
            throw ErrorFactory.createHapFileError(
                `Failed to analyze HAP: ${ErrorUtils.getErrorMessage(error)}`,
                hapFilePath,
                error instanceof Error ? error : new Error(String(error))
            );
        } finally {
            // 清理资源（如果需要的话）
            zipAdapter = null;
        }
    }

    /**
     * 解压HAP包
     * @param hapFilePath HAP包路径
     * @param extractDir 解压目录
     */
    private async extractHap(hapFilePath: string, extractDir: string): Promise<void> {
        try {
            const hapData = fs.readFileSync(hapFilePath);
            const zip = await JSZip.loadAsync(hapData);

            for (const [relativePath, zipEntry] of Object.entries(zip.files)) {
                if (zipEntry.dir) {
                    // 创建目录
                    const dirPath = path.join(extractDir, relativePath);
                    ensureDirectoryExists(dirPath);
                } else {
                    // 提取文件
                    const filePath = path.join(extractDir, relativePath);
                    const fileDir = path.dirname(filePath);
                    ensureDirectoryExists(fileDir);

                    const content = await zipEntry.async('nodebuffer');
                    fs.writeFileSync(filePath, content);
                }
            }

            if (this.verbose) {
                console.log(`HAP extracted to: ${extractDir}`);
            }
        } catch (error) {
            throw new Error(`Failed to extract HAP: ${error}`);
        }
    }

    /**
     * 清理临时目录
     * @param tempDir 临时目录路径
     */
    private async cleanupTempDirectory(tempDir: string): Promise<void> {
        try {
            if (fileExists(tempDir)) {
                fs.rmSync(tempDir, { recursive: true, force: true });
                if (this.verbose) {
                    console.log(`Cleaned up temp directory: ${tempDir}`);
                }
            }
        } catch (error) {
            console.warn(`Failed to cleanup temp directory: ${tempDir}`, error);
        }
    }

    /**
     * 记录分析结果
     * @param result 分析结果
     */
    private logAnalysisResults(result: HapStaticAnalysisResult): void {
        console.log('\n=== HAP Static Analysis Results ===');
        console.log(`HAP: ${result.hapPath}`);
        console.log(`Analysis Time: ${result.timestamp.toISOString()}`);

        // SO文件分析结果
        console.log('\n--- SO Analysis ---');
        console.log(`Total SO files: ${result.soAnalysis.totalSoFiles}`);
        console.log(`Detected frameworks: ${result.soAnalysis.detectedFrameworks.join(', ') || 'None'}`);

        if (result.soAnalysis.soFiles.length > 0) {
            console.log('SO files:');
            for (const soFile of result.soAnalysis.soFiles) {
                console.log(`  - ${soFile.fileName} (${soFile.frameworks.join(', ')})`);
            }
        }

        // 资源文件分析结果
        console.log('\n--- Resource Analysis ---');
        console.log(`Total files: ${result.resourceAnalysis.totalFiles} (including nested)`);
        console.log(`Total size: ${this.formatBytes(result.resourceAnalysis.totalSize)}`);
        console.log(`Archive files: ${result.resourceAnalysis.archiveFiles.length}`);
        console.log(`JS files: ${result.resourceAnalysis.jsFiles.length}`);
        console.log(`Hermes files: ${result.resourceAnalysis.hermesFiles.length}`);

        if (result.resourceAnalysis.extractedArchiveCount > 0) {
            console.log(`Extracted archives: ${result.resourceAnalysis.extractedArchiveCount}`);
            console.log(`Max extraction depth: ${result.resourceAnalysis.maxExtractionDepth}`);
        }

        if (result.resourceAnalysis.filesByType.size > 0) {
            console.log('Files by type:');
            for (const [fileType, files] of result.resourceAnalysis.filesByType) {
                const totalSize = files.reduce((sum, file) => sum + file.fileSize, 0);
                console.log(`  - ${fileType}: ${files.length} files (${this.formatBytes(totalSize)})`);
            }
        }

        // 显示压缩文件详情
        if (result.resourceAnalysis.archiveFiles.length > 0) {
            console.log('\nArchive details:');
            for (const archive of result.resourceAnalysis.archiveFiles) {
                console.log(`  - ${archive.fileName} (${this.formatBytes(archive.fileSize)})`);
                if (archive.extracted) {
                    console.log(`    ✓ Extracted: ${archive.entryCount} files, depth: ${archive.extractionDepth}`);
                    if (archive.nestedFiles && archive.nestedFiles.length > 0) {
                        const nestedByType = new Map<string, number>();
                        for (const file of archive.nestedFiles) {
                            nestedByType.set(file.fileType, (nestedByType.get(file.fileType) || 0) + 1);
                        }
                        console.log(`    └─ Nested files: ${Array.from(nestedByType.entries()).map(([type, count]) => `${type}(${count})`).join(', ')}`);
                    }
                } else {
                    console.log(`    ✗ Not extracted (depth limit or error)`);
                }
            }
        }

        console.log('=====================================\n');
    }

    /**
     * 格式化字节数
     * @param bytes 字节数
     * @returns 格式化的字符串
     */
    private formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';

        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }


}
