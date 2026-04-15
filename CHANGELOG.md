# Changelog

All notable changes to the Nestbrain Research Pipeline will be documented in this file.

## [Unreleased] - 2026-04-15

### Changed
- Synchronized repository Markdown documentation with active Python runtime and workflow ownership.
- Rewrote top-level README with current setup flow, feature list, and structure map.
- Updated architecture and context docs to reflect the active `pipeline_runner.py -> workflow_engine.py` path.
- Updated launcher and scripts docs to remove stale service and folder assumptions.
- Updated known issues to remove stale claims and add explicit legacy/dead-code reporting notes.

## [Unreleased] - 2026-04-08

### Added
- **Native GUI:** Fully developed PyQt6-based Desktop Application (`nestbrain.main`).
- **Python Bridge:** Implemented `notebooklm_bridge.py` natively calling `notebooklm-py` without relying on Node.js/TypeScript subprocesses.
- **Packaging:** Added `scripts/build.spec` and `scripts/build.bat` to package the application into a standalone `.exe` using PyInstaller.
- **Native NotebookLM Browser Auth:** Added `nestbrain/core/notebooklm_browser_auth.py` for Playwright-driven interactive login and token capture.
- **CLI Auth Entry:** Added `--notebooklm-auth` entry handling in `nestbrain/main.py`.
- **Auth Cache Migration:** Added app-managed auth cache with legacy migration/fallback support in `nestbrain/core/notebooklm_auth.py`.

### Removed
- **Node.js Dependency:** Fully deprecated and removed the background pipeline written in TypeScript, including `package.json`, `tsconfig.json`, and the `agents`/`mcp-servers` folders.
- **Docker Compose Complexities:** Removed redundant `Dockerfile.watcher` and `Dockerfile.pipeline`, maintaining only a simplified container approach for optional GUI runs.
- **Legacy Launcher Auth Script:** Removed `launcher/windows/start-notebooklm-authentication.bat`.
- **Stale Root Semantic Cache:** Removed stale repository-root `.nestbrain_index.json` and added ignore rules for generated index caches.

### Changed
- Runtime orchestration flows through `nestbrain/core/pipeline_runner.py` to `nestbrain/core/workflow_engine.py`.
- NotebookLM authentication now launches from the settings dialog into a Python-native browser flow.
- Re-structured `docker/docker-compose.yml` to define only the optional `nestbrain` GUI service in a desktop profile.
