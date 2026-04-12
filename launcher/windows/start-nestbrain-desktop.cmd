@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"

pushd "%REPO_ROOT%" >nul

if exist "%VENV_PY%" (
  echo Starting Nestbrain with virtual environment interpreter...
  "%VENV_PY%" -m nestbrain.main
  set "EXIT_CODE=%ERRORLEVEL%"
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    echo ERROR: No virtual environment interpreter found at:
    echo   %VENV_PY%
    echo.
    echo And Python launcher ^(py^) is not available on PATH.
    echo.
    echo Fix:
    echo   1^) Create venv:  py -m venv .venv
    echo   2^) Install deps: .venv\Scripts\pip install -r nestbrain\requirements.txt
    echo   3^) Install browser: .venv\Scripts\playwright install chromium
    set "EXIT_CODE=1"
  ) else (
    echo Virtual environment not found, falling back to Python launcher ^(py^)...
    py -m nestbrain.main
    set "EXIT_CODE=%ERRORLEVEL%"
  )
)

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Nestbrain exited with code %EXIT_CODE%.
  echo Check startup logs at:
  echo   %APPDATA%\Nestbrain\logs\nestbrain.log
)

popd >nul
exit /b %EXIT_CODE%
