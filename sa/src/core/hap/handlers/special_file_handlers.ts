import { HandlerRegistry, type FileHandler, type FileProcessorContext } from '../registry';
import type {
    ArchiveFileInfo,
    ResourceFileInfo,
    JsFileInfo,
    HermesFileInfo,
    FlutterAnalysisResult,
} from '../../../config/types';
import path from 'path';
import fs from 'fs';
import { getMimeType } from '../../../config/magic-numbers';
import type { FileSizeLimits, ZipEntry, ZipInstance } from '../../../types/zip-types';
import { isValidZipEntry, getSafeFileSize, safeReadZipEntry, isFileSizeExceeded } from '../../../types/zip-types';
import type { MemoryMonitor } from '../../../types/zip-types';
import type { JSZipAdapter } from '../../../utils/zip-adapter';
import { createZipAdapter } from '../../../utils/zip-adapter';
import { ErrorFactory, ErrorUtils } from '../../../errors';
import { getFrameworkPatterns, matchSoPattern } from '../../../config/framework-patterns';
import { FlutterAnalyzer } from '../analyzers/flutter_analyzer';
import { tmpdir } from 'os';

export class SoFileHandler implements FileHandler {
    private readonly supportedArchitectures: Array<string> = ['libs/arm64-v8a/', 'libs/arm64/'];
    private readonly flutterAnalyzer: FlutterAnalyzer;

    constructor() {
        this.flutterAnalyzer = FlutterAnalyzer.getInstance();
    }

    public canHandle(filePath: string): boolean {
        return this.supportedArchitectures.some((arch) => filePath.startsWith(arch)) && filePath.endsWith('.so');
    }
    public async handle(
        filePath: string,
        zipEntry: ZipEntry,
        zip: ZipInstance,
        context: FileProcessorContext
    ): Promise<void> {
        if (!isValidZipEntry(zipEntry)) {
            return;
        }
        const fileName = path.basename(filePath);
        let fileSize = 0;
        // 优先使用元数据判断是否越界，越界则直接采用压缩大小估算，避免抛错
        const limits = context.getFileSizeLimits();
        const metaUncompressed = (zipEntry.uncompressedSize ?? getSafeFileSize(zipEntry)) || 0;
        if (metaUncompressed > limits.maxFileSize) {
            fileSize = zipEntry.compressedSize;
        } else {
            try {
                fileSize = await getFileSizeWithMemoryCheck(zipEntry, filePath, context.getMemoryMonitor(), limits);
            } catch (error) {
                if ((error as Error & { code?: string }).code === 'FILE_SIZE_LIMIT_ERROR') {
                    fileSize = zipEntry.compressedSize;
                } else {
                    throw error;
                }
            }
        }
        if (fileSize === 0) {
            return;
        }
        let frameworks = identifyFrameworks(fileName);

        // 如果是Unknown框架，尝试进行深度检测（KMP）
        if (frameworks.includes('Unknown')) {
            const isKmp = await this.detectKmpFramework(filePath, zipEntry, zip);
            if (isKmp) {
                frameworks = frameworks.filter((f) => f !== 'Unknown');
                frameworks.push('KMP');
            }
        }

        // 如果是Flutter相关的SO文件，进行详细分析
        let flutterAnalysisResult = null;
        if (frameworks.includes('Flutter')) {
            try {
                flutterAnalysisResult = await this.performFlutterAnalysis(fileName, zip);
            } catch (error) {
                console.warn(`Failed to perform Flutter analysis for ${fileName}: ${(error as Error).message}`);
            }
        }

        context.addSoResult({
            filePath,
            fileName,
            frameworks: frameworks as unknown as Array<string>,
            fileSize,
            isSystemLib: false,
            flutterAnalysis: flutterAnalysisResult,
        });
        frameworks.forEach((f) => context.addDetectedFramework(f));
    }

    /**
     * 检测SO文件是否为KMP框架
     * @param filePath SO文件路径
     * @param zipEntry ZIP条目
     * @param zip ZIP实例
     * @returns 是否为KMP框架
     */
    /**
     * 使用流式读取检测 KMP 框架特征
     * 优化：分块读取，找到特征后立即停止
     */
    private async detectKmpFramework(filePath: string, zipEntry: ZipEntry, _zip: ZipInstance): Promise<boolean> {
        try {
            const fileName = path.basename(filePath);

            // Kotlin 特征模式（Buffer 格式）
            const kotlinPatterns = [
                Buffer.from('Kotlin', 'utf8'),
                Buffer.from('kotlin', 'utf8'),
                Buffer.from('kfun:', 'utf8'),
                Buffer.from('KOTLIN_NATIVE', 'utf8'),
            ];

            // 流式读取：分块处理，避免一次性加载大文件到内存
            const chunkSize = 1 * 1024 * 1024; // 每次读取 1MB
            const maxChunks = 50; // 最多读取 50MB（50 个块）

            // 使用 JSZip 的 async 方法获取完整 buffer，然后分块处理
            // 注意：JSZip 不支持真正的流式读取，但我们可以分块搜索
            const fileSize = zipEntry.uncompressedSize ?? zipEntry.compressedSize ?? 0;

            // 对于小文件（<10MB），直接读取全部
            if (fileSize < 10 * 1024 * 1024) {
                try {
                    const buffer = await zipEntry.async('nodebuffer');

                    // 在 buffer 中搜索 Kotlin 特征
                    for (const pattern of kotlinPatterns) {
                        if (buffer.indexOf(pattern) !== -1) {
                            return true;
                        }
                    }
                    return false;
                } catch (error) {
                    console.warn(`KMP detection failed for ${fileName}:`, error);
                    return false;
                }
            }

            // 对于大文件（>=10MB），使用分块读取策略
            // 由于 JSZip 不支持真正的流式读取，我们需要读取整个文件
            // 但可以在读取后分块搜索，找到后立即返回
            try {
                const buffer = await zipEntry.async('nodebuffer');

                // 分块搜索，找到后立即停止
                const totalChunks = Math.min(Math.ceil(buffer.length / chunkSize), maxChunks);

                for (let i = 0; i < totalChunks; i++) {
                    const start = i * chunkSize;
                    const end = Math.min(start + chunkSize, buffer.length);
                    const chunk = buffer.subarray(start, end);

                    // 在当前块中搜索 Kotlin 特征
                    for (const pattern of kotlinPatterns) {
                        if (chunk.indexOf(pattern) !== -1) {
                            return true;
                        }
                    }

                    // 检查跨块边界的情况：保留最后几个字节到下一块
                    // 避免特征字符串被分割到两个块中
                    if (i < totalChunks - 1) {
                        const maxPatternLength = Math.max(...kotlinPatterns.map((p) => p.length));
                        const overlap = buffer.subarray(Math.max(start, end - maxPatternLength), end);
                        const nextChunkStart = buffer.subarray(end, Math.min(end + maxPatternLength, buffer.length));
                        const boundary = Buffer.concat([overlap, nextChunkStart]);

                        for (const pattern of kotlinPatterns) {
                            if (boundary.indexOf(pattern) !== -1) {
                                return true;
                            }
                        }
                    }
                }

                return false;
            } catch (error) {
                console.warn(`KMP detection failed for ${fileName}:`, error);
                return false;
            }
        } catch (error) {
            console.warn(`KMP framework detection failed for ${filePath}:`, error);
            return false;
        }
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
    private async performFlutterFullAnalysis(
        fileName: string,
        zip: ZipInstance
    ): Promise<FlutterAnalysisResult | null> {
        try {
            // 查找当前SO文件和libflutter.so
            let currentSoPath: string | null = null;
            let libflutterSoPath: string | null = null;

            for (const [filePath] of Object.entries(zip.files)) {
                const basename = path.basename(filePath);
                if (basename === fileName) {
                    currentSoPath = filePath;
                } else if (basename === 'libflutter.so') {
                    libflutterSoPath = filePath;
                }
            }

            if (!currentSoPath) {
                console.warn(`${fileName} not found for Flutter analysis`);
                return null;
            }

            // 创建临时文件进行分析
            const tempDir = tmpdir();
            const tempAnalysisDir = fs.mkdtempSync(path.join(tempDir, 'flutter-analysis-'));
            let currentSoTempPath: string | null = null;
            let libflutterTempPath: string | null = null;

            try {
                // 提取当前SO文件到临时文件
                const currentSoEntry = zip.files[currentSoPath];
                const currentSoData = await safeReadZipEntry(currentSoEntry, {
                    maxFileSize: 100 * 1024 * 1024,
                    maxMemoryUsage: 200 * 1024 * 1024,
                    largeFileThreshold: 10 * 1024 * 1024,
                });
                currentSoTempPath = path.join(tempAnalysisDir, fileName);
                fs.writeFileSync(currentSoTempPath, currentSoData);

                // 提取libflutter.so到临时文件（如果存在且不是当前文件）
                if (libflutterSoPath && fileName !== 'libflutter.so') {
                    const libflutterEntry = zip.files[libflutterSoPath];
                    const libflutterData = await safeReadZipEntry(libflutterEntry, {
                        maxFileSize: 100 * 1024 * 1024,
                        maxMemoryUsage: 200 * 1024 * 1024,
                        largeFileThreshold: 10 * 1024 * 1024,
                    });
                    libflutterTempPath = path.join(tempAnalysisDir, 'libflutter.so');
                    fs.writeFileSync(libflutterTempPath, libflutterData);
                }

                // 执行Flutter分析
                if (!currentSoTempPath) {
                    console.warn('Temp path for current SO not prepared');
                    return null;
                }
                const libflutterPath =
                    (fileName === 'libflutter.so' ? currentSoTempPath : libflutterTempPath) ?? undefined;
                const analysisResult = await this.flutterAnalyzer.analyzeFlutter(currentSoTempPath, libflutterPath);

                console.warn(
                    `Flutter analysis completed for ${fileName}: isFlutter=${analysisResult.isFlutter}, packages=${
                        analysisResult.dartPackages.length
                    }, version=${analysisResult.flutterVersion?.hex40 ?? 'unknown'}`
                );

                return analysisResult;
            } finally {
                // 清理临时文件
                try {
                    if (fs.existsSync(tempAnalysisDir)) {
                        fs.rmSync(tempAnalysisDir, { recursive: true, force: true });
                    }
                } catch (cleanupError) {
                    console.warn(`Failed to cleanup temp directory ${tempAnalysisDir}:`, cleanupError);
                }
            }
        } catch (error) {
            console.error(`Flutter full analysis failed: ${(error as Error).message}`);
            return null;
        }
    }
}

export class GenericArchiveFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.zip');
    }
    public async handle(
        filePath: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance,
        context: FileProcessorContext
    ): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, true);
    }
}

export class HermesBytecodeFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.hbc');
    }
    public async handle(
        filePath: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance,
        context: FileProcessorContext
    ): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}

export class JsBundleFileHandler implements FileHandler {
    public canHandle(filePath: string): boolean {
        return filePath.toLowerCase().endsWith('.jsbundle');
    }
    public async handle(
        filePath: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance,
        context: FileProcessorContext
    ): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}

async function processResourceFile(
    filePath: string,
    zipEntry: ZipEntry,
    context: FileProcessorContext,
    isArchive: boolean
): Promise<void> {
    if (!isValidZipEntry(zipEntry)) {
        return;
    }
    const fileName = path.basename(filePath);
    let fileSize = 0;
    const limits = context.getFileSizeLimits();
    const metaUncompressed = (zipEntry.uncompressedSize ?? getSafeFileSize(zipEntry)) || 0;
    if (metaUncompressed > limits.maxFileSize) {
        fileSize = zipEntry.compressedSize;
    } else {
        try {
            fileSize = await getFileSizeWithMemoryCheck(zipEntry, filePath, context.getMemoryMonitor(), limits);
        } catch (error) {
            if ((error as Error & { code?: string }).code === 'FILE_SIZE_LIMIT_ERROR') {
                fileSize = zipEntry.compressedSize;
            } else {
                throw error;
            }
        }
    }
    if (fileSize === 0) {
        return;
    }
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
        const archiveInfo: Record<string, unknown> = {
            ...base,
            entryCount: 0,
            extracted: false,
            extractionDepth: 0,
            nestedFiles: [],
            nestedArchives: [],
        };
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
            if (ErrorUtils.isMemoryError(error)) {
                throw error;
            }
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

async function getFileSizeWithMemoryCheck(
    zipEntry: ZipEntry,
    filePath: string,
    memoryMonitor: MemoryMonitor,
    limits: FileSizeLimits
): Promise<number> {
    const size = getSafeFileSize(zipEntry);
    if (isFileSizeExceeded(size, limits)) {
        throw ErrorFactory.createFileSizeLimitError(
            `文件大小 ${size} 超过限制 ${limits.maxFileSize}`,
            size,
            limits.maxFileSize,
            filePath
        );
    }
    if (size === 0 && zipEntry.uncompressedSize === undefined) {
        if (!memoryMonitor.canAllocate(zipEntry.compressedSize)) {
            throw ErrorFactory.createOutOfMemoryError(`内存不足，无法处理文件：${filePath}`, zipEntry.compressedSize);
        }
        memoryMonitor.allocate(zipEntry.compressedSize);
        try {
            const content = await safeReadZipEntry(zipEntry, limits);
            return content.length;
        } finally {
            memoryMonitor.deallocate(zipEntry.compressedSize);
        }
    }
    return size;
}

function identifyFrameworks(fileName: string): Array<string> {
    try {
        const frameworkPatterns = getFrameworkPatterns();
        const detected: Array<string> = [];
        for (const [frameworkType, patterns] of Object.entries(frameworkPatterns)) {
            for (const pattern of patterns) {
                if (matchSoPattern(fileName, pattern)) {
                    if (!detected.includes(frameworkType)) {
                        detected.push(frameworkType);
                    }
                    break;
                }
            }
        }
        return detected.length > 0 ? detected : ['Unknown'];
    } catch {
        return ['Unknown'];
    }
}

async function extractAndAnalyzeNestedArchive(
    nestedZip: JSZipAdapter,
    archiveInfo: Record<string, unknown>,
    depth: number,
    context: FileProcessorContext
): Promise<void> {
    const MAX_DEPTH = 5;
    const nextDepth = depth + 1;
    archiveInfo.extractionDepth = nextDepth;
    context.updateMaxExtractionDepth(nextDepth);
    const entries = Object.entries(nestedZip.files);
    let nestedFilesCount = 0;
    for (const [nestedPath, nestedEntry] of entries) {
        if ((nestedEntry as unknown as Record<string, unknown>).dir) {
            continue;
        }
        nestedFilesCount++;
        const fileName = path.basename(nestedPath);
        const size =
            ((nestedEntry as unknown as Record<string, unknown>).uncompressedSize as number) ||
            ((nestedEntry as unknown as Record<string, unknown>).compressedSize as number) ||
            0;
        const fileType = HandlerRegistry.getInstance().detectByAll(fileName);
        const info: Record<string, unknown> = {
            filePath: nestedPath,
            fileName,
            fileType,
            fileSize: size,
            mimeType: getMimeType(fileName),
            isTextFile: isLikelyTextFile(fileType),
        };
        (archiveInfo.nestedFiles as Array<unknown>).push(info);
        context.addResourceFile(info as unknown as ResourceFileInfo);
        context.increaseTotalFiles(1);
        context.increaseTotalSize(size);
        if (fileType === 'JS') {
            context.addJsFile({
                ...info,
                isMinified: isMinifiedJs(fileName),
                estimatedLines: estimateJsLines(size),
            } as unknown as JsFileInfo);
        }
        if (fileType === 'HERMES_BYTECODE') {
            context.addHermesFile({ ...info, version: undefined, isValidHermes: true } as unknown as HermesFileInfo);
        }
        if (nextDepth < MAX_DEPTH && fileName.toLowerCase().endsWith('.zip')) {
            try {
                const buf = await (nestedEntry as unknown as { async: (format: string) => Promise<Buffer> }).async(
                    'nodebuffer'
                );
                const deeperZip = await createZipAdapter(Buffer.from(buf));
                const childArchive: Record<string, unknown> = {
                    ...info,
                    entryCount: 0,
                    extracted: false,
                    extractionDepth: nextDepth,
                    nestedFiles: [],
                    nestedArchives: [],
                };
                await extractAndAnalyzeNestedArchive(deeperZip, childArchive, nextDepth, context);
                childArchive.extracted = true;
                (archiveInfo.nestedArchives as Array<unknown>).push(childArchive);
                context.increaseExtractedArchiveCount();
            } catch (e) {
                if (ErrorUtils.isMemoryError(e)) {
                    throw e;
                }
            }
        }
    }
    archiveInfo.entryCount = nestedFilesCount;
}

export class DefaultResourceFileHandler implements FileHandler {
    public canHandle(_filePath: string): boolean {
        return true; // fallback for any other file types
    }
    public async handle(
        filePath: string,
        zipEntry: ZipEntry,
        _zip: ZipInstance,
        context: FileProcessorContext
    ): Promise<void> {
        await processResourceFile(filePath, zipEntry, context, false);
    }
}
