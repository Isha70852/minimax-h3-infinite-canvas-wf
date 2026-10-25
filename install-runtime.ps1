$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.10 or newer and enable Add Python to PATH first.' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE) { throw 'venv failed' }
}
& .\.venv\Scripts\python.exe -m pip install --cache-dir .pip-cache -r requirements.lock.txt
if ($LASTEXITCODE) { throw 'pip install failed' }
Write-Host 'Ready. Double-click the launcher CMD or run start.ps1.'
