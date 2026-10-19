$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 24 LTS first.' }
    uv sync --project backend --locked
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    uv run --directory backend python -m app.seed
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
    Write-Host "`nDemo accounts (local sandbox only):"
    $runtimeDir = if ($env:BUILDTRUST_DATA_DIR) { $env:BUILDTRUST_DATA_DIR } else { Join-Path $repoRoot 'data' }
    Get-Content -LiteralPath (Join-Path $runtimeDir 'demo-credentials.json')
    Write-Host "`nReady. Run: .\scripts\run_demo.ps1"
} finally { Pop-Location }
