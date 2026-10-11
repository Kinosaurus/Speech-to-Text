# Shared audio tests

These WAV files are copies of the project's resampled test recordings. Each is
16 kHz, mono, signed 16-bit PCM. They can be passed directly to `--files`; the
original recordings outside this folder are not required.

Start the ASR server and prepare the Windows client using the main
[README quickstart](../../README.md#quickstart--test-on-a-windows-pc-with-an-nvidia-gpu).
The commands below use `medium.en`. For model comparison, use the same recording
and settings, changing only `--model` to `small.en`. The first use of a model may
download its weights; model weights are not included with these recordings.

Run commands from the repository root. Run one recording per client session,
with the matching book manifest. The expected checkpoint counts below describe
the manifests, not guaranteed recognition results.

| Recording | Checkpoint manifest | Checkpoints |
|---|---|---|
| `tea.wav` | `examples/tea_story.json` | 3 |
| `fat_cat.wav` | `examples/fat_cat_story.json` | 2 |
| `horse.wav` | `examples/horse_story.json` | 1 |
| `little_mermaid.wav` | `examples/little_mermaid_story.json` | 2 |
| `dog.wav` | ASR only; omit `--checkpoints` | - |
| `recording_2.wav` | ASR only; omit `--checkpoints` | - |
| `dragon.wav` | ASR only; omit `--checkpoints` | - |
| `nickel.wav` | ASR only; omit `--checkpoints` | - |

## Test a recording with checkpoints

```powershell
.\.venv\Scripts\python.exe run_client.py --model medium.en --files .\examples\audio\tea.wav --mute_audio_playback --checkpoints .\examples\tea_story.json
```

To try another passage, change both the audio path and checkpoint path according
to the table. Look for `[TRIGGER]` and `[SKIPPED]`; completed means every
checkpoint was processed, including any skips. Effect payloads are printed;
physical playback is not implemented.

To compare automatic book hints on and off, repeat the same command with
`--no_book_context` added. Explicit manual hints still apply if supplied.

## Test recognition without checkpoints

```powershell
.\.venv\Scripts\python.exe run_client.py --model medium.en --files .\examples\audio\dog.wav --mute_audio_playback --n_display_segments 20 --enable_timestamps
```

`--mute_audio_playback` stops speaker playback but still sends the file to ASR.
Remove it to listen along. The client writes a transcript to `output.srt` on exit;
save that file before a later test overwrites it.

The client may create another `*_resampled.wav` in the repository root while
processing an input. Those generated files remain ignored by Git. These shared
fixtures are intentionally stored under `examples/audio/`. Audio stays excluded
from Docker build images; these commands use the native client and checkout.

## Source filenames

The shared files preserve the source audio bytes; only the filenames changed.

| Shared filename | Local source filename |
|---|---|
| `tea.wav` | `4YearOldTea_resampled.wav` |
| `fat_cat.wav` | `5YearOldFatCat_resampled.wav` |
| `horse.wav` | `5YearOldHorse_resampled.wav` |
| `little_mermaid.wav` | `4YearOldMermaid_resampled.wav` |
| `dog.wav` | `KidDog1_resampled.wav` |
| `recording_2.wav` | `Recording (2)_resampled.wav` |
| `dragon.wav` | `3YearOldDragon_resampled.wav` |
| `nickel.wav` | `3YearOldNickel_resampled.wav` |
