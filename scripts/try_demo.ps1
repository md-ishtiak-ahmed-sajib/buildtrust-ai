$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    foreach ($tool in @('uv', 'node', 'npm')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "Install Python 3.12, uv and Node.js 24 first. See README.md. Missing: $tool"
        }
    }
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8003)
    try { $listener.Start() }
    catch { throw 'Port 8003 is already in use. Close the existing demo and try again.' }
    finally { $listener.Stop() }
    uv sync --project backend --locked
    if ($LASTEXITCODE -ne 0) { throw 'Backend setup failed. Check your connection and Python installation.' }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $lock = [System.BitConverter]::ToString($hasher.ComputeHash([System.IO.File]::ReadAllBytes((Join-Path $repoRoot 'frontend/package-lock.json')))).Replace('-', '')
    } finally { $hasher.Dispose() }
    $installed = Join-Path $repoRoot 'frontend/node_modules/.buildtrust-lock'
    if (-not (Test-Path -LiteralPath $installed) -or (Get-Content -LiteralPath $installed -Raw).Trim() -ne $lock) {
        npm --prefix frontend ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend setup failed. Check your connection and Node.js installation.' }
        Set-Content -LiteralPath $installed -Value $lock
    }
    # The build is small and must include the current source, even after a Git update.
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'The frontend could not be built. See the error above.' }
    Write-Host "`nPublic demo: http://127.0.0.1:8003"
    Write-Host 'Use the four public passwords in README.md. Your working app stays separate.'
    uv run --directory backend python -m app.public_demo
    if ($LASTEXITCODE -ne 0) { throw 'The public demo stopped with an error. See the message above.' }
} finally { Pop-Location }
