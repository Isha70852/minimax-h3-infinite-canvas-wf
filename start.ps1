$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe') -or -not (Test-Path 'dist\index.html')) {
    throw 'Please run setup.ps1 first.'
}
Write-Host 'H3 Canvas: http://127.0.0.1:8766' -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8766 --no-access-log
