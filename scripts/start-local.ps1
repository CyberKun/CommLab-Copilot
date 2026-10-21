$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$stateDir = Join-Path $backendDir "data"
if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Create .venv and install backend dependencies first; see README." }
foreach ($port in @(8000, 5173)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop that service or run manually on different ports."
    }
}
New-Item -ItemType Directory -Force $stateDir | Out-Null
$api = Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn commlab.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput "$stateDir\api.log" -RedirectStandardError "$stateDir\api-error.log"
$worker = Start-Process -FilePath $pythonExe -ArgumentList "-m commlab.local_worker" -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput "$stateDir\worker.log" -RedirectStandardError "$stateDir\worker-error.log"
$vitePath = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
$web = Start-Process -FilePath (Get-Command node).Source -ArgumentList "`"$vitePath`" --host 127.0.0.1 --port 5173 --strictPort" -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput "$stateDir\web.log" -RedirectStandardError "$stateDir\web-error.log"
@(
    @{name="api"; id=$api.Id; started=$api.StartTime.ToUniversalTime().ToString("o")},
    @{name="worker"; id=$worker.Id; started=$worker.StartTime.ToUniversalTime().ToString("o")},
    @{name="web"; id=$web.Id; started=$web.StartTime.ToUniversalTime().ToString("o")}
) | ConvertTo-Json | Set-Content -LiteralPath "$stateDir\processes.json"
Write-Output "Started local API, development worker, and UI at http://127.0.0.1:5173. Logs: $stateDir"
