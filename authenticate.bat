@echo off
echo.
echo ╔══════════════════════════════════════════════╗
echo ║     NotebookLM MCP Authentication Helper       ║
echo ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0\antigravity-notebooklm-mcp"
if not exist node_modules (
    echo Installing dependencies...
    npm install
)

echo Opening browser for authentication...
node build/browser-auth.js

if %errorlevel% neq 0 (
    echo.
    echo ❌ Error: Failed to open browser.
    echo Ensure Node.js is installed and you have an active internet connection.
    pause
) else (
    echo.
    echo ✅ Authentication successful!
)
pause
