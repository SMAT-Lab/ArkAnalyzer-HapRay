import type { FileType } from '../../../config/types';
import { detectFileTypeByExtension } from '../../../config/magic-numbers';

export class DefaultExtensionHandler {
    public canHandle(fileName: string): boolean {
        // 使用配置文件中的检测函数
        const detectedType = detectFileTypeByExtension(fileName);
        return detectedType !== 'Unknown';
    }

    public detect(fileName: string): FileType {
        // 使用配置文件中的检测函数
        return detectFileTypeByExtension(fileName);
    }
}


