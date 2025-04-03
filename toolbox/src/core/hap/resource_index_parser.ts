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

class BufferHelper {
    private buffer: Buffer;
    private offset: number;

    constructor(buffer: Buffer) {
        this.buffer = buffer;
        this.offset = 0;
    }

    public readInt32(): number {
        let value = this.buffer.readInt32LE(this.offset);
        this.offset += 4;
        return value;
    }

    public readInt16(): number {
        let value = this.buffer.readInt16LE(this.offset);
        this.offset += 2;
        return value;
    }

    public readString(len: number): string {
        let buf = this.buffer.subarray(this.offset, this.offset + len);
        if (buf[buf.length - 1] === 0) {
            buf = buf.subarray(0, buf.length - 1);
        }
        let value = buf.toString('utf8');
        this.offset += len;
        return value;
    }

    public setOffset(offset: number): void {
        this.offset = offset;
    }

    public getOffset(): number {
        return this.offset;
    }
}

enum ResType {
    VALUES = 0,
    ANIMATOR = 1,
    DRAWABLE = 2,
    LAYOUT = 3,
    MENU = 4,
    MIPMAP = 5,
    RAW = 6,
    XML = 7,
    INTEGER = 8,
    STRING = 9,
    STRINGARRAY = 10,
    INTARRAY = 11,
    BOOLEAN = 12,
    DIMEN = 13,
    COLOR = 14,
    ID = 15,
    THEME = 16,
    PLURALS = 17,
    FLOAT = 18,
    MEDIA = 19,
    PROF = 20,
    SVG = 21,
    PATTERN = 22,
    INVALID_RES_TYPE = -1
}

export class ResourceIndexParser {
    bufferHelper: BufferHelper
    stringValueMap: Map<string, string>[];
    constructor(buffer: Buffer) {
        this.bufferHelper = new BufferHelper(buffer);
        this.stringValueMap = [];
        this.loadResourceIndex();
    }

    public getStringValue(key: string): string {
        for (const map of this.stringValueMap) {
            if (map.has(key)) {
                return map.get(key)!;
            }
        }
        return '';
    }

    private loadResourceIndex(): void {
        this.bufferHelper.readString(128);
        this.bufferHelper.readInt32();
        let keyCount = this.bufferHelper.readInt32();
        for (let i = 0; i < keyCount; i++) {
            this.bufferHelper.readString(4);
            let offset = this.bufferHelper.readInt32();
            this.parseIdss(i, offset);
            let keyParamsCount = this.bufferHelper.readInt32();
            for (let j = 0; j < keyParamsCount; j++) {
                this.bufferHelper.readInt32();
                this.bufferHelper.readInt32();
            }
        }
    }

    private parseIdss(idssIdx: number, offset: number): void {
        let back = this.bufferHelper.getOffset();

        this.bufferHelper.setOffset(offset);
        let tag = this.bufferHelper.readString(4);
        if (tag !== 'IDSS') {
            this.bufferHelper.setOffset(back);
            throw new Error('Not found IDSS.');
        }
        this.stringValueMap.push(new Map());
        let count = this.bufferHelper.readInt32();
        for (let i = 0; i < count; i++) {
            let id = this.bufferHelper.readInt32();
            let idOffset = this.bufferHelper.readInt32();
            this.parseResValue(idssIdx, id, idOffset);
        }

        this.bufferHelper.setOffset(back);
    }

    private parseResValue(idssIdx: number, id: number, offset: number): void {
        let back = this.bufferHelper.getOffset();

        this.bufferHelper.setOffset(offset);
        this.bufferHelper.readInt32();
        let resType = this.bufferHelper.readInt32();
        this.bufferHelper.readInt32();
        if (resType === ResType.STRING) {
            let valueLen = this.bufferHelper.readInt16();
            let value = this.bufferHelper.readString(valueLen);
            let nameLen = this.bufferHelper.readInt16();
            let name = this.bufferHelper.readString(nameLen);
            this.stringValueMap[idssIdx].set(name, value);
        }

        this.bufferHelper.setOffset(back);
    }
}