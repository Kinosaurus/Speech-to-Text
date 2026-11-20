param(
    [string]$QtBin = 'C:\Qt\6.12.0\mingw_64\bin',
    [string]$MinGWBin = 'C:\Qt\Tools\mingw1310_64\bin'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$output = Join-Path $root 'output/reading-pod'
$patch = Join-Path $root 'pod/mapmap/reading-pod.patch'
$revision = 'cc29e940385aa85c14a28832b20315dc2378b89d'
$patchHash = (Get-FileHash -LiteralPath $patch -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$buildName = 'mapmap-' + $revision.Substring(0, 8) + '-' + $patchHash
$source = Join-Path $output "$buildName/src"
$build = Join-Path $output "$buildName/build"
$runtime = "$buildName/build/MapMap/MapMap.exe"
$exe = Join-Path $output $runtime
$ready = Join-Path $output "$buildName/ready"

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE." }
}

if (-not ((Test-Path -LiteralPath $ready -PathType Leaf) -and (Test-Path -LiteralPath $exe -PathType Leaf))) {
    $qmake = Join-Path $QtBin 'qmake.exe'
    $deploy = Join-Path $QtBin 'windeployqt.exe'
    $make = Join-Path $MinGWBin 'mingw32-make.exe'
    foreach ($tool in @($qmake, $deploy, $make)) {
        if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
            throw "Missing $tool. See docs/READING_POD_SETUP.md for the Qt Multimedia and MinGW prerequisites."
        }
    }

    New-Item -ItemType Directory -Force $source, $build | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $source '.git') -PathType Container)) {
        Invoke-Checked git @('-C', $source, 'init', '--quiet')
    }
    & git -C $source cat-file -e "$revision^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Checked git @('-C', $source, 'fetch', '--no-tags', '--depth=1', 'https://github.com/mapmapteam/mapmap.git', $revision)
    }
    Invoke-Checked git @('-C', $source, '-c', 'core.autocrlf=false', 'checkout', '--quiet', '--detach', $revision)
    & git -C $source apply --reverse --check $patch 2>$null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Checked git @('-C', $source, '-c', 'core.autocrlf=false', 'apply', $patch)
    }

    $originalPath = $env:Path
    Push-Location -LiteralPath $build
    try {
        $env:Path = "$MinGWBin;$QtBin;$originalPath"
        Invoke-Checked $qmake @((Join-Path $source 'mapmap.pro'), 'CONFIG+=release', 'CONFIG-=debug')
        Invoke-Checked $make @('-j4')
        Invoke-Checked $deploy @('--release', '--no-system-d3d-compiler', $exe)
        Copy-Item -LiteralPath (Join-Path $source 'LICENSE') -Destination (Split-Path -Parent $exe)
        Set-Content -LiteralPath $ready -Value $revision -Encoding ASCII
    } finally {
        $env:Path = $originalPath
        Pop-Location
    }
}

Set-Content -LiteralPath (Join-Path $output 'mapmap-runtime.txt') -Value $runtime -Encoding ASCII
Write-Host "Reading Pod MapMap is ready at $exe"
