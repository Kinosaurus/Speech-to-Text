# Recordings and reading text

Open the [recording library](library/README.md) for the complete catalogue.

Each story groups its readers under `library/stories/<story>/readers/<reader>/`:

- `passage.txt`: original supplied reading text, when available.
- `reference.txt`: a separately labelled corpus reference when original print is unavailable; check `text_status.json`.
- `transcript.txt` / `transcript.srt`: recorded speech, including reading mistakes, adult prompts or ASR errors.
- `audio.wav`: recording, or `audio.json` linking to a shared canonical recording.
- `checkpoints.json`: matching checkpoints; `expected.json` contains provisional timing when available.
- `checkpoint_status.json` or `recording_status.json`: explicitly missing checkpoints or audio.

The supplied Tea, Fat Cat, Horse and Little Mermaid passages sit beside their audio and transcripts. The sample microphone demo has passage text and checkpoints but no matching recording. Multiple CJ-and-Marcus and Grandma readers share story folders; partial peanut decoding is labelled separately from full reading.

Complete source sessions are under `library/full_sessions/`; complete reading tasks are under `library/reading_sessions/`. Whole sessions have checkpoint coverage only for their reading interval. `library/transcript_history/` retains older ASR variants. The two timestamp-review clips are under `library/reviews/timestamp_check/`.

Old root WAVs, `ocsc_more/`, `ocsc_batch2/`, `transcripts/`, `cache/` and `examples/` copies have been retired after preservation checks. `library/migration.json` resolves historical paths. Unique old metadata is retained under `library/provenance/`; historical benchmark results are not rewritten.

```powershell
.venv/Scripts/python.exe -m books_to_life.cli.run_client --model parakeet-nemo --port 9097 --matching_mode split --files recordings/library/stories/tea/readers/tea/audio.wav --checkpoints recordings/library/stories/tea/readers/tea/checkpoints.json --mute_audio_playback
```

New microphone captures use `library/captures/<session>/audio.wav` and `transcript.srt`. File-run transcripts use the recording folder's `asr/` directory; external or multi-file runs use `library/runs/`. Temporary resampling uses `library/.cache/`.

The eight original public recordings and supplied texts are tracked at their new paths. OCSC media, transcripts and derived references remain Git-ignored. See [OCSC_LOCAL_SETUP.md](OCSC_LOCAL_SETUP.md) for local corpus use and transfer restrictions.

Refresh the catalogue with `python benchmarks/organize_recording_library.py`; verify preserved assets with `python benchmarks/verify_recording_library.py`.
