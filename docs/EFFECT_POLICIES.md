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

## Separate authored effect cues

Split mode accepts an optional `effect_cue` inside the checkpoint's tracking
phrase. It must be a non-empty, unique contiguous phrase within
`checkpoint_text`. The full pages, checkpoint text and `word_start`/`word_end`
remain the original book reference. The cue supplies the effect boundary and
recent effect-permission phrase; surrounding book text remains available for
alignment. Existing manifests without this field keep their original anchor.

```json
{
  "id": "balloon_pop",
  "checkpoint_text": "The red balloon popped. Everyone looked up.",
  "effect_cue": "The red balloon popped.",
  "required_words": ["popped"],
  "effect_policy": "one_shot",
  "effect": {"effect_id": "balloon_pop"}
}
```

This is a fragment; the normal book, position, page and range fields still
apply. Required words must belong to the effect cue and retain the existing
strict spelling support. The book author declares what an effect represents;
the runtime does not infer synonyms or arbitrary paraphrases. Cue text is book
data, never a correction applied to the ASR transcript. The comparison modes
remain baselines; use `--matching_mode split` for these permissions.

A short cue still needs reading context. Ordinary alignment keeps its configured
minimum words, score, coverage, ambiguity and independent confirmations. Once
that alignment confirms the next nearby cue, an absent nonessential leading
fragment may be tolerated if at least three distinct exact words of the remaining
cue suffix, its endpoint and every declared essential word are present recently.
The accepted alignment must overlap that suffix. This route supplies no progress
or confirmation on its own. It cannot fill a missing required action, introduce
a sound substitution into that exact suffix, or grant a bare short phrase
permission at a cold start.

Missing descriptive words outside the authored cue are a different policy from
missing essential words inside it. Original full-anchor omission trials retain
their original manifests and labels. Authored-cue comparisons are reported
separately. Declaring an essential word may also expose a recognition miss:
an actual word transcribed as a different unsupported word remains blocked.

## Bounded acquisition using observed pronunciation

The next unread cue may use the existing pronunciation comparison during
acquisition, before reading position has entered the cue. Previous book progress
must be nonzero and within the existing backtrack bound. Cold starts, distant
scenes and jumps to a different checkpoint cannot use this route.

The latest ASR segment must contain a contiguous context run with at least the
configured minimum number of words, at least three distinct ordinary supported
words, and one occurrence in the full book. It must cover the cue. Only one
observed nonessential internal cue word may need pronunciation support, with
exact immediate neighbours and exact cue/context endpoints. Missing tokens,
unknown pronunciations, uncertain essential words and multiple unsupported
tokens fail closed. Context can include the existing last-three-word endpoint
neighbourhood, without crossing the next cue.

The run supplies an ordinary alignment candidate with the existing 0.75 word
credit for one uncertain observed token. Normal score, coverage, ambiguity and
independent-confirmation checks still decide progress. A stronger ordinary
alignment may share this support only while it overlaps the same cue and the
bounded context passes its threshold independently. Old-segment edits, duplicate
text and timestamp-only changes do not supply fresh votes. ASR words are never
rewritten, and declared essential words receive no pronunciation substitution.

The model, phonetic dictionary/rule and configured numeric thresholds are
unchanged: normal score 82, recovery 92, coverage 0.8, stability two and minimum
context length five by default. Per-book settings remain authoritative.

## Shared reading and coaching

Either voice may supply supported story text. Positive coaching such as "can you
say" or "please repeat" does not veto an otherwise eligible effect or its prior
prefix evidence. A parent saying a complete story phrase can advance progress
and emit its effect; a child repeating it does not replay that one-shot. The
system does not infer a speaker's identity or distinguish coaching intent from
reading intent. No voice-specific aliases, ASR rewrites or new manifest fields
are used.

Ordinary search bounds, ambiguity, score, coverage, fresh-confirmation, endpoint
and required-word checks still apply. Unrelated conversation is not eligible
merely because both voices are trusted. A supported later phrase can use the
existing forward-recovery rules and skip earlier checkpoints; parent and child
receive the same treatment. This policy does not guarantee a trigger for every
audible phrase or fix overlapping speech and confirmation failures.

Explicit negation just before the matched anchor continues to veto one-shot
permission unless that prefix belongs to the authored book context. Prefix
assistance likewise retains its negation guards. Alignment progress and effect
permission remain separate: a negated phrase can still advance progress while
its effect is suppressed. These bounded text checks are not a general understanding
of intent. Earlier frozen prompt-negative reports describe the previous policy;
positive quoted phrases now have a different expected outcome. A coaching clip
that contains a formerly omitted word is not a literal-word omission control.

## Pronunciation acceptance for the pod

The user accepts the five reviewed contextual variants: coat/goat, fan/van,
seal/zeal, pen/pin and sink/zinc. A close pronunciation with strong surrounding
phrase and reading-context evidence should count in these cases. The existing
matcher already emits all five, so this is an acceptance-label correction with
no ASR, threshold, matcher or manifest change. No word-specific exception is added.

The [user listening assessment](../benchmarks/results/pronunciation-acceptance-review-2026-11-03.json)
is attached separately to historical reports. Their original literal-word
measurements remain intact. These five emissions are accepted pod behavior;
requiring exact endpoints to reject them would reject user-approved readings.
Essential-word omissions, unrelated speech and other controls retain their
expectations. Acceptance does not extend automatically to every substitution.
The reviewed voices are synthetic adults; this is not child-accent validation.

## Guarded internal pronunciation support

After ordinary alignment and independent confirmations have acquired the next
checkpoint, split mode may count one observed internal word using the
[existing pronunciation comparison](#contextual-phonetic-endpoints). The anchor
must meet its configured minimum alignment length. This aid applies only when
ordinary spelling support falls exactly one match below the unchanged coverage
requirement. It cannot change acquisition, candidate scores, book position,
ambiguity handling or configured thresholds.

The endpoint must match exactly. The internal ASR token must be unused by the
ordinary ordered alignment and lie between exact matches for its two immediate
reference neighbours. At least three distinct ordinary anchor words must already
be supported. Exactly one internal sound-match candidate may qualify; competing
candidates fail closed. Missing tokens, unknown dictionary words and non-adjacent
neighbours cannot supply this match. Essential `required_words` retain their
ordinary stricter spelling checks and receive no phonetic credit.

The ASR transcript is preserved. In the confirmed sheep case, spelling supplies
six of eight anchor words and the existing sound rule supports sheep/ship between
one/was. This reaches the existing seven-word requirement; lost/locked remains
unmatched. There is no word-specific alias or recognition rewrite. These remain
dictionary/text heuristics; a deliberately spoken close word may be accepted
under the same pronunciation-tolerant pod policy.

## Reading across an unrelated aside

For the already-acquired next checkpoint, split mode can retain an exact leading
prefix with at least two distinct words and one occurrence in the book. This
stores only words actually observed in ASR and grants no effect or extra vote.
The additional continuation route becomes eligible only after that prefix's
source utterance completes with an off-book continuation of at least the existing
minimum alignment length whose first word does not match the next anchor word.
Ordinary uninterrupted reading keeps its existing path.

A later utterance must resume at the next expected anchor word. Its observed
suffix and the saved observed prefix are aligned with the normal score, coverage,
minimum-length, ambiguity and confirmation checks. Required words and the endpoint
must still be supported; no book word is filled in. Up to three following words
use the existing endpoint neighbourhood. An accepted incomplete continuation may
supply the normal earlier boundary evidence for a later endpoint. The ASR text is
preserved separately from this proposed reading evidence.

The prefix expires after twelve real-audio seconds or twelve supported reading
updates. Unrelated updates do not consume reading evidence. A retracted prefix,
negation, ambiguity or change of checkpoint abandons it. A completed old utterance
cannot support arbitrary later reading outside these bounds. One-shot history
and book position persist across ASR utterance changes.

## Digital silence and ASR utterances

The NeMo server completes an ASR utterance after a full existing encoder
right-context of exact zero PCM. It flushes the real pending frames with the
model's existing finalization method and starts a fresh decoder when nonzero
audio resumes. Additional digital quiet retains its original stream time without
being fed through a stale decoder. All nonzero audio is preserved, independent of
network packet boundaries. This adds no phase-specific padding, replacement words,
new amplitude threshold, ASR weights or matcher threshold changes.

Completed transcript segments remain available to the book tracker. Only ASR
utterance state restarts; reading position and one-shot history continue. Final
timestamps retain the original recording duration. Segment/callback markers are
not human-verified word timing. This detector handles digital quiet; nonzero room
noise and soft speech pass through unchanged rather than being classified as
silence. Microphone/room behaviour still needs its own testing.

The [completed resumption regression](../benchmarks/results/resumption-regression-2026-11-03.json)
runs 81 fresh streams with the same model and thresholds. Both accepted misses
recover, all four pause/phase targets emit, and the tested word omissions and
unrelated controls remain off. The report preserves an unreviewed ASR change in
the coached sheep variant instead of assuming every changed effect is correct.

## Exact prefix confirmation during recovery

The split matcher can retain one unique exact leading prefix of an unread
checkpoint without advancing reading position. The prefix needs at least
`minimum_words - 1` words (four with the normal five-word minimum), at least three
distinct words, and at most three anchor words still to come. Its exact text must
occur once in the whole book. One additional token may be a proper unfinished
prefix of the next authored word; no word-specific mappings are used. Prefix
occurrence counts are indexed once when loading the book.

This evidence can support an accepted ordinary candidate at that checkpoint,
including a later checkpoint reached through existing recovery searches. The
new callback must contain the complete exact anchor in the recent tail, and its
accepted alignment must overlap at least two prefix words. The ordinary search,
score, coverage, ambiguity, minimum alignment length and effect permission checks
still run. No candidate score or threshold is changed.

Both pieces must come from the same ASR segment, with changed text, newer audio,
and the existing bounds of twelve audio seconds/twelve fresh updates. Capture
uses the latest segment's words, so retained older segments cannot impersonate
fresh prefix evidence. Revising older context or changing timestamps alone does
not refresh its age. Contradictory/unrelated continuations, negation, ambiguity,
expiry and segment changes clear this additional evidence path.

A completed phrase cannot create its own earlier prefix vote. The prefix supplies
at most one vote and cannot double-count a vote already held for that checkpoint;
a stability requirement of three still needs three pieces of evidence. Whole
phrase duplicates and silence never supply extra confirmation. Fuzzy, phonetic,
split-word and existing local-prefix routes retain their separate rules; this
new route requires exact complete text and does not replace omitted words.

The [frozen prefix regression](../benchmarks/results/prefix-confirmation-regression-2026-11-03.json)
replays 214 saved comparisons and runs 32 fresh streams with unchanged ASR and
thresholds. Both reviewed confirmation misses recover; the three fresh natural
omissions and seven saved provider-deletion controls remain off. Existing ASR
errors remain separate limitations. The five reviewed close-word emissions are
accepted under the pod pronunciation policy above. The initial
batch was retained and aborted after an additional segment-binding check; final
metrics use the corrected frozen version.

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
within the latest four tokens, and the existing negation checks still apply.
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

Cold-start jumps, negation rejection, strict `required_words`, coverage and
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
correctness. The user subsequently accepted all five examples for the pod;
the required-word observer rejects all five accepted cases. See the pronunciation
acceptance policy above. No runtime or manifest change follows from that review.
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
negated instructions, recovery jumps, ambiguity and already-passed phrase context do not
receive this aid. Reading position continues to advance independently.

At most one effect can wait. Its window is bounded by two seconds of audio and
four fresh ASR updates, checked when callbacks arrive, and it closes if progress
moves more than three book words past the anchor or another checkpoint commits.
A fresh, changed hypothesis over newer audio can resolve it; final utterance
completion may also supply changed endpoint text at the same audio time. The
ordinary endpoint, ordered coverage, required-word, negation, split-word and
phonetic permission rules must all still pass. Neither a duplicate callback nor
a timer invents a word or emits an effect. Raw ASR tokens remain unchanged.

If support never arrives, completion, expiry, negation or leaving the local scene
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
after suppression, ambience catch-up, wording variants, shared coaching, negation, stale anchors,
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
