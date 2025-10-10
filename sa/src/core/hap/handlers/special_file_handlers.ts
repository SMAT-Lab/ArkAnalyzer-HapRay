import { HandlerRegistry, type FileHandler, type FileProcessorContext } from '../registry';
import path from 'path';
import { getMimeType } from '../../../config/magic-numbers';
import type { ZipEntry, ZipInstance } from '../../../types/zip-types';
import { isValidZipEntry, getSafeFileSize, safeReadZipEntry, isFileSizeExceeded, MemoryMonitor } from '../../../types/zip-types';
import { FileType } from '../../../config/types';
import { createZipAdapter } from '../../../utils/zip-adapter';
import { ErrorFactory, ErrorUtils } from '../../../errors';
import { getFrameworkPatterns, matchSoPattern, isSystemSo } from '../../../config/framework-patterns';
import { FlutterAnalyzer } from '../analyzers/flutter_analyzer';

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
        if (!isValidZipEntry(zipEntry)) { return; }
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
                if ((error as any)?.code === 'FILE_SIZE_LIMIT_ERROR') {
                    fileSize = zipEntry.compressedSize;
                } else {
                    throw error;
                }
            }
        }
        if (fileSize === 0) { return; }
        const frameworks = identifyFrameworks(fileName);
        const isSystemLib = isSystemSo(fileName);
        
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
            frameworks: frameworks as unknown as Array<any>, 
            fileSize, 
            isSystemLib,
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
    private async performFlutterAnalysis(fileName: string, zip: ZipInstance): Promise<any> {
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
    private async performFlutterFullAnalysis(fileName: string, zip: ZipInstance): Promise<any> {
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
            const tempDir = require('os').tmpdir();
            const fs = require('fs');
            const tempAnalysisDir = fs.mkdtempSync(path.join(tempDir, 'flutter-analysis-'));
            let currentSoTempPath: string | null = null;
            let libflutterTempPath: string | null = null;

            try {
                // 提取当前SO文件到临时文件
                const currentSoEntry = zip.files[currentSoPath];
                if (currentSoEntry) {
                    const currentSoData = await safeReadZipEntry(currentSoEntry, { maxFileSize: 100 * 1024 * 1024, maxMemoryUsage: 200 * 1024 * 1024, largeFileThreshold: 10 * 1024 * 1024 });
                    currentSoTempPath = path.join(tempAnalysisDir, fileName);
                    fs.writeFileSync(currentSoTempPath, currentSoData);
                }

                // 提取libflutter.so到临时文件（如果存在且不是当前文件）
                if (libflutterSoPath && fileName !== 'libflutter.so') {
                    const libflutterEntry = zip.files[libflutterSoPath];
                    if (libflutterEntry) {
                        const libflutterData = await safeReadZipEntry(libflutterEntry, { maxFileSize: 100 * 1024 * 1024, maxMemoryUsage: 200 * 1024 * 1024, largeFileThreshold: 10 * 1024 * 1024 });
                        libflutterTempPath = path.join(tempAnalysisDir, 'libflutter.so');
                        fs.writeFileSync(libflutterTempPath, libflutterData);
                    }
                }

                // 执行Flutter分析
                const analysisResult = await this.flutterAnalyzer.analyzeFlutter(
                    currentSoTempPath!,
                    (fileName === 'libflutter.so' ? currentSoTempPath : libflutterTempPath) || undefined
                );

                console.log(`Flutter analysis completed for ${fileName}: isFlutter=${analysisResult.isFlutter}, packages=${analysisResult.dartPackages.length}, version=${analysisResult.flutterVersion?.hex40 || 'unknown'}`);

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
    if (!isValidZipEntry(zipEntry)) { return; }
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
            if ((error as any)?.code === 'FILE_SIZE_LIMIT_ERROR') {
                fileSize = zipEntry.compressedSize;
            } else {
                throw error;
            }
        }
    }
    if (fileSize === 0) { return; }
    const fileType = HandlerRegistry.getInstance().detectByAll(fileName) as unknown as keyof typeof FileType;
    const mimeType = getMimeType(fileName);
    const base = { filePath, fileName, fileType: fileType as any, fileSize, mimeType, isTextFile: isLikelyTextFile(fileType as any) };
    context.increaseTotalFiles(1);
    context.increaseTotalSize(fileSize);
    context.addResourceFile(base);
    if (fileType === (FileType as any).JS) {
        const jsInfo = { ...base, isMinified: isMinifiedJs(fileName), estimatedLines: estimateJsLines(fileSize) };
        context.addJsFile(jsInfo);
    }
    if ((fileType as any) === (FileType as any).HERMES_BYTECODE) {
        const hermesInfo = { ...base, version: undefined, isValidHermes: true };
        context.addHermesFile(hermesInfo);
    }
    if (isArchive && (fileType as any) === (FileType as any).ZIP) {
        const archiveInfo: any = { ...base, entryCount: 0, extracted: false, extractionDepth: 0, nestedFiles: [], nestedArchives: [] };
        try {
            // 对超大ZIP同样容错：若超过限制，不解压，记录为未解压，仍计入统计
            const limits = context.getFileSizeLimits();
            const metaUncompressed = (zipEntry.uncompressedSize ?? getSafeFileSize(zipEntry)) || 0;
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
        context.addArchiveFile(archiveInfo);
    }
}

function isLikelyTextFile(fileType: keyof typeof FileType): boolean {
    const textTypes: Array<any> = [(FileType as any).JS, (FileType as any).JSON, (FileType as any).XML, (FileType as any).TEXT];
    return textTypes.includes(fileType as any);
}

function isMinifiedJs(fileName: string): boolean {
    return fileName.includes('.min.') || fileName.includes('-min.');
}

function estimateJsLines(fileSize: number): number {
    return Math.max(1, Math.floor(fileSize / 50));
}

async function getFileSizeWithMemoryCheck(zipEntry: ZipEntry, filePath: string, memoryMonitor: MemoryMonitor, limits: import('../../../types/zip-types').FileSizeLimits): Promise<number> {
    const size = getSafeFileSize(zipEntry);
    if (isFileSizeExceeded(size, limits)) {
        throw ErrorFactory.createFileSizeLimitError(`文件大小 ${size} 超过限制 ${limits.maxFileSize}`, size, limits.maxFileSize, filePath);
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
        if (isSystemSo(fileName)) { return ['System']; }
        const frameworkPatterns = getFrameworkPatterns();
        const detected: Array<string> = [];
        for (const [frameworkType, patterns] of Object.entries(frameworkPatterns)) {
            for (const pattern of patterns) {
                if (matchSoPattern(fileName, pattern)) {
                    if (!detected.includes(frameworkType)) { detected.push(frameworkType); }
                    break;
                }
            }
        }
        return detected.length > 0 ? detected : ['Unknown'];
    } catch {
        return ['Unknown'];
    }
}

async function extractAndAnalyzeNestedArchive(nestedZip: import('../../../utils/zip-adapter').JSZipAdapter, archiveInfo: any, depth: number, context: FileProcessorContext): Promise<void> {
    const MAX_DEPTH = 5;
    const nextDepth = depth + 1;
    archiveInfo.extractionDepth = nextDepth;
    context.updateMaxExtractionDepth(nextDepth);
    const entries = Object.entries(nestedZip.files);
    let nestedFilesCount = 0;
    for (const [nestedPath, nestedEntry] of entries) {
        if ((nestedEntry as any).dir) { continue; }
        nestedFilesCount++;
        const fileName = path.basename(nestedPath);
        const size = (nestedEntry as any).uncompressedSize ?? (nestedEntry as any).compressedSize ?? 0;
        const fileType = HandlerRegistry.getInstance().detectByAll(fileName) as unknown as keyof typeof FileType;
        const info: any = {
            filePath: nestedPath,
            fileName,
            fileType: fileType as any,
            fileSize: size,
            mimeType: getMimeType(fileName),
            isTextFile: isLikelyTextFile(fileType as any)
        };
        archiveInfo.nestedFiles.push(info);
        context.addResourceFile(info);
        context.increaseTotalFiles(1);
        context.increaseTotalSize(size);
        if ((fileType as any) === (FileType as any).JS) {
            context.addJsFile({ ...info, isMinified: isMinifiedJs(fileName), estimatedLines: estimateJsLines(size) });
        }
        if ((fileType as any) === (FileType as any).HERMES_BYTECODE) {
            context.addHermesFile({ ...info, version: undefined, isValidHermes: true });
        }
        if (nextDepth < MAX_DEPTH && fileName.toLowerCase().endsWith('.zip')) {
            try {
                const buf = await (nestedEntry as any).async('nodebuffer');
                const deeperZip = await createZipAdapter(Buffer.from(buf));
                const childArchive: any = {
                    ...info,
                    entryCount: 0,
                    extracted: false,
                    extractionDepth: nextDepth,
                    nestedFiles: [],
                    nestedArchives: []
                };
                await extractAndAnalyzeNestedArchive(deeperZip, childArchive, nextDepth, context);
                childArchive.extracted = true;
                archiveInfo.nestedArchives.push(childArchive);
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


