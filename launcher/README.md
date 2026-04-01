# Launcher

Purpose: central, unambiguous startup entry points for local development and desktop runtime.

## Canonical entry points

- Windows full stack launcher: `launcher/windows/start-research-pipeline.vbs`
- Windows Nestbrain GUI launcher: `launcher/windows/start-nestbrain-desktop.vbs`
- Windows NotebookLM auth launcher: `launcher/windows/start-notebooklm-authentication.bat`

## What this folder should contain

- User-facing startup files (scripts or executables)
- Startup documentation and run sequence

## What this folder should NOT contain

- Business logic implementation
- Service internals
- Reusable library code

## Runtime connection

1. `start-research-pipeline.vbs` starts VcXsrv and then executes `docker compose --profile desktop up -d` from repository root.
2. Docker starts `watcher`, `pipeline`, `ollama`, and optional `nestbrain` services.
3. The TypeScript orchestrator runs via `dist/agents/pipeline.js` which delegates to `src/features/pipeline/workflow.ts`.
