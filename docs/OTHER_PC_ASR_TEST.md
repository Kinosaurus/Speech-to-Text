# ASR test checklist for the other PC

Run commands from the repository root. The [saved comparison](../benchmarks/README.md#saved-asr-comparison) gives you the baseline for interpreting the new PC’s results.

## Get a baseline on the other PC

1. **Pull `codex/nemotron-asr-comparison`.** In an existing checkout, run `git fetch origin`, `git switch codex/nemotron-asr-comparison`, and `git pull --ff-only`. A fresh clone can use `git clone -b codex/nemotron-asr-comparison https://github.com/Kinosaurus/Speech-to-Text.git`.
2. **Check the tracker and speakers.** Install the Windows client dependencies using the [running guide](RUNNING.md). Run `python -m unittest discover -s tests -p "*phonetic*.py"` with that environment’s Python. Then run the [sound playback demo](SOUND_PLAYBACK.md) and confirm that the effect plays once through the intended speakers.
3. **Smoke-test Nemotron 160 ms.** Use Ubuntu under WSL with CUDA visible to `nvidia-smi` and follow the [NeMo prerequisites](RUNNING.md#parakeet-with-moving-phrase-hints-nemo-linuxwsl-cuda). Use a separate WSL Python environment. The two commands below install the benchmark dependencies and download the pinned 2.47 GB checkpoint. Skip the download if that checkpoint is already in `model-cache/nemotron-nemo/`.

   ```bash
   python -m pip install --no-cache-dir -r requirements/requirements-nemotron-benchmark.txt 'rapidfuzz>=3.14,<4' 'cmudict==1.1.3'
   python benchmarks/download_nemotron.py
   ```

   Run the same tracked WAVs with hints off and with next-checkpoint-only hints. Each run writes a local JSON containing the cue IDs, trigger clocks and final text. This smoke test uses the benchmark adapter.

   ```bash
   python - <<'PY'
   from pathlib import Path
   from benchmarks.replay_nemotron_corpus import MODEL, load_model, read, replay, sha, write

   output = Path('output/other-pc-nemotron-smoke')
   output.mkdir(parents=True, exist_ok=True)
   for label, lookahead in [('off', None), ('next-only', 0)]:
       model = load_model(MODEL, chunk_ms=160, enable_hints=lookahead is not None)
       for story in ('horse', 'tea', 'little_mermaid'):
           audio = Path(f'recordings/library/stories/{story}/readers/{story}/audio.wav')
           manifest = audio.with_name('checkpoints.json')
           checkpoints = read(manifest)['checkpoints']
           row = dict(name=story, audio=audio.as_posix(), audio_sha256=sha(audio),
                      manifest_sha256=sha(manifest), expected=[cue['id'] for cue in checkpoints])
           result = replay(model, row, lookahead=lookahead)
           write(output / f'{story}-{label}.json', result)
           print(story, label, result['tracker_counts'], flush=True)
       del model
   PY
   ```

4. **Try live reading with the existing Parakeet setup.** Use the [file and microphone client](RUNNING.md) in `--matching_mode split` with `--no_book_context` as the baseline. Record the mic, GPU, cue hits, duplicates and early firings. Try an accurate read, a pause mid-cue, a skipped cue, a reread and off-book speech. For live latency, capture the cue ending and the audible effect in the same recording. The Nemotron smoke test measures replay timing.

## Evaluate the matcher change

5. **Use the current RapidFuzz and CMU pronunciation matcher as the baseline.** Double Metaphone would be an additional experiment. Replay identical ASR callbacks through the current tracker and each candidate. Track correct hits, early or wrong hits, misses, duplicates and time from cue end. Include the [known wrong-word controls](EFFECT_POLICIES.md#contextual-phonetic-endpoints), short cues and adjacent cues. Check split words such as “drag on” separately from homophones. Keep the existing one-shot guards in each run so the comparison measures the matching change.
6. **Expand to the full corpus after the smoke test.** Copy the original local `recordings/library/` inputs and `output/parakeet-corpus/` archive through a [private transfer](../recordings/OCSC_LOCAL_SETUP.md). The full runner checks the original recording hashes and uses the archive’s file list and references. Keep raw recordings and replay logs local. Use fresh output paths on the other PC.

   ```bash
   python benchmarks/replay_nemotron_corpus.py --output output/other-pc-nemotron-off
   python benchmarks/replay_nemotron_corpus.py --rolling-lookahead 0 --output output/other-pc-nemotron-next
   ```
