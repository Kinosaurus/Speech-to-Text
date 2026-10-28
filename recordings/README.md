# Recordings and matching transcripts

For the exact OCSC subset, redistribution restrictions, and commands to transfer
your existing local data to another PC, see [OCSC_LOCAL_SETUP.md](OCSC_LOCAL_SETUP.md).

All project recording audio is consolidated here. For each recording, matching
filenames identify its audio, readable transcript and subtitles:

```text
recordings/
  tea.wav
  tea.txt
  tea.srt
  6008_reading.wav
  6008_reading.txt
  6008_reading.srt
  6008_full.wav
  6008_full.txt
  6008_full.srt
  6008_full.cha
  transcripts/<recording>/<original-run>.srt
  transcripts/unmatched/root-output.srt
  cache/previous-resamples/
  index.json
```

## Available recordings

| Recording stem | Contents | Checkpoints |
| --- | --- | --- |
| `tea` | Original repo sample | `examples/tea_story.json` |
| `fat_cat` | Original repo sample | `examples/fat_cat_story.json` |
| `horse` | Original repo sample | `examples/horse_story.json` |
| `little_mermaid` | Original repo sample | `examples/little_mermaid_story.json` |
| `dog`, `dragon`, `nickel`, `recording_2` | Original repo samples / off-book controls | None |
| `6008_reading`, `7057_reading` | OCSC reading-task clips, 16 kHz mono | Local `output/ocsc/manifests/` |
| `6008_full`, `7057_full` | Complete original OCSC sessions, 44.1 kHz mono | Full sessions, not the benchmark clips |

The eight original samples and their selected transcripts are included in Git.
OCSC media, its transcripts, all historical runs, the conversion cache and the
local index remain ignored. Downloaded originals outside the project were
copied here without removing the user's Downloads files.

## What the transcript files mean

- Beside each original sample and reading clip, `.txt` and `.srt` contain the
  final ASR output from the latest full Parakeet comparison without book hints.
  Reading mistakes and recognition errors are preserved. These are not cleaned
  book passages or manually verified reference transcripts.
- Full-session OCSC `.cha` files are the corpus transcripts. Their `.txt` files
  preserve speaker-labelled main turns, and `.srt` files use the corpus's
  automatically aligned utterance timestamps. Untimed turns remain in the text
  and CHAT files; they cannot be given invented subtitle times. No new whole-
  session Parakeet inference was run.
- `transcripts/<recording>/` retains every historical SRT, labelled by original
  folder/run. A no-hints transcript is selected beside the main WAV for browsing;
  different models and hint conditions remain separate in the history.
- The old root `output.srt` is a microphone session without confidently matched
  saved audio. It is retained in `transcripts/unmatched/`, not assigned to a
  different child's recording.
- `index.json` records audio/transcript pairs, provenance, original paths and
  SHA-256 hashes. It maps old transcript locations mentioned in historical
  benchmark reports to their new locations. Historical result JSON and logs
  are unchanged. All moved/copied files were hash checked.

Generated root-level resampled WAVs were verified PCM-identical to their input
fixtures and moved to `cache/previous-resamples/`. They are not additional
recordings. Existing ready-to-stream PCM is now reused directly. Other audio
formats are converted under `recordings/cache/` instead of the project root.

## Run a recording

From the project root, with the installed server running:

```powershell
.\.venv\Scripts\python.exe run_client.py --model parakeet-nemo --port 9097 --matching_mode split --files recordings/tea.wav --mute_audio_playback --checkpoints examples/tea_story.json
```

Without `--transcript_file`, new file-session transcripts go to
`recordings/transcripts/<recording>/live-<timestamp>.srt`. Microphone sessions
use matching `recordings/microphone-<timestamp>.wav` and `.srt` names (audio is
saved only with `--save_output_recording`). An explicit output path still works.
The paced player, audio packets and tracker logic are unchanged by this cleanup.
