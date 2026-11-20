@echo off
setlocal DisableDelayedExpansion
set "READING_POD_ROOT=%~dp0"

powershell.exe -NoLogo -NoProfile -Command ^
    "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';" ^
    "$url = 'http://127.0.0.1:8765/';" ^
    "function Test-ReadingPod {" ^
    "    try {" ^
    "        $status = Invoke-RestMethod ($url + 'api/session') -UseBasicParsing -TimeoutSec 2;" ^
    "        return $null -ne $status.recognition;" ^
    "    } catch { return $false }" ^
    "};" ^
    "if (Test-ReadingPod) { Start-Process $url; exit 0 };" ^
    "$checkout = Join-Path $env:READING_POD_ROOT 'output\reading-pod-first-pipeline';" ^
    "$python = Join-Path $checkout '.venv\Scripts\python.exe';" ^
    "if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw ('Panel Python was not found at ' + $python) };" ^
    "$handoff = Join-Path $env:READING_POD_ROOT 'output\mapmap-other-pc\MapMap-Reading-Pod-Handoff';" ^
    "$bridge = Join-Path $handoff 'Reading Pod MapMap\Sky Garden\play_cue.py';" ^
    "$master = Join-Path $handoff 'Reading Pod MapMap\Sky Garden\Sky Garden - Two Scenes.mmp';" ^
    "$quote = [char]34;" ^
    "$panelArgs = @('-m', 'books_to_life.cli.operator_panel', '--mapmap-bridge', ($quote + $bridge + $quote), '--mapmap-project', ($quote + $master + $quote), '--mapmap-story-dir', 'output\operator-mapmap\live', '--osc-port', '12346');" ^
    "Write-Host 'Starting the Reading Pod panel...';" ^
    "$server = Start-Process -FilePath $python -ArgumentList $panelArgs -WorkingDirectory $checkout -NoNewWindow -PassThru;" ^
    "$deadline = (Get-Date).AddSeconds(45);" ^
    "while (-not (Test-ReadingPod)) {" ^
    "    if ($server.HasExited) { throw 'The panel server exited during startup. See the output above.' };" ^
    "    if ((Get-Date) -ge $deadline) { throw ('The panel did not respond at ' + $url) };" ^
    "    Start-Sleep -Milliseconds 300;" ^
    "};" ^
    "Write-Host 'Keep this window open while using the panel. Press Ctrl+C here to stop it.';" ^
    "Start-Process $url;" ^
    "$server.WaitForExit(); exit $server.ExitCode"

set "result=%errorlevel%"
if %result% neq 0 pause
exit /b %result%
