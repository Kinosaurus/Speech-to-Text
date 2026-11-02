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

## Exact split words

After the ordinary guard fails, an already acquired next checkpoint may use a
separate exact-text route. It must match the **entire contiguous anchor**, with
each authored word represented by one or two whole adjacent ASR tokens. All
characters and reference words must be present in order and consumed once.
This applies to split words anywhere in the anchor, including its endpoint;
there are no word-specific mappings or additional manifest fields.

For example, snow man can supply snowman, and note book can supply notebook.
Partial words, intervening words, substitutions, or omitted required words do
not satisfy this route. It does not reinterpret several authored words as a
single different recognized word. The last supporting ASR token must remain
within the latest four tokens, and the existing prompt checks still apply.
Raw recognition snapshots and the matcher's buffer are unchanged.

The normal score, coverage, independent-confirmation and phonetic-endpoint
rules are retained. A complete split anchor can also supply an exact position
candidate for the already acquired next checkpoint, inside the ordinary search
bounds, provided its text is unique in the book. This prevents a final split
word from requiring a following sentence to reach the checkpoint. Duplicate
callbacks still cannot create confirmation; normal stability or utterance
completion rules apply. This route is stricter about complete phrase content and
addresses token boundaries; a split combined with another recognition error
can still be withheld. Its fresh reruns are regression tests on inspected
recordings, not a new held-out accuracy study.

## Contextual phonetic endpoints

After confirmed progress inside the next checkpoint's region, split mode may
compare endpoint pronunciations from the [CMU dictionary](https://github.com/cmusphinx/cmudict)
using the pinned `cmudict` client dependency. This applies to known English
words across books, with no per-word or per-checkpoint alias declarations.
The original passage, checkpoint text and recognized transcript stay unchanged.

This fallback requires the entire exact contiguous anchor prefix: at least
four words, including at least four distinct words. The endpoint must remain
within the last four tokens. The original structural route requires both
pronunciations to share their first phone and final two phones, contain at least
two consonants, and differ by at most
one consonant edit. A vowel substitution costs 0.25 and other edits cost 1;
total distance must not exceed 1.25 or 25% of the longer pronunciation. Unknown
words receive no phonetic support. The dictionary loads before audio callbacks.

A second route compares coarse articulatory features across the complete CMU
phone inventory. Pronunciations must have equal length (at least three phones),
a consonantal onset, at least two consonants, and an identical final phone.
At most two aligned phones can differ, each in exactly one feature; at most one
changed phone can be consonantal. Consonant features describe sonority, place,
manner and voicing; vowel features describe height, backness, rounding, tenseness,
rhoticity and glide destination. No phone insertion, deletion, multi-feature
change or vowel/consonant interchange is supported by this route. This is a
general lexical heuristic, not a measured ASR-confusion model or acoustic check.

Cold-start jumps, prompt rejection, strict `required_words`, coverage and
candidate ranking retain their existing checks. For an acquired next checkpoint,
a complete phonetic anchor unique in the book can also supply a local progress
candidate. Its uncertain endpoint receives 0.75 word credit; configured score,
coverage, ambiguity and independent-confirmation rules still apply. This keeps
valid endpoint evidence from ageing out while spelling-only alignment waits for
following words. Required endpoints still need their ordinary stricter spelling
support. Existing manifests need no
new tolerance metadata. For example, scales/cells can pass the phonetic rule
in the exact phrase context, while coils has a different onset and is rejected.

This is a rule-based pronunciation tolerance, not a trained child-pronunciation
model or speaker verification. Similar-sounding intentional word substitutions
can remain indistinguishable from mispronunciation in a text-only tracker.
The [frozen synthetic adult challenge](../benchmarks/results/false-trigger-challenges-2026-11-02.json)
demonstrates this boundary: ASR retains goat, van, zeal, pin or zinc while the
book expects coat, fan, seal, pen or sink, and the default one-shot guard emits.
The previous spelling rules already accept two of these; the newer phonetic
route adds three. Required-word checks block these five short-word examples,
but can reject valid ASR substitutions and do not establish literal-word
correctness. No production policies were changed after this evaluation.
The earlier checkpoint-specific endpoint-variant experiment was removed; its
local streams remain historical artifacts and are not current validation.

## Ambience: explicit catch-up

Use `"effect_policy": "ambience"` when reaching the current scene should update
persistent ambience even after a skip. This deliberately permits position-based
catch-up. It does not make the recognition or reading position infallible.

The policy applies to the **whole checkpoint payload**. A payload containing a
one-shot sound/animation should not be labelled ambience merely to allow its
lighting/background component to catch up. Keep mixed payloads conservative
until component-level actuator policies are implemented. Real projector/sound
actuation remains outside the current terminal-trigger integration.

## Provisional endpoints can remain pending

A rejected one-shot can remain pending when the reader has already acquired
the next checkpoint, its full exact prefix ends at the transcript tail with
at most one unfinished/restarted token, and the endpoint is not yet supported.
The prefix needs at least two words and two distinct words. Completed utterances,
prompts, recovery jumps, ambiguity and already-passed phrase context do not
receive this aid. Reading position continues to advance independently.

At most one effect can wait. Its window is bounded by two seconds of audio and
four fresh ASR updates, checked when callbacks arrive, and it closes if progress
moves more than three book words past the anchor or another checkpoint commits.
A fresh, changed hypothesis over newer audio can resolve it; final utterance
completion may also supply changed endpoint text at the same audio time. The
ordinary endpoint, ordered coverage, required-word, prompt, split-word and
phonetic permission rules must all still pass. Neither a duplicate callback nor
a timer invents a word or emits an effect. Raw ASR tokens remain unchanged.

If support never arrives, completion, expiry, prompts or leaving the local scene
finalize suppression. A new utterance cannot borrow an old incomplete prefix.
A later checkpoint can still emit on the callback that closes the old pending
effect. There are no per-word exceptions, altered spelling thresholds or new
manifest settings.

While waiting, `effect_pending_checkpoint_id` identifies the effect and the client
prints `[PENDING]`. A pending ID belongs to neither emitted nor suppressed history.
`additional_suppressed_checkpoint_ids` reports an older pending decision closed
alongside a new checkpoint event; the client and benchmark record both decisions.

## Final suppression is visible, and progress continues

For a blocked one-shot:

- `triggered` is false and `effect` is `None`.
- `effect_suppressed` is true, with `effect_suppression_reason` and policy.
- Reading position and the next checkpoint advance normally.
- The ID enters `suppressed_checkpoint_ids`, not `triggered_checkpoint_ids`.
- The client prints `[SUPPRESSED]`, not `[TRIGGER]`.

A finalized suppressed effect is not replayed when later speech catches up.
A corrected rereading after the tracker has passed it currently requires a new
session to re-arm that checkpoint. `completed` means story progress is finished
and no effect remains pending; it does not mean every effect was emitted.
`current_checkpoint` describes remaining reading progress and can be `None`
while the final effect is pending.

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
