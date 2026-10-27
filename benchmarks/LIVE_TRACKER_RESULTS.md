# Fresh audio streaming tracker comparison — 24 October 2026

These are fresh ASR runs, not saved-transcript replays. Eight recordings were
streamed through the application in 4096-sample/256 ms packets. Whisper medium.en
and Parakeet NeMo ran sequentially on the RTX 3070 Ti at normal GPU settings.
The four matched books ran with no hints and with fixed vocabulary hints; the
other four recordings ran without hints as off-book controls. Automatic moving
book hints were disabled so tracker decisions could not change ASR input.

Original and split trackers processed each NEW ASR callback online in the same
client process. Thus each pair received identical fresh recognition text. The
actual app ran split mode, and its triggers were audited against the live split
observer: exact match in all 16 matched-book streams. This isolates tracker
behavior without a second decode introducing different recognition results.

## Activations

| Recognizer / condition | Original | Split |
| --- | ---: | ---: |
| Whisper medium.en, no hints | 4/8 | 4/8 |
| Whisper medium.en, fixed hints | 5/8 | 5/8 |
| Parakeet NeMo, no hints | 6/8 | 8/8 |
| Parakeet NeMo, fixed hints | 6/8 | 8/8 |
| Total configured scene opportunities | 21/32 | 25/32 |

No original activations lost. Four added activations: Tea stove and house in
both Parakeet hint conditions. Configured scenes not activated fall from 11 to
7. Remaining seven are all Whisper: unhinted Fat Cat both scenes, hinted Fat Cat
hat scene, unhinted Tea stove/house, hinted Tea initial tea/house. Activation
counts are NOT verified correct spoken-phrase detections. Fat Cat's first
anchor was reportedly skipped; catch-up remains a caveat.

Eight fresh off-book streams (Dog, Dragon, Nickel, Recording 2 x two recognizers)
were checked online against all four available manifests: 32 comparisons,
zero activations for either tracker. No related parent-prompt dataset or annotated
on-book false-trigger ground truth exists, so zero errors in these controls is
not proof of a zero false-trigger rate.

## Timing

Of 21 common original/split activations, 16 occurred on the same ASR callback.
Five were later with split mode; median added delay across all 21 is zero:

| Common scene | Split minus original |
| --- | ---: |
| Whisper Horse, no hints | +1.777 s |
| Whisper Fat Cat first scene, hints | +0.690 s |
| Whisper Tea first scene, no hints | +0.545 s |
| Parakeet Mermaid second scene, no hints | +0.543 s |
| Parakeet Mermaid second scene, hints | +0.479 s |

Parakeet stove activated at the FIRST callback containing complete word stove
in both conditions: about 55.70/55.72 s after first audio packet, corresponding
to audio endpoint 53.76 s. Zero extra callback wait; observer decisions finished
about 2–3 ms after receipt. It did not need the following sentence. This is NOT
spoken-word-to-effect latency: the source word end has not been manually marked,
and file delivery itself drifts. House recovery remains late, about 94.23/94.30 s
after first packet. A recovered house activation does not mean an on-time house
boundary effect.

## Transport and operational audit

24/24 completed streams: every expected WAV sample sent, END_OF_AUDIO recorded,
partial transcripts received, no callback exceptions. Application split triggers
exactly match live split observers. Delivery took 1.038–1.044 times audio duration
(roughly 4% slower than real time), reflecting client pacing overhead. Recognition
started while only early packets had arrived; no complete-file ASR was used.

One initial Whisper hinted Fat Cat attempt timed out after 240 s because final
hypotheses kept revising. It is excluded. The harness now retains the ordinary
15-second quiet wait but caps post-audio settling at 30 seconds. The successful
retry and every other retained Whisper run finished before that cap; no retained
run was cut off by it. Native Parakeet uses its normal STREAM_DONE acknowledgment.
A normal WebSocket 1000 close may be logged as ERROR by the client; retained runs
all exit successfully with complete transport/transcripts. One raw TCP readiness
probe generates a harmless server handshake warning.

The test servers were stopped after completion. GPU power/clocks were never
modified. The original tracker remains the application default.

## Interpretation

The Tea improvements reproduce with fresh streaming ASR, so the gain is not
limited to feeding back saved transcripts. It is a useful, narrow improvement,
with a measurable confirmation-delay cost on five existing activations. These
are the same development recordings, single trials per model/condition, normal
GPU settings; they do not establish performance on new children, a microphone
inside the pod, or Jetson. Independent recordings and annotated scene timings
remain necessary before promoting split mode as the default.

## Reproduce and inspect

- `benchmarks/live_tracker_probe.py`: packet logging and online tracker observers.
- `benchmarks/run_live_tracker_comparison.py`: actual application/server runner.
- `benchmarks/summarize_live_tracker.py`: audit and timing comparison.
- `output/live-tracker-2026-10-24/comparison.json`: full results, source/audio hashes.
- Same output directory: raw per-packet/partial-transcript/tracker events, SRTs,
  logs, and per-model results. Logs are ignored by Git; preserve this folder.
