$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:npm_config_cache = Join-Path $PSScriptRoot '.npm-cache'
if (-not (Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE) { throw 'venv failed' } }
& .\.venv\Scripts\python.exe -m pip install --cache-dir .pip-cache -r requirements.txt
if ($LASTEXITCODE) { throw 'pip install failed' }
npm ci --no-audit --no-fund
if ($LASTEXITCODE) { throw 'npm ci failed' }
npm run build
if ($LASTEXITCODE) { throw 'build failed' }
Write-Host 'Ready. Run start.ps1.' -ForegroundColor Green
