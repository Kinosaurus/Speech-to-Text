# Review of the 17 flagged child-reading checkpoints

Implementation follow-up: [effect guards and the complete fresh rerun](GUARDED_PILOT_RESULTS.md).
The audit below describes the pre-fix evidence; human listening sign-off remains pending.

2 November 2026. **Evidence audit, not auditory verification.** This environment
did not provide a direct listening tool. Provider word annotations, both saved
acoustic passes, live ASR callbacks, and exact matcher replay were compared.
No checkpoint has been marked human-verified and no runtime matching was changed.

The original 35/36 activation count is unchanged. It is not a correctness score.
The review identifies **3 high-priority cases, 4 unresolved cases, and 10
lower-priority annotation/tolerance cases**. Low priority does not mean cleared
by listening.

## Three priority findings

| Case | Evidence | Implication |
| --- | --- | --- |
| `5b2b…538_2 / escape_enemies` | Provider marks the endpoint `enemies` deleted. The live text moves from `escape from its` to the next sentence, then fires. | Confirmed trigger without the endpoint in the recognition evidence. Needs effect-policy review before treating this as a successful word-specific activation. |
| `4a35g…426_2 / hibernate` | Provider marks `hibernate` deleted; both reference models and the live text omit it. The checkpoint still fires after the date phrase. | Progress/scene matching can tolerate a missing meaning-bearing word. That may suit ambience, but not an effect that requires the action to have been read. |
| `5a21k…538_2 / damaged_wing` | At the first `a bit of wings` ASR update, a valid candidate reaches book endpoint 80 with score 93.603. A candidate ending at 79 scores 93.750 and wins. Later repetition reaches 80 and fires. | Reproduced candidate-ranking delay. The observed ASR-update-to-trigger gap is **4.925 s**. The earlier **5.543 s word-to-trigger estimate remains provisional**. |

The third case is not solely a GPU latency explanation or a finalization wait:
the winning trigger occurs before end-of-audio, following a repeated phrase.
The alternative endpoint candidate was already above the configured threshold
with 31/32 matched query words. Globally favouring checkpoint endpoints would
be risky given the first two cases; any fix needs bounded local support and
paired omission/skip controls.

These observations establish what the annotated text and algorithm did. They
do not independently establish exactly what phonemes the child produced.

## All 17 cases

IDs below omit the shared `EN-OL-RC` portion for readability.

| Reader / paragraph | Checkpoint | Priority | Evidence interpretation |
| --- | --- | --- | --- |
| 4a18f / 426_1 | thick_legs | Low | Provider labels correct; live ending and medium reference support legs. One reference-locator failure; timing stays unscored. |
| 4a18f / 426_1 | fish_and_seals | Low | Phonetic provider transcription of usually; both references recover the phrase and agree within 60 ms. Plausible reading tolerance. |
| 4a18f / 426_1 | keep_away | Medium | us/use disagreement; both endpoint locators fail. Listening needed to distinguish pronunciation from changed wording. |
| 4a18f / 426_2 | clever_bears | Low | Internal word variations, with clever supported by live ASR and medium reference. Two-model timing unavailable. |
| 4b25a / 426_2 | hibernate | Low | bears/beers variation; the core hibernate–April phrase remains supported. |
| 4a35g / 426_1 | fish_and_seals | Medium | Provider says seals; live ASR says seas; neither reference locator supports the printed anchor. Unresolved source disagreement. |
| 4a35g / 426_2 | hibernate | High | Trigger despite provider/recognizer omission of the central verb. |
| 4a35g / 426_2 | clever_bears | Low | Internal very/well variation; both references and live ASR support clever. |
| 4a35g / 426_2 | begging_paws | Medium | Configured miss; provider substitutions and unsupported final-word recognition. Keep the miss, without inventing timing or lowering thresholds. |
| 5a28c / 538_1 | fine_patterns | Low | Singular pattern throughout provider and recognizers. Inflection-policy case. |
| 5b2b / 538_1 | wing_colours | Low | their/they/the variation, with wings consistently supported. |
| 5b2b / 538_1 | small_scales | Medium | scales/sales/cells disagreement; no justified two-model endpoint. |
| 5b2b / 538_1 | fine_patterns | Low | Singular pattern plus an article; same descriptive context. |
| 5b2b / 538_2 | escape_enemies | High | Trigger after the endpoint is annotated deleted and absent from live recognition. |
| 5b2b / 538_2 | damaged_wing | Low | bit/bite variation; wing remains supported. Plausible tolerance, not a listening sign-off. |
| 5a21k / 538_1 | fine_patterns | Low | Singular pattern in all text evidence; inflection-policy case. |
| 5a21k / 538_2 | damaged_wing | High | Near-tied candidate stops one word short; later repetition produces a late trigger. |

## What remains unresolved

- Four medium-priority cases need actual listening to distinguish recognition
  errors, pronunciation variants, changed words, and an appropriate refusal.
- Eight low-priority cases look compatible with tolerant scene tracking; two
  are timing-reference gaps. None has been cleared by auditory review.
- The omission cases need a product rule: continuing scene ambience is different
  from firing a one-shot effect that requires a specific word/action.
- Do not fix these by globally tightening or loosening similarity. That could
  reject harmless variants while leaving location/effect-policy problems intact.

## Audit artifacts

`benchmarks/review_flagged_readings.py` reproduces the audit using existing
local artifacts. Replay trigger sequences exactly match the recorded timely
observer for **all 12 readings**. This is saved-callback diagnostic replay,
not another fresh audio trial. The recorded runtime sources are unchanged.

Local files:

- `output/mps-expansion-2026-11-02/review/flagged-evidence-review/index.html`:
  all 17 cases in priority order with context audio and evidence.
- `…/flagged-evidence-review/review.json`: per-case annotations and the ranking
  diagnostic trace. These are assistant evidence findings, not human labels.
- The original `review/manual_review.csv` is preserved byte-for-byte. Human
  endpoint, reviewer, and sign-off fields remain blank.

All 17 context clips are explicitly labelled by their basis. Trigger-centred
and end-of-recording windows are **not word-aligned timestamps**. The late case
includes the later repetition, rather than cutting the audio at the first
automatic endpoint estimate.
