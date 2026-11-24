# Nemotron comparison and panel integration, 22 November 2026

## ASR only: six setups on the same recordings

All six setups completed the same 31 recordings (186 trials). Scores below use
27 recordings across nine passage sections, with 2,345 reference words and 50
eligible exact cues. Four supplied-text checks remain separate from these scores.
No tracker or phonetic matching ran in this experiment.

| Setup | WER | Exact cues | Shared-cue median estimated delay |
|---|---:|---:|---:|
| Parakeet NeMo, fixed cue hints | 12.1% | 45/50 | 1.15 s |
| KeenASR Web SDK, full-passage graph | 11.7% | 48/50 | 0.36 s |
| Whisper Tiny English, CPU | 27.9% | 19/50 | 2.06 s |
| Moonshine Medium, CPU | 18.6% | 33/50 | 2.90 s |
| Nemotron 160 ms, fixed cue hints | 11.7% | 47/50 | 0.40 s |
| Nemotron 320 ms, fixed cue hints, experimental | 11.6% | 47/50 | 0.40 s |

Delay uses the same 15 cues recognized by all six setups. Automatic acoustic
endings are estimates, not manually reviewed timing ground truth. GPU trials
simulate paced packet arrivals and include measured synchronous processing;
CPU/Keen trials use actual paced wall-clock replay. Cold model/graph loading is
excluded. Fixed hints were supplied before audio to NeMo engines; Keen used its
independent full-passage graph. Noise annotation labels were removed from provider
manual references. Prior figures calculated with those labels are superseded.

The aggregate numbers are saved in
[JSON](results/nemotron-six-setups-20261122.json). Source snapshots are in
[the experiment archive](experiments/20261122/README.md). Original input hashes,
per-recording scores, callbacks and failed setup attempts remain local.

## Tracker to actual digital sound output

Two new replays per story per Nemotron setting used the exact original source
WAVs, effect files, fixed full-excerpt hints and original tracker. Tracker settings
were threshold 82, stability 2 and coverage 0.8; input packets were 80 ms at 1x.
The Parakeet comparator reuses the saved 19 November captures.

| Recording | Saved Parakeet: 160 ms chunk / 560 ms future context | Nemotron 160 ms | Nemotron 320 ms, experimental |
|---|---:|---:|---:|
| The Moon | 1.181 s | 0.506 s | 0.888 s |
| The Lion and the Mouse excerpt | 0.792 s | 0.345 s | 0.461 s |

These are medians on the original comparison cue subset: opening/cat/mouse for
The Moon and all four cues for the Lion excerpt. Each setup captured all 16
configured cue opportunities across its two stories and repeats, with no duplicate
tracker triggers or early sound onsets. The Moon's dog remains included in those
configured-cue counts. The slowest Lion cue at 320 ms was 1.787 s despite its lower
median. Results and ranges are retained in
[aggregate JSON](results/nemotron-tracker-latency-20261122.json).

Actual production SoundPlayer output was captured using process-only Windows
loopback. The metric is sound onset minus the same estimated synthetic cue
ending. This small synthetic pilot does not measure physical microphone/speaker
acoustics or projector latency. It does not establish live child-reading accuracy
or a perceptible experience improvement. Nemotron 320 ms uses an experimental
`[70,3]` context; the shipped panel uses the trained 160 ms `[70,1]` setting.

## Panel

The model dropdown now includes **Nemotron · 160 ms**. Its shared server controls
load the selected Nemotron/Parakeet checkpoint, and readiness validates the actual
backend. Live transcripts, split tracking, changing checkpoint hints and existing
effect routing use the same client. A saved-file production-client check completed
the Moon recording, triggered four of four cues, acknowledged three hint updates,
and wrote the final transcript. It opened no live microphone or physical output.
The focused Windows suite passed 53 tests, with one NeMo GPU-only test skipped;
the real WSL GPU replay exercised Nemotron. The React production build passed.

Live microphone, speaker and projection checks on the other PC remain to do.
Follow [the handoff checklist](../docs/OTHER_PC_ASR_TEST.md).
