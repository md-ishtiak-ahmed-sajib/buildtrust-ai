$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\dist\index.html'))) { throw 'Run scripts/setup.ps1 first.' }
Push-Location $repoRoot
try { uv run --directory backend python -m app.seed; uv run --directory backend uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000 }
finally { Pop-Location }
