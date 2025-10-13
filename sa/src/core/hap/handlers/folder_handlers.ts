import type { FileType } from '../../../config/types';

export class DefaultFolderHandler {
    public canHandle(filePath: string): boolean {
        return filePath.startsWith('assets/') || filePath.startsWith('resources/');
    }
    public detect(_filePath: string): FileType {
        return 'Unknown' as unknown as FileType;
    }
}


