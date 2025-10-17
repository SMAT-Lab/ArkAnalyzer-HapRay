import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { initConfig } from '../../src/config';
import { PerfAnalyzer } from '../../src/core/perf/perf_analyzer';
import { traceStreamerCmd } from '../../src/services/external/trace_streamer';
import fs from 'fs';
import path from 'path';
import { createHash } from 'crypto';

describe('Dbtools CLI Test - isRight Method Validation', () => {
    let originalConsoleLog: typeof console.log;
    let originalConsoleError: typeof console.error;
    let consoleOutput: string[] = [];
    let consoleErrors: string[] = [];

    beforeEach(() => {
        // 重置配置
        initConfig({}, (config) => {
            config.ut = false;
            config.inDbtools = true;
            config.choose = false;
            config.compatibility = false;
        });

        // Mock console.log 和 console.error 来捕获输出
        originalConsoleLog = console.log;
        originalConsoleError = console.error;
        consoleOutput = [];
        consoleErrors = [];

        console.log = vi.fn((...args) => {
            consoleOutput.push(args.join(' '));
        });

        console.error = vi.fn((...args) => {
            consoleErrors.push(args.join(' '));
        });
    });

    afterEach(() => {
        // 恢复原始的 console 方法
        console.log = originalConsoleLog;
        console.error = originalConsoleError;
    });



    it('should parse real perf.db file and generate steps data for hash comparison', { timeout: 15000 }, async () => {
        // 使用真实的PerfAnalyzer解析perf.db文件，获取真实的steps数据进行hash对比

        // 1. 设置UT模式
        initConfig({ ut: true }, (config) => {
            config.ut = true;
        });

        // 2. 使用真实的测试资源路径
        const testResourcePath = path.join(__dirname, '..', 'resources', 'ResourceUsage_PerformanceDynamic_jingdong_0010');
        const expectedHiperfInfoPath = path.join(testResourcePath, 'hiperf', 'hiperf_info.json');

        // 3. 验证测试文件存在
        const testInfoPath = path.join(testResourcePath, 'testInfo.json');
        const stepsPath = path.join(testResourcePath, 'hiperf', 'steps.json');
        const perfDbPath = path.join(testResourcePath, 'hiperf', 'step1', 'perf.db');

        expect(fs.existsSync(testInfoPath)).toBe(true);
        expect(fs.existsSync(stepsPath)).toBe(true);
        expect(fs.existsSync(expectedHiperfInfoPath)).toBe(true);

        // 检查perf.db文件是否存在，如果不存在则从perf.data生成
        const perfDataPath = path.join(testResourcePath, 'hiperf', 'step1', 'perf.data');
        expect(fs.existsSync(perfDataPath)).toBe(true);

        if (!fs.existsSync(perfDbPath)) {
            console.log(`perf.db not found, generating from perf.data: ${perfDataPath} -> ${perfDbPath}`);
            try {
                await traceStreamerCmd(perfDataPath, perfDbPath);
                console.log(`Successfully generated perf.db file`);
            } catch (error) {
                console.log(`Failed to generate perf.db: ${error}`);
                console.log(`Skipping test due to trace_streamer tool unavailability`);
                return; // 跳过测试
            }
        }

        // 4. 读取测试数据
        const testInfoRaw = JSON.parse(fs.readFileSync(testInfoPath, 'utf-8'));
        const testInfo = {
            app_id: testInfoRaw.app_id,
            app_name: testInfoRaw.app_name,
            app_version: testInfoRaw.app_version,
            scene: testInfoRaw.scene,
            timestamp: testInfoRaw.timestamp,
            rom_version: testInfoRaw.device?.version ?? '',
            device_sn: testInfoRaw.device?.sn ?? ''
        };

        const steps = JSON.parse(fs.readFileSync(stepsPath, 'utf-8'));

        // 5. 创建PerfAnalyzer实例并执行分析
        const perfAnalyzer = new PerfAnalyzer(testResourcePath);

        // 构建TestSceneInfo
        const testSceneInfo = {
            packageName: testInfo.app_id,
            appName: testInfo.app_name,
            scene: testInfo.scene,
            osVersion: testInfo.rom_version,
            timestamp: testInfo.timestamp,
            appVersion: testInfo.app_version,
            rounds: [{
                steps: steps.map((step: any) => ({
                    reportRoot: testResourcePath,
                    groupId: step.stepIdx,
                    groupName: step.description,
                    dbfile: path.join(testResourcePath, 'hiperf', `step${step.stepIdx}`, 'perf.db'),
                    perfFile: path.join(testResourcePath, 'hiperf', `step${step.stepIdx}`, 'perf.data'),
                    traceFile: path.join(testResourcePath, 'htrace', `step${step.stepIdx}`, 'trace.htrace')
                }))
            }],
            chooseRound: 0
        };

        // 6. 执行分析，这会从perf.db文件中加载真实的数据到details数组
        const outputDir = path.join(testResourcePath, 'report');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        try {
            // 执行分析，这会填充perfAnalyzer.details数组
            await perfAnalyzer.analyze(testSceneInfo, outputDir);

            // 7. 在UT模式下执行saveHiperfJson，这会调用isRight方法进行hash对比
            const isRight = await perfAnalyzer.saveHiperfJson(testSceneInfo, expectedHiperfInfoPath);
            expect(isRight).toBe(true);
            // 8. 读取期望文件内容进行验证
            const expectedContent = fs.readFileSync(expectedHiperfInfoPath, 'utf-8');
            const expectedHash = createHash('sha256').update(expectedContent).digest('hex');
            const expectedData = JSON.parse(expectedContent);

            // 9. 验证期望文件的内容结构
            expect(Array.isArray(expectedData)).toBe(true);
            expect(expectedData.length).toBeGreaterThan(0);

            const firstItem = expectedData[0];
            expect(firstItem).toHaveProperty('steps');
            expect(firstItem).toHaveProperty('har');
            expect(Array.isArray(firstItem.steps)).toBe(true);
            expect(Array.isArray(firstItem.har)).toBe(true);

            // 10. 输出测试结果
            console.log(`Real perf.db analysis completed`);
            console.log(`Expected file hash: ${expectedHash}`);
            console.log(`Expected file has ${firstItem.steps.length} steps and ${firstItem.har.length} har entries`);

            // 验证steps数据不为空（说明成功从perf.db解析了数据）
            if (firstItem.steps.length > 0) {
                const firstStep = firstItem.steps[0];
                expect(firstStep).toHaveProperty('step_name');
                expect(firstStep).toHaveProperty('step_id');
                expect(firstStep).toHaveProperty('count');
                expect(firstStep).toHaveProperty('data');
                expect(Array.isArray(firstStep.data)).toBe(true);

                console.log(`First step: ${firstStep.step_name}, count: ${firstStep.count}, data items: ${firstStep.data.length}`);
            }

            // 验证har数据不为空（说明成功解析了应用组件数据）
            if (firstItem.har.length > 0) {
                const firstHar = firstItem.har[0];
                expect(firstHar).toHaveProperty('name');
                expect(firstHar).toHaveProperty('count');

                console.log(`First har component: ${firstHar.name}, count: ${firstHar.count}`);
            }

            console.log(`Test completed - Real perf.db parsing and hash comparison successful`);

        } catch (error) {
            console.error(`Test execution error: ${error}`);
            throw error;
        }
    });
});
