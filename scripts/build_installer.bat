@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo Building Nestbrain Production Installer
echo ==============================================

cd /d "%~dp0\.."
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to switch to repository root.
    exit /b 1
)

if not exist "scripts\build.spec" (
    echo [ERROR] Missing scripts\build.spec
    exit /b 1
)

if not exist "scripts\version_info.txt" (
    echo [ERROR] Missing scripts\version_info.txt
    exit /b 1
)

if not exist "installer.iss" (
    echo [ERROR] Missing installer.iss
    exit /b 1
)

if not exist "installer_assets\license.txt" (
    echo [ERROR] Missing installer_assets\license.txt
    exit /b 1
)

echo [1/3] Building PyInstaller distribution...
call scripts\build.bat
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build step failed.
    exit /b %ERRORLEVEL%
)

if not exist "scripts\dist\Nestbrain\Nestbrain.exe" (
    echo [ERROR] Expected build output missing: scripts\dist\Nestbrain\Nestbrain.exe
    exit /b 1
)

echo [2/3] Resolving Inno Setup compiler...
set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" (
    set "ISCC_EXE="
)

if "%ISCC_EXE%"=="" (
    for /f "usebackq delims=" %%I in (`where ISCC.exe 2^>nul`) do (
        if "%ISCC_EXE%"=="" set "ISCC_EXE=%%I"
    )
)

if "%ISCC_EXE%"=="" (
    echo [ERROR] Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH.
    exit /b 1
)

echo [3/3] Compiling installer with Inno Setup...
"%ISCC_EXE%" "installer.iss"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b %ERRORLEVEL%
)

if not exist "dist\installer\NestbrainSetup.exe" (
    echo [ERROR] Expected installer output missing: dist\installer\NestbrainSetup.exe
    exit /b 1
)

echo.
echo ==============================================
echo [SUCCESS] Installer build completed.
echo Output: dist\installer\NestbrainSetup.exe
echo ==============================================
exit /b 0
