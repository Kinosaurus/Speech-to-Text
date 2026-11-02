param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
$taskJobs = Get-Content -LiteralPath (Join-Path $taskOutput 'jobs.json') -Raw | ConvertFrom-Json
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskSynth.SelectVoice('Microsoft Zira Desktop')
    $taskSynth.Rate = 0
    $taskSynth.Volume = 100
    $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    foreach ($taskJob in $taskJobs) {
        if (Test-Path -LiteralPath $taskJob.audio) { throw "Refusing to overwrite $($taskJob.audio)" }
        $taskAudio = [System.IO.Path]::GetFullPath($taskJob.audio)
        if (-not $taskAudio.StartsWith($taskOutput + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Audio output escaped the challenge directory.'
        }
        $taskSynth.SetOutputToWaveFile($taskAudio, $taskFormat)
        $taskSynth.SpeakSsml((Get-Content -LiteralPath $taskJob.ssml -Raw))
        $taskSynth.SetOutputToNull()
        Write-Output "SYNTHESIZED $($taskJob.id)"
    }
} finally { $taskSynth.Dispose() }
