@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo Building Nestbrain Standalone Application
echo ==============================================

cd /d "%~dp0\.."
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to switch to repository root.
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not available on PATH.
    exit /b 1
)

if not exist "nestbrain\assets\app.ico" (
    echo [ERROR] Missing required asset: nestbrain\assets\app.ico
    exit /b 1
)

if not exist "nestbrain\assets\logo.png" (
    echo [ERROR] Missing required asset: nestbrain\assets\logo.png
    exit /b 1
)

if not exist "scripts\version_info.txt" (
    echo [ERROR] Missing required metadata file: scripts\version_info.txt
    exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to upgrade pip.
    exit /b %ERRORLEVEL%
)

python -m pip install -r nestbrain\requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install application requirements.
    exit /b %ERRORLEVEL%
)

python -m pip install pyinstaller playwright
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install build tools.
    exit /b %ERRORLEVEL%
)

echo [2/3] Installing Playwright browsers...
set "PLAYWRIGHT_BROWSERS_PATH=0"
python -m playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Playwright Chromium browser.
    exit /b %ERRORLEVEL%
)

echo [3/3] Running PyInstaller...
cd scripts
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to switch to scripts directory.
    exit /b 1
)

pyinstaller --noconfirm build.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed!
    exit /b %ERRORLEVEL%
)

if not exist "dist\Nestbrain\Nestbrain.exe" (
    echo [ERROR] PyInstaller output missing: scripts\dist\Nestbrain\Nestbrain.exe
    exit /b 1
)

set "CHROMIUM_FOUND="
for /f %%F in ('dir /s /b "dist\Nestbrain\chrome.exe" 2^>nul') do set "CHROMIUM_FOUND=1"
if not defined CHROMIUM_FOUND (
    echo [ERROR] Bundled Chromium runtime not found in scripts\dist\Nestbrain.
    echo [ERROR] NotebookLM authentication in installer builds will fail without this artifact.
    exit /b 1
)

echo.
echo ==============================================
echo [SUCCESS] Build finished!
echo Executable is located in scripts\dist\Nestbrain\Nestbrain.exe
echo ==============================================
exit /b 0
