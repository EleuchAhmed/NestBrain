# Installer Build Guide

## Overview

This repository ships a production Windows installer pipeline using:

- `installer.iss` (Inno Setup script)
- `scripts/build.spec` (PyInstaller spec)
- `scripts/build_installer.bat` (end-to-end build runner)
- `scripts/version_info.txt` (Windows executable metadata)

The canonical output is:

- `dist/installer/NestbrainSetup.exe`

## Prerequisites

1. Windows 10/11 x64.
2. Python 3.11+ available on PATH.
3. Inno Setup 6 installed (`ISCC.exe`) or available on PATH.
4. Internet access for dependency and Playwright Chromium installation.
5. Run from repository root.

## Required Files

- `installer.iss`
- `scripts/build.spec`
- `scripts/build_installer.bat`
- `scripts/build.bat`
- `scripts/version_info.txt`
- `installer_assets/license.txt`
- `nestbrain/assets/app.ico`
- `nestbrain/assets/logo.png`

## Build Command

```bat
scripts\build_installer.bat
```

## Build Stages

1. Validate required files and paths.
2. Run `scripts/build.bat` to build PyInstaller one-folder output.
3. Verify PyInstaller output exists at `scripts/dist/Nestbrain/Nestbrain.exe`.
4. Locate `ISCC.exe`.
5. Compile `installer.iss`.
6. Verify final installer at `dist/installer/NestbrainSetup.exe`.

## Notes

- Installer source directory is `scripts/dist/Nestbrain` and must match PyInstaller COLLECT output name exactly.
- Version is pinned to `1.0.0` across installer metadata and version info.
- Replace placeholder content in `installer_assets/` before distribution if needed.
