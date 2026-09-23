/*
 * Copyright (c) 2026 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import { describe, expect, it, vi } from 'vitest';
import Logger from '../../src/utils/logger';
import {
    resolveLogPath,
    resolveOutputPath,
    resolveRuntimeDir,
    resolveUserDataDir,
    type RuntimePathContext,
} from '../../src/utils/runtime_paths';

function macContext(overrides: Partial<RuntimePathContext> = {}): RuntimePathContext {
    return {
        platform: 'darwin',
        cwd: '/work/project',
        homeDir: '/Users/tester',
        env: {},
        cwdWritable: true,
        ...overrides,
    };
}

describe('runtime path resolution', () => {
    it('keeps writable macOS CLI paths in the caller workspace', () => {
        const context = macContext();

        expect(resolveRuntimeDir('runtime', context)).toBe('/work/project/runtime');
        expect(resolveUserDataDir('static_analyzer', context)).toBe('/work/project/static_analyzer');
        expect(resolveLogPath('HapRay.log', context)).toBe('HapRay.log');
        expect(resolveOutputPath('hap', './output', context)).toBe('./output');
    });

    it('uses HAPRAY_WORKSPACE for relative runtime, log, and output paths', () => {
        const context = macContext({
            env: { HAPRAY_WORKSPACE: '/tmp/hapray-workspace' },
        });

        expect(resolveRuntimeDir('runtime', context)).toBe('/tmp/hapray-workspace/runtime');
        expect(resolveUserDataDir('static_analyzer', context)).toBe(
            '/tmp/hapray-workspace/static_analyzer',
        );
        expect(resolveLogPath('HapRay.log', context)).toBe(
            '/tmp/hapray-workspace/logs/HapRay.log',
        );
        expect(resolveOutputPath('hap', './reports/output', context)).toBe(
            '/tmp/hapray-workspace/reports/output',
        );
    });

    it('preserves an absolute output path when a workspace override is set', () => {
        const context = macContext({
            env: { HAPRAY_WORKSPACE: '/tmp/hapray-workspace' },
        });

        expect(resolveOutputPath('elf', '/work/results/report.json', context)).toBe(
            '/work/results/report.json',
        );
    });

    it('falls back to the home directory only when cwd is read-only', () => {
        const context = macContext({ cwdWritable: false });

        expect(resolveRuntimeDir('runtime', context)).toBe(
            '/Users/tester/ArkAnalyzer-HapRay/runtime',
        );
        expect(resolveLogPath('HapRay.log', context)).toBe(
            '/Users/tester/ArkAnalyzer-HapRay/logs/HapRay.log',
        );
        expect(resolveOutputPath('bjc', './nested/output', context)).toBe(
            '/Users/tester/ArkAnalyzer-HapRay/static_analyzer/bjc/nested/output',
        );
    });

    it('uses platform-specific path semantics for Windows contexts', () => {
        const context: RuntimePathContext = {
            platform: 'win32',
            cwd: 'C:\\work\\project',
            homeDir: 'C:\\Users\\tester',
            env: { HAPRAY_WORKSPACE: 'D:\\hapray-workspace' },
            cwdWritable: true,
        };

        expect(resolveLogPath('HapRay.log', context)).toBe(
            'D:\\hapray-workspace\\logs\\HapRay.log',
        );
        expect(resolveOutputPath('hap', 'reports\\output', context)).toBe(
            'D:\\hapray-workspace\\reports\\output',
        );
    });

    it('does not change the caller cwd when it is writable', () => {
        const chdir = vi.spyOn(process, 'chdir').mockImplementation(() => undefined);

        Logger.ensureWritableCwd(macContext());

        expect(chdir).not.toHaveBeenCalled();
        chdir.mockRestore();
    });
});
