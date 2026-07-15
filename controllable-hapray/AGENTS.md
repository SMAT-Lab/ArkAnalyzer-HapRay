# Repository Guidelines

## Project Structure & Module Organization

The root package is a Node.js 20+ TypeScript service. Backend code lives in `src/`: `server.ts` handles HTTP/SSE, `runtime-options.ts` discovers and validates constrained inputs, `hdc-preview.ts` owns web-only device preview, `pipeline.ts` orchestrates runs, and `src/stages/` contains workflow steps. Root tests are `test/*.test.ts`.

`dashboard/` is the React/Vite workspace; follow `dashboard/AGENTS.md` there. HapRay specifications come from external `HAPRAY_SKILL_ROOT`; do not vendor them. Full runs separately require a validated per-run `haprayRoot` tool directory.

## Build, Test, and Development Commands

- `npm install`: install service and dashboard dependencies.
- `npm run dev`: run the backend with automatic TypeScript reload.
- `npm run dashboard:dev`: run the backend and Vite dashboard together.
- `npm run analyze -- --help`: show CLI workflow options.
- `npm run typecheck`: check strict backend TypeScript.
- `npm test`: run root tests with Node's built-in test runner.
- `npm run build`: compile the service to `dist/` and build the dashboard.
- `npm start`: serve the compiled API and dashboard.
- `npm --workspace controllable-hapray-dashboard run lint`: lint dashboard code with oxlint.

## Coding Style & Naming Conventions

Use two-space indentation and preserve local syntax: backend files use double quotes and semicolons; dashboard files use single quotes and generally omit semicolons. Avoid `any`, account for `noUncheckedIndexedAccess`, and use `import type` for type-only imports. Use PascalCase for classes/components, camelCase for functions/variables, and lowercase kebab-case for files.

## Testing Guidelines

Tests use `node:test` with `node:assert/strict`. Add focused `*.test.ts` coverage for changed behavior and failure paths. There is no coverage threshold. Run root and dashboard tests when contracts cross the service/UI boundary.

## Commit & Pull Request Guidelines

Use concise, imperative Conventional Commit subjects such as `feat: integrate dashboard`. Keep commits scoped. Pull requests should explain behavior, list verification, link issues, and include screenshots for UI changes. Call out API, environment-variable, or persistence-format changes.

## Security & Configuration

Never commit credentials or pass them through CLI arguments. Use OpenCode's credential store or environment variables and trusted HapRay directories. The unauthenticated service must remain on trusted local interfaces.

Keep device preview startup in `src/main.ts`; `src/cli.ts` must not start the preview worker. The backend owns the single HDC lifecycle and screenshot cache—dashboard clients only consume `/v1/device` and `/v1/device/frame`.

Keep path and runtime-option validation authoritative on the backend. Dashboard directory inputs must use `/v1/fs/directories`; agent/model/device/package/testcase controls must use `/v1/options`. CLI preflight must occur before run persistence and clean up embedded services on failure.
