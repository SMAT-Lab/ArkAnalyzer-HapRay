import { describe, it, expect, beforeEach } from 'vitest';
import { ResourceAnalyzer } from '../../../src/analyzers/resource-analyzer';
import { FileType } from '../../../src/types';
import { createEnhancedZipAdapter } from '../../../src/utils/zip-adapter';
import { ResourceAnalysisError, ErrorUtils } from '../../../src/errors';
import JSZip from 'jszip';

describe('ResourceAnalyzer', () => {
    let analyzer: ResourceAnalyzer;

    beforeEach(() => {
        analyzer = new ResourceAnalyzer();
    });

    describe('analyzeResourcesFromZip', () => {
        it('should handle empty ZIP', async () => {
            const zip = new JSZip();
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.totalFiles).toBe(0);
            expect(result.totalSize).toBe(0);
            expect(result.filesByType.size).toBe(0);
        });

        it('should analyze JavaScript files correctly', async () => {
            const zip = new JSZip();
            zip.file('assets/js/bundle.js', 'console.log("Hello World");');
            zip.file('assets/js/vendor.min.js', 'var a=1;');
            
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.totalFiles).toBe(2);
            expect(result.jsFiles).toHaveLength(2);
            
            const bundleJs = result.jsFiles.find(f => f.fileName === 'bundle.js');
            const vendorJs = result.jsFiles.find(f => f.fileName === 'vendor.min.js');
            
            expect(bundleJs?.isMinified).toBe(false);
            expect(vendorJs?.isMinified).toBe(true);
        });

        it('should skip SO files in libs directory', async () => {
            const zip = new JSZip();
            zip.file('libs/arm64-v8a/libtest.so', Buffer.alloc(1024));
            zip.file('assets/js/bundle.js', 'console.log("test");');
            
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.totalFiles).toBe(1);
            expect(result.jsFiles).toHaveLength(1);
            expect(result.jsFiles[0].fileName).toBe('bundle.js');
        });

        it('should handle invalid ZIP gracefully', async () => {
            await expect(
                analyzer.analyzeResourcesFromZip(null as any)
            ).rejects.toThrow(ResourceAnalysisError);
        });

        it('should categorize files by type', async () => {
            const zip = new JSZip();
            zip.file('assets/images/icon.png', Buffer.alloc(512));
            zip.file('assets/data/config.json', '{"test": true}');
            zip.file('assets/layouts/main.xml', '<root></root>');
            
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.filesByType.get(FileType.PNG)).toHaveLength(1);
            expect(result.filesByType.get(FileType.JSON)).toHaveLength(1);
            expect(result.filesByType.get(FileType.XML)).toHaveLength(1);
        });

        it('should handle large files within limits', async () => {
            const zip = new JSZip();
            const largeContent = Buffer.alloc(1024 * 1024 + 100); // 1MB + 100 bytes
            zip.file('large-file.txt', largeContent);

            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.totalFiles).toBe(1);
            expect(result.totalSize).toBeGreaterThan(1024 * 1024);
        });

        it('should estimate JS file lines correctly', async () => {
            const zip = new JSZip();
            const jsContent = 'console.log("line1");\nconsole.log("line2");\nconsole.log("line3");';
            zip.file('test.js', jsContent);
            
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));

            const result = await analyzer.analyzeResourcesFromZip(adapter);

            expect(result.jsFiles).toHaveLength(1);
            expect(result.jsFiles[0].estimatedLines).toBeGreaterThan(0);
        });
    });

    describe('error handling', () => {
        it('should throw ResourceAnalysisError for invalid input', async () => {
            try {
                await analyzer.analyzeResourcesFromZip(null as any);
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect(ErrorUtils.isAnalysisError(error)).toBe(true);
                expect(error).toBeInstanceOf(ResourceAnalysisError);
            }
        });

        it('should handle file processing errors gracefully', async () => {
            const zip = new JSZip();
            zip.file('valid-file.txt', 'content');
            
            const adapter = await createEnhancedZipAdapter(await zip.generateAsync({ type: 'nodebuffer' }));
            
            // Mock a file entry to cause an error
            const mockEntry = {
                name: 'error-file.txt',
                dir: false,
                uncompressedSize: undefined,
                compressedSize: 0,
                async: () => Promise.reject(new Error('Mock error'))
            };
            
            adapter.files['error-file.txt'] = mockEntry as any;

            // Should not throw, but should log warnings
            const result = await analyzer.analyzeResourcesFromZip(adapter);
            
            // Should still process the valid file
            expect(result.totalFiles).toBe(1);
        });
    });
});
