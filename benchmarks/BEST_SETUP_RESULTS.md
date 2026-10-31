# Best-setup streaming verification after project reorganization

Date: 31 October 2026. **26/27 configured reading checkpoints fired across nine fresh streams. Zero triggers occurred in 36 unrelated-audio/manifest comparisons.** This repeats the earlier coverage result after moving application code into the `books_to_life` package. It does not establish production accuracy.

## Configuration

- Parakeet Unified NeMo 0.6B; RTX 3070 Ti 8 GB; WSL Ubuntu-24.04; CUDA bfloat16.
- 560 ms chunk + 560 ms right context; 5.6 seconds left history; server boost 1.0, with no phrase hints supplied.
- Windows application client; `--model parakeet-nemo --matching_mode split --no_book_context`; current split mode is `TimelyEvidenceMatcher`.
- Threshold 82, stability 2, minimum coverage 0.8; existing frozen manifests; no threshold, anchor, or model tuning during these trials.
- Actual WAV audio paced through the application WebSocket connection in 4096-sample packets at 16 kHz. Not saved-transcript replay.
- One run per recording, no separate recognition warmup. The first run includes first-inference effects. No GPU clock or power changes were made.
- Windows Python 3.10.7 / WhisperLive 0.10.0; WSL Python 3.12.3 / Torch 2.7.1 / NeMo package version 3.1.0. GPU driver 610.88, power limit 310 W.

## Fresh reading results

| Recording | Current triggers / configured | Missing | Median estimated delay among detections |
| --- | ---: | --- | ---: |
| 3a14g_EN-OL-RC-234_1 | 3/3 | None | 0.482 s |
| 3a14g_EN-OL-RC-234_2 | 3/3 | None | 0.849 s |
| 3c29g_EN-OL-RC-234_1 | 3/3 | None | 0.664 s |
| 3c29g_EN-OL-RC-234_2 | 3/3 | None | 1.002 s |
| 3d60g_EN-OL-RC-234_1 | 3/3 | None | 0.784 s |
| 3d60g_EN-OL-RC-234_2 | 3/3 | None | 0.952 s |
| making-kites-7028 | 3/3 | None | 1.176 s |
| billy-visits-grandpa-6027 | 2/3 | cookies_and_chess | 1.442 s |
| tom-s-secret-study-7015 | 3/3 | None | 0.666 s |

The six MPS streams fired **18/18** checkpoints; Kites/Billy/Tom fired **8/9**. Billy's final checkpoint remains missed, as in the earlier no-hints baseline. The original alignment observer fired **24/27** on these same live recognition callbacks; the current tracker fired **26/27**. This is a tracker comparison on shared ASR, not a new comparison between recognizers.

Among the 26 activations, median estimated endpoint-to-trigger delay was **0.886 s**, with a range of **0.017–1.935 s**. No activation was more than one second early against those estimates. The earlier nine-recording no-hints median was 0.830 s; one repetition with automatic endpoints does not establish a meaningful latency change.

Median time from the first audio packet to first ASR text was **2.730 s**; the first recording took **4.706 s**. First-text time is a startup measure, not checkpoint delay. Do not equate model chunk size or ASR snapshot end time with word-to-effect latency.

## Unrelated-speech controls

Four fresh streams (dog, dragon, nickel, recording_2) were evaluated against all nine passage manifests: **36 audio/manifest comparisons, zero activations** for the current tracker, and zero for the original, older split, and boundary observers. Repeated passages and shared audio mean these are not 36 independent books/readers. These controls do not test near-book conversation, adult prompting, negation, interruptions, or genuine skipping.

## Audit and evidence

- Every reading stream delivered every WAV sample, produced recognition before EOF, and received STREAM_DONE. All four controls delivered every sample and completed their final response and normal close checks.
- Application trigger sequences matched the current tracker observer in all nine reading runs. No duplicate triggers or unexpected checkpoint IDs were found.
- Audio and frozen-manifest hashes, observed trigger delays, source hashes, and runtime versions are in the [measurement summary](results/best-setup-2026-10-31.json). It contains no raw audio, passages, or ASR transcripts.
- All nine audio and manifest hashes match the earlier baseline. Exact executed Python sources were preserved locally in `output/best-setup-2026-10-31-verified/source-snapshot/` and checked against the recorded protocol hashes.
- Inference, client, matcher, and live-probe sources were unchanged during the sweep. After the streams completed, the coordinator report reader was repaired to tolerate legacy Windows stdout encoding, and future subprocesses were configured for UTF-8. Both coordinator source hashes are retained in the summary. No audio stream was rerun to select a result.
- Word endpoints are the previously frozen, no-prompt small.en/medium.en acoustic estimates, mapped onto each fresh run's actual packet clock. They were not manually checked and are not ground truth. See the [timing method and provenance](READING_CONTEXT_RESULTS.md).
- Six distinct reading subjects and a few passages; these recordings were already used in development. Trigger count does not prove scene correctness or timely effect playback. Projector/audio/lighting integration remains outside this test.
- No fresh Whisper, Vulkan, microphone, Jetson, or Pi run was performed in this sweep. Prior comparisons inform the choice of recognizer; these trials verify the selected setup after reorganization.

Raw artifacts are preserved locally under `output/best-setup-2026-10-31-verified/`. The initial server log is under `output/best-setup-2026-10-31/server.log`; the first attempt in that folder stopped before audio because sandboxed Windows-to-WSL sockets were unavailable. Restricted corpus inputs and raw transcripts remain ignored by Git.

## Reproduce

Start the prepared NeMo server with the settings in [setups and tradeoffs](../docs/SETUPS.md), then run:

```powershell
.\.venv\Scripts\python.exe -X utf8 -u benchmarks/run_best_setup.py --output output/best-setup-new-run
```

The helper requires the locally acquired MPS and published-passage inputs and prior timing artifacts. Choose a new output folder for each new sweep. For an existing completed sweep, use `--summarize-only` to audit and regenerate the summary without replaying audio.

All 119 unit tests, CLI help smoke checks for all seven launchers, the default checkpoint demo, the recording-library verifier, and all four Compose configuration validations are checked separately from the audio measurements. Container images and board deployments were not rebuilt in this sweep.
