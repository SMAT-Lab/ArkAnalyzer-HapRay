import assert from "node:assert/strict";
import { mkdtemp, mkdir, realpath } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { parseRunRequest, validatePathGate } from "../src/validation.js";

test("request parser applies workflow defaults", () => {
  const result = parseRunRequest({ request: "collect", projectRoot: "/workspace" });
  assert.equal(result.kind, "full");
  assert.equal(result.mode, "full");
  assert.equal(result.runtimeTrack, "auto");
  assert.equal(result.symbolRecovery, "auto");
});

test("request parser rejects arbitrary enum values", () => {
  assert.throws(() => parseRunRequest({ request: "analyze", projectRoot: "/tmp", kind: "sometimes" }), /kind must be one of/);
  assert.throws(() => parseRunRequest({ request: "analyze", projectRoot: "/tmp", mode: 3 }), /mode must be one of/);
});

test("path gate requires existing-report input under projectRoot", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-validation-"));
  const outside = await mkdtemp(path.join(os.tmpdir(), "hapray-outside-"));
  await assert.rejects(
    validatePathGate({ request: "analyze", projectRoot, kind: "existing-report" }),
    /reportsPath is required/,
  );
  await assert.rejects(
    validatePathGate({ request: "analyze", projectRoot, kind: "existing-report", reportsPath: outside }),
    /reportsPath must be inside projectRoot/,
  );
  const reportsPath = path.join(projectRoot, "reports", "run");
  await mkdir(reportsPath, { recursive: true });
  const data = await validatePathGate({ request: "analyze", projectRoot, kind: "existing-report", reportsPath });
  assert.equal(data.reportsPath, await realpath(reportsPath));
});

test("path gate authorizes and canonicalizes an explicit external output directory", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-validation-"));
  const reportsPath = path.join(projectRoot, "reports", "run");
  const outputDir = await mkdtemp(path.join(os.tmpdir(), "hapray-output-"));
  await mkdir(reportsPath, { recursive: true });
  const request = { request: "analyze", projectRoot, kind: "existing-report" as const, reportsPath, outputDir };
  const data = await validatePathGate(request);
  assert.equal(request.outputDir, await realpath(outputDir));
  assert.equal(data.outputDir, await realpath(outputDir));
});

test("path gate requires a canonical HapRay tool root only for full runs", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-validation-"));
  await assert.rejects(
    validatePathGate({ request: "collect", projectRoot, kind: "full" }),
    /haprayRoot is required/,
  );
  await assert.rejects(
    validatePathGate({ request: "collect", projectRoot, kind: "full", haprayRoot: "relative/tool" }),
    /haprayRoot must be an absolute path/,
  );

  const haprayRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-tool-"));
  const request = { request: "collect", projectRoot, kind: "full" as const, haprayRoot };
  const data = await validatePathGate(request);
  assert.equal(request.haprayRoot, await realpath(haprayRoot));
  assert.equal(data.haprayRoot, await realpath(haprayRoot));

  const reportsPath = path.join(projectRoot, "reports", "run");
  await mkdir(reportsPath, { recursive: true });
  await assert.rejects(
    validatePathGate({ request: "analyze", projectRoot, kind: "existing-report", reportsPath, haprayRoot }),
    /haprayRoot is only valid/,
  );
});
