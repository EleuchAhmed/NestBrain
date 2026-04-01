@echo off
setlocal

set SCRIPT_DIR=%~dp0
set VBS=%SCRIPT_DIR%start-research-pipeline.vbs

if not exist "%VBS%" (
  echo ERROR: %VBS% was not found.
  exit /b 1
)

wscript.exe "%VBS%"
endlocal
