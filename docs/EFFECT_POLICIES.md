# Reading progress and effect permission

The current **split** CLI mode uses `TimelyEvidenceMatcher`. It now makes two
separate decisions: whether reading progress has reached a scene, and whether
that scene's effect has enough recent anchor support to be emitted.

The original `alignment`, `evidence`, and `fuzzy` modes remain comparison
baselines. They do not implement this new effect-permission layer. Use explicit
`--matching_mode split` for the guarded pilot.

## One-shot effects: conservative default

An alignment reaching a later position no longer automatically grants a
one-shot effect. The guard requires ordered support for the local checkpoint
phrase, a recognizably similar endpoint, and any essential words declared by
the book author.

```json
{
  "id": "hibernate",
  "checkpoint_text": "bears hibernate from October to April",
  "effect_policy": "one_shot",
  "required_words": ["hibernate"],
  "effect": {"effect_id": "hibernation_animation"}
}
```

This is a checkpoint fragment; normal book ID, position, page/range, and manifest
fields are still required. `required_words` contains single words from the
checkpoint phrase. It declares effect meaning, not an ASR correction or a
dictionary of replacements. Without this declaration, a generic similarity
guard cannot know which internal word is essential to the effect.

The pilot policy file is `benchmarks/pilot_effect_policy.json`. It requires
`hibernate` for the hibernation one-shot. The additional-reader importer now
applies that authored policy; existing local manifests were versioned with their
pre-policy copies under `history/before-effect-policy-2026-11-02/`. Original
provider passages, recordings, and frozen earlier evaluation inputs are preserved.

The guard uses the checkpoint's coverage setting (default 0.8). Each recognized
word can support at most one anchor word, in order. Ordinary singular/plural
forms and limited spelling similarity remain supported. Required words use a
stricter similarity threshold than ordinary anchor words. There is no word
substitution in the ASR transcript.

Support must be in the recent buffer, with the endpoint among its last four
token positions. A small amount of following speech can share an ASR callback;
an old anchor elsewhere in the transcript is not unrestricted permission for a
late one-shot. This can withhold an effect when recognition is unclear even if
the child actually read the word correctly. Long paragraph checkpoints may need
shorter authored effect anchors/checkpoints rather than relying on full-paragraph
recognition in a 32-word buffer.

Prompt-like wording just before the matched anchor is rejected unless that
prefix belongs to the authored book context. This bounded text rule is not
speaker identification or general understanding of negation or adult prompting.

## Ambience: explicit catch-up

Use `"effect_policy": "ambience"` when reaching the current scene should update
persistent ambience even after a skip. This deliberately permits position-based
catch-up. It does not make the recognition or reading position infallible.

The policy applies to the **whole checkpoint payload**. A payload containing a
one-shot sound/animation should not be labelled ambience merely to allow its
lighting/background component to catch up. Keep mixed payloads conservative
until component-level actuator policies are implemented. Real projector/sound
actuation remains outside the current terminal-trigger integration.

## Suppression is visible, and progress continues

For a blocked one-shot:

- `triggered` is false and `effect` is `None`.
- `effect_suppressed` is true, with `effect_suppression_reason` and policy.
- Reading position and the next checkpoint advance normally.
- The ID enters `suppressed_checkpoint_ids`, not `triggered_checkpoint_ids`.
- The client prints `[SUPPRESSED]`, not `[TRIGGER]`.

A suppressed effect is not automatically replayed when later speech catches up.
A corrected rereading after the tracker has passed it currently requires a new
session to re-arm that checkpoint. `completed` means the story progress is
finished; it does not mean every effect was emitted.

## Bounded endpoint ranking

The demonstrated late case had two almost equal candidates: the winning one
ended one word short, although another already reached the checkpoint. Split
mode now prefers the reached endpoint only when:

1. It is the next checkpoint and progress has already acquired its local region.
2. The best ordinary candidate stops exactly one word before that endpoint.
3. A qualifying, overlapping endpoint candidate is within 0.5 score points.
4. Recent anchor/endpoint/required-word support is present, even for an ambience
   checkpoint.

The normal score/coverage filtering, ambiguity checks, and independent
confirmation requirements still apply. This is not a general preference for
later scenes or a relaxation of book-wide recovery thresholds.

For a short anchor, an already-acquired position and a unique exact five-word
book-context prefix from an earlier callback can supply the prior confirmation.
It must include at least two anchor words; repeated context, same-audio
revisions, and expired evidence do not qualify. This handles short phrases such
as “a bit of the wing” without counting one hypothesis twice.

## Evaluation and remaining work

The new regression tests cover omitted endpoints, essential words, progress
after suppression, ambience catch-up, wording variants, prompts, stale anchors,
and bounded near-tie ranking. Saved-callback diagnostics also check the earlier
whole-passage-hint Tom regression; that early comic-books effect is suppressed.
Diagnostic replay is kept separate from fresh audio trials.

See [the guarded pilot evaluation](../benchmarks/GUARDED_PILOT_RESULTS.md) for
both reading batches, effects withheld as well as emitted, unrelated-speech
controls, and timing limits. Human listening sign-off and a Singapore trial
through the real microphone/enclosure are still pending. This change does not
establish production readiness or make automatic word timestamps human gold.

The [Singapore microphone collection kit](pilot/singapore/README.md) is prepared
for supervised testing. It is a collection template, not Singapore performance
evidence, and its passage has not been calibrated to an age band.
