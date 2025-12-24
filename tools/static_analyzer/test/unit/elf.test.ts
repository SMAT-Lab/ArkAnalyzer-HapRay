import { describe, expect, it } from 'vitest';
import path from 'path';
import fs from 'fs';
import { ElfAnalyzer } from '../../src/core/elf/elf_analyzer';

describe('ElfAnalyzerTest', () => {
    it('extract', async () => {
        let elfAnalyzer = await ElfAnalyzer.getInstance();
        let strings = await elfAnalyzer.strings(path.join(__dirname, '../resources/libflutter.so'), /^[0-9a-fA-F]{40}$/);
        expect(strings[0]).eq('2317265cd53ac33c71f76ecc22cc06d97309b6db');
        expect(strings[1]).eq('274d4c13286757c366db077bdd73bf8d44bba863');
    });

    it('getElfInfo - should extract exports, imports and dependencies', async () => {
        const elfAnalyzer = ElfAnalyzer.getInstance();
        const elfInfo = await elfAnalyzer.getElfInfo(path.join(__dirname, '../resources/libflutter.so'));

        // 验证返回的数据结构
        expect(elfInfo).toBeDefined();
        // nm -D libflutter.so | grep " T " | wc -l 结果为 60
        // 只提取 .dynsym 中的 GLOBAL FUNC 类型符号（与 nm -D | grep " T " 一致）
        expect(elfInfo.exports.length).toBe(60);
        expect(elfInfo.imports).toBeInstanceOf(Array);
        expect(elfInfo.dependencies).toBeInstanceOf(Array);

        // 验证去重功能：exports 和 imports 应该没有重复项
        const exportsSet = new Set(elfInfo.exports);
        const importsSet = new Set(elfInfo.imports);
        expect(exportsSet.size).toBe(60);
        expect(importsSet.size).toBe(elfInfo.imports.length);
    });

    it('getElfInfo - should handle invalid ELF file gracefully', async () => {
        const elfAnalyzer = ElfAnalyzer.getInstance();
        
        // 创建一个临时的无效 ELF 文件
        const invalidPath = path.join(__dirname, '../resources/invalid_elf.so');
        const invalidContent = Buffer.from('This is not a valid ELF file');
        fs.writeFileSync(invalidPath, invalidContent);
        
        try {
            // 对于无效的 ELF 文件，应该返回空数组
            const elfInfo = await elfAnalyzer.getElfInfo(invalidPath);
            
            expect(elfInfo).toBeDefined();
            expect(elfInfo.exports).toEqual([]);
            expect(elfInfo.imports).toEqual([]);
            expect(elfInfo.dependencies).toEqual([]);
        } finally {
            // 清理临时文件
            if (fs.existsSync(invalidPath)) {
                fs.unlinkSync(invalidPath);
            }
        }
    });
});