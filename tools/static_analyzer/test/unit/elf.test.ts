import { describe, expect, it } from 'vitest';
import path from 'path';
import { ElfAnalyzer } from '../../src/core/elf/elf_analyzer';

describe('ElfAnalyzerTest', () => {
    it('extract', async () => {
        let elfAnalyzer = await ElfAnalyzer.getInstance();
        let strings = await elfAnalyzer.strings(path.join(__dirname, '../resources/libflutter.so'), /^[0-9a-fA-F]{40}$/);
        expect(strings[0]).eq('2317265cd53ac33c71f76ecc22cc06d97309b6db');
        expect(strings[1]).eq('274d4c13286757c366db077bdd73bf8d44bba863');
    });
});