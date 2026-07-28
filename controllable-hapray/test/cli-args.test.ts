import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { parseCliArgs } from "../src/cli-args.js";

test("CLI infers an existing-report workflow from --reports for backward compatibility", () => {
  const result = parseCliArgs([
    "--project-root", "/workspace",
    "--reports", "/workspace/reports/case",
    "--source", "/source",
    "--so", "/libs",
    "--output-dir", "/reports-output",
    "--model", "deepseek/deepseek-v4-flash",
    "--symbol-recovery", "never",
    "--json",
  ]);
  assert.equal(result.request.kind, "existing-report");
  assert.equal(result.request.opencode?.model?.providerID, "deepseek");
  assert.equal(result.request.opencode?.model?.modelID, "deepseek-v4-flash");
  assert.equal(result.request.symbolRecovery, "never");
  assert.equal(result.request.runtimeTrack, "auto");
  assert.equal(result.request.outputDir, path.resolve("/reports-output"));
  assert.equal(result.json, true);
});

test("CLI maps collection and device arguments to a full workflow", () => {
  const result = parseCliArgs([
    "--kind", "full",
    "--project-root", "/workspace",
    "--hapray-root", "/hapray-tool",
    "--request", "collect and analyze the home feed",
    "--package-name", "com.example.app",
    "--testcase", "PerfLoad_home_scroll",
    "--device", "device-001",
    "--runtime-track", "source",
    "--repo-root", "/hapray",
    "--source", "/source",
    "--so", "/libs",
  ]);
  assert.deepEqual(result.request, {
    request: "collect and analyze the home feed",
    projectRoot: path.resolve("/workspace"),
    kind: "full",
    haprayRoot: path.resolve("/hapray-tool"),
    mode: "full",
    runtimeTrack: "source",
    symbolRecovery: "auto",
    sourceDir: path.resolve("/source"),
    soDir: path.resolve("/libs"),
    repoRoot: path.resolve("/hapray"),
    packageName: "com.example.app",
    testcase: "PerfLoad_home_scroll",
    device: "device-001",
  });
});

test("CLI defaults to a full workflow when --reports is absent", () => {
  const result = parseCliArgs(["--project-root", "/workspace", "--hapray-root", "/hapray-tool"]);
  assert.equal(result.request.kind, "full");
  assert.match(result.request.request, /connected device/);
});

test("CLI rejects malformed, unknown, and mode-incompatible arguments", () => {
  assert.throws(() => parseCliArgs([]), /project-root/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--reports", "/w/r", "--model", "bad"]), /provider\/model/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--kind", "existing-report"]), /--reports is required/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--kind", "full", "--reports", "/w/r"]), /--reports is only valid/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--kind", "full"]), /--hapray-root is required/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--reports", "/w/r", "--hapray-root", "/tool"]), /--hapray-root is only valid/);
  assert.throws(() => parseCliArgs(["--project-root", "/w", "--pakage-name", "typo"]), /Unknown option/);
});
