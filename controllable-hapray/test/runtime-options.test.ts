import assert from "node:assert/strict";
import { mkdtemp, mkdir, realpath, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import type { RunRequest } from "../src/domain.js";
import {
  discoverTestcases,
  listDirectories,
  parseConnectedTargets,
  parsePackageNames,
  RuntimeOptionsService,
} from "../src/runtime-options.js";

test("runtime discovery parses connected targets and installed packages", () => {
  assert.deepEqual(parseConnectedTargets("device-a USB Connected localhost\ndevice-b TCP Offline localhost\n"), ["device-a"]);
  assert.deepEqual(parsePackageNames("ID: 100:\n  com.example.beta\n  invalid\n  com.example.alpha\n"), ["com.example.alpha", "com.example.beta"]);
});

test("runtime options discover testcases and validate full-run selections", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-options-project-"));
  const haprayRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-options-tool-"));
  await mkdir(path.join(haprayRoot, "testcases"));
  await writeFile(path.join(haprayRoot, "testcases", "PerfLoad0010.ts"), "export default {}", "utf8");
  const hdc = async (args: readonly string[]) => args.includes("bm")
    ? "ID: 100:\n  com.example.app\n"
    : "device-a USB Connected localhost\n";
  const openCode = async () => ({ agents: [], providers: [], models: [] });
  const service = new RuntimeOptionsService(hdc, openCode);
  const request: RunRequest = {
    request: "collect",
    projectRoot,
    kind: "full",
    haprayRoot,
    device: "device-a",
    packageName: "com.example.app",
    testcase: "PerfLoad0010",
  };

  const catalog = await service.load({ projectRoot, haprayRoot, device: "device-a" });
  assert.deepEqual(catalog.devices.map((option) => option.id), ["device-a"]);
  assert.deepEqual(catalog.packages.map((option) => option.id), ["com.example.app"]);
  assert.deepEqual(catalog.testcases.map((option) => option.id), ["PerfLoad0010"]);
  await service.validate(request);
  await assert.rejects(service.validate({ ...request, packageName: "com.example.missing" }), /not installed/);
});

test("directory browser canonicalizes and lists directories only", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "hapray-directory-browser-"));
  await mkdir(path.join(root, "source"));
  await writeFile(path.join(root, "file.txt"), "ignored", "utf8");
  const listing = await listDirectories(root);
  const canonical = await realpath(root);
  assert.equal(listing.path, canonical);
  assert.deepEqual(listing.directories, [{ name: "source", path: path.join(canonical, "source") }]);
  assert.ok(listing.parent);
});

test("testcase discovery ignores unrelated files", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "hapray-testcase-discovery-"));
  await writeFile(path.join(root, "PerfLoad_home_scroll.js"), "", "utf8");
  await writeFile(path.join(root, "helper.ts"), "", "utf8");
  assert.deepEqual((await discoverTestcases(root)).map((option) => option.id), ["PerfLoad_home_scroll"]);
});
