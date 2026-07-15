import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export interface DevicePreviewStatus {
  available: boolean;
  connected: boolean;
  frameAvailable: boolean;
  target?: string;
  updatedAt?: string;
  error?: string;
}

export interface DevicePreview {
  status(): DevicePreviewStatus;
  frame(): Buffer | undefined;
}

export type HdcCommand = (args: readonly string[]) => Promise<string>;

interface HdcDevicePreviewOptions {
  command?: HdcCommand;
  intervalMs?: number;
  temporaryRoot?: string;
}

export class HdcDevicePreview implements DevicePreview {
  readonly #command: HdcCommand;
  readonly #intervalMs: number;
  readonly #temporaryRoot: string;
  readonly #remoteFrame = `/data/local/tmp/controllable-hapray-preview-${process.pid}.jpeg`;
  #localDirectory?: string;
  #timer?: NodeJS.Timeout;
  #refresh?: Promise<void>;
  #started = false;
  #closed = false;
  #frame: Buffer | undefined;
  #status: DevicePreviewStatus = { available: false, connected: false, frameAvailable: false };

  constructor(options: HdcDevicePreviewOptions = {}) {
    this.#command = options.command ?? createHdcCommand();
    this.#intervalMs = options.intervalMs ?? 1_000;
    this.#temporaryRoot = options.temporaryRoot ?? os.tmpdir();
  }

  async start(): Promise<void> {
    if (this.#started) return;
    this.#started = true;
    try {
      await this.#command(["start"]);
      this.#status = { available: true, connected: false, frameAvailable: false };
    } catch (error) {
      this.#status = {
        available: false,
        connected: false,
        frameAvailable: false,
        error: errorMessage(error),
      };
    }
    this.#schedule(0);
  }

  status(): DevicePreviewStatus {
    return { ...this.#status };
  }

  frame(): Buffer | undefined {
    return this.#frame;
  }

  async close(): Promise<void> {
    this.#closed = true;
    if (this.#timer) clearTimeout(this.#timer);
    await this.#refresh;
    if (this.#localDirectory) await rm(this.#localDirectory, { recursive: true, force: true });
  }

  #schedule(delay: number): void {
    if (this.#closed) return;
    this.#timer = setTimeout(() => {
      this.#refresh = this.#update().finally(() => this.#schedule(this.#intervalMs));
    }, delay);
  }

  async #update(): Promise<void> {
    try {
      const targets = await this.#command(["list", "targets", "-v"]);
      const target = connectedTarget(targets);
      if (!target) {
        this.#frame = undefined;
        this.#status = { available: true, connected: false, frameAvailable: false };
        return;
      }

      this.#localDirectory ??= await mkdtemp(path.join(this.#temporaryRoot, "controllable-hapray-device-"));
      const localFrame = path.join(this.#localDirectory, "frame.jpeg");
      await this.#command(["-t", target, "shell", "snapshot_display", "-f", this.#remoteFrame, "-t", "jpeg"]);
      await this.#command(["-t", target, "file", "recv", this.#remoteFrame, localFrame]);
      this.#frame = await readFile(localFrame);
      this.#status = {
        available: true,
        connected: true,
        frameAvailable: true,
        target,
        updatedAt: new Date().toISOString(),
      };
    } catch (error) {
      this.#status = {
        ...this.#status,
        frameAvailable: Boolean(this.#frame),
        error: errorMessage(error),
      };
    }
  }
}

export function connectedTarget(output: string): string | undefined {
  for (const line of output.split(/\r?\n/)) {
    const columns = line.trim().split(/\s+/);
    if (columns.length > 1 && columns.some((column) => column.toLowerCase() === "connected")) return columns[0];
  }
  return undefined;
}

export function createHdcCommand(executable = process.env.HDC_PATH ?? "hdc"): HdcCommand {
  return (args) => new Promise((resolve, reject) => {
    execFile(executable, [...args], { encoding: "utf8", timeout: 15_000, maxBuffer: 1_048_576 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr.trim() || error.message));
        return;
      }
      resolve(stdout);
    });
  });
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
