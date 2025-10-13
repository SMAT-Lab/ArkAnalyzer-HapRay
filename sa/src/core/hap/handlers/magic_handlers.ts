import type { FileType } from '../../../config/types';
import { detectFileTypeByMagic } from '../../../config/magic-numbers';

export class ZipMagicHandler {
    public canHandle(buffer: Uint8Array): boolean {
        // 使用配置文件中的魔术字检测
        const detectedType = detectFileTypeByMagic(Buffer.from(buffer));
        return detectedType !== 'Unknown';
    }
    
    public detect(buffer: Uint8Array): FileType {
        // 使用配置文件中的魔术字检测
        return detectFileTypeByMagic(Buffer.from(buffer));
    }
}


