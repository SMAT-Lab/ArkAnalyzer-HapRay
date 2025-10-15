/**
 * HAP 文件扫描器 - 从 ZIP 中提取文件信息
 */

import type { FileInfo } from '../types';
import type { ZipInstance, ZipEntry } from '../../../types/zip-types';
import { getSafeFileSize } from '../../../types/zip-types';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * HAP 文件扫描器
 */
export class HapFileScanner {
    /**
     * 扫描 ZIP 文件，提取所有文件信息
     *
     * 注意：默认扫描所有文件并加载内容，不做任何过滤。
     * 文件过滤应该由配置文件中的规则决定，而不是在扫描阶段。
     */
    public static async scanZip(zip: ZipInstance): Promise<Array<FileInfo>> {
        const fileInfos: Array<FileInfo> = [];

        for (const [filePath, zipEntry] of Object.entries(zip.files)) {
            // 跳过目录
            if (zipEntry.dir) {
                continue;
            }

            try {
                const fileInfo = await this.extractFileInfo(filePath, zipEntry);
                fileInfos.push(fileInfo);
            } catch (error) {
                logger.warn(`Failed to extract file info for ${filePath}:`, error);
            }
        }

        logger.info(`Scanned ${fileInfos.length} files from ZIP`);
        return fileInfos;
    }

    /**
     * 提取单个文件信息
     */
    private static async extractFileInfo(
        filePath: string,
        zipEntry: ZipEntry
    ): Promise<FileInfo> {
        const fileName = this.getFileName(filePath);
        const folder = this.getFolder(filePath);

        // 加载文件内容
        let content: Buffer | undefined;
        try {
            content = await zipEntry.async('nodebuffer');
        } catch (error) {
            logger.warn(`Failed to load content for ${filePath}:`, error);
        }

        // 使用实际内容大小，如果加载失败则使用 ZIP 元数据
        const fileSize = content ? content.length : getSafeFileSize(zipEntry);

        return {
            folder,
            file: fileName,
            path: filePath,
            size: fileSize,
            content,
            lastModified: zipEntry.date
        };
    }

    /**
     * 获取文件名
     */
    private static getFileName(filePath: string): string {
        const parts = filePath.split('/');
        return parts[parts.length - 1];
    }

    /**
     * 获取文件夹路径
     */
    private static getFolder(filePath: string): string {
        const parts = filePath.split('/');
        parts.pop(); // 移除文件名
        return parts.join('/');
    }

    /**
     * 创建 SO 文件过滤器
     */
    public static createSoFileFilter(): (fileName: string) => boolean {
        return (fileName: string) => fileName.endsWith('.so');
    }

    /**
     * 按文件类型分组
     */
    public static groupByType(fileInfos: Array<FileInfo>): Map<string, Array<FileInfo>> {
        const groups = new Map<string, Array<FileInfo>>();

        for (const fileInfo of fileInfos) {
            const ext = this.getExtension(fileInfo.file);
            const type = ext ?? 'unknown';

            if (!groups.has(type)) {
                groups.set(type, []);
            }

            groups.get(type)!.push(fileInfo);
        }

        return groups;
    }

    /**
     * 获取文件扩展名
     */
    private static getExtension(fileName: string): string | null {
        const parts = fileName.split('.');
        if (parts.length > 1) {
            return '.' + parts[parts.length - 1];
        }
        return null;
    }

    /**
     * 统计文件信息
     */
    public static getStats(fileInfos: Array<FileInfo>): {
        totalFiles: number;
        totalSize: number;
        filesByType: Map<string, number>;
        avgFileSize: number;
    } {
        let totalSize = 0;
        const filesByType = new Map<string, number>();

        for (const fileInfo of fileInfos) {
            totalSize += fileInfo.size;

            const ext = this.getExtension(fileInfo.file) ?? 'unknown';
            const count = filesByType.get(ext) ?? 0;
            filesByType.set(ext, count + 1);
        }

        return {
            totalFiles: fileInfos.length,
            totalSize,
            filesByType,
            avgFileSize: fileInfos.length > 0 ? totalSize / fileInfos.length : 0
        };
    }
}

