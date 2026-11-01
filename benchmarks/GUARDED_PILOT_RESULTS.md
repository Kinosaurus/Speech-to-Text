# Guarded one-shot effects and short-anchor timing

2 November 2026. **Both reading batches were rerun: 21 fresh reading streams, 63 configured checkpoints, plus four fresh unrelated-speech streams against nine unique passage manifests.** No model, passage wording, score threshold, or ASR hint tuning was performed during the completed sweep.

## What changed

- Current split mode separates reading progress from permission to emit a one-shot effect. Unsupported effects are explicitly suppressed while progress can continue. Ambience catch-up is an explicit authored policy.
- One-shot effects require recent ordered anchor support, a supported endpoint, and any authored essential words. Hibernation checkpoints now explicitly require hibernate; this is an effect-policy declaration, not an ASR substitution.
- Near-tied candidates can favour the acquired next endpoint within a 0.5-score margin. Short anchors may use unique exact prior book context from a different callback for confirmation. Same-audio changes, stale evidence and repeated book context cannot manufacture that vote.
- The recognizer remains Parakeet Unified NeMo 0.6B, CUDA bf16, RTX 3070 Ti, WSL server/Windows client, 560 ms chunk + 560 ms right context, 5.6 s history; split, no book hints, threshold 82, stability 2, coverage 0.8.
- See [effect-policy semantics](../docs/EFFECT_POLICIES.md) for defaults, essential-word configuration, suppressed IDs and limitations. Original alignment/evidence/fuzzy modes remain unguarded comparison baselines.

## Fresh outcomes

| Batch | Recordings | Configured | Previous emissions | Current emissions | Explicitly withheld | Unreached |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original passage batch | 9 | 27 | 26 | 24 | 2 | 1 |
| Additional Bears/Butterflies | 12 | 36 | 35 | 32 | 3 | 1 |

**Total: 56 emitted, five withheld, two unreached; no additional skips.** Earlier baseline emission totals were 61/63. The drop is an intentional conservative effect-permission tradeoff, not an accuracy improvement or a recognizer score. Suppressed effects are not counted as successes.

| Withheld case | Reason / interpretation |
| --- | --- |
| 3c29g_EN-OL-RC-234_2 / found_in_bush | Recognition says burst rather than a supported bush ending; possible false-negative cost needs listening. |
| billy-visits-grandpa-6027 / cold_toes | Recognition changes Billy/cold and omits part of the phrase; local anchor coverage insufficient. Needs listening. |
| 4a35g_EN-OL-RC-426_2 / hibernate | Authored essential action word absent in recognition; progress continues to clever_bears. |
| 5b2b_EN-OL-RC-538_1 / small_scales | Recognition says cells for scales; conservative withholding, not a proven child reading error. |
| 5b2b_EN-OL-RC-538_2 / escape_enemies | Endpoint enemies absent in recognition; later damaged_wing still emits. |

The two unreached checkpoints are the pre-existing Billy cookies/chess endpoint and reader 4a35g begging_paws. No silent threshold relaxation or forced substitution was added to make them fire.

## Demonstrated delay regression

For reader 5a21k, damaged_wing, the fresh estimated word-to-effect delay is **0.709 s**, versus **5.543 s** in the preceding fresh baseline: **4.835 s earlier** using the same previously frozen acoustic endpoint.

Saved-callback diagnostics isolate the mechanism: the corrected matcher emits at the first supporting a bit of wings update (48.723 s in that saved stream), rather than 53.644 s after a later repetition. An acquired, unique five-word prefix from the earlier callback supplies the prior independent vote. This replay is diagnostic evidence, not another live trial.

The fresh endpoint estimate remains flagged and is **not manually verified**. Both timing references are Whisper variants and can share bias. The paired improvement and the reproduced ranking/confirmation path are stronger evidence than an aggregate latency median.

| Current emitted subset | Timed emissions | Median provisional delay |
| --- | ---: | ---: |
| Original | 24 | 0.815 s |
| Expansion | 28 | 0.862 s |

Suppression changes which effects remain in these subsets. These medians must not be presented as a general recognizer speedup or directly comparable accuracy statistic.

## Controls and audit

- **Zero emitted effects and zero suppressions in 36 unrelated-audio/passage comparisons.** The four recordings are dog, dragon, nickel and recording_2; repeated passage references were deduplicated to nine. All original/intermediate observers also emitted zero effects.
- Every WAV sample was delivered in a contiguous packet sequence; all 25 streams produced ASR before EOF, final complete coverage, and STREAM_DONE. App emitted and suppression sequences match the current observer.
- No duplicate emitted/suppressed IDs or unexpected checkpoint IDs. Guarded progress continues after both targeted omissions; the later supported effects remain available.
- The completed sweep used one fresh stream per recording with unchanged source hashes and the frozen policy manifests. No separate inference warmup; the first stream includes first-inference effects.
- **135 unit tests pass**, including progress after suppression, genuine skipping without replaying skipped one-shots, ambience catch-up, inflections, split teapot wording, required words, prompts, stale/same-audio evidence, repeated context and bounded ranking.
- Seven launcher help checks, four Compose configuration checks, and the recording-library verifier pass. Container images and target boards were not rebuilt.
- The earlier whole-passage-hint Tom regression is separately checked by saved-callback replay: its early comic-books effect is suppressed. No fresh hinted sweep was run and the pilot still disables hints.

## Preliminary attempt and evidence boundaries

The preliminary guarded run was interrupted when full replay revealed that candidate ranking alone did not remove the extra confirmation wait. Its source snapshot and partial audio streams remain under output/guarded-pilot-2026-11-02 and are marked ABORTED. They are excluded from the results above. A separate complete sweep under output/guarded-pilot-v2-2026-11-02/evaluation uses the corrected confirmation path. No completed stream in that sweep was rerun to select a favourable result.

The policy declarations changed alongside the matcher; count differences cannot be attributed solely to ranking. These are already inspected development recordings, not held-out Singapore children. A text guard cannot verify the speaker, recover words ASR never recognized, or guarantee that a supported ASR word was actually spoken.

## Handoff and reproduction

- [Portable measurements](results/guarded-pilot-2026-11-02.json): emitted/suppressed/unreached statuses, provisional delays, source hashes and versions; no raw child audio or transcripts.
- Local listening handoff: output/guarded-pilot-v2-2026-11-02/evaluation/review/index.html and manual_review.csv. Human labels remain blank.
- [Singapore microphone pilot kit](../docs/pilot/singapore/README.md): original collection passage, four checkpoints, recording commands and blank metadata. No actual Singapore child recording has been collected here.
- Existing provider passages/WAVs and old frozen manifests are retained. New local canonical expansion manifests carry authored effect metadata; their prior versions are archived in each reader folder.

```powershell
# Start the documented NeMo server first, then choose a fresh destination:
.\.venv\Scripts\python.exe -X utf8 -u benchmarks/run_guarded_pilot.py --output output/guarded-pilot-new-run
.\.venv\Scripts\python.exe -X utf8 benchmarks/score_guarded_pilot.py --output output/guarded-pilot-new-run
```

**Still pending:** human listening sign-off, real Singapore microphone/enclosure and soundtrack testing, operator/reset/reconnect behavior beyond current session restart, and physical actuator integration. The prepared collection kit and listening clips make those steps concrete; this change is not production certification.
