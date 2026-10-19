$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$mediaDir = Join-Path $repoRoot 'data\media'
New-Item -ItemType Directory -Force -Path $mediaDir | Out-Null
Add-Type -AssemblyName System.Speech
$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $narrator.SelectVoice('Microsoft Zira Desktop')
    $narrator.Rate = 0
    $segments = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'demo_segments.json') -Raw | ConvertFrom-Json
    for ($sceneIndex = 0; $sceneIndex -lt $segments.Count; $sceneIndex++) {
        $narrator.SetOutputToWaveFile((Join-Path $mediaDir ("scene-{0}.wav" -f $sceneIndex)))
        $narrator.Speak($segments[$sceneIndex].text)
        $narrator.SetOutputToNull()
    }
    Write-Host 'Generated local Windows synthetic narration for nine scenes.'
} finally { $narrator.Dispose() }
