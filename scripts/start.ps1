# Starts (or restarts) the Kudos FastAPI dev server on http://localhost:8000
# Usage: powershell -ExecutionPolicy Bypass -File scripts/start.ps1 [-Reload]

param(
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtualenv not found at $Python. Create it first, e.g.:`n  python -m venv .venv`n  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "Freeing port 8000..."
$owningPids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($procId in $owningPids) {
    taskkill /F /PID $procId 2>$null | Out-Null
}
if ($owningPids) {
    Start-Sleep -Milliseconds 600
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
if ($Reload) {
    $uvicornArgs += "--reload"
}

Write-Host "Starting Kudos server at http://localhost:8000 ..."
& $Python @uvicornArgs
