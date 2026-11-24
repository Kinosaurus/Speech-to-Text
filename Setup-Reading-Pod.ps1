param(
    [string]$Distro = 'Ubuntu',
    [string]$QtBin = 'C:\Qt\6.12.0\mingw_64\bin',
    [string]$MinGWBin = 'C:\Qt\Tools\mingw1310_64\bin',
    [switch]$SkipRecognition
)

$ErrorActionPreference = 'Stop'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE." }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    & (Join-Path $PSScriptRoot 'scripts/reading-pod/Build-MapMap.ps1') -QtBin $QtBin -MinGWBin $MinGWBin
    $python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Invoke-Checked py.exe @('-3.12', '-m', 'venv', '.venv')
    }
    Invoke-Checked $python @('-m', 'pip', 'install', '-r', 'requirements/requirements-client.txt')
    Invoke-Checked $python @('-m', 'pip', 'install', '--no-deps', 'whisper-live==0.10.0')
    Invoke-Checked npm.cmd @('--prefix', 'operator-panel', 'ci')
    Invoke-Checked npm.cmd @('--prefix', 'operator-panel', 'run', 'build')

    if (-not $SkipRecognition) {
        Invoke-Checked wsl.exe @('-d', $Distro, '--cd', $PSScriptRoot, '--exec', 'bash', 'scripts/reading-pod/install-nemo.sh')
        @{ distro = $Distro } | ConvertTo-Json | Set-Content 'output/reading-pod/recognition.json' -Encoding UTF8
    }
} finally {
    Pop-Location
}

Write-Host 'Setup complete. Open Start Reading Pod Panel.cmd.'
