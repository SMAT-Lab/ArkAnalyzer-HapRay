import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';
import * as fs from 'fs';
import * as path from 'path';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export function getFirstLevelFolders(dirPath: string): string[] {
    try {
        // 读取指定目录下的所有文件和文件夹
        const items = fs.readdirSync(dirPath);
        const folders: string[] = [];

        for (const item of items) {
            // 拼接完整路径
            const itemPath = path.join(dirPath, item);
            // 检查该路径是否为目录
            const stat = fs.statSync(itemPath);
            if (stat.isDirectory() && item!=='report') {
                logger.info('Round path: '+ itemPath);
                folders.push(itemPath);
            }
        }

        return folders;
    } catch (error) {
        logger.error('Access directory :' + dirPath, error);
        return [];
    }
}

// 使用示例
// const targetPath = 'D:/github/ArkAnalyzer-HapRay/perf_testing/reports/20250430091811'; // 替换为你要查询的路径
// const firstLevelFolders = getFirstLevelFolders(targetPath);
// console.log('第一层的所有文件夹:', firstLevelFolders);
    