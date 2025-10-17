/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import JSZip from 'jszip';
import type { ZipInstance, ZipEntry, ZipFiles } from '../types/zip-types';

/**
 * JSZip对象适配器，将JSZipObject转换为我们的ZipEntry接口
 */
class JSZipEntryAdapter implements ZipEntry {
    private readonly jsZipObject: JSZip.JSZipObject;

    constructor(jsZipObject: JSZip.JSZipObject) {
        this.jsZipObject = jsZipObject;
    }

    get name(): string {
        return this.jsZipObject.name;
    }

    get dir(): boolean {
        return this.jsZipObject.dir;
    }

    get uncompressedSize(): number | undefined {
        // JSZip可能没有这个属性，需要安全访问
        return (this.jsZipObject as JSZip.JSZipObject & { uncompressedSize?: number }).uncompressedSize;
    }

    get compressedSize(): number {
        // JSZip可能没有这个属性，使用默认值
        return getJSZipObjectCompressedSize(this.jsZipObject);
    }

    get date(): Date | undefined {
        return this.jsZipObject.date;
    }

    async async(type: 'nodebuffer'): Promise<Buffer>;
    async async(type: 'string'): Promise<string>;
    async async(type: 'uint8array'): Promise<Uint8Array>;
    async async(type: 'nodebuffer' | 'string' | 'uint8array'): Promise<Buffer | string | Uint8Array> {
        switch (type) {
            case 'nodebuffer':
                return await this.jsZipObject.async('nodebuffer');
            case 'string':
                return await this.jsZipObject.async('string');
            case 'uint8array':
                return await this.jsZipObject.async('uint8array');
            default:
                throw new Error(`Unsupported async type: ${type}`);
        }
    }
}

/**
 * JSZip适配器，将JSZip实例转换为我们的ZipInstance接口
 */
export class JSZipAdapter implements ZipInstance {
    private readonly jsZip: JSZip;
    private _files?: ZipFiles;

    constructor(jsZip: JSZip) {
        this.jsZip = jsZip;
    }

    get files(): ZipFiles {
        if (!this._files) {
            this._files = {};
            for (const [path, jsZipObject] of Object.entries(this.jsZip.files)) {
                this._files[path] = new JSZipEntryAdapter(jsZipObject);
            }
        }
        return this._files;
    }

    async loadAsync(data: Buffer): Promise<ZipInstance> {
        const newJsZip = await JSZip.loadAsync(data);
        return new JSZipAdapter(newJsZip);
    }

    /**
     * 获取原始JSZip实例（用于向后兼容）
     */
    getJSZip(): JSZip {
        return this.jsZip;
    }
}

/**
 * 创建JSZip适配器的工厂函数
 */
export async function createZipAdapter(data: Buffer): Promise<JSZipAdapter> {
    const jsZip = await JSZip.loadAsync(data);
    return new JSZipAdapter(jsZip);
}

/**
 * 从现有JSZip实例创建适配器
 */
export function wrapJSZip(jsZip: JSZip): JSZipAdapter {
    return new JSZipAdapter(jsZip);
}

/**
 * 检查对象是否为有效的JSZip实例
 */
export function isJSZipInstance(obj: unknown): obj is JSZip {
    return obj !== null &&
           typeof obj === 'object' &&
           'loadAsync' in obj &&
           'files' in obj &&
           typeof (obj as Record<string, unknown>).loadAsync === 'function' &&
           typeof (obj as Record<string, unknown>).files === 'object';
}

/**
 * 安全地获取JSZip对象的压缩大小
 */
export function getJSZipObjectCompressedSize(jsZipObject: JSZip.JSZipObject): number {
    // 尝试多种方式获取压缩大小
    const obj = jsZipObject as JSZip.JSZipObject & {
        compressedSize?: number;
        _data?: { compressedSize?: number };
        options?: { compressedSize?: number };
    };

    // 方式1: 直接访问compressedSize属性
    if (typeof obj.compressedSize === 'number') {
        return obj.compressedSize;
    }

    // 方式2: 访问内部_data属性
    if (obj._data && typeof (obj._data as Record<string, unknown>).compressedSize === 'number') {
        return (obj._data as Record<string, unknown>).compressedSize as number;
    }

    // 方式3: 访问内部数据结构
    if (typeof obj.options.compressedSize === 'number') {
        return obj.options.compressedSize;
    }

    // 回退到未压缩大小的估算值
    const uncompressed = getJSZipObjectUncompressedSize(jsZipObject);
    if (typeof uncompressed === 'number' && uncompressed > 0) {
        // 假设压缩率为70%（即压缩后为原大小的70%）
        return Math.floor(uncompressed * 0.7);
    }

    // 最后回退：如果是目录返回0，否则返回一个小的默认值
    return jsZipObject.dir ? 0 : 100;
}

/**
 * 安全地获取JSZip对象的未压缩大小
 */
export function getJSZipObjectUncompressedSize(jsZipObject: JSZip.JSZipObject): number | undefined {
    const obj = jsZipObject as JSZip.JSZipObject & {
        uncompressedSize?: number;
        _data?: { uncompressedSize?: number };
        options?: { uncompressedSize?: number };
    };

    // 方式1: 直接访问uncompressedSize属性
    if (typeof obj.uncompressedSize === 'number') {
        return obj.uncompressedSize;
    }

    // 方式2: 访问内部_data属性
    if (obj._data && typeof (obj._data as Record<string, unknown>).uncompressedSize === 'number') {
        return (obj._data as Record<string, unknown>).uncompressedSize as number;
    }

    // 方式3: 访问内部数据结构
    if (typeof obj.options.uncompressedSize === 'number') {
        return obj.options.uncompressedSize;
    }

    return undefined;
}

/**
 * 增强的JSZip条目适配器，包含更多元数据
 */
export class EnhancedJSZipEntryAdapter extends JSZipEntryAdapter {
    constructor(jsZipObject: JSZip.JSZipObject) {
        super(jsZipObject);
    }

    get compressedSize(): number {
        return getJSZipObjectCompressedSize(this['jsZipObject']);
    }

    get uncompressedSize(): number | undefined {
        return getJSZipObjectUncompressedSize(this['jsZipObject']);
    }

    /**
     * 获取压缩比率
     */
    getCompressionRatio(): number {
        const uncompressed = this.uncompressedSize;
        const compressed = this.compressedSize;
        
        if (!uncompressed || uncompressed === 0) {
            return 0;
        }
        
        return compressed / uncompressed;
    }

    /**
     * 检查文件是否被压缩
     */
    isCompressed(): boolean {
        const ratio = this.getCompressionRatio();
        return ratio > 0 && ratio < 0.95; // 如果压缩比小于95%，认为是压缩的
    }

    /**
     * 获取文件扩展名
     */
    getExtension(): string {
        const lastDotIndex = this.name.lastIndexOf('.');
        return lastDotIndex > 0 ? this.name.substring(lastDotIndex + 1).toLowerCase() : '';
    }

    /**
     * 检查是否为目录
     */
    isDirectory(): boolean {
        return this.dir;
    }

    /**
     * 检查是否为文件
     */
    isFile(): boolean {
        return !this.dir;
    }
}

/**
 * 增强的JSZip适配器
 */
export class EnhancedJSZipAdapter extends JSZipAdapter {
    constructor(jsZip: JSZip) {
        super(jsZip);
    }

    get files(): ZipFiles {
        if (!this['_files']) {
            this['_files'] = {};
            for (const [path, jsZipObject] of Object.entries(this.getJSZip().files)) {
                this['_files'][path] = new EnhancedJSZipEntryAdapter(jsZipObject);
            }
        }
        return this['_files'];
    }

    /**
     * 获取所有文件条目（排除目录）
     */
    getFileEntries(): Array<[string, EnhancedJSZipEntryAdapter]> {
        return Object.entries(this.files)
            .filter(([, entry]) => !entry.dir)
            .map(([path, entry]) => [path, entry as EnhancedJSZipEntryAdapter]);
    }

    /**
     * 获取所有目录条目
     */
    getDirectoryEntries(): Array<[string, EnhancedJSZipEntryAdapter]> {
        return Object.entries(this.files)
            .filter(([, entry]) => entry.dir)
            .map(([path, entry]) => [path, entry as EnhancedJSZipEntryAdapter]);
    }

    /**
     * 按扩展名过滤文件
     */
    getFilesByExtension(extension: string): Array<[string, EnhancedJSZipEntryAdapter]> {
        const ext = extension.toLowerCase();
        return this.getFileEntries()
            .filter(([, entry]) => entry.getExtension() === ext);
    }

    /**
     * 获取总的未压缩大小
     */
    getTotalUncompressedSize(): number {
        return this.getFileEntries()
            .reduce((total, [, entry]) => {
                const size = entry.uncompressedSize ?? 0;
                return total + size;
            }, 0);
    }

    /**
     * 获取总的压缩大小
     */
    getTotalCompressedSize(): number {
        return this.getFileEntries()
            .reduce((total, [, entry]) => {
                return total + entry.compressedSize;
            }, 0);
    }

    /**
     * 获取整体压缩比率
     */
    getOverallCompressionRatio(): number {
        const uncompressed = this.getTotalUncompressedSize();
        const compressed = this.getTotalCompressedSize();
        
        if (uncompressed === 0) {
            return 0;
        }
        
        return compressed / uncompressed;
    }
}

/**
 * 创建增强的JSZip适配器
 */
export async function createEnhancedZipAdapter(data: Buffer): Promise<EnhancedJSZipAdapter> {
    const jsZip = await JSZip.loadAsync(data);
    return new EnhancedJSZipAdapter(jsZip);
}

/**
 * 从现有JSZip实例创建增强适配器
 */
export function wrapJSZipEnhanced(jsZip: JSZip): EnhancedJSZipAdapter {
    return new EnhancedJSZipAdapter(jsZip);
}
