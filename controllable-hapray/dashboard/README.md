# Controllable HapRay Dashboard

The browser GUI for the Controllable HapRay service in the parent repository. Its interface follows the VS Code Light+ workbench model while using the parent service as the only workflow authority.

The dashboard does not spawn OpenCode, HDC, or maintain a second workflow state machine. It creates typed service runs, subscribes to persisted SSE events, renders the backend's seven stage states and OpenCode sessions, surfaces structured artifacts and findings, and displays the backend's shared connected-device screenshot cache.

## Run locally

Requirements are the same as the parent service: Node.js 20+, an available `opencode` CLI, configured provider credentials, and `HAPRAY_SKILL_ROOT` pointing to an external HapRay skill directory containing `SKILL.md`. This service-level directory is distinct from the `haprayRoot` selected when creating a Full run.

Device monitoring additionally requires `hdc` in `PATH` (or `HDC_PATH`). The backend selects the first Connected target. Monitor stays disabled until one is detected; later capture errors retain the last cached frame. Workflow and API service remain usable throughout.

```bash
cd dashboard
npm install
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm run dev
```

`npm run dev` starts both processes:

- Controllable HapRay service: `http://127.0.0.1:8787`
- Vite dashboard: `http://localhost:5173`

Vite proxies `/health` and `/v1/*` to the service. `npm run dev:service` starts only the parent service.

For production, run from the parent repository:

```bash
npm install
npm run build
HAPRAY_SKILL_ROOT=/absolute/path/to/hapray-skill npm start
```

The HapRay Node server serves `dashboard/dist` and the API from the same origin at `http://127.0.0.1:8787`, including SPA route fallback. Set `DASHBOARD_DIST` only when the built frontend lives elsewhere.

## User flow

1. Enter the free-form analysis request and choose the project root through the backend directory browser.
2. Choose a full collection run or analysis of an existing report. Select all path fields through the directory picker.
3. For Full runs, choose device, installed package, and discovered `PerfLoad_*` testcase from live options. Choose OpenCode agent, connected provider, and model from the OpenCode service catalog.
4. Start the run. The service validates paths before persisting it.
5. Watch stage state, artifacts, findings, sessions, and replayable events update live. Expanded stage values can be copied from their individual panels.
6. When a device is connected, select **Monitor** above Findings to open its live screenshot; select **Hide** to reclaim the space.
7. Cancel an active run or reopen one from browser-local recent history.

Recent history contains only the run ID, project root, label, and creation time. Run state and events remain authoritative in `<projectRoot>/.hapray-service/runs/<run-id>/`.

## Architecture

```text
React dashboard
  ├─ GET  /v1/fs/directories            browse canonical local directories
  ├─ GET  /v1/options                   discover constrained runtime values
  ├─ GET  /v1/device                   poll shared HDC connection/frame state
  ├─ GET  /v1/device/frame             load the latest cached JPEG
  ├─ POST /v1/runs                     create a validated run
  ├─ GET  /v1/runs/:id?projectRoot=…   refresh authoritative state
  ├─ GET  ...&stream=true              replay + follow named SSE events
  └─ DELETE /v1/runs/:id?projectRoot=… cancel an active run
            │
            ▼
Controllable HapRay service (parent repository)
  ├─ HdcDevicePreview (web entrypoint only; one shared worker)
  ├─ PipelineRunner
  ├─ RunStore (state.json + events.jsonl)
  └─ OpenCode SDK stage agents
```

The frontend contract is mirrored in `src/types/hapray.ts`. Workflow transport lives in `src/hooks/useHapRayService.ts`; `src/hooks/useRuntimeOptions.ts` refreshes live constrained choices, and `src/hooks/useDevicePreview.ts` polls the preview API. The service remains authoritative: it repeats path and runtime-option validation when creating a run.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start parent service and Vite together |
| `npm run dev:service` | Start only the parent service |
| `npm run build` | Type-check and build the SPA |
| `npm test` | Run dashboard unit tests |
| `npm run lint` | Run Oxlint |
| `npm run preview` | Preview only the built SPA (API requests still require a proxy) |

## Stage mapping

| UI stage | Service stage ID | Skip behavior |
| --- | --- | --- |
| 0 Path Gate | `path-gate` | never |
| 1 Setup | `setup` | existing-report runs |
| 2 Collect | `collect` | existing-report runs |
| 3 Symbols | `symbol-recovery` | `never`; or `auto` without a symbol-level request/evidence |
| 4 Analysis | `analysis` | never |
| 5 Root Cause | `root-cause` | quick mode |
| 6 Deliver | `deliver` | never |

## Verification

```bash
npm run build
npm test
npm run lint
```
