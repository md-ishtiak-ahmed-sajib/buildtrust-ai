$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    uv run --project backend pytest backend/tests
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    npm --prefix frontend test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
