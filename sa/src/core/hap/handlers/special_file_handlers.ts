import path from 'path';
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

        // 添加到上下文
        context.addSoResult({
            filePath,
            fileName,
            frameworks: frameworks as unknown as Array<string>,
            fileSize: sizeResult.size,
            isSystemLib: false,
            flutterAnalysis: flutterAnalysisResult
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

export class DefaultResourceFileHandler implements FileHandler {
    public canHandle(_filePath: string): boolean {
        return true; // fallback for any other file types
    }
    public async handle(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}


