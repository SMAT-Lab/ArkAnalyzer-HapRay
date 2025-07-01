interface VSCodeApi {
  postMessage(message: unknown): void;
  setState(state: unknown): void;
  getState(): unknown;
}

declare const acquireVsCodeApi: () => VSCodeApi;

class VSCodeManager {
  private static instance: VSCodeApi;

  static getInstance(): VSCodeApi {
    if (!this.instance) {
      if (typeof acquireVsCodeApi === 'undefined') {
        this.instance = {
          postMessage: console.log,
          setState: console.log,
          getState: () => null,
        };
      } else {
        this.instance = acquireVsCodeApi();
      }
    }
    return this.instance;
  }
}

export const vscode = VSCodeManager.getInstance();
