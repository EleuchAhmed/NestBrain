# Launcher

Purpose: central, unambiguous startup entry points for local development and desktop runtime.

## Canonical entry points

- Windows full stack launcher: `launcher/windows/start-research-pipeline.vbs`
- Windows Nestbrain GUI launcher: `launcher/windows/start-nestbrain-desktop.vbs`

## What this folder should contain

- User-facing startup files (scripts or executables)
- Startup documentation and run sequence

## What this folder should NOT contain

- Business logic implementation
- Service internals
- Reusable library code

## Runtime connection

1. `start-research-pipeline.vbs` starts VcXsrv and then executes `docker compose -f docker/docker-compose.yml --profile desktop up -d` from repository root.
2. Docker currently starts the `nestbrain` desktop profile service defined in `docker/docker-compose.yml`.
3. NotebookLM authentication is launched from the Nestbrain Settings dialog via a Python-native browser flow.
