$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Path '.test-temp' -Force | Out-Null
$testTemp = Join-Path $PSScriptRoot ('.test-temp\' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest -q --basetemp $testTemp
if ($LASTEXITCODE) { throw 'Backend tests failed' }
npm test
if ($LASTEXITCODE) { throw 'Frontend logic tests failed' }
npm run build
if ($LASTEXITCODE) { throw 'Frontend build failed' }
