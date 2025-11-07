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

import { describe, it, expect } from 'vitest';
import { JsBeautifier } from '../../src/utils/js_beautifier';

describe('JsBeautifier', () => {
    describe('isJavaScriptContent', () => {
        it('should detect JS file by extension', () => {
            const content = 'console.log("hello");';
            expect(JsBeautifier.isJavaScriptContent(content, 'test.js')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent(content, 'test.mjs')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent(content, 'test.cjs')).toBe(true);
        });

        it('should detect JS content by patterns', () => {
            expect(JsBeautifier.isJavaScriptContent('function test() { return 1; }')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('const x = 10;')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('let y = 20;')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('var z = 30;')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('class MyClass {}')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('import { foo } from "bar";')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('export default function() {}')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('module.exports = {}')).toBe(true);
            expect(JsBeautifier.isJavaScriptContent('const x = () => {}')).toBe(true);
        });

        it('should reject non-JS content', () => {
            expect(JsBeautifier.isJavaScriptContent('Hello World')).toBe(false);
            expect(JsBeautifier.isJavaScriptContent('')).toBe(false);
            expect(JsBeautifier.isJavaScriptContent('   ')).toBe(false);
        });

        it('should handle Buffer input', () => {
            const buffer = Buffer.from('function test() { return 1; }', 'utf-8');
            expect(JsBeautifier.isJavaScriptContent(buffer)).toBe(true);
        });
    });

    describe('isMinified', () => {
        it('should detect minified code', () => {
            const minified = 'function add(a,b){return a+b;}function multiply(x,y){return x*y;}const result=add(5,3);console.log(result);';
            expect(JsBeautifier.isMinified(minified)).toBe(true);
        });

        it('should detect non-minified code', () => {
            const normal = `
function add(a, b) {
    return a + b;
}

function multiply(x, y) {
    return x * y;
}

const result = add(5, 3);
console.log(result);
`;
            expect(JsBeautifier.isMinified(normal)).toBe(false);
        });

        it('should handle empty input', () => {
            expect(JsBeautifier.isMinified('')).toBe(false);
            expect(JsBeautifier.isMinified('   ')).toBe(false);
        });
    });

    describe('beautify', () => {
        it('should beautify minified code', () => {
            const minified = 'function add(a,b){return a+b;}';
            const beautified = JsBeautifier.beautify(minified);
            
            expect(beautified).toContain('function add');
            expect(beautified).toContain('return a + b');
            expect(beautified.split('\n').length).toBeGreaterThan(1);
        });

        it('should handle complex code', () => {
            const code = 'const obj={name:"test",value:123};function process(x){return x*2;}';
            const beautified = JsBeautifier.beautify(code);
            
            expect(beautified).toContain('const obj');
            expect(beautified).toContain('function process');
        });

        it('should preserve code semantics', () => {
            const original = 'function test(a,b){return a+b;}';
            const beautified = JsBeautifier.beautify(original);
            
            // 验证美化后的代码仍然包含关键元素
            expect(beautified).toContain('function test');
            expect(beautified).toContain('return');
        });
    });

    describe('beautifyFile', () => {
        it('should beautify minified JS file', () => {
            // 创建一个足够长的 minified 代码来触发 isMinified 检测
            const minified = 'function add(a,b){return a+b;}function multiply(x,y){return x*y;}const result=add(5,3);console.log(result);function subtract(a,b){return a-b;}function divide(x,y){return x/y;}const obj={name:"test",value:123,items:[1,2,3,4,5]};';
            const result = JsBeautifier.beautifyFile(minified, 'test.js', false);

            expect(result).not.toBeNull();
            expect(result).toContain('function add');
        });

        it('should skip non-minified files', () => {
            const normal = `
function add(a, b) {
    return a + b;
}
`;
            const result = JsBeautifier.beautifyFile(normal, 'test.js', false);
            expect(result).toBeNull();
        });

        it('should force beautify when requested', () => {
            const normal = `
function add(a, b) {
    return a + b;
}
`;
            const result = JsBeautifier.beautifyFile(normal, 'test.js', true);
            expect(result).not.toBeNull();
        });

        it('should return null for non-JS content', () => {
            const text = 'This is not JavaScript code';
            const result = JsBeautifier.beautifyFile(text, 'test.txt', false);
            expect(result).toBeNull();
        });

        it('should handle Buffer input', () => {
            // 创建一个足够长的 minified 代码来触发 isMinified 检测
            const minified = 'function add(a,b){return a+b;}function multiply(x,y){return x*y;}const result=add(5,3);console.log(result);function subtract(a,b){return a-b;}function divide(x,y){return x/y;}const obj={name:"test",value:123,items:[1,2,3,4,5]};';
            const buffer = Buffer.from(minified, 'utf-8');
            const result = JsBeautifier.beautifyFile(buffer, 'test.js', false);

            expect(result).not.toBeNull();
            expect(result).toContain('function add');
        });
    });
});

