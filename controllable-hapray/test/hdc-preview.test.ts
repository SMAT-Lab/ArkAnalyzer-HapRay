import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { connectedTarget, HdcDevicePreview, type HdcCommand } from "../src/hdc-preview.js";

test("connectedTarget selects the first connected HDC target", () => {
  assert.equal(connectedTarget("device-1\tUSB\tConnected\tlocalhost\ndevice-2 TCP Offline localhost\n"), "device-1");
  assert.equal(connectedTarget("[Empty]\n"), undefined);
});

test("HDC preview starts HDC once and maintains one cached frame", async () => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-hdc-test-"));
  const calls: string[][] = [];
  const command: HdcCommand = async (args) => {
    calls.push([...args]);
    if (args[0] === "list") return "device-1\tUSB\tConnected\tlocalhost\n";
    if (args.includes("recv")) await writeFile(args.at(-1)!, Buffer.from("jpeg-frame"));
    return "";
  };
  const preview = new HdcDevicePreview({ command, intervalMs: 60_000, temporaryRoot });
  await preview.start();
  await preview.start();
  await waitFor(() => preview.status().frameAvailable);

  assert.equal(calls.filter((args) => args[0] === "start").length, 1);
  assert.equal(calls.filter((args) => args.includes("snapshot_display")).length, 1);
  assert.equal(preview.status().target, "device-1");
  assert.deepEqual(preview.frame(), Buffer.from("jpeg-frame"));
  await preview.close();
});

async function waitFor(predicate: () => boolean): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("timed out waiting for preview frame");
}
