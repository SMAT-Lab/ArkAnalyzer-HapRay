import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";
import { Agent as UndiciAgent } from "undici";
import { createOpenCodeFetch, parseTextStageResult, permissionRequest, shouldPersistAgentEvent, summarizeAgentEvent } from "../src/agent.js";

test("plain-text provider fallback parses a tagged stage result", () => {
  const result = parseTextStageResult([{ type: "text", text: `Work finished.
<hapray-stage-result>
{"status":"completed","summary":"done","artifacts":[],"findings":[],"data":{}}
</hapray-stage-result>` }]);
  assert.equal(result.status, "completed");
  assert.equal(result.summary, "done");
});

test("plain-text provider fallback rejects prose without a result", () => {
  assert.throws(() => parseTextStageResult([{ type: "text", text: "done" }]), /valid stage result/);
});

test("OpenCode event compaction removes recursive snapshot patches", () => {
  const event = {
    type: "message.updated",
    properties: {
      sessionID: "session",
      info: {
        sessionID: "session",
        summary: { diffs: [{ file: ".hapray-service/runs/1/events.jsonl", patch: "x".repeat(100_000), additions: 10, deletions: 0 }] },
      },
    },
  };
  const compacted = summarizeAgentEvent(event as never);
  const serialized = JSON.stringify(compacted);
  assert.ok(serialized.length < 2_000);
  assert.doesNotMatch(serialized, /x{100}/);
  assert.match(serialized, /patchBytes/);
});

test("token deltas are not persisted as durable workflow events", () => {
  assert.equal(shouldPersistAgentEvent({ type: "message.part.delta" }), false);
  assert.equal(shouldPersistAgentEvent({ type: "message.part.updated" }), true);
});

test("OpenCode transport permits responses whose headers take longer than its configured limit", async () => {
  const server = createServer((request, response) => {
    setTimeout(() => response.end("completed"), request.url === "/slow" ? 1_500 : 80);
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;
  const short = new UndiciAgent({ headersTimeout: 100 });
  const unlimited = new UndiciAgent({ headersTimeout: 0, bodyTimeout: 0 });
  try {
    await assert.rejects(createOpenCodeFetch(short)(new Request(`${origin}/slow`, { method: "POST", body: "prompt" })), /fetch failed/);
    const response = await createOpenCodeFetch(unlimited)(new Request(`${origin}/session/prompt`, { method: "POST", body: "prompt" }));
    assert.equal(await response.text(), "completed");
  } finally {
    await short.close();
    await unlimited.close();
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

test("headless permission replies are limited to validated workflow roots", () => {
  const event = (filepath: string) => ({
    type: "permission.asked",
    properties: {
      id: "permission-1",
      permission: "external_directory",
      metadata: { filepath },
    },
  });
  assert.deepEqual(permissionRequest(event("/allowed/source/file.ets"), ["/allowed/source"]), {
    requestID: "permission-1",
    authorized: true,
  });
  assert.deepEqual(permissionRequest(event("/private/secret"), ["/allowed/source"]), {
    requestID: "permission-1",
    authorized: false,
  });
});
