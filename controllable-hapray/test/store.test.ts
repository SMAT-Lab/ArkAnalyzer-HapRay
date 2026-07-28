import assert from "node:assert/strict";
import test from "node:test";
import { renameWithRetry } from "../src/store.js";

for (const code of ["EACCES", "EBUSY", "EPERM"] as const) {
  test(`state rename retries transient ${code} failures`, async () => {
    let attempts = 0;
    await renameWithRetry("state.json.tmp", "state.json", async () => {
      attempts += 1;
      if (attempts < 3) {
        const error = new Error("file is in use") as NodeJS.ErrnoException;
        error.code = code;
        throw error;
      }
    });
    assert.equal(attempts, 3);
  });
}
