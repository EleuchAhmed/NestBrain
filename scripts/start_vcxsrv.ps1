$ErrorActionPreference = "Stop"

$vcxCandidates = @(
    "C:\Program Files\VcXsrv\vcxsrv.exe",
    "C:\Program Files (x86)\VcXsrv\vcxsrv.exe"
)

$vcxPath = $vcxCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $vcxPath) {
    Write-Error "VcXsrv not found. Install it from https://sourceforge.net/projects/vcxsrv/"
}

$alreadyRunning = Get-Process -Name vcxsrv -ErrorAction SilentlyContinue
if ($alreadyRunning) {
    Write-Output "VcXsrv is already running."
    exit 0
}

# Host display bridge defaults:
# - :0 display
# - disable access control (-ac) for local Docker bridge convenience
# - multiwindow + clipboard integration
Start-Process -FilePath $vcxPath -ArgumentList @(
    ":0",
    "-multiwindow",
    "-clipboard",
    "-wgl",
    "-ac"
)

Write-Output "VcXsrv started on display :0"
Write-Output "Set DISPLAY=host.docker.internal:0.0 in .env for Docker containers."
