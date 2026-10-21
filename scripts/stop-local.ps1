$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot "backend\data\processes.json"
if (Test-Path -LiteralPath $pidFile) {
    foreach ($entry in (Get-Content -LiteralPath $pidFile | ConvertFrom-Json)) {
        $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime() -eq ([datetime]$entry.started).ToUniversalTime()) {
            Stop-Process -Id $process.Id
        }
    }
    Remove-Item -LiteralPath $pidFile
}
