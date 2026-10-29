# Local OCSC inputs

OCSC corpus data live under `recordings/library/`. They are deliberately local and Git-ignored. Contributor permission for web redistribution has not been obtained; do not force-add these files, attach them to public issues/releases, or publish them via Git LFS. See [TalkBank rules](https://talkbank.org/0share/rules.html).

## Locations

- `library/full_sessions/<reader>/`: complete source WAV, original CHAT, exported corpus transcript and subtitles.
- `library/reading_sessions/<reader>/`: complete reading task, corpus transcript, selected ASR transcript where available, checkpoints and expected timing.
- `library/stories/<story>/readers/<reader>/`: passage-level audio/text/checkpoints with reader-specific variants.
- `library/jobs/`: current per-reader benchmark definitions for the two newer batches.
- `library/evaluation/ocsc_subsets/`: standard/early Grandma benchmark definitions.
- `library/reviews/timestamp_check/`: audio excerpts and provisional acoustic boundary checks.

Original source times and SHA-256 hashes are retained in source/provenance metadata. Corpus timings are automatically aligned, not manually verified gold. Transcript-derived references are labelled; they must not be presented as original printed books.

## Run a recording

With the GPU ASR server running:

```powershell
.venv/Scripts/python.exe run_client.py --model parakeet-nemo --server GPU_PC_IP --port 9097 --matching_mode split --files recordings/library/reading_sessions/7057/audio.wav --checkpoints recordings/library/reading_sessions/7057/checkpoints_early.json --no_book_context --mute_audio_playback
```

Use each reader's own manifest. Full sessions include non-reading tasks and should not substitute for reading clips in comparisons. A matched checkpoint does not establish timely activation; inspect evaluation reports for misses and long delays.

## Another personal PC

Copy the local corpus library directly between your own PCs while preserving its layout. Keep the public sample/demo folders from Git and the restricted corpus folders local. Do not upload the corpus library to share it.

The existing optional transfer CLI supports the original 6008/7057 subset and now exports canonical library paths. It creates an archive only if you explicitly run `export`; cleanup itself creates no archive:

```powershell
.venv/Scripts/python.exe benchmarks/ocsc_local_bundle.py export --output output/ocsc-private-transfer.zip
.venv/Scripts/python.exe benchmarks/ocsc_local_bundle.py verify --archive output/ocsc-private-transfer.zip
.venv/Scripts/python.exe benchmarks/ocsc_local_bundle.py import --archive D:/Transfer/ocsc-private-transfer.zip
```

Import verifies hashes and rejects conflicting existing files. Supported older archive paths are mapped into the canonical library; legacy recording folders are not recreated. This optional subset archive is not a complete export of every newer reader.

Official source: [Ohio Child Speech Corpus](https://talkbank.org/childes/access/Eng-NA/OCSC.html). Use your own TalkBank account for fresh downloads. Cite Wagner et al. (2025), *The Ohio Child Speech Corpus*, Speech Communication 170, 103206.
