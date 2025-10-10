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

import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import type { FormatResult } from './index';
import { BaseFormatter } from './index';
import type { HapStaticAnalysisResult, ResourceFileInfo } from '../../config/types';

/**
 * 扩展的文件信息，用于HTML展示
 */
interface ExtendedFileInfo extends ResourceFileInfo {
    /** 格式化后的文件大小 */
    fileSizeFormatted: string;
    /** 是否为嵌套文件 */
    isNested: boolean;
    /** 来源描述 */
    source: string;
    /** 父级信息 */
    parentInfo: string;
}

/**
 * HTML格式化器
 */
export class HtmlFormatter extends BaseFormatter {
    /**
     * 格式化分析结果为HTML
     */
    async format(result: HapStaticAnalysisResult): Promise<FormatResult> {
        const startTime = Date.now();
        
        try {
            this.validateOptions();
            
            // 确保输出目录存在
            const outputDir = path.dirname(this.options.outputPath);
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }

            // 构建HTML报告数据
            const templateData = this.buildTemplateData(result);
            
            // 获取模板内容
            const template = this.getTemplate();
            
            // 编译模板
            const compiledTemplate = Handlebars.compile(template);
            const htmlContent = compiledTemplate(templateData);
            
            // 写入文件
            fs.writeFileSync(this.options.outputPath, htmlContent, 'utf8');
            
            const fileSize = fs.statSync(this.options.outputPath).size;
            const duration = Date.now() - startTime;

            return {
                filePath: this.options.outputPath,
                fileSize,
                duration,
                success: true
            };

        } catch (error) {
            return {
                filePath: this.options.outputPath,
                fileSize: 0,
                duration: Date.now() - startTime,
                success: false,
                error: error instanceof Error ? error.message : String(error)
            };
        }
    }

    /**
     * 获取文件扩展名
     */
    getFileExtension(): string {
        return '.html';
    }

    /**
     * 获取HTML模板
     */
    private getTemplate(): string {
        // 如果指定了自定义模板路径，使用自定义模板
        if (this.options.templatePath && fs.existsSync(this.options.templatePath)) {
            return fs.readFileSync(this.options.templatePath, 'utf8');
        }
        
        // 使用默认模板
        return this.getDefaultTemplate();
    }

    /**
     * 构建模板数据
     */
    private buildTemplateData(result: HapStaticAnalysisResult) {
        const fileTypeStats = this.getFileTypeStats(result);
        const frameworkStats = this.getFrameworkStats(result);
        const allFiles = this.buildAllFilesList(result);
        const dynamicFilterButtons = this.generateFrameworkFilterButtons(result, allFiles);

        return {
            metadata: {
                hapPath: result.hapPath,
                hapFileName: path.basename(result.hapPath),
                timestamp: result.timestamp,
                analysisDate: this.formatDateTime(result.timestamp),
                version: '1.1.0'
            },
            summary: {
                totalSoFiles: result.soAnalysis.totalSoFiles,
                totalResourceFiles: result.resourceAnalysis.totalFiles,
                totalSize: this.formatFileSize(result.resourceAnalysis.totalSize),
                detectedFrameworks: result.soAnalysis.detectedFrameworks,
                jsFilesCount: result.resourceAnalysis.jsFiles.length,
                hermesFilesCount: result.resourceAnalysis.hermesFiles.length,
                archiveFilesCount: result.resourceAnalysis.archiveFiles.length,
                extractedArchiveCount: result.resourceAnalysis.extractedArchiveCount,
                maxExtractionDepth: result.resourceAnalysis.maxExtractionDepth,
                hasNestedArchives: result.resourceAnalysis.extractedArchiveCount > 0
            },
            statistics: {
                fileTypes: fileTypeStats,
                frameworks: frameworkStats,
                hasFileTypes: fileTypeStats.length > 0,
                hasFrameworks: frameworkStats.length > 0
            },
            soAnalysis: {
                detectedFrameworks: result.soAnalysis.detectedFrameworks,
                totalSoFiles: result.soAnalysis.totalSoFiles,
                soFiles: result.soAnalysis.soFiles.map(soFile => ({
                    ...soFile,
                    fileSizeFormatted: this.formatFileSize(soFile.fileSize),
                    frameworksText: soFile.frameworks.join(', '),
                    isLibFlutter: soFile.fileName?.toLowerCase() === 'libflutter.so',
                    flutterHex40: soFile.flutterAnalysis?.flutterVersion?.hex40 || '',
                    flutterLastModified: soFile.flutterAnalysis?.flutterVersion?.lastModified || '',
                    flutterAnalysis: soFile.flutterAnalysis ? {
                        isFlutter: soFile.flutterAnalysis.isFlutter,
                        dartPackages: soFile.flutterAnalysis.dartPackages,
                        flutterVersion: soFile.flutterAnalysis.flutterVersion,
                        hasFlutterAnalysis: true
                    } : {
                        hasFlutterAnalysis: false
                    }
                })),
                hasSoFiles: result.soAnalysis.soFiles.length > 0
            },
            resourceAnalysis: {
                totalFiles: result.resourceAnalysis.totalFiles,
                totalSize: this.formatFileSize(result.resourceAnalysis.totalSize),
                jsFiles: result.resourceAnalysis.jsFiles.map(jsFile => ({
                    ...jsFile,
                    fileSizeFormatted: this.formatFileSize(jsFile.fileSize),
                    isNested: jsFile.filePath.includes('/')
                })),
                hermesFiles: result.resourceAnalysis.hermesFiles.map(hermesFile => ({
                    ...hermesFile,
                    fileSizeFormatted: this.formatFileSize(hermesFile.fileSize),
                    isNested: hermesFile.filePath.includes('/')
                })),
                archiveFiles: result.resourceAnalysis.archiveFiles.map(archiveFile => ({
                    ...archiveFile,
                    fileSizeFormatted: this.formatFileSize(archiveFile.fileSize),
                    nestedFiles: archiveFile.nestedFiles?.map(nestedFile => ({
                        ...nestedFile,
                        fileSizeFormatted: this.formatFileSize(nestedFile.fileSize),
                        isNested: true,
                        parentArchive: archiveFile.fileName
                    })) || [],
                    nestedArchives: archiveFile.nestedArchives?.map(nestedArchive => ({
                        ...nestedArchive,
                        fileSizeFormatted: this.formatFileSize(nestedArchive.fileSize),
                        isNested: true,
                        parentArchive: archiveFile.fileName,
                        nestedFiles: nestedArchive.nestedFiles?.map(deepFile => ({
                            ...deepFile,
                            fileSizeFormatted: this.formatFileSize(deepFile.fileSize),
                            isNested: true,
                            parentArchive: `${archiveFile.fileName}/${nestedArchive.fileName}`
                        })) || [],
                        hasNestedFiles: (nestedArchive.nestedFiles?.length || 0) > 0
                    })) || [],
                    hasNestedFiles: (archiveFile.nestedFiles?.length || 0) > 0,
                    hasNestedArchives: (archiveFile.nestedArchives?.length || 0) > 0
                })),
                allFiles: allFiles,
                hasJsFiles: result.resourceAnalysis.jsFiles.length > 0,
                hasHermesFiles: result.resourceAnalysis.hermesFiles.length > 0,
                hasArchiveFiles: result.resourceAnalysis.archiveFiles.length > 0
            },
            filters: {
                archiveFilterButtons: dynamicFilterButtons.archiveButtons,
                allFilesFilterButtons: dynamicFilterButtons.allFilesButtons
            },
            options: {
                includeDetails: this.options.includeDetails !== false
            }
        };
    }

    /**
     * 构建所有文件的完整列表
     */
    private buildAllFilesList(result: HapStaticAnalysisResult): Array<ExtendedFileInfo & { frameworkKey: string; frameworksText: string; }> {
        const allFiles: Array<ExtendedFileInfo & { frameworkKey: string; frameworksText: string; }> = [];

        // 收集所有嵌套文件的路径，避免重复展示
        const nestedFilePaths = new Set<string>();
        for (const archiveFile of result.resourceAnalysis.archiveFiles) {
            if (archiveFile.nestedFiles) {
                for (const nestedFile of archiveFile.nestedFiles) {
                    nestedFilePaths.add(nestedFile.filePath);
                }
            }
            if (archiveFile.nestedArchives) {
                for (const nestedArchive of archiveFile.nestedArchives) {
                    if (nestedArchive.nestedFiles) {
                        for (const deepFile of nestedArchive.nestedFiles) {
                            nestedFilePaths.add(deepFile.filePath);
                        }
                    }
                }
            }
        }

        // 添加直接的资源文件（从filesByType中获取，排除嵌套文件）
        for (const [, files] of result.resourceAnalysis.filesByType) {
            for (const file of files) {
                // 跳过已经在压缩包分析中展示的嵌套文件
                if (nestedFilePaths.has(file.filePath)) {
                    continue;
                }

                const isNested = this.isNestedFile(file.filePath);
                const frameworks = this.lookupFrameworksForFile(result, file.filePath, file.fileName);
                allFiles.push({
                    ...file,
                    fileSizeFormatted: this.formatFileSize(file.fileSize),
                    isNested: isNested,
                    source: isNested ? '🗂️ 嵌套' : '📄 直接',
                    parentInfo: this.getParentInfo(file.filePath),
                    frameworkKey: frameworks.join(', '),
                    frameworksText: frameworks.join(', ')
                });
            }
        }

        return allFiles.sort((a, b) => {
            // 先按是否嵌套排序，再按文件名排序
            if (a.isNested !== b.isNested) {
                return a.isNested ? 1 : -1;
            }
            return a.fileName.localeCompare(b.fileName);
        });
    }

    /**
     * 为资源文件推断框架：
     * - 若在 libs 中存在同名/同前缀的 SO，继承其框架
     * - 否则归类为 Unknown
     */
    private lookupFrameworksForFile(result: HapStaticAnalysisResult, _filePath: string, fileName: string): Array<string> {
        // 按此前逻辑：仅以 SO 分析结果为准，不做路径/类型猜测
        const lowerName = fileName.toLowerCase();
        const matches = result.soAnalysis.soFiles.filter(so => so.fileName.toLowerCase() === lowerName);
        if (matches.length > 0) {
            const set = new Set<string>();
            for (const so of matches) { so.frameworks.forEach(f => set.add(f)); }
            return Array.from(set);
        }
        return ['Unknown'];
    }

    /**
     * 判断是否为嵌套文件
     */
    private isNestedFile(filePath: string): boolean {
        // 如果路径包含压缩包名称（.zip/），则为嵌套文件
        return filePath.includes('.zip/');
    }

    /**
     * 获取文件的父级信息
     */
    private getParentInfo(filePath: string): string {
        const parts = filePath.split('/');
        if (parts.length <= 1) {
            return '';
        }

        // 如果是直接在assets或libs下的文件
        if (parts[0] === 'assets' || parts[0] === 'libs') {
            return '';
        }

        // 如果是嵌套文件，返回父级路径
        const parentParts = parts.slice(0, -1);
        return parentParts.join('/');
    }

    /**
     * 生成动态过滤按钮
     */
    private generateFrameworkFilterButtons(
        result: HapStaticAnalysisResult,
        allFiles: Array<ExtendedFileInfo & { frameworkKey: string; frameworksText: string; }>
    ) {
        // 压缩包分析按钮：仅展示存在的数据类型
        const anyExtracted = result.resourceAnalysis.archiveFiles.some(a => a.extracted);
        const anyNotExtracted = result.resourceAnalysis.archiveFiles.some(a => !a.extracted);

        const archiveButtons = [
            { type: 'all', label: '全部', active: true }
        ];
        if (anyExtracted) {
            archiveButtons.push({ type: 'extracted', label: '已解压', active: false });
        }
        if (anyNotExtracted) {
            archiveButtons.push({ type: 'not-extracted', label: '未解压', active: false });
        }

        // 所有文件详情按钮：仅展示实际存在的框架与嵌套项
        const allFilesButtons = [
            { type: 'all', label: '全部', active: true }
        ];

        const hasNested = allFiles.some(f => f.isNested);
        if (hasNested) {
            allFilesButtons.push({ type: 'nested', label: '嵌套文件', active: false });
        }

        const presentFrameworks = new Set<string>();
        for (const file of allFiles) {
            const parts = file.frameworksText.split(',').map(s => s.trim()).filter(Boolean);
            for (const fw of parts) {
                presentFrameworks.add(fw);
            }
        }
        for (const fw of Array.from(presentFrameworks).sort()) {
            allFilesButtons.push({ type: fw, label: fw, active: false });
        }

        return {
            archiveButtons,
            allFilesButtons
        };
    }

    

    /**
     * 获取默认HTML模板
     */
    private getDefaultTemplate(): string {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HAP静态分析报告 - {{metadata.hapFileName}}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .meta { opacity: 0.9; font-size: 1.1em; }
        .card { background: white; border-radius: 10px; padding: 25px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card h2 { color: #2c3e50; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .summary-item { text-align: center; padding: 20px; background: linear-gradient(135deg, #74b9ff, #0984e3); color: white; border-radius: 8px; }
        .summary-item .number { font-size: 2.5em; font-weight: bold; display: block; }
        .summary-item .label { font-size: 1.1em; opacity: 0.9; }
        .table { width: 100%; border-collapse: collapse; margin-top: 15px; table-layout: fixed; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; vertical-align: top; word-break: break-word; overflow-wrap: anywhere; }
        .table th { background: #f8f9fa; font-weight: 600; color: #2c3e50; }
        .table tr:hover { background: #f8f9fa; }
        code { white-space: normal; word-break: break-all; overflow-wrap: anywhere; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500; }
        .badge-primary { background: #3498db; color: white; }
        .badge-success { background: #27ae60; color: white; }
        .badge-warning { background: #f39c12; color: white; }
        .badge-danger { background: #e74c3c; color: white; }
        .frameworks { margin: 15px 0; }
        .framework-tag { display: inline-block; margin: 3px; padding: 6px 12px; background: #3498db; color: white; border-radius: 20px; font-size: 0.9em; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: top; }
        .flutter-analysis { font-size: 0.9em; }
        .flutter-analysis ul { margin: 5px 0; padding-left: 20px; }
        .flutter-analysis li { margin: 2px 0; }
        .flutter-analysis code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 0.85em; }
        .badge-secondary { background: #6c757d; color: white; }
        .badge-light { background: #f8f9fa; color: #6c757d; border: 1px solid #dee2e6; }

        /* 递归压缩包样式 */
        .archive-tree { margin: 10px 0; }
        .archive-item { margin: 8px 0; padding: 12px; border: 1px solid #e0e0e0; border-radius: 6px; background: #fafafa; word-break: break-word; overflow-wrap: anywhere; }
        .archive-header { display: flex; align-items: center; margin-bottom: 8px; }
        .archive-icon { margin-right: 8px; font-size: 1.2em; }
        .archive-name { font-weight: bold; color: #2c3e50; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .archive-info { margin-left: auto; font-size: 0.9em; color: #7f8c8d; }
        .archive-stats { margin: 8px 0; font-size: 0.9em; color: #555; }
        .nested-files { margin-left: 20px; margin-top: 10px; }
        .nested-file { padding: 6px 10px; margin: 3px 0; background: white; border-left: 3px solid #3498db; border-radius: 3px; font-size: 0.9em; word-break: break-word; overflow-wrap: anywhere; }
        .nested-archive { margin-left: 20px; margin-top: 10px; border-left: 2px solid #e74c3c; padding-left: 15px; }
        .depth-indicator { display: inline-block; padding: 2px 6px; background: #e74c3c; color: white; border-radius: 10px; font-size: 0.8em; margin-left: 8px; }
        .extraction-status { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 0.8em; margin-left: 8px; }
        .extracted { background: #27ae60; color: white; }
        .not-extracted { background: #e74c3c; color: white; }
        .file-type-tag { display: inline-block; padding: 2px 6px; background: #95a5a6; color: white; border-radius: 3px; font-size: 0.8em; margin-right: 4px; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: top; }
        .collapsible { cursor: pointer; user-select: none; }
        .collapsible:hover { background: #f0f0f0; }
        .collapsible::before { content: '▼ '; color: #3498db; font-weight: bold; }
        .collapsible.collapsed::before { content: '▶ '; }
        .collapsible-content { display: block; }
        .collapsible-content.collapsed { display: none; }

        /* 搜索和过滤功能 */
        .search-container { margin: 20px 0; }
        .search-box { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 1em; }
        .search-box:focus { border-color: #3498db; outline: none; }
        .filter-buttons { margin: 10px 0; }
        .filter-btn { padding: 8px 16px; margin: 4px; border: none; border-radius: 20px; cursor: pointer; font-size: 0.9em; transition: all 0.3s; }
        .filter-btn.active { background: #3498db; color: white; }
        .filter-btn:not(.active) { background: #ecf0f1; color: #2c3e50; }
        .filter-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 5px rgba(0,0,0,0.2); }

        /* 统计图表样式 */
        .chart-container { margin: 20px 0; }
        .chart-item { margin: 8px 0; }
        .chart-bar {
            height: 30px;
            background: linear-gradient(90deg, #3498db, #2980b9);
            border-radius: 10px;
            position: relative;
            min-width: 120px;
            transition: all 0.3s ease;
        }
        .chart-bar:hover {
            background: linear-gradient(90deg, #2980b9, #1f4e79);
            transform: translateX(5px);
        }
        .chart-label {
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-weight: bold;
            font-size: 0.9em;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            right: 70px;
        }
        .chart-value {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-size: 0.8em;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            white-space: nowrap;
        }

        /* 响应式设计 */
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .summary-grid { grid-template-columns: repeat(2, 1fr); }
            .table { font-size: 0.9em; table-layout: fixed; }
            .nested-files { margin-left: 10px; }
            .nested-archive { margin-left: 10px; }
            .framework-tag, .file-type-tag { max-width: 160px; }
        }

        .no-data { text-align: center; color: #7f8c8d; font-style: italic; padding: 40px; }
        .footer { text-align: center; margin-top: 40px; padding: 20px; color: #7f8c8d; border-top: 1px solid #ddd; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>HAP静态分析报告</h1>
            <div class="meta">
                <div>文件: {{metadata.hapFileName}}</div>
                <div>分析时间: {{metadata.analysisDate}}</div>
                <div>版本: {{metadata.version}}</div>
            </div>
        </div>

        <div class="card">
            <h2>📊 分析摘要</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <span class="number">{{summary.totalSoFiles}}</span>
                    <span class="label">SO文件</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.totalResourceFiles}}</span>
                    <span class="label">资源文件</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.jsFilesCount}}</span>
                    <span class="label">JS文件</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.totalSize}}</span>
                    <span class="label">总大小</span>
                </div>
                {{#if summary.hasNestedArchives}}
                <div class="summary-item">
                    <span class="number">{{summary.extractedArchiveCount}}</span>
                    <span class="label">解压压缩包</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.maxExtractionDepth}}</span>
                    <span class="label">最大深度</span>
                </div>
                {{/if}}
            </div>
            
            {{#if summary.detectedFrameworks.length}}
            <div class="frameworks">
                <strong>检测到的框架:</strong>
                {{#each summary.detectedFrameworks}}
                <span class="framework-tag">{{this}}</span>
                {{/each}}
            </div>
            {{/if}}
        </div>

        {{#if statistics.hasFrameworks}}
        <div class="card">
            <h2>🔧 框架统计</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>框架</th>
                        <th>文件数量</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
                    {{#each statistics.frameworks}}
                    <tr>
                        <td><span class="badge badge-primary">{{framework}}</span></td>
                        <td>{{count}}</td>
                        <td>{{percentage}}</td>
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>
        {{/if}}

        {{#if statistics.hasFileTypes}}
        <div class="card">
            <h2>📁 文件类型统计</h2>
            <div class="chart-container">
                {{#each statistics.fileTypes}}
                <div class="chart-item">
                    <div class="chart-bar" style="width: {{barWidth}}%;">
                        <span class="chart-label">{{type}}</span>
                        <span class="chart-value">{{count}} ({{percentage}})</span>
                    </div>
                </div>
                {{/each}}
            </div>
            <table class="table">
                <thead>
                    <tr>
                        <th>文件类型</th>
                        <th>文件数量</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
                    {{#each statistics.fileTypes}}
                    <tr>
                        <td><span class="badge badge-success">{{type}}</span></td>
                        <td>{{count}}</td>
                        <td>{{percentage}}</td>
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>
        {{/if}}

        {{#if options.includeDetails}}
        {{#if soAnalysis.hasSoFiles}}
        <div class="card">
            <h2>📦 SO文件详情</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>文件名</th>
                        <th>路径</th>
                        <th>框架</th>
                        <th>大小</th>
                        <th>系统库</th>
                        <th>Flutter分析</th>
                    </tr>
                </thead>
                <tbody>
                    {{#each soAnalysis.soFiles}}
                    <tr>
                        <td><strong>{{fileName}}</strong></td>
                        <td><code>{{filePath}}</code></td>
                        <td>{{frameworksText}}</td>
                        <td>{{fileSizeFormatted}}</td>
                        <td>{{#if isSystemLib}}<span class="badge badge-warning">是</span>{{else}}<span class="badge badge-success">否</span>{{/if}}</td>
                        <td>
                            {{#if flutterAnalysis.hasFlutterAnalysis}}
                                {{#if flutterAnalysis.isFlutter}}
                                    <div class="flutter-analysis">
                                        <div><strong>Flutter应用</strong></div>
                                        {{#if flutterAnalysis.dartPackages}}
                                            <div><strong>Dart包 ({{flutterAnalysis.dartPackages.length}}):</strong></div>
                                            <ul>
                                                {{#each flutterAnalysis.dartPackages}}
                                                <li>{{name}}{{#if version}}@{{version}}{{/if}}</li>
                                                {{/each}}
                                            </ul>
                                        {{/if}}
                                        {{#if flutterAnalysis.flutterVersion}}
                                            <div><strong>Flutter版本:</strong></div>
                                            <div>Hex: <code>{{flutterAnalysis.flutterVersion.hex40}}</code></div>
                                            <div>修改时间: <code>{{flutterAnalysis.flutterVersion.lastModified}}</code></div>
                                        {{else}}
                                            {{#if isLibFlutter}}
                                                {{#if flutterHex40}}
                                                    <div><strong>Flutter版本:</strong></div>
                                                    <div>Hex: <code>{{flutterHex40}}</code></div>
                                                    {{#if flutterLastModified}}
                                                        <div>修改时间: <code>{{flutterLastModified}}</code></div>
                                                    {{/if}}
                                                {{/if}}
                                            {{/if}}
                                        {{/if}}
                                    </div>
                                {{else}}
                                    <span class="badge badge-secondary">非Flutter</span>
                                {{/if}}
                            {{else}}
                                {{#if isLibFlutter}}
                                    {{#if flutterHex40}}
                                        <div class="flutter-analysis">
                                            <div><strong>Flutter版本:</strong></div>
                                            <div>Hex: <code>{{flutterHex40}}</code></div>
                                            {{#if flutterLastModified}}
                                                <div>修改时间: <code>{{flutterLastModified}}</code></div>
                                            {{/if}}
                                        </div>
                                    {{else}}
                                        <span class="badge badge-light">未分析</span>
                                    {{/if}}
                                {{else}}
                                    <span class="badge badge-light">未分析</span>
                                {{/if}}
                            {{/if}}
                        </td>
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>
        {{/if}}

        {{#if resourceAnalysis.hasArchiveFiles}}
        <div class="card">
            <h2>📦 压缩包分析</h2>
            <div class="search-container">
                <input type="text" class="search-box" placeholder="🔍 搜索文件名、路径或类型..." onkeyup="searchFiles(this.value)">
                <div class="filter-buttons">
                    {{#each filters.archiveFilterButtons}}
                    <button class="filter-btn {{#if active}}active{{/if}}" onclick="filterFiles('{{type}}')">{{label}}</button>
                    {{/each}}
                </div>
            </div>
            <div class="archive-tree">
                {{#each resourceAnalysis.archiveFiles}}
                <div class="archive-item">
                    <div class="archive-header collapsible" onclick="toggleCollapse(this)">
                        <span class="archive-icon">📦</span>
                        <span class="archive-name">{{fileName}}</span>
                        <span class="archive-info">{{fileSizeFormatted}}</span>
                        <span class="extraction-status {{#if extracted}}extracted{{else}}not-extracted{{/if}}">
                            {{#if extracted}}✓ 已解压{{else}}✗ 未解压{{/if}}
                        </span>
                        <span class="depth-indicator">深度: {{extractionDepth}}</span>
                    </div>
                    <div class="collapsible-content">
                        {{#if extracted}}
                        <div class="archive-stats">
                            📊 包含 {{entryCount}} 个文件
                            {{#if hasNestedFiles}}
                            | 直接文件: {{nestedFiles.length}} 个
                            {{/if}}
                            {{#if hasNestedArchives}}
                            | 嵌套压缩包: {{nestedArchives.length}} 个
                            {{/if}}
                        </div>

                        {{#if hasNestedFiles}}
                        <div class="nested-files">
                            <strong>📄 直接文件:</strong>
                            {{#each nestedFiles}}
                            <div class="nested-file">
                                <span class="file-type-tag">{{fileType}}</span>
                                <strong>{{fileName}}</strong>
                                <span style="margin-left: 10px; color: #7f8c8d;">{{fileSizeFormatted}}</span>
                                <code style="margin-left: 10px; font-size: 0.8em;">{{filePath}}</code>
                            </div>
                            {{/each}}
                        </div>
                        {{/if}}

                        {{#if hasNestedArchives}}
                        <div class="nested-archive">
                            <strong>📦 嵌套压缩包:</strong>
                            {{#each nestedArchives}}
                            <div class="archive-item" style="margin-top: 10px;">
                                <div class="archive-header collapsible" onclick="toggleCollapse(this)">
                                    <span class="archive-icon">📦</span>
                                    <span class="archive-name">{{fileName}}</span>
                                    <span class="archive-info">{{fileSizeFormatted}}</span>
                                    <span class="extraction-status {{#if extracted}}extracted{{else}}not-extracted{{/if}}">
                                        {{#if extracted}}✓ 已解压{{else}}✗ 未解压{{/if}}
                                    </span>
                                    <span class="depth-indicator">深度: {{extractionDepth}}</span>
                                </div>
                                <div class="collapsible-content">
                                    {{#if extracted}}
                                    <div class="archive-stats">
                                        📊 包含 {{entryCount}} 个文件
                                        {{#if hasNestedFiles}}
                                        | 直接文件: {{nestedFiles.length}} 个
                                        {{/if}}
                                    </div>
                                    {{#if hasNestedFiles}}
                                    <div class="nested-files">
                                        <strong>📄 文件:</strong>
                                        {{#each nestedFiles}}
                                        <div class="nested-file">
                                            <span class="file-type-tag">{{fileType}}</span>
                                            <strong>{{fileName}}</strong>
                                            <span style="margin-left: 10px; color: #7f8c8d;">{{fileSizeFormatted}}</span>
                                            <code style="margin-left: 10px; font-size: 0.8em;">{{filePath}}</code>
                                        </div>
                                        {{/each}}
                                    </div>
                                    {{/if}}
                                    {{else}}
                                    <div class="no-data">未解压或解压失败</div>
                                    {{/if}}
                                </div>
                            </div>
                            {{/each}}
                        </div>
                        {{/if}}
                        {{else}}
                        <div class="no-data">压缩包未解压或解压失败</div>
                        {{/if}}
                    </div>
                </div>
                {{/each}}
            </div>
        </div>
        {{/if}}

        <div class="card">
            <h2>📁 所有文件详情（按框架筛选）</h2>
            <div class="search-container">
                <input type="text" class="search-box" placeholder="🔍 搜索所有文件..." onkeyup="searchAllFiles(this.value)">
                <div class="filter-buttons">
                    {{#each filters.allFilesFilterButtons}}
                    <button class="filter-btn {{#if active}}active{{/if}}" onclick="filterAllFiles('{{type}}')">{{label}}</button>
                    {{/each}}
                </div>
            </div>
            <table class="table" id="all-files-table">
                <thead>
                    <tr>
                        <th>文件名</th>
                        <th>框架</th>
                        <th>路径</th>
                        <th>大小</th>
                        <th>来源</th>
                    </tr>
                </thead>
                <tbody>
                    {{#each resourceAnalysis.allFiles}}
                    <tr class="file-row" data-framework="{{frameworkKey}}" data-source="{{#if isNested}}nested{{else}}direct{{/if}}">
                        <td><strong>{{fileName}}</strong></td>
                        <td><span class="file-type-tag">{{frameworksText}}</span></td>
                        <td><code>{{filePath}}</code></td>
                        <td>{{fileSizeFormatted}}</td>
                        <td>{{source}}{{#if parentInfo}} ({{parentInfo}}){{/if}}</td>
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>


        {{/if}}

        <div class="footer">
            <p>报告由 HAP静态分析器 v{{metadata.version}} 生成</p>
            <p>生成时间: {{metadata.analysisDate}}</p>
        </div>
    </div>

    <script>
        function toggleCollapse(element) {
            const content = element.nextElementSibling;
            const isCollapsed = content.classList.contains('collapsed');

            if (isCollapsed) {
                content.classList.remove('collapsed');
                element.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                element.classList.add('collapsed');
            }
        }

        // 搜索功能
        function searchFiles(query) {
            const searchTerm = query.toLowerCase();
            const allFiles = document.querySelectorAll('.nested-file, .archive-item');

            allFiles.forEach(function(file) {
                const text = file.textContent.toLowerCase();
                const shouldShow = text.includes(searchTerm);
                file.style.display = shouldShow ? 'block' : 'none';

                // 如果是搜索结果，展开父级容器
                if (shouldShow && searchTerm) {
                    let parent = file.closest('.collapsible-content');
                    while (parent) {
                        parent.classList.remove('collapsed');
                        const header = parent.previousElementSibling;
                        if (header && header.classList.contains('collapsible')) {
                            header.classList.remove('collapsed');
                        }
                        parent = parent.parentElement.closest('.collapsible-content');
                    }
                }
            });
        }

        // 过滤功能
        function filterFiles(filterType) {
            // 更新按钮状态
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            const allFiles = document.querySelectorAll('.nested-file, .archive-item');

            allFiles.forEach(function(file) {
                let shouldShow = true;

                if (filterType === 'all') {
                    shouldShow = true;
                } else if (filterType === 'extracted') {
                    shouldShow = file.querySelector('.extracted') !== null;
                } else if (filterType === 'not-extracted') {
                    shouldShow = file.querySelector('.not-extracted') !== null;
                } else {
                    // 按文件类型过滤
                    const typeTag = file.querySelector('.file-type-tag');
                    shouldShow = typeTag && typeTag.textContent === filterType;
                }

                file.style.display = shouldShow ? 'block' : 'none';

                // 如果是过滤结果，展开父级容器
                if (shouldShow && filterType !== 'all') {
                    let parent = file.closest('.collapsible-content');
                    while (parent) {
                        parent.classList.remove('collapsed');
                        const header = parent.previousElementSibling;
                        if (header && header.classList.contains('collapsible')) {
                            header.classList.remove('collapsed');
                        }
                        parent = parent.parentElement.closest('.collapsible-content');
                    }
                }
            });
        }

        // 搜索所有文件
        function searchAllFiles(query) {
            const searchTerm = query.toLowerCase();
            const allRows = document.querySelectorAll('#all-files-table .file-row');

            allRows.forEach(function(row) {
                const text = row.textContent.toLowerCase();
                const shouldShow = text.includes(searchTerm);
                row.style.display = shouldShow ? 'table-row' : 'none';
            });
        }

        // 过滤所有文件
        function filterAllFiles(filterType) {
            // 更新按钮状态
            const allFilesCard = document.querySelector('.card:has(#all-files-table)');
            if (allFilesCard) {
                const buttons = allFilesCard.querySelectorAll('.filter-btn');
                buttons.forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
            }

            const allRows = document.querySelectorAll('#all-files-table .file-row');

            allRows.forEach(function(row) {
                let shouldShow = true;

                if (filterType === 'all') {
                    shouldShow = true;
                } else if (filterType === 'nested') {
                    shouldShow = row.dataset.source === 'nested';
                } else {
                    // 按框架过滤
                    // 多框架文件使用逗号分隔，支持包含判断
                    const fw = row.dataset.framework || '';
                    const arr = fw.split(',').map(s => s.trim()).filter(Boolean);
                    shouldShow = arr.includes(filterType);
                }

                row.style.display = shouldShow ? 'table-row' : 'none';
            });
        }

        // 初始化：默认展开第一层，折叠深层嵌套
        document.addEventListener('DOMContentLoaded', function() {
            const nestedArchives = document.querySelectorAll('.nested-archive .collapsible');
            nestedArchives.forEach(function(element) {
                const content = element.nextElementSibling;
                content.classList.add('collapsed');
                element.classList.add('collapsed');
            });
        });
    </script>
</body>
</html>`;
    }
}
