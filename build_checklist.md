# Build Checklist

## Prerequisites

- Windows 10/11 x64.
- Python 3.11+ installed and available on PATH.
- Inno Setup 6 installed (ISCC.exe available at default install location or on PATH).
- Internet access for pip dependency install and Playwright Chromium download.
- Repository opened from root folder.

## Required Files Before Build

- installer.iss
- INSTALLER_README.md
- scripts/build.spec
- scripts/build.bat
- scripts/build_installer.bat
- scripts/version_info.txt
- installer_assets/license.txt
- installer_assets/post_install_readme.txt
- nestbrain/assets/app.ico
- nestbrain/assets/logo.png
- launcher/windows/start-application.cmd
- launcher/windows/start-nestbrain-desktop.cmd
- launcher/windows/start-nestbrain-desktop.vbs
- launcher/windows/start-research-pipeline.vbs
- nestbrain/main.py
- nestbrain/requirements.txt

## Version and Identity Lock

- Release version: 1.0.0.
- Installer filename: dist/installer/NestbrainSetup.exe.
- Inno Setup AppId GUID: D0A2E2A9-7A3E-4F99-BD8A-0E5E6C4C4F71.
- installer.iss SourceDir: scripts/dist/Nestbrain.
- PyInstaller COLLECT output name: Nestbrain.

## Exact Commands (Run in Order)

```bat
cd /d C:\Users\Mega Pc\Desktop\research-pipeline
scripts\build_installer.bat
```

## Build Output Verification

- scripts/dist/Nestbrain/Nestbrain.exe exists.
- dist/installer/NestbrainSetup.exe exists.
- installer compilation exits with code 0.
- build_installer.bat exits with code 0.

## Resolved Discrepancies

1. Missing source-of-truth files in repository:
- Created installer.iss.
- Created scripts/build_installer.bat.
- Created INSTALLER_README.md.

2. Missing installer_assets directory and placeholders:
- Created installer_assets/license.txt.
- Created installer_assets/post_install_readme.txt.

3. Missing PyInstaller executable metadata file:
- Created scripts/version_info.txt and wired it in scripts/build.spec.

4. Output path mismatch between standalone build and installer expectations:
- Updated scripts/build.spec to use COLLECT with name Nestbrain.
- Updated scripts/build.bat validation target to scripts/dist/Nestbrain/Nestbrain.exe.
- Set installer.iss SourceDir to scripts/dist/Nestbrain to match COLLECT output exactly.

5. Launcher asset inclusion mismatch:
- Added launcher/windows/start-nestbrain-desktop.cmd to scripts/build.spec datas list.

6. Silent-failure risk in build pipeline:
- Added fail-fast checks in scripts/build.bat for toolchain, assets, version metadata, and output existence.
- scripts/build_installer.bat validates required files, resolves ISCC, and verifies final installer artifact.
