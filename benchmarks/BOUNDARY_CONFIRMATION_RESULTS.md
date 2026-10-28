# Boundary confirmation: three-way live audio evaluation

Follow-up latency investigation and four-way streaming results:
[TIMELY_TRACKER_RESULTS.md](TIMELY_TRACKER_RESULTS.md). The results below are
preserved as the pre-latency-fix experiment; the shared runner now defaults to
the newer timely output directory.

Evaluation date: 28 October 2026. Raw local logs and machine-readable comparison:
`output/boundary-streaming-2026-10-28/`.

Status: all 14 live streams complete, comprising 949.999 seconds of source
audio across 10 unique recordings. All 101 unit tests pass. Source hashes stayed
unchanged during the sweep. Every stream delivered all samples, produced live
ASR before EOF and completed its final transcript. Application decisions agreed
with the fixed observer. The temporary Parakeet server was stopped afterward.

## Scene results

| Evaluation | Opportunities | Original caught / missed | Current-new caught / missed | Fixed caught / missed |
| --- | ---: | --- | --- | --- |
| OCSC standard checkpoints | 4 reached | 2 / 2 | 2 / 2 | 4 / 0 |
| OCSC earlier checkpoints | 8 reached | 5 / 3 | 7 / 1 | 8 / 0 |
| Earlier stories, no hints | 8 configured | 6 / 2 | 8 / 0 | 8 / 0 |
| Earlier stories, fixed hints | 8 configured | 6 / 2 | 8 / 0 | 8 / 0 |

The fixed tracker recovers the two previously missed OCSC final endpoints:
6008 `kind_boy` and 7057 `live_with_grandma`. The latter is the same endpoint
in both OCSC manifests, not two independent recovered reading events. No scene
activated by current-new is lost. Original misses the tea stove and house in
both hint conditions; current-new and fixed activate them. See the Fat Cat
and correlated-manifest caveats below before interpreting counts as accuracy.

All three trackers produced **0 triggers in 16 off-book clip/book controls**.
There were no unexpected scene IDs, duplicate activations or apparent early
activations against the approximate OCSC annotations. This does not make the
known late activations appropriate effects at the moment they occur, and does
not resolve the skipped-anchor Fat Cat case.

### Timing

| OCSC scene | Original | Current-new | Fixed |
| --- | ---: | ---: | ---: |
| 6008 `new_home` (early set) | about 3.24 s | about 3.24 s | about 0.85 s |
| 6008 `ambulance_hospital` | about 2.83 s | about 2.83 s | about 0.44 s |
| 6008 `kind_boy` | Missed | Missed | about 1.15 s |
| 7057 `live_with_grandma` | Missed | Missed | about 1.18 s |

These approximate delays use the streamed-boundary clock described below.
Several older delays persist: the fixed tracker's first three earlier
checkpoints for 7057 are still about 22.71 s, 16.23 s and 22.68 s late. The
first paragraph endpoint for 6008 remains about 19 s late. Fixing confirmation
loss does not solve all local alignment/recovery failures.

Across all shared scene/manifest/condition comparisons, fixed versus current-new
was earlier in 10 cases, identical in 15, and later in 0. Median change was 0 s;
largest improvement was 2.505 s. Versus original it was earlier in 11, identical
in 6, and later in 2, with a median improvement of 0.535 s and maximum added
delay of 0.535 s. These are paired ASR-callback times, excluding tiny sequential
observer compute overhead. Counts include both OCSC manifests and both hint
conditions and should not be interpreted as independent observations.

The fix is exposed through the existing experimental split mode. It is a
measured improvement on the evaluated boundary failures, not a production
readiness claim or a switch of the default tracker.

## Implementation

`BoundaryEvidenceMatcher` extends the unchanged `SplitEvidenceMatcher`. It saves
one supporting vote from an accepted alignment near the end of the next
checkpoint's anchor. The anchor prefix must contain several matching words.
When a fresh accepted candidate reaches that exact checkpoint endpoint, ends
with the book's final word and overlaps the prefix, that vote carries across
the scene boundary. The normal endpoint match supplies the next confirmation.

The carry expires after 12 seconds or 12 fresh updates, clears on ambiguity,
requires newer audio and changed words, and cannot jump an unread checkpoint.
Prompt/negation words block this extra credit. No threshold or coverage
requirements are lowered. A checkpoint configured for three confirmations
still needs three; one prefix cannot supply unlimited votes. No timer triggers
scenes. Existing same-position and split-token confirmation behavior remains.

This is deliberately a bounded transfer of anchor-prefix support, not a claim
that every previous book alignment supports every future scene. Very short
anchors or recordings without an accepted prefix still need ordinary support.

`run_client.py --matching_mode split` now uses the fixed tracker. The default
`alignment` mode remains the original. The pre-fix split and evidence classes
are unchanged, preserving reproducible comparison baselines.

## Protocol

- Three online observers receive identical fresh Parakeet ASR callbacks:
  `original` = AlignmentMatcher; `split` = pre-fix SplitEvidenceMatcher;
  `boundary` = fixed BoundaryEvidenceMatcher.
- Ten unique WAV clips: eight earlier development recordings and two OCSC
  children's reading tasks. Four story clips each run twice, with no hints and
  with the same fixed hints for all observers: 14 actual audio streams total.
- Each OCSC clip streams once; both its standard and early checkpoint manifests
  run online on that same stream. These two evaluations are correlated.
- All four unrelated development clips are compared against all four story
  manifests: 16 off-book clip/book controls per tracker.
- Actual application file streaming, 4,096 float32 samples per packet at 16 kHz,
  paced rather than uploaded for whole-file inference. Normal installed GPU
  server configuration; no changing hints based on a tracker's position.
- Original/evidence/split source hashes are recorded alongside the fixed source
  and application. Scoring verifies those hashes stayed unchanged during runs.
- Complete sample counts, live callbacks before EOF, final completed coverage,
closure, and application/fixed-observer agreement are checked.

The native client consumes STREAM_DONE before the base-client probe sees it.
An initial overly strict logging assertion stopped after the first completed
recording. A later check also needed to allow the native client's local-close
callback to report None instead of peer status 1000. In both cases valid live
logs were retained, completion validation was corrected, and the sweep resumed.
Final completed sample coverage and absence of server errors remained required.
Recognition and tracker decisions were not rerun from saved text or changed to
repair those assertions.

## Limits of the metrics

OCSC delays use automatically aligned CHAT utterance endpoints and are
approximate. They are mapped onto actual packet-send clocks to remove sender
scheduling drift, with further uncertainty within a 256 ms packet. Development
recordings lack manually verified scene-end times, so their delay comparison is
paired callback timing, not claimed absolute effect latency.

The first Fat Cat anchor was reportedly skipped in historical listening notes;
its activation is a disputed scene catch-up rather than proven phrase detection.
Development tables count configured activations/unactivated scenes, with that
caveat, rather than claiming verified scene recall. An expected scene ID can
still fire much too late and create an inappropriate effect. Wrong-book
controls and apparent early/duplicate triggers are reported separately.

These recordings and the boundary examples informed development. They are
regression/development checks, not an independent production validation set.
No child media, transcripts or private manifests are published in Git.

## Reproduction

Start the installed Parakeet server, then:

```powershell
.\.venv\Scripts\python.exe -u benchmarks/run_boundary_comparison.py
.\.venv\Scripts\python.exe benchmarks/summarize_boundary_comparison.py
```

Use `--resume` only to validate and retain already completed live logs after an
interruption. It does not replay saved transcripts into trackers.
