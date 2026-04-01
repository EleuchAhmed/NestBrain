# Changelog

All notable changes to the Nestbrain Research Pipeline will be documented in this file.

## [Unreleased] - 2026-03-31

### Added
- **Native GUI:** Fully developed PyQt6-based Desktop Application (`nestbrain.main`).
- **Python Bridge:** Implemented `notebooklm_bridge.py` natively calling `notebooklm-py` without relying on Node.js/TypeScript subprocesses.
- **Packaging:** Added `scripts/build.spec` and `scripts/build.bat` to package the application into a standalone `.exe` using PyInstaller.

### Removed
- **Node.js Dependency:** Fully deprecated and removed the background pipeline written in TypeScript, including `package.json`, `tsconfig.json`, and the `agents`/`mcp-servers` folders.
- **Docker Compose Complexities:** Removed redundant `Dockerfile.watcher` and `Dockerfile.pipeline`, maintaining only a simplified container approach for optional GUI runs.

### Changed
- The entire research flow is now orchestrated through `nestbrain.core.workflow` within the desktop application loop.
- Re-structured `docker-compose.yml` to only initialize Ollama and conditionally run the `nestbrain` GUI service in a desktop profile.
