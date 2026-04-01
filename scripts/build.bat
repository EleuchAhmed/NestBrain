@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo Building Nestbrain Standalone Application
echo ==============================================

cd /d "%~dp0\.."

echo [1/3] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r nestbrain\requirements.txt
python -m pip install pyinstaller playwright

echo [2/3] Installing Playwright browsers...
python -m playwright install chromium

echo [3/3] Running PyInstaller...
cd scripts
pyinstaller --noconfirm build.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed!
    exit /b %ERRORLEVEL%
)

echo.
echo ==============================================
echo [SUCCESS] Build finished!
echo Executable is located in scripts\dist\Nestbrain.exe
echo ==============================================
pause
