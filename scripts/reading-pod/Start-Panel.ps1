param(
    [switch]$NoBrowser,
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [ValidateRange(1, 65535)]
    [int]$OscPort = 12346
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $root '.venv/Scripts/python.exe'
$output = Join-Path $root 'output/reading-pod'
$config = Join-Path $output 'recognition.json'
$bundle = Join-Path $root 'pod/mapmap'
$distro = 'Ubuntu'
if (Test-Path -LiteralPath $config -PathType Leaf) {
    $distro = (Get-Content -LiteralPath $config -Raw | ConvertFrom-Json).distro
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $output 'mapmap-runtime.txt') -PathType Leaf)) {
    throw 'Run Setup-Reading-Pod.ps1 before starting the panel. See docs/READING_POD_SETUP.md.'
}

$panelArguments = @(
    '-m', 'books_to_life.cli.operator_panel', '--port', $Port, '--osc-port', $OscPort,
    '--nemo-distro', $distro,
    '--mapmap-template', (Join-Path $bundle 'Reading Pod.mmp'),
    '--mapmap-project', (Join-Path $output 'Reading Pod.mmp'),
    '--mapmap-default-assignments', (Join-Path $bundle 'assignments.json'),
    '--mapmap-story-dir', (Join-Path $output 'live'),
    '--mapmap-launcher', (Join-Path $PSScriptRoot 'Start-MapMap.ps1')
)
if (-not $NoBrowser) { $panelArguments += '--open-browser' }

Push-Location -LiteralPath $root
try {
    & $python @panelArguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
