/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

/** HapRay tool-result v1 — machine-readable CLI contract for agents. */

export const SCHEMA_VERSION = '1.0';

export interface ToolResultV1 {
    schema_version: string;
    tool_id: string;
    success: boolean | null;
    exit_code: number;
    outputs: Record<string, unknown>;
    error: string | null;
    action?: string;
    tool_version?: string;
}

export function buildToolResult(
    toolId: string,
    success: boolean | null,
    exitCode: number,
    outputs: Record<string, unknown> = {},
    error: string | null = null,
    toolVersion?: string,
    action?: string
): ToolResultV1 {
    const payload: ToolResultV1 = {
        schema_version: SCHEMA_VERSION,
        tool_id: toolId,
        success,
        exit_code: exitCode,
        outputs,
        error,
    };
    if (toolVersion) {
        payload.tool_version = toolVersion;
    }
    if (action) {
        payload.action = action;
    }
    return payload;
}

export function emitToolResult(payload: ToolResultV1): void {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
}
