/**
 * 结果适配器 - 将新的检测结果转换为简化格式
 */

import type { FileDetectionResult, DetectionResult } from '../types';
import type { SoAnalysisResult } from '../../../config/types';

/**
 * 结果适配器
 */
export class ResultAdapter {
    /**
     * 将文件检测结果转换为 SO 分析结果
     */
    public static toSoAnalysisResult(
        fileDetection: FileDetectionResult
    ): SoAnalysisResult | null {
        // 只处理 SO 文件
        if (!fileDetection.file.endsWith('.so')) {
            return null;
        }

        // 提取技术栈（取第一个检测到的框架）
        const techStack = fileDetection.detections.length > 0
            ? fileDetection.detections[0].techStack
            : 'Unknown';

        // 合并所有元数据
        const metadata = this.mergeMetadata(fileDetection.detections);

        return {
            folder: fileDetection.folder,
            file: fileDetection.file,
            size: fileDetection.size,
            techStack,
            metadata
        };
    }

    /**
     * 批量转换文件检测结果
     */
    public static toSoAnalysisResults(
        fileDetections: Array<FileDetectionResult>,
        baseFolder: string
    ): Array<SoAnalysisResult> {
        const results: Array<SoAnalysisResult> = [];

        for (const fileDetection of fileDetections) {
            const soResult = this.toSoAnalysisResult(fileDetection);
            if (soResult) {
                results.push(soResult);
            }
        }

        return results;
    }

    /**
     * 合并所有检测结果的元数据
     */
    private static mergeMetadata(detections: Array<DetectionResult>): SoAnalysisResult['metadata'] {
        const merged: SoAnalysisResult['metadata'] = {};

        for (const detection of detections) {
            if (detection.metadata) {
                // 合并元数据
                Object.assign(merged, detection.metadata);
            }
        }

        return merged;
    }

    /**
     * 提取所有检测到的框架（去重）
     */
    public static extractAllFrameworks(
        fileDetections: Array<FileDetectionResult>
    ): Array<string> {
        const frameworks = new Set<string>();

        for (const fileDetection of fileDetections) {
            for (const detection of fileDetection.detections) {
                frameworks.add(detection.techStack);
            }
        }

        return Array.from(frameworks);
    }

    /**
     * 统计检测结果
     */
    public static getDetectionStats(fileDetections: Array<FileDetectionResult>): {
        totalFiles: number;
        detectedFiles: number;
        totalDetections: number;
        frameworkCounts: Map<string, number>;
    } {
        const frameworkCounts = new Map<string, number>();
        let detectedFiles = 0;
        let totalDetections = 0;

        for (const fileDetection of fileDetections) {
            if (fileDetection.detections.length > 0) {
                detectedFiles++;
                totalDetections += fileDetection.detections.length;

                for (const detection of fileDetection.detections) {
                    const count = frameworkCounts.get(detection.techStack) || 0;
                    frameworkCounts.set(detection.techStack, count + 1);
                }
            }
        }

        return {
            totalFiles: fileDetections.length,
            detectedFiles,
            totalDetections,
            frameworkCounts
        };
    }
}

