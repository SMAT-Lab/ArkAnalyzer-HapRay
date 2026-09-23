/*
 * Copyright (c) 2026 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

import path from 'node:path';

export const HAPRAY_WORKSPACE_ENV = 'HAPRAY_WORKSPACE';

export interface RuntimePathContext {
    platform: NodeJS.Platform;
    cwd: string;
    homeDir: string;
    env: NodeJS.ProcessEnv;
    cwdWritable: boolean;
}

function pathApi(platform: NodeJS.Platform): typeof path.posix | typeof path.win32 {
    return platform === 'win32' ? path.win32 : path.posix;
}

function workspaceOverride(context: RuntimePathContext): string | undefined {
    const value = context.env[HAPRAY_WORKSPACE_ENV]?.trim();
    if (!value) {
        return undefined;
    }
    return pathApi(context.platform).resolve(context.cwd, value);
}

export function resolveWorkspaceRoot(context: RuntimePathContext): string {
    const override = workspaceOverride(context);
    if (override) {
        return override;
    }
    if (context.cwdWritable) {
        return context.cwd;
    }
    return pathApi(context.platform).join(context.homeDir, 'ArkAnalyzer-HapRay');
}

export function resolveRuntimeDir(dirName: string, context: RuntimePathContext): string {
    return pathApi(context.platform).join(resolveWorkspaceRoot(context), dirName);
}

export function resolveUserDataDir(dirName: string, context: RuntimePathContext): string {
    return pathApi(context.platform).join(resolveWorkspaceRoot(context), dirName);
}

export function resolveLogPath(logFileName: string, context: RuntimePathContext): string {
    if (!workspaceOverride(context) && context.cwdWritable) {
        return logFileName;
    }
    return pathApi(context.platform).join(resolveWorkspaceRoot(context), 'logs', logFileName);
}

export function resolveOutputPath(
    subdir: string,
    outputPath: string,
    context: RuntimePathContext,
): string {
    const platformPath = pathApi(context.platform);
    if (platformPath.isAbsolute(outputPath)) {
        return outputPath;
    }

    const override = workspaceOverride(context);
    if (override) {
        return platformPath.resolve(override, outputPath);
    }
    if (context.cwdWritable) {
        return outputPath;
    }
    return platformPath.resolve(
        resolveWorkspaceRoot(context),
        'static_analyzer',
        subdir,
        outputPath,
    );
}
