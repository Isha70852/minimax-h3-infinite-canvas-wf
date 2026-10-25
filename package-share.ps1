$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path '.venv\Scripts\python.exe') { & .\.venv\Scripts\python.exe scripts\package_release.py }
else { python scripts\package_release.py }
if ($LASTEXITCODE) { throw 'Release packaging failed.' }
