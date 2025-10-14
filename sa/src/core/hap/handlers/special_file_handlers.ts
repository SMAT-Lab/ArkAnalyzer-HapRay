import path from 'path';
import fs from 'fs/promises';
import { js as jsBeautify } from 'js-beautify';
import type { ArchiveFileInfo, ResourceFileInfo, JsFileInfo, HermesFileInfo, FlutterAnalysisResult } from '../../../config/types';
import { getMimeType } from '../../../config/magic-numbers';
import type { ZipEntry, ZipInstance } from '../../../types/zip-types';
import { isValidZipEntry, getSafeFileSize, safeReadZipEntry } from '../../../types/zip-types';
import { createZipAdapter, type JSZipAdapter } from '../../../utils/zip-adapter';
import { getFileSizeWithFallback } from '../../../utils/file-size-helper';
import { withTempDirectory } from '../../../utils/temp-file-manager';
import { ErrorUtils } from '../../../errors';
import { detectFrameworks } from '../../framework/framework-detector';
import { FlutterAnalyzer } from '../analyzers/flutter_analyzer';
import { HandlerRegistry, type FileHandler, type FileProcessorContext } from '../registry';
import { Logger, LOG_MODULE_TYPE } from 'arkanalyzer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export class SoFileHandler implements FileHandler {
    private readonly supportedArchitectures: Array<string> = ['libs/arm64-v8a/', 'libs/arm64/'];
    private readonly flutterAnalyzer: FlutterAnalyzer;

    constructor() {
        this.flutterAnalyzer = FlutterAnalyzer.getInstance();
    }

    public canHandle(filePath: string): boolean {
        return this.supportedArchitectures.some(arch => filePath.startsWith(arch)) && filePath.endsWith('.so');
    }
    public async handle(filePath: string, zipEntry: ZipEntry, zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        // 验证ZIP条目
        if (!isValidZipEntry(zipEntry)) {
            return;
        }

        const fileName = path.basename(filePath);

        // 获取文件大小（使用统一的工具函数）
        const sizeResult = await getFileSizeWithFallback({
            zipEntry,
            filePath,
            memoryMonitor: context.getMemoryMonitor(),
            limits: context.getFileSizeLimits()
        });

        if (sizeResult.size === 0) {
            return;
        }

        // 框架检测（使用统一的检测器）
        const detectionResult = await detectFrameworks(fileName, zipEntry, zip);
        const frameworks = detectionResult.frameworks;

        // Flutter详细分析
        let flutterAnalysisResult = null;
        if (frameworks.includes('Flutter')) {
            try {
                flutterAnalysisResult = await this.performFlutterAnalysis(fileName, zip);
            } catch (error) {
                console.warn(`Failed to perform Flutter analysis for ${fileName}: ${(error as Error).message}`);
            }
        }

        // 构建 KMP 分析详情
        let kmpAnalysisDetail = null;
        if (frameworks.includes('KMP') && detectionResult.kmpMatchedSignatures) {
            kmpAnalysisDetail = {
                isKmp: true,
                matchedSignatures: detectionResult.kmpMatchedSignatures,
                detectionMethod: detectionResult.detectionMethod
            };
        }

        // 添加到上下文
        context.addSoResult({
            filePath,
            fileName,
            frameworks: frameworks as unknown as Array<string>,
            fileSize: sizeResult.size,
            isSystemLib: false,
            flutterAnalysis: flutterAnalysisResult,
            kmpAnalysisDetail
        });

        frameworks.forEach(f => context.addDetectedFramework(f));
    }



    /**
     * 执行Flutter详细分析
     * @param fileName SO文件名
     * @param zip ZIP实例
     * @returns Flutter分析结果
     */
    private async performFlutterAnalysis(fileName: string, zip: ZipInstance): Promise<FlutterAnalysisResult | null> {
        try {
            // 所有Flutter相关的SO文件都进行完整分析（包信息+版本信息）
            return await this.performFlutterFullAnalysis(fileName, zip);
        } catch (error) {
            console.error(`Flutter analysis failed: ${(error as Error).message}`);
            return null;
        }
    }

    /**
     * 执行完整的Flutter分析（分析当前SO文件的包信息和版本信息）
     */
    private async performFlutterFullAnalysis(fileName: string, zip: ZipInstance): Promise<FlutterAnalysisResult | null> {
        try {
            // 查找当前SO文件和libflutter.so
            const currentSoPath = this.findFileInZip(zip, fileName);
            const libflutterSoPath = fileName !== 'libflutter.so'
                ? this.findFileInZip(zip, 'libflutter.so')
                : null;

            if (!currentSoPath) {
                console.warn(`${fileName} not found for Flutter analysis`);
                return null;
            }

            // 使用临时文件管理器（自动清理）
            return await withTempDirectory('flutter-analysis-', async (tempDir) => {
                const limits = {
                    maxFileSize: 100 * 1024 * 1024,
                    maxMemoryUsage: 200 * 1024 * 1024,
                    largeFileThreshold: 10 * 1024 * 1024
                };

                // 提取当前SO文件
                const currentSoEntry = zip.files[currentSoPath];
                const currentSoData = await safeReadZipEntry(currentSoEntry, limits);
                const currentSoFile = tempDir.writeFile(fileName, currentSoData);

                // 提取libflutter.so（如果需要）
                let libflutterPath: string | undefined;
                if (libflutterSoPath) {
                    const libflutterEntry = zip.files[libflutterSoPath];
                    const libflutterData = await safeReadZipEntry(libflutterEntry, limits);
                    const libflutterFile = tempDir.writeFile('libflutter.so', libflutterData);
                    libflutterPath = libflutterFile.path;
                } else if (fileName === 'libflutter.so') {
                    libflutterPath = currentSoFile.path;
                }

                // 执行Flutter分析
                const analysisResult = await this.flutterAnalyzer.analyzeFlutter(
                    currentSoFile.path,
                    libflutterPath
                );

                console.warn(
                    `Flutter analysis completed for ${fileName}: ` +
                    `isFlutter=${analysisResult.isFlutter}, ` +
                    `packages=${analysisResult.dartPackages.length}, ` +
                    `version=${analysisResult.flutterVersion?.hex40 ?? 'unknown'}`
                );

                return analysisResult;
            });

        } catch (error) {
            console.error(`Flutter full analysis failed: ${(error as Error).message}`);
            return null;
        }
    }

    /**
     * 在ZIP中查找文件
     */
    private findFileInZip(zip: ZipInstance, fileName: string): string | null {
        for (const [filePath] of Object.entries(zip.files)) {
            if (path.basename(filePath) === fileName) {
                return filePath;
            }
        }
        return null;
    }


}

export class GenericArchiveFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.zip');
    }
    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, true);
    }
}

export class HermesBytecodeFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.hbc');
    }
    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}

export class JsBundleFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.jsbundle');
    }
    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}

async function processResourceFile(filePath: string, zipEntry: ZipEntry, context: FileProcessorContext, isArchive: boolean): Promise<void> {
    if (!isValidZipEntry(zipEntry)) {
        return;
    }

    const fileName = path.basename(filePath);

    // 获取文件大小（使用统一的工具函数）
    const sizeResult = await getFileSizeWithFallback({
        zipEntry,
        filePath,
        memoryMonitor: context.getMemoryMonitor(),
        limits: context.getFileSizeLimits()
    });

    if (sizeResult.size === 0) {
        return;
    }

    const fileSize = sizeResult.size;
    const fileType = HandlerRegistry.getInstance().detectByAll(fileName);
    const mimeType = getMimeType(fileName);
    const base = { filePath, fileName, fileType, fileSize, mimeType, isTextFile: isLikelyTextFile(fileType) };
    context.increaseTotalFiles(1);
    context.increaseTotalSize(fileSize);
    context.addResourceFile(base);
    if (fileType === 'JS') {
        const jsInfo = { ...base, isMinified: isMinifiedJs(fileName), estimatedLines: estimateJsLines(fileSize) };
        context.addJsFile(jsInfo);
    }
    if (fileType === 'HERMES_BYTECODE') {
        const hermesInfo = { ...base, version: undefined, isValidHermes: true };
        context.addHermesFile(hermesInfo);
    }
    if (isArchive && fileType === 'ZIP') {
        const archiveInfo: Record<string, unknown> = { ...base, entryCount: 0, extracted: false, extractionDepth: 0, nestedFiles: [], nestedArchives: [] };
        try {
            // 对超大ZIP同样容错：若超过限制，不解压，记录为未解压，仍计入统计
            const limits = context.getFileSizeLimits();
            const metaUncompressed = zipEntry.uncompressedSize ?? (getSafeFileSize(zipEntry) || 0);
            if (metaUncompressed > limits.maxFileSize) {
                archiveInfo.extracted = false;
            } else {
                const archiveBuffer = await safeReadZipEntry(zipEntry, limits);
                const nestedZip = await createZipAdapter(Buffer.from(archiveBuffer));
                archiveInfo.extracted = true;
                await extractAndAnalyzeNestedArchive(nestedZip, archiveInfo, 0, context);
            }
        } catch (error) {
            if (ErrorUtils.isMemoryError(error)) { throw error; }
            archiveInfo.extracted = false;
        }
        context.addArchiveFile(archiveInfo as unknown as ArchiveFileInfo);
    }
}

function isLikelyTextFile(fileType: string): boolean {
    const textTypes: Array<string> = ['JS', 'JSON', 'XML', 'TEXT'];
    return textTypes.includes(fileType);
}

function isMinifiedJs(fileName: string): boolean {
    return fileName.includes('.min.') || fileName.includes('-min.');
}

function estimateJsLines(fileSize: number): number {
    return Math.max(1, Math.floor(fileSize / 50));
}



async function extractAndAnalyzeNestedArchive(nestedZip: JSZipAdapter, archiveInfo: Record<string, unknown>, depth: number, context: FileProcessorContext): Promise<void> {
    const MAX_DEPTH = 5;
    const nextDepth = depth + 1;
    archiveInfo.extractionDepth = nextDepth;
    context.updateMaxExtractionDepth(nextDepth);
    const entries = Object.entries(nestedZip.files);
    let nestedFilesCount = 0;
    for (const [nestedPath, nestedEntry] of entries) {
        if ((nestedEntry as unknown as Record<string, unknown>).dir) { continue; }
        nestedFilesCount++;
        const fileName = path.basename(nestedPath);
        const size = (nestedEntry as unknown as Record<string, unknown>).uncompressedSize as number || (nestedEntry as unknown as Record<string, unknown>).compressedSize as number || 0;
        const fileType = HandlerRegistry.getInstance().detectByAll(fileName);
        const info: Record<string, unknown> = {
            filePath: nestedPath,
            fileName,
            fileType,
            fileSize: size,
            mimeType: getMimeType(fileName),
            isTextFile: isLikelyTextFile(fileType)
        };
        (archiveInfo.nestedFiles as Array<unknown>).push(info);
        context.addResourceFile(info as unknown as ResourceFileInfo);
        context.increaseTotalFiles(1);
        context.increaseTotalSize(size);
        if (fileType === 'JS') {
            context.addJsFile({ ...info, isMinified: isMinifiedJs(fileName), estimatedLines: estimateJsLines(size) } as unknown as JsFileInfo);
        }
        if (fileType === 'HERMES_BYTECODE') {
            context.addHermesFile({ ...info, version: undefined, isValidHermes: true } as unknown as HermesFileInfo);
        }
        if (nextDepth < MAX_DEPTH && fileName.toLowerCase().endsWith('.zip')) {
            try {
                const buf = await (nestedEntry as unknown as { async: (format: string) => Promise<Buffer> }).async('nodebuffer');
                const deeperZip = await createZipAdapter(Buffer.from(buf));
                const childArchive: Record<string, unknown> = {
                    ...info,
                    entryCount: 0,
                    extracted: false,
                    extractionDepth: nextDepth,
                    nestedFiles: [],
                    nestedArchives: []
                };
                await extractAndAnalyzeNestedArchive(deeperZip, childArchive, nextDepth, context);
                childArchive.extracted = true;
                (archiveInfo.nestedArchives as Array<unknown>).push(childArchive);
                context.increaseExtractedArchiveCount();
            } catch (e) {
                if (ErrorUtils.isMemoryError(e)) { throw e; }
            }
        }
    }
    archiveInfo.entryCount = nestedFilesCount;
}

/**
 * JS 文件处理器
 * 识别并处理 JavaScript 文件，支持可选的代码美化功能
 */
export class JsFileHandler implements FileHandler {
    private readonly jsExtensions: Array<string> = ['.js', '.mjs', '.cjs'];
    private readonly jsPatterns: Array<RegExp> = [
        /\bfunction\s+\w+\s*\(/,
        /\bconst\s+\w+\s*=/,
        /\blet\s+\w+\s*=/,
        /\bvar\s+\w+\s*=/,
        /=>\s*{/,
        /\bexport\s+(default\s+)?/,
        /\bimport\s+.*\s+from\s+/,
        /\brequire\s*\(/
    ];

    public canHandle(filePath: string): boolean {
        // 首先检查扩展名
        const ext = path.extname(filePath).toLowerCase();
        if (this.jsExtensions.includes(ext)) {
            return true;
        }
        return false;
    }

    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        if (!isValidZipEntry(zipEntry)) {
            return;
        }

        const fileName = path.basename(filePath);
        const sizeResult = await getFileSizeWithFallback({
            zipEntry,
            filePath,
            memoryMonitor: context.getMemoryMonitor(),
            limits: context.getFileSizeLimits()
        });

        if (sizeResult.size === 0) {
            return;
        }

        // 读取文件内容以检测是否为 JS 文件
        let content: string;
        try {
            const buffer = await zipEntry.async('nodebuffer');
            content = buffer.toString('utf8');
        } catch (error) {
            console.warn(`Failed to read JS file ${fileName}: ${(error as Error).message}`);
            return;
        }

        // 如果没有扩展名匹配，检查内容特征
        const ext = path.extname(filePath).toLowerCase();
        if (!this.jsExtensions.includes(ext)) {
            const isJs = this.jsPatterns.some(pattern => pattern.test(content));
            if (!isJs) {
                return; // 不是 JS 文件
            }
        }

        // 检测是否为压缩代码
        const isMinified = this.detectMinified(content);
        const estimatedLines = content.split('\n').length;

        // 构建 JS 文件信息
        const jsFileInfo: JsFileInfo = {
            filePath,
            fileName,
            fileType: 'JS',
            fileSize: sizeResult.size,
            mimeType: 'application/javascript',
            isTextFile: true,
            isMinified,
            estimatedLines
        };

        // 如果启用了美化且代码是压缩的，进行美化
        const options = context.getOptions();
        const beautifyJs = options?.beautifyJs ?? false;
        const outputDir = options?.outputDir;

        if (beautifyJs && isMinified && outputDir) {
            try {
                const beautifiedPath = await this.beautifyAndSave(filePath, content, outputDir);
                jsFileInfo.beautifiedPath = beautifiedPath;
                logger.info(`[JS Handler] Beautified ${fileName} saved to: ${beautifiedPath}`);
            } catch (error) {
                logger.warn(`Failed to beautify JS file ${fileName}: ${(error as Error).message}`);
            }
        }

        // 添加到上下文
        context.addJsFile(jsFileInfo);
    }

    /**
     * 检测 JS 代码是否被压缩
     */
    private detectMinified(content: string): boolean {
        const lines = content.split('\n');

        // 如果只有很少的行数但文件很大，可能是压缩的
        if (lines.length < 10 && content.length > 1000) {
            return true;
        }

        // 计算平均行长度
        const avgLineLength = content.length / lines.length;
        if (avgLineLength > 200) {
            return true; // 平均行长度超过 200 字符，可能是压缩的
        }

        // 检查是否有适当的缩进
        const indentedLines = lines.filter(line => /^\s{2,}/.test(line));
        const indentRatio = indentedLines.length / lines.length;
        if (indentRatio < 0.1) {
            return true; // 缩进行数少于 10%，可能是压缩的
        }

        return false;
    }

    /**
     * 美化 JS 代码并保存到输出目录
     */
    private async beautifyAndSave(filePath: string, content: string, outputDir: string): Promise<string> {
        // 创建 js 子目录（使用绝对路径）
        const absoluteOutputDir = path.isAbsolute(outputDir) ? outputDir : path.resolve(process.cwd(), outputDir);
        const jsDir = path.join(absoluteOutputDir, 'js');
        await fs.mkdir(jsDir, { recursive: true });

        // 美化代码
        const beautified = jsBeautify(content, {
            indent_size: 2,
            indent_char: ' ',
            max_preserve_newlines: 2,
            preserve_newlines: true,
            keep_array_indentation: false,
            break_chained_methods: false,
            brace_style: 'collapse',
            space_before_conditional: true,
            unescape_strings: false,
            jslint_happy: false,
            end_with_newline: true,
            wrap_line_length: 0,
            comma_first: false,
            e4x: false
        });

        // 生成输出文件路径
        const relativePath = filePath.replace(/^\//, '').replace(/\\/g, '_').replace(/\//g, '_');
        const outputPath = path.join(jsDir, relativePath);

        // 保存美化后的文件
        await fs.writeFile(outputPath, beautified, 'utf8');

        return outputPath;
    }
}

export class DefaultResourceFileHandler implements FileHandler {
    public canHandle(_filePath: string): boolean {
        return true; // fallback for any other file types
    }
    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}


