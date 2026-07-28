import { createServer as createNetServer } from "node:net";
import { createOpencode } from "@opencode-ai/sdk/v2";

export async function ensureOpenCodeServer(): Promise<() => void> {
  if (process.env.OPENCODE_BASE_URL) return () => {};
  const embedded = await createOpencode({ port: await availablePort(), timeout: 30_000 });
  process.env.OPENCODE_BASE_URL = embedded.server.url;
  return embedded.server.close;
}

async function availablePort(): Promise<number> {
  return new Promise<number>((resolve, reject) => {
    const probe = createNetServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      if (!address || typeof address === "string") {
        probe.close();
        reject(new Error("Failed to allocate an OpenCode port"));
        return;
      }
      const selected = address.port;
      probe.close((error) => error ? reject(error) : resolve(selected));
    });
  });
}
