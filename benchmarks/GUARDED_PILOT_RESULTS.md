# Guarded one-shot effects and short-anchor timing

Known failure boundary: [45 frozen synthetic adult challenges](results/false-trigger-challenges-2026-11-02.json)
produce five close-word false triggers under literal-word expectations, with
the wrong word correctly preserved in ASR. Two occur with the previous matcher
(coat/goat, seal/zeal); three are new (fan/van, pen/pin, sink/zinc). All 30 other
negatives stay off and all ten correct/reread controls emit once, with no
duplicates. All delivery/hash/app-replay checks pass; no ASR/matcher tuning
occurred. The required-endpoint observer blocks these five examples but can
also lose valid readings after ASR substitutions. The five synthetic clips
need human listening confirmation; these are counterexamples, not child
accuracy estimates or microphone results.

Post-phonetic unseen-speaker check: [24 frozen untuned MPS streams](results/mps-heldout-phonetic-2026-11-02.json)
use 12 new IDs, excluding all 57 prior IDs. Of 72 checkpoints, 64 emit, five
are suppressed and three unreached. All 46 provider-marked correct anchors emit.
Every delivery/hash/app-replay audit passes. This batch contains no provider-deleted
endpoints/essential words, so it does not extend omission-control evidence.
Its 26 flagged listening cases remain unlabelled; counts are operational
outcomes on six familiar texts, not human accuracy or verified latency.

Contextual phonetic/progress repair: [inspected-data regression](results/phonetic-feature-regression-2026-11-02.json)
adds only the user-confirmed hundred_sheep effect in all 99 saved reading
timelines, losing none; all seven provider-deletion controls remain off. Nine
fresh reviewed/omission streams likewise add that one effect (18 to 19 of 27),
with six suppressed and two unreached. ASR callbacks are identical in all nine;
all three fresh omission assertions stay off. Four fresh unrelated streams emit
zero effects in 24 passage comparisons. The general phone-feature route
retains exact-prefix/local-acquisition guards and supplies consistent local
endpoint progress without a word alias. These are inspected-data results; a
dictionary feature comparison cannot verify which word was spoken acoustically.

Post-pending unseen-speaker test: [24 fresh untuned streams from 12 new MPS IDs](results/mps-heldout-pending-2026-11-02.json)
exclude all 45 prior IDs and keep the complete pipeline frozen. All delivery,
source/model and app/audit checks pass. Of 72 checkpoints, 64 emit, five are
suppressed and three unreached. User listening confirms the sole provider-correct
miss, hundred_sheep, as an accepted reading. ASR retains "hundred chip" and the
existing endpoint checks reject it. The user's approximate excerpt end at 0:10
maps to original 11.36 seconds; exact word alignment is unverified. No runtime
changes follow this review. The sole provider-deleted endpoint does not emit.
No pending decisions occur.
These are outcomes on familiar passages, not human effect-accuracy scores.

Provisional-rejection repair: [75 saved streaming timelines plus 35 fresh streams](results/pending-regression-2026-11-02.json)
test a general, bounded pending-effect lifecycle with unchanged ASR and word
permission rules. Only the user-confirmed restart is added, with no effects lost.
The 31 fresh readings emit 77/93 effects versus 76 before; all five fresh omission
controls remain off. All six saved-timeline omission controls also remain off,
and four fresh unrelated recordings emit zero effects in 24 passage comparisons.
These are inspected-data regressions, separate from the frozen evaluations below.

Final frozen speaker check: [24 more untuned MPS streams from 12 new speaker IDs](results/mps-heldout-eos-2026-11-02.json)
exclude all 33 previously used IDs and retain the complete repaired pipeline
without changes. All delivery/hash audits pass. Of 72 checkpoints, 62 emit,
seven are suppressed and three unreached. User listening confirms one false
negative: the matcher permanently suppresses intermediate enemy before the
complete enemies arrives in the next ASR update. Original batch snapshots remain unchanged;
neither provider-deleted endpoint emits. These are outcomes
on six familiar passages, not an effect-accuracy score or microphone validation.

End-of-stream repair: [51 fresh reading streams plus four unrelated controls](results/eos-regression-2026-11-02.json)
use the unchanged matcher and original audio. The ASR adapter completes real tail
frames with full encoder context, retaining original timestamps and excluding
padding-only decoder frames. All 51 pre-EOF transcripts remain identical.
Emissions increase from 126 to 128, with none lost: wing is recovered, retaining
its soft/cut-off source-quality note, and the user confirms the additional paws
trigger is correct. All four omission controls
remain non-emitting; unrelated audio emits zero effects in 24 comparisons. This
inspected-data regression does not replace the earlier held-out results.

Endpoint diagnostic: [two fresh original/+2-second-silence streams](results/mps-tail-silence-2026-11-02.json)
reproduce the unpadded wing miss and recover the word plus the effect with trailing
silence. Speech samples, matcher, recognizer settings and model remain unchanged;
both delivery audits pass. This supports trailing-context/end-of-stream sensitivity
and leaves the original held-out counts unchanged. No production change was made.

Post-split unseen-speaker check: [24 untuned MPS streams from 12 further speaker IDs](results/mps-heldout-split-word-2026-11-02.json)
exclude all 21 prior IDs and retain every selected trial with unchanged source,
model and manifest hashes. Both guards emit 63/72 effects, suppress five and
leave four unreached, with no added/lost effects or new split-word recoveries.
The user hears the missed phrase but qualifies its final wing as soft and possibly
cut off. ASR omits that token; the original provider ending was preserved.
The matcher remains unchanged; provider labels alone do not establish effect
accuracy. This is a speaker-disjoint test on the same six
passages. Saved unrelated ASR replay emits zero effects in 24 comparisons.

General split-word follow-up: [27 fresh streaming regressions](results/split-word-regression-2026-11-02.json)
produce 63 emissions versus 62 for the pre-split guard on the same callbacks.
The sole addition is the user-confirmed riverside reading; no emissions are lost.
The two user-confirmed omissions and the separate annotated hibernate omission
remain suppressed. The repair requires a complete exact contiguous anchor,
allowing any authored word to consume two adjacent ASR tokens, with no word-specific
aliases. All 150 unit tests pass. These inspected-data results retain the earlier
held-out evaluation below as a separate frozen record. Four fresh unrelated-speech
streams emit zero effects across 24 passage comparisons. All 31 completed streams
pass delivery and frozen-source/model checks.

New-speaker validation: [24 untuned fresh MPS streams from 12 disjoint speakers](results/mps-heldout-2026-11-02.json)
retain all trials and the frozen matcher/model settings. Both guards emit 56/72
configured effects, with 12 withheld and four unreached; no effect decisions
change. These operational counts are separate from human effect correctness.

Broader local regression: [15 readings, nine passage texts, 41 checkpoints](results/local-phonetic-sweep-2026-11-02.json)
produce 32 pre-phonetic emissions and 33 current emissions on paired ASR
callbacks, with no emissions lost. This includes 12 additional fresh streams
and three existing verified streams. The sole addition is small_scales; seven
effects remain withheld and one unreached. Expanded unrelated-speech callback
replay emits zero effects in 36 comparisons. These counts do not establish
accuracy or broad pronunciation recovery.

Later human-reviewed follow-up: [the focused endpoint regression](results/reviewed-endpoint-regression-2026-11-02.json)
uses general dictionary-based phonetic comparison for locally acquired endpoints,
with no checkpoint aliases or manifest changes. Three fresh streams confirm
small_scales now emits, with hibernate
and enemies omissions still suppressed. Four fresh unrelated streams emit zero
effects across 12 current-matcher/passage comparisons. The full-sweep counts below retain
their original pre-phonetic implementation and results. The earlier local
checkpoint-alias experiment is excluded from this current focused verification.

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
