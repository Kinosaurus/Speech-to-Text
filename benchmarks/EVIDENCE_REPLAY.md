# Experimental evidence tracker replay (revised boundary confirmation)

Default: `--matching_mode alignment`. Opt in: `--matching_mode evidence`.
Run comparison: `.\.venv\Scripts\python.exe benchmarks/replay_evidence.py`.
Machine-readable evidence: `output/evidence-replay/comparison.json`.

## Behavior

Both trackers share book text, coverage, candidate alignment, ambiguity checks
and scene selection. The experimental tracker retains a strong candidate across
unmatched updates for at most 12 seconds of segment time or 12 fresh callbacks.
Ambiguity clears it; an accepted different scene replaces it. A held scene can
receive further support at the normal score threshold during recovery; a new
scene still requires recovery strength.

New book words are NOT universally required. Support can come from forward
progress, or a strong (at least 92 and the normal threshold), non-backward match
that survives changed text over newer audio or a transition to a completed
utterance. Timestamp-only changes and exact duplicate callbacks do not count.
Completion is a stability signal, not independent acoustic evidence. Strong
matches still need the manifest's required confirmations; there is no timer-only
trigger. There is no phonetic matching or new effect-type schema.

## Timestamped callbacks

16 matched-book streams: four passages x two recognizers x hints on/off.
Across 32 configured scene opportunities:

| Metric | Original | Revised evidence |
| --- | ---: | ---: |
| Activations | 19 | 21 |
| Configured scenes not activated | 13 | 11 |
| Activations in 56 wrong-book pairs | 0 | 0 |

Both Parakeet Tea conditions recover the house scene, at audio endpoint 90.88 s;
the stove remains missed and is explicitly skipped on house recovery. The
previous Whisper hinted Mermaid regression is resolved. No baseline scene
activation is lost. These counts are not annotated correct-detection rates.

Timing uses original callback wall-clock arrival, not segment audio endpoints.
Of 19 common activations, 17 occur at the same callback. Parakeet Mermaid's
second scene is later by 0.548 s with hints and 0.566 s without. Median extra
delay is zero; maximum is 0.566 s. There is no comparable baseline activation
time for the newly recovered Tea scene. Actual spoken-boundary-to-effect latency
requires manually annotated phrase-end times and is not available here.

## Older logs and all eight recordings

Thirty separate text-only comparisons cover Horse, Fat Cat, Tea, Little Mermaid,
Dog, Dragon, Nickel and Recording 2. Matched-book logs produce 14 original and
17 experimental activations. Twenty off-book comparisons of Dog, Dragon, Nickel
and Recording 2 against the available manifests produce zero for both.
These logs lack segment timestamps/completion. They can check scene counts but
cannot establish callback timing or acoustic independence. Do not pool them
with timestamped comparisons.

## Limits

These replay saved recognition callbacks, not fresh ASR inference. No new
wrong-book triggers were observed. This cannot establish zero wrong scenes
within a matching book: manual reading-position annotations are missing. Fat
Cat's first anchor was reportedly skipped, so catch-up activation is not phrase
detection. Related off-book speech, parent prompting and live microphone noise
remain separate tests. House recovery is late and does not mean an appropriately
timed original house-boundary effect. Keep the tracker opt-in while validating
those cases and the finalization rule. The default tracker remains unchanged.
