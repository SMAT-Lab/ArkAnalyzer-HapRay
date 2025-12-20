/**
 * ZIP 工具类 - 从 ZIP 中提取文件信息
 */

import type { FileInfo } from '../core/techstack/types';
import JSZip from 'jszip';
import path from 'path';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * ZIP 工具类
 */
export class ZipUtils {
    /**
     * 扫描 ZIP 文件，提取所有文件信息
     *
     * 注意：默认扫描所有文件并加载内容，不做任何过滤。
     * 文件过滤应该由配置文件中的规则决定，而不是在扫描阶段。
     */
    public static async scanZip(zip: JSZip): Promise<Array<FileInfo>> {
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
     * 扫描ZIP文件，支持嵌套压缩包的深度扫描
     */
    public static async scanZipWithNestedSupport(zip: JSZip, basePath = '', depth = 0): Promise<Array<FileInfo>> {
        const fileInfos: Array<FileInfo> = [];

        const maxDepth = 10; // 最大嵌套深度，防止无限递归
        if (depth > maxDepth) {
            logger.warn(`Maximum archive depth (${maxDepth}) reached, skipping deeper archives`);
            return fileInfos;
        }

        for (const [relativePath, zipEntry] of Object.entries(zip.files)) {
            if (zipEntry.dir) {
                continue; // 跳过目录
            }

            const fullPath = basePath ? path.posix.join(basePath, relativePath) : relativePath;
            const fileName = path.posix.basename(relativePath);
            const folder = path.posix.dirname(relativePath);
            // skip armeabi-v7a and x86_64 folders
            if (folder === 'libs/armeabi-v7a' || folder === 'libs/x86_64') {
                continue;
            }
            
            try {
                const content = await zipEntry.async('nodebuffer');
                const fileSize = content.length;

                // 检查是否为压缩包
                const archiveType = this.detectArchiveType(fileName, content);
                const isArchive = archiveType !== null;

                // 添加当前文件信息
                fileInfos.push({
                    folder,
                    file: fileName,
                    path: fullPath,
                    size: fileSize,
                    content: content,
                    lastModified: zipEntry.date
                });

                // 如果是压缩包，递归扫描其内容
                if (isArchive && archiveType) {
                    try {
                        const nestedZip = await JSZip.loadAsync(content);
                        const nestedFiles = await this.scanZipWithNestedSupport(nestedZip, fullPath, depth + 1);
                        fileInfos.push(...nestedFiles);
                    } catch (error) {
                        logger.warn(`Failed to scan nested archive ${fullPath}: ${error}`);
                    }
                }
            } catch (error) {
                logger.warn(`Failed to process file ${fullPath}: ${error}`);
            }
        }

        return fileInfos;
    }

    /**
     * 检测文件是否为压缩包
     */
    public static detectArchiveType(fileName: string, content: Buffer): string | null {
        const ext = fileName.toLowerCase().split('.').pop();
        
        // 检查文件扩展名
        if (['zip', 'jar', 'war', 'ear', 'hap'].includes(ext ?? '')) {
            return 'zip';
        }
        
        // 检查文件头
        if (content.length >= 4) {
            const header = content.subarray(0, 4);
            
            // ZIP 文件头: 50 4B 03 04 或 50 4B 05 06 或 50 4B 07 08
            if (header[0] === 0x50 && header[1] === 0x4B) {
                if (header[2] === 0x03 && header[3] === 0x04) {return 'zip';} // 标准ZIP
                if (header[2] === 0x05 && header[3] === 0x06) {return 'zip';} // 空ZIP
                if (header[2] === 0x07 && header[3] === 0x08) {return 'zip';} // ZIP64
            }
        }
        
        return null;
    }

    /**
     * 提取单个文件信息
     */
    private static async extractFileInfo(
        filePath: string,
        zipEntry: JSZip.JSZipObject
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

        // 使用实际内容大小
        const fileSize = content ? content.length : 0;

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
        return path.posix.basename(filePath);
    }

    /**
     * 获取文件夹路径
     */
    private static getFolder(filePath: string): string {
        return path.posix.dirname(filePath);
    }
}
