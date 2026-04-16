# Nestbrain Release Distribution Checklist (One Page)

Use this checklist before sharing the Windows installer with end users.

## 1) Version And Metadata Alignment

- Confirm installer script version is correct in [installer.iss](installer.iss):
  - `MyAppVersion`
  - `AppVersion`
  - `AppVerName`
- Confirm executable version resource is correct in [scripts/version_info.txt](scripts/version_info.txt):
  - `filevers`
  - `prodvers`
  - `FileVersion`
  - `ProductVersion`
- Confirm these values match the intended release version exactly.

## 2) Build Preconditions

- Build host is Windows 10/11 x64.
- Python is available in PATH or run through your project interpreter.
- Inno Setup 6 is installed and ISCC.exe is discoverable.
- Required packaging files exist:
  - [scripts/build_installer.bat](scripts/build_installer.bat)
  - [scripts/build.bat](scripts/build.bat)
  - [scripts/build.spec](scripts/build.spec)
  - [installer.iss](installer.iss)
  - [installer_assets/license.txt](installer_assets/license.txt)

## 3) Build And Output Verification

- Run installer build from repo root:
  - `& "scripts/build_installer.bat"`
- Confirm generated application binary exists:
  - [scripts/dist/Nestbrain/Nestbrain.exe](scripts/dist/Nestbrain/Nestbrain.exe)
- Confirm generated installer exists:
  - [dist/installer/NestbrainSetup.exe](dist/installer/NestbrainSetup.exe)
- Record installer hash (SHA-256) for release notes and integrity verification.

## 4) Runtime Packaging Sanity

- Verify launcher files are packaged under installed output.
- Verify app icon is present in installer and app shortcuts.
- Verify install target defaults to Program Files and app starts from Start Menu shortcut.

## 5) Security And Trust

- Confirm installer signing status:
  - Unsigned release accepted for this cycle.
  - If signed in future, verify certificate chain and timestamp.
- Keep hash published in release notes for user verification.

## 6) Installer UX Smoke Test

- On a test machine or clean user profile:
  - Install successfully with admin prompt.
  - Launch app from completion screen.
  - Launch app from Start Menu and desktop shortcut.
  - Uninstall successfully from Apps/Programs list.

## 7) Distribution Package Contents

- [dist/installer/NestbrainSetup.exe](dist/installer/NestbrainSetup.exe)
- Release notes including:
  - version
  - release date
  - SHA-256 hash
  - known issues
  - minimum OS requirements

## 8) Current Release Audit Snapshot (2026-04-16)

- App metadata observed:
  - FileVersion: 1.0.0.0
  - ProductVersion: 1.0.0.0
- Installer metadata observed:
  - ProductVersion: 1.0.0
  - FileDescription: Nestbrain Research Pipeline Setup
- Installer signing status observed:
  - NotSigned
- Installer hash observed:
  - SHA-256: 3EA6875C57F491586F84B630A7D4D791059F0CAAC9D14A095C54855CD7EAF233

## 9) Final Go/No-Go

- Go only if:
  - version fields are aligned,
  - license text is final,
  - smoke test passes,
  - hash is documented,
  - release notes are complete.
