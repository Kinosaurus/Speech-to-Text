param(
    [string]$OutputDirectory,
    [switch]$ListVoices
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($ListVoices) {
        $taskSynth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
        return
    }
    $taskOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
    $taskJobs = Get-Content -LiteralPath (Join-Path $taskOutput 'synthesis-jobs.json') -Raw | ConvertFrom-Json
    $taskSynth.Rate = 0
    $taskSynth.Volume = 100
    $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    foreach ($taskJob in $taskJobs) {
        $taskAudio = [System.IO.Path]::GetFullPath($taskJob.audio)
        if (-not $taskAudio.StartsWith($taskOutput + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Synthesis output escaped the test directory.'
        }
        if (Test-Path -LiteralPath $taskAudio) { throw "Refusing to overwrite $taskAudio" }
        $taskSynth.SelectVoice($taskJob.voice)
        $taskSynth.SetOutputToWaveFile($taskAudio, $taskFormat)
        $taskSynth.Speak($taskJob.text)
        $taskSynth.SetOutputToNull()
        Write-Output "SYNTHESIZED $($taskJob.id)"
    }
} finally { $taskSynth.Dispose() }
