# Source snapshots from 22 November 2026

These are the exact authored scripts used for the six-setup ASR comparison,
the tracker-to-sound retest, and the saved-file panel integration check.
`source-hashes.json` records each snapshot's SHA256. The support files are
snapshots of this repository's recognition/scoring helpers. No model weights,
licensed SDK, recordings, references, transcript events or captured audio are
included here.

These scripts retain their original workspace-relative layout and are an
audit archive, not a portable installation entry point. Their original output
folders were `output/asr-slide26-20261122`,
`output/tracker-latency-nemotron-20261122`, and
`output/panel-nemotron-20261122` in an enclosing workspace. The active app was
`output/reading-pod-first-pipeline`. The ASR experiment also used the existing
private corpus, locally installed recognizers and licensed KeenASR SDK. The
latency experiment used the preserved original WAVs, SAPI cue timings, effect
files and original tracker snapshot. Those inputs remain local; copying these
scripts alone does not reconstruct the datasets.

For a portable other-PC setup and tests using the bundled passages, follow
[the current checklist](../../../docs/OTHER_PC_ASR_TEST.md).
For the measured results and their limits, see
[the report](../../NEMOTRON_RESULTS_20261122.md).
