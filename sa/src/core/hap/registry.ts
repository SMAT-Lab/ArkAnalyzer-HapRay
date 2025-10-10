/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import type { FileType, SoAnalysisResult, ResourceFileInfo, ArchiveFileInfo, JsFileInfo, HermesFileInfo } from '../../config/types';
import type { ZipEntry, ZipInstance, FileSizeLimits } from '../../types/zip-types';

export interface ExtensionHandler {
    canHandle(fileName: string): boolean;
    detect(fileName: string): FileType;
}

export interface MagicHandler {
    canHandle(buffer: Uint8Array): boolean;
    detect(buffer: Uint8Array): FileType;
}

export interface FolderHandler {
    canHandle(filePath: string): boolean;
    detect(filePath: string): FileType;
}

export interface FileProcessorContext {
    // SO accumulation
    addSoResult(result: SoAnalysisResult): void;
    addDetectedFramework(framework: string): void;
    // Resource accumulation
    addResourceFile(file: ResourceFileInfo): void;
    addArchiveFile(file: ArchiveFileInfo): void;
    addJsFile(file: JsFileInfo): void;
    addHermesFile(file: HermesFileInfo): void;
    increaseTotalFiles(count: number): void;
    increaseTotalSize(size: number): void;
    updateMaxExtractionDepth(depth: number): void;
    increaseExtractedArchiveCount(): void;
    // Utilities
    getFileSizeLimits(): FileSizeLimits;
    getMemoryMonitor(): import('../../types/zip-types').MemoryMonitor;
}

export interface FileHandler {
    canHandle(filePath: string): boolean;
    handle(filePath: string, zipEntry: ZipEntry, zip: ZipInstance, context: FileProcessorContext): Promise<void> | void;
}

export interface DirectoryHandler {
    canHandle(dirPath: string): boolean;
    handle(dirPath: string, context: FileProcessorContext): Promise<void> | void;
}

export class HandlerRegistry {
    private static instance: HandlerRegistry | null = null;
    private extensionHandlers: Array<ExtensionHandler> = [];
    private magicHandlers: Array<MagicHandler> = [];
    private folderHandlers: Array<FolderHandler> = [];
    private fileHandlers: Array<FileHandler> = [];
    private directoryHandlers: Array<DirectoryHandler> = [];

    private constructor() {}

    public static getInstance(): HandlerRegistry {
        if (!HandlerRegistry.instance) {
            HandlerRegistry.instance = new HandlerRegistry();
        }
        return HandlerRegistry.instance;
    }

    public registerExtension(handler: ExtensionHandler): void {
        this.extensionHandlers.push(handler);
    }

    public registerMagic(handler: MagicHandler): void {
        this.magicHandlers.push(handler);
    }

    public registerFolder(handler: FolderHandler): void {
        this.folderHandlers.push(handler);
    }

    public registerFile(handler: FileHandler): void {
        this.fileHandlers.push(handler);
    }

    public registerDirectory(handler: DirectoryHandler): void {
        this.directoryHandlers.push(handler);
    }

    public detectByExtension(fileName: string): FileType {
        for (const handler of this.extensionHandlers) {
            if (handler.canHandle(fileName)) {
                return handler.detect(fileName);
            }
        }
        // fall back Unknown by casting name-based handlers to not decide
        return 'Unknown' as unknown as FileType;
    }

    public detectByFolder(filePath: string): FileType {
        for (const handler of this.folderHandlers) {
            if (handler.canHandle(filePath)) {
                return handler.detect(filePath);
            }
        }
        return 'Unknown' as unknown as FileType;
    }

    public detectByMagic(buffer: Uint8Array): FileType {
        for (const handler of this.magicHandlers) {
            if (handler.canHandle(buffer)) {
                return handler.detect(buffer);
            }
        }
        return 'Unknown' as unknown as FileType;
    }

    public detectByAll(filePathOrName: string, buffer?: Uint8Array): FileType {
        // priority: folder -> extension -> magic (if buffer provided)
        const byFolder = this.detectByFolder(filePathOrName);
        if (byFolder !== ('Unknown' as unknown as FileType)) {return byFolder;}

        const byExt = this.detectByExtension(filePathOrName);
        if (byExt !== ('Unknown' as unknown as FileType)) {return byExt;}

        if (buffer) {
            const byMagic = this.detectByMagic(buffer);
            if (byMagic !== ('Unknown' as unknown as FileType)) {return byMagic;}
        }

        return 'Unknown' as unknown as FileType;
    }

    public async dispatchFile(filePath: string, zipEntry: ZipEntry, zip: ZipInstance, context: FileProcessorContext): Promise<void> {
        for (const handler of this.fileHandlers) {
            if (handler.canHandle(filePath)) {
                await handler.handle(filePath, zipEntry, zip, context);
            }
        }
    }

    public async dispatchDirectory(dirPath: string, context: FileProcessorContext): Promise<void> {
        for (const handler of this.directoryHandlers) {
            if (handler.canHandle(dirPath)) {
                await handler.handle(dirPath, context);
            }
        }
    }
}


