param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [ValidateRange(1, 65535)]
    [int]$OscPort = 12346
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$output = Join-Path $root 'output/reading-pod'
$pointer = Join-Path $output 'mapmap-runtime.txt'
if (-not (Test-Path -LiteralPath $pointer -PathType Leaf)) {
    throw 'Run Setup-Reading-Pod.ps1 to build the Reading Pod version of MapMap.'
}
$exe = Join-Path $output (Get-Content -LiteralPath $pointer -Raw).Trim()
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw 'The Reading Pod MapMap executable was not found. Run Setup-Reading-Pod.ps1 again.'
}

$env:READING_POD_MAPMAP_PROJECT = $project
$env:QT_MEDIA_BACKEND = 'ffmpeg'
$env:QT_FFMPEG_DECODING_HW_DEVICE_TYPES = ','
$env:QT_DISABLE_HW_TEXTURES_CONVERSION = '1'
Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -ArgumentList @('-p', $OscPort, ('"{0}"' -f $project))
