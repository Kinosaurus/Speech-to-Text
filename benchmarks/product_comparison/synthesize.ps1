param(
    [Parameter(Mandatory=$true)][string]$TextPath,
    [Parameter(Mandatory=$true)][string]$OutputPrefix,
    [int]$Rate = 0
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
Add-Type -ReferencedAssemblies System.Speech -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Speech.AudioFormat;
using System.Speech.Synthesis;
public sealed class LocalReadingMark {
    public string Kind;
    public string Text;
    public int CharacterPosition;
    public int CharacterCount;
    public double AudioSeconds;
    public double DurationSeconds;
}
public sealed class LocalReadingResult {
    public string Voice;
    public int Rate;
    public List<LocalReadingMark> Marks = new List<LocalReadingMark>();
}
public static class LocalReadingSynthesis {
    public static LocalReadingResult Generate(string[] lines, string wavPath, int rate) {
        var result = new LocalReadingResult();
        using (var synth = new SpeechSynthesizer()) {
            synth.SelectVoiceByHints(VoiceGender.Male, VoiceAge.Adult, 0,
                CultureInfo.GetCultureInfo("en-US"));
            synth.Rate = rate;
            result.Voice = synth.Voice.Name;
            result.Rate = rate;
            synth.SetOutputToWaveFile(wavPath,
                new SpeechAudioFormatInfo(16000, AudioBitsPerSample.Sixteen, AudioChannel.Mono));
            synth.SpeakProgress += (sender, e) => result.Marks.Add(new LocalReadingMark {
                Kind="word_start", Text=e.Text, CharacterPosition=e.CharacterPosition,
                CharacterCount=e.CharacterCount, AudioSeconds=e.AudioPosition.TotalSeconds });
            synth.PhonemeReached += (sender, e) => result.Marks.Add(new LocalReadingMark {
                Kind="phoneme", Text=e.Phoneme, AudioSeconds=e.AudioPosition.TotalSeconds,
                DurationSeconds=e.Duration.TotalSeconds });
            synth.BookmarkReached += (sender, e) => result.Marks.Add(new LocalReadingMark {
                Kind="bookmark", Text=e.Bookmark, AudioSeconds=e.AudioPosition.TotalSeconds });
            var prompt = new PromptBuilder(CultureInfo.GetCultureInfo("en-US"));
            prompt.AppendBreak(TimeSpan.FromSeconds(2));
            int index = 0;
            foreach (string line in lines) {
                if (String.IsNullOrWhiteSpace(line)) continue;
                prompt.AppendBookmark("line_" + index + "_start");
                prompt.AppendText(line.Trim());
                prompt.AppendBookmark("line_" + index + "_end");
                prompt.AppendBreak(TimeSpan.FromMilliseconds(800));
                index++;
            }
            prompt.AppendBreak(TimeSpan.FromSeconds(3));
            synth.Speak(prompt);
            synth.SetOutputToNull();
        }
        return result;
    }
}
'@
$resolvedText = (Resolve-Path -LiteralPath $TextPath).Path
$prefix = [System.IO.Path]::GetFullPath($OutputPrefix)
if (Test-Path -LiteralPath ($prefix + '.wav')) { throw 'Preserve existing recording; choose a new output prefix.' }
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($prefix)) | Out-Null
$result = [LocalReadingSynthesis]::Generate([System.IO.File]::ReadAllLines($resolvedText), $prefix + '.wav', $Rate)
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($prefix + '.marks.json') -Encoding UTF8
Write-Output ($result.Voice + ': generated local WAV and synthesis timing marks; no speaker playback.')
