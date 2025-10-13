import type {
    SoAnalysisResult,
    ResourceFileInfo,
    ArchiveFileInfo,
    JsFileInfo,
    HermesFileInfo,
    HapStaticAnalysisResult,
} from '../../config/types';
import type { FileType } from '../../config/types';
import type { FileProcessorContext } from './registry';
import type { FileSizeLimits } from '../../types/zip-types';
import { DEFAULT_FILE_SIZE_LIMITS } from '../../types/zip-types';
import { MemoryMonitor } from '../../types/zip-types';

/**
 * FileProcessorContext 的默认实现，聚合各 Handler 产生的数据，便于最终产出分析结果。
 */
export class FileProcessorContextImpl implements FileProcessorContext {
    private readonly soFiles: Array<SoAnalysisResult> = [];
    private readonly detectedFrameworks: Set<string> = new Set<string>();

    private readonly filesByType: Map<keyof typeof FileType, Array<ResourceFileInfo>> = new Map();
    private readonly archiveFiles: Array<ArchiveFileInfo> = [];
    private readonly jsFiles: Array<JsFileInfo> = [];
    private readonly hermesFiles: Array<HermesFileInfo> = [];
    private totalFiles = 0;
    private totalSize = 0;
    private maxExtractionDepth = 0;
    private extractedArchiveCount = 0;

    private readonly memoryMonitor: MemoryMonitor;
    private readonly fileSizeLimits: FileSizeLimits;

    constructor(limits: FileSizeLimits = DEFAULT_FILE_SIZE_LIMITS) {
        this.fileSizeLimits = limits;
        this.memoryMonitor = new MemoryMonitor(limits.maxMemoryUsage);
    }

    // SO
    addSoResult(result: SoAnalysisResult): void {
        this.soFiles.push(result);
    }
    addDetectedFramework(framework: string): void {
        if (framework) {
            this.detectedFrameworks.add(framework);
        }
    }

    // Resource
    addResourceFile(file: ResourceFileInfo): void {
        const key = file.fileType as unknown as keyof typeof FileType;
        if (!this.filesByType.has(key)) {
            this.filesByType.set(key, []);
        }
        this.filesByType.get(key)!.push(file);
    }
    addArchiveFile(file: ArchiveFileInfo): void { this.archiveFiles.push(file); }
    addJsFile(file: JsFileInfo): void { this.jsFiles.push(file); }
    addHermesFile(file: HermesFileInfo): void { this.hermesFiles.push(file); }
    increaseTotalFiles(count: number): void { this.totalFiles += count; }
    increaseTotalSize(size: number): void { this.totalSize += size; }
    updateMaxExtractionDepth(depth: number): void { this.maxExtractionDepth = Math.max(this.maxExtractionDepth, depth); }
    increaseExtractedArchiveCount(): void { this.extractedArchiveCount++; }

    // Utils
    getFileSizeLimits(): FileSizeLimits { return this.fileSizeLimits; }
    getMemoryMonitor(): MemoryMonitor { return this.memoryMonitor; }

    // Builders
    buildSoAnalysis(): HapStaticAnalysisResult['soAnalysis'] {
        return {
            detectedFrameworks: Array.from(this.detectedFrameworks) as unknown as HapStaticAnalysisResult['soAnalysis']['detectedFrameworks'],
            soFiles: this.soFiles,
            totalSoFiles: this.soFiles.length,
        };
    }

    buildResourceAnalysis(): HapStaticAnalysisResult['resourceAnalysis'] {
        return {
            totalFiles: this.totalFiles,
            filesByType: this.filesByType as unknown as Map<FileType, Array<ResourceFileInfo>>,
            archiveFiles: this.archiveFiles,
            jsFiles: this.jsFiles,
            hermesFiles: this.hermesFiles,
            totalSize: this.totalSize,
            maxExtractionDepth: this.maxExtractionDepth,
            extractedArchiveCount: this.extractedArchiveCount,
        };
    }
}


