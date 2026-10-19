$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiProcess = Start-Process -FilePath 'uv' -ArgumentList 'run --directory backend uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000 --reload' -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru
Push-Location $repoRoot
try { npm --prefix frontend run dev }
finally { if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }; Pop-Location }
