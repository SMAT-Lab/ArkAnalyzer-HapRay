# Controllable HapRay Dashboard — Agent Guide

This directory is the React/Vite npm workspace that provides the GUI for the TypeScript service in the parent directory.

## Authority boundary

The parent service is the only workflow authority. Do not add another OpenCode runner, workflow orchestrator, task state machine, or persistence format to the dashboard.

The supported service contract is:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service availability |
| `GET` | `/v1/device` | Shared backend HDC/device preview status |
| `GET` | `/v1/device/frame` | Latest backend-cached device JPEG |
| `GET` | `/v1/fs/directories` | Canonical local directory browser |
| `GET` | `/v1/options` | Live OpenCode, HDC, package, and testcase choices |
| `POST` | `/v1/runs` | Create a run from `RunRequest` |
| `GET` | `/v1/runs/:id?projectRoot=…` | Load authoritative `RunState` |
| `GET` | `/v1/runs/:id?projectRoot=…&stream=true` | Replay and follow typed SSE events |
| `DELETE` | `/v1/runs/:id?projectRoot=…` | Cancel a queued/running run |

Types mirror `../src/domain.ts` in `src/types/hapray.ts`. When the backend contract changes, update both the mirror and the UI mapping in the same change.

## Runtime structure

- `src/App.tsx`: VS Code-style workbench shell, request form, workflow editor, panels, findings, and optional device monitor.
- `src/hooks/useHapRayService.ts`: create/load/cancel calls, EventSource lifecycle, replay deduplication, and state refresh.
- `src/hooks/useDevicePreview.ts`: polls backend-owned device status and refreshes the shared screenshot URL.
- `src/hooks/useRuntimeOptions.ts`: refreshes constrained runtime choices and partial discovery errors.
- `src/runtime-validation.ts`: blocks stale or manually typed dynamic values before submission.
- `src/session-events.ts`: filters and deduplicates replayed OpenCode snapshots for the per-stage Sessions terminal.
- `src/clipboard.ts`: Clipboard API handling and the legacy copy fallback for stage details.
- `src/types/hapray.ts`: frontend mirror of the service domain contract.
- `src/App.css`: stage and event animations retained from the original dashboard.
- `src/index.css`: theme tokens and shared input styling.
- `vite.config.ts`: development proxy to `127.0.0.1:8787`.
- `../src/server.ts`: production static serving and SPA fallback from `dashboard/dist`.

There is intentionally no dashboard-side server. All backend behavior belongs to the parent service. Never spawn HDC or run screenshot commands from browser/dashboard code; poll the shared cache instead.

## Design language

Preserve the VS Code Light+ visual language: flat white editor surfaces, light gray chrome, one-pixel separators, blue focus/status accents, compact typography, tree rows, editor tabs, breadcrumbs, panel tables, and minimal motion. Avoid SaaS-dashboard conventions such as floating cards, large radii, shadows, gradients, pill-heavy metadata, and ornamental animation.

The main mappings are direct:

- `RunState.stages` → stage deck and progress.
- `RunState.request` → editor property tables.
- `RunState.artifacts` → Artifacts panel table.
- `RunState.findings` → findings pane.
- `WorkflowEvent[]` → replayable event table and per-stage Sessions terminal.

The Explorer maps `RunRequest.haprayRoot` to a required conditional field for `full` runs and `reportsPath` to the corresponding field for `existing-report`. Never submit the hidden kind-specific value.

Path inputs are read-only and use the backend directory picker. Agent, provider, model, device, and testcase are selects; package search still requires an exact live match. Backend validation is authoritative.

## Commands

Run from this directory:

```bash
npm install
npm run dev
npm run build
npm test
npm run lint
```

`npm run dev` starts the parent service and Vite. Verification requires build, test, and lint to pass.

## Security and deployment

This is a local-only tool. The service has no authentication. Do not expose it to untrusted networks. `HAPRAY_SKILL_ROOT` must reference a trusted external skill directory; the skill is not part of this workspace. Full-run `haprayRoot` values may be external directories but must pass the parent service's path gate. In production the parent Node server serves the SPA and `/health` and `/v1` on one origin; Vite proxying exists only in development.
