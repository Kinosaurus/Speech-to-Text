# Books to Life Pod: current flow, handover and verification

Separate effect cues and bounded acquisition, 6 November: the
[completed regression](../benchmarks/results/effect-cue-regression-2026-11-06.json)
adds optional authored `effect_cue` phrases while preserving full checkpoint text
as book context. Required words belong to the cue and retain strict spelling
support. Short cues use normal confirmed context; an exact suffix with three
distinct cue words can tolerate an absent nonessential opening fragment. The
next nearby cue may also use one existing internal pronunciation comparison
inside a unique contiguous context run with exact neighbours/endpoints. The
normal minimum context length, score, coverage, ambiguity and independent votes
remain authoritative. See [the policy contract](EFFECT_POLICIES.md#separate-authored-effect-cues).

Only `effect_permission.py` and `timely_matcher.py` change in the runtime. ASR,
model, lexicon, book hints and numeric thresholds are unchanged. The pilot's
authored lost-sheep cue is "one sheep was lost", with required word `lost`;
the following sentence remains tracking context. This declaration is book data,
not a transcript replacement or a speaker/word exception. New importer output
copies authored cues alongside required words. Original manifests and all old
reports remain preserved; versioned cue manifests are used for comparison.

All 383 saved legacy ledgers reproduce and remain identical under the new
matcher. With the same authored essential-word declarations on both sides, 54
saved cue comparisons add 13 emissions and remove none. A changed book policy
can still withhold an old emission: explicitly requiring `lost` blocks the
human-accepted 3a8b source where ASR says "locked". Fourteen repeated saved
conditions involve that same underlying source, not fourteen readers. This is
kept visible as an ASR false negative, with no alias or invented action word.

All 42 final fresh streams complete once in fixed order (1329.32 seconds): 25
legacy inputs, nine authored-cue inputs and eight fixed synthetic inputs. The
eight supported authored-cue cases emit, including both recent misses and the
optional-opening-word regression. All four synthetic positives emit; all four
synthetic essential-word omissions stay off. Across the full batch, seven
declared-essential omission targets and all thirteen word-omission targets stay
off. Four fresh unrelated timelines against six authored policies produce zero
effects in 24 callback replays. Previous pause/phase, interruption, endpoint and
reviewed MPS assertions still pass. The known `locked`/`lost` source remains the
one human-positive target miss under the stricter authored cue policy.

All 33 required ASR callback comparisons are identical; the additional historical
optional-prefix input is reported separately. Model/source/lexicon/manifest/audio
hashes, delivery, interim/EOF, pacing and app/observer/replay checks pass. Windows
runs 223 tests: 222 pass and the existing NeMo-only test is skipped. The server is
stopped. Final raw artifacts, source snapshots and listening page are under
`output/effect-cue-regression-v4-2026-11-06/`. Three earlier preparation/preflight
attempts retain their artifacts and `ABORTED.json`; none ran fresh recognition.
These are inspected regressions and synthetic controls, not new-reader accuracy,
room/microphone validation or verified word-end latency.

Recognition/progress investigation, 6 November: the
[read-only diagnosis](../benchmarks/results/mps-progress-investigation-2026-11-06.json)
replays 147 original MPS callback histories (74 speakers, 441 checkpoints),
including all 24 readings of the lost-sheep passage. All 8033 instrumented saved
updates exactly agree with an independent vanilla frozen tracker and reproduce
their existing ledgers. Seven fixed, outcome-informed diagnostic cases also
stream their original full WAVs once through the unchanged current server
(311.02 seconds, 376 callbacks). Every checkpoint outcome repeats. The four
latest callback sequences are identical; three historical sequences change
slightly under current streaming but retain their outcomes. These are diagnostic
reruns, not new holdout or human-listening accuracy evidence.

In the user's reported recording, progress finishes at normalized word 55,
before the final anchor's start at 57. Actual recognition supplies six spelling
matches where seven of eight are required. No acceptable final alignment is
selected, and even the current local permission aids cannot support that ASR
tail. A counterfactual text-only replay substitutes prefixes of the user's
transcription into six corresponding final hypotheses, retaining all earlier
recognition and existing callback times. The unchanged tracker then emits
`lost_sheep`. This isolates the recognition/evidence issue; it does not measure
ASR accuracy or establish an acoustic correction.

Across the 24 saved lost-sheep histories, 14 emit and ten remain unreached:
five have all crossing candidates filtered, three choose another alignment,
and two lack confirmed crossing progress. Four of those misses contain the
exact first sentence in ASR; seven have a provider-correct first sentence.
The four-word event cannot independently meet the five-word alignment minimum,
and the authored eight-word checkpoint additionally depends on the following
sentence. One other recent miss could pass existing local permission aids but
never acquires the anchor, so permission support alone is not progress recovery.
None of the ten missed histories ever passes ordinary permission; no universal
progress-only fix is established. Eight saved provider-deleted endpoint/essential
controls stay off, including actual omitted following sentences. Such omissions
must not silently become positives under a changed checkpoint-authoring policy.

No ASR, matcher, phonetic rule, model, threshold, hints, manifest or original audio
changes are made. The server is stopped. Protocols, exact per-callback traces,
original-input reruns, the oracle-text probe and seven exact PCM review crops
are retained in `output/mps-progress-investigation-2026-11-06/`. Next work should
separate effect-bearing cues from following descriptive text and investigate
bounded contextual acquisition using existing evidence, with further listening
and unchanged omission controls before approving a general repair.

Frozen new-speaker evaluation, 6 November: the current runtime is unchanged from
the internal-pronunciation regression below. The
[completed MPS streaming batch](../benchmarks/results/mps-frozen-streaming-2026-11-06.json)
selects 12 new speaker IDs, balanced across grades 3–5 and provider gender labels,
after excluding all 69 previously used IDs found in local artifacts. Both
paragraphs per speaker are streamed once in a fixed seeded order: 24 original
recordings, 1014.48 seconds and 72 checkpoints. Selection, source snapshots,
model/lexicon hashes and manifests are frozen before download/recognition. No
ASR, matcher, threshold, hint, checkpoint or audio tuning is applied. The 24 audio
hashes also have no overlap with 215 distinct audio hashes in prior result files.

All 37 provider-marked correct anchors emit. The single provider-marked essential
word deletion (`hibernate`) stays off. Overall outcomes are 53 emitted, 14
suppressed, one skipped and four unreached; the 19 non-emitting anchors all have
provider-marked substitutions or deletions. These are not automatically correct
rejections: pronunciation acceptance and remaining ASR misses need listening.
One reader emits no effects in the first sheep passage and one in the second,
so aggregate provider-correct coverage does not establish a good experience for
every reader. Four saved unrelated ASR timelines replay against the six passage
policies with zero effects in 24 comparisons; these are not fresh audio trials.

All source/model/lexicon/manifest/audio hashes, full delivery, interim results,
EOF, pacing and app/observer/replay audits pass. The local ASR server is stopped.
The ignored folder `output/mps-frozen-streaming-2026-11-06/` preserves the complete
source snapshot, fixed protocol, original WAVs, logs, transcripts and a local
listening page with 35 flagged checkpoints. No production source changes are
made. This is new-speaker evidence on the same six familiar Indian MPS texts,
not unseen-book, Southeast Asian reader, microphone/room or word-latency evidence.

Subsequent [listening diagnosis](../benchmarks/results/mps-listening-review-2026-11-06.json):
for the zero-effect sheep recording, the user hears "he took the sheep to the
river" and "one sheep was lost; the sheep was sad" and asks whether they should
count. The pod-policy recommendation accepts both; that recommendation is kept
separate from the user's independent word transcription. The ordinary effect
guard already accepts the latter wording in isolation. Actual ASR instead ends
"one ship was lost the ship was said", fails that guard and never reaches the
checkpoint in streaming. The river case is separately blocked by its one-shot
endpoint requirement. Existing ambience policy is suitable for background scene
catch-up after progress is established; it does not promise exact word timing.
`hundred_sheep` has no new listening assessment. No runtime or manifest changes
are made, and these inspected phrases are now regression/diagnostic material.

Internal pronunciation repair, 4 November: the user confirms the previously
flagged sheep excerpt is very clear and should count. It is now recovered by
[a guarded general rule](../benchmarks/results/internal-phonetic-regression-2026-11-04.json),
with no ASR, model, numeric-threshold, word-alias or input-audio changes. After
ordinary alignment acquires the next checkpoint, one internal observed token
may use the existing pronunciation comparison if it is uniquely bracketed by
exact ordered neighbours and the endpoint is exact. Ordinary support must fall
exactly one match short; required words retain their stricter spelling checks.
Missing tokens cannot supply this match. See [the contract](EFFECT_POLICIES.md#guarded-internal-pronunciation-support).

The phrase still reaches ASR as "one ship was locked ...". Spelling supports six
of eight anchor words; sheep/ship adds one supported match, reaching the existing
seven-word coverage requirement. Lost/locked remains unmatched. Both coached and
uncoached fresh readings now emit `lost_sheep`; every ASR callback sequence in
the 25-stream batch is identical to the prior version (844.94 seconds). All nine
reviewed MPS target checks pass, as do the earlier pause/aside recoveries and all
four pause/phase cases. Eight fresh word-omission controls and seven saved
provider-deletion controls stay off. Four unrelated recordings produce zero
effects across 24 policy replays. All delivery, EOF, model/source/audio hashes
and app/observer/replay audits pass; no duplicate effects occur.

All 327 saved old ledgers reproduce. The new matcher removes no emitted effects
and changes no checkpoint skips. Twelve comparisons gain only `lost_sheep` across
repeated conditions for this same underlying child recording; they are not twelve
new readers or independent accuracy observations. Windows runs 211 unit tests:
210 pass and the unchanged NeMo-only check is skipped, with its passing WSL
decoder-budget check retained and source hashes verified. The user confirmation
and resolution are attached separately to the original resumption report; its
raw trials remain unchanged. The frozen output directory retains its 3 November
start label. The local ASR server has been stopped.

General resumption repair, 3 November: the two user-accepted misses now emit in
[the completed final regression](../benchmarks/results/resumption-regression-2026-11-03.json).
NeMo completes an utterance after a full existing right-context of digital zero
PCM and starts a fresh decoder when nonzero audio resumes. Book position and
one-shot history continue. The matcher can retain an observed unique prefix of
the acquired next anchor across a completed off-book aside, then align observed
continuation words with the normal filters. An old completed utterance's negation
does not poison a new exact prefix. Model weights, chunk/right context, lexicon,
score/coverage/stability thresholds, hints and input audio remain unchanged.
There are no word exceptions or phase-specific padding rules. See [the contract](EFFECT_POLICIES.md#reading-across-an-unrelated-aside).

The final v3 batch streams 81 selected inputs once each (1893.09 seconds): the
32 earlier regression inputs, 45 synthetic challenges and four pause/phase
inputs. All delivery, EOF, model/source/audio hashes and app/observer/replay audits
pass. All 246 saved old ledgers reproduce and remain unchanged with the new
matcher. All nine fresh reviewed MPS targets pass, with their complete outcomes
unchanged. Three fresh natural word omissions, five synthetic endpoint omissions
and seven saved provider-deletion controls remain off. The 20 accepted synthetic
positives emit; all 25 synthetic negatives stay off. Four unrelated recordings
produce zero effects across 24 book-policy replays. All four pause/phase targets
emit, and the Singapore left-hand trigger is preserved. No duplicate effects occur.

On the fresh audio, five effects are added versus the original runs and one
then-unreviewed effect is withheld: `lost_sheep` in the coached sheep variant changes
after ASR hears "locked" instead of "lost". Both old and new matchers withhold
that effect on the new ASR. It was unconfirmed at that evaluation; subsequent
user listening confirms the regression and the repair above recovers it. Its listening excerpt is
under the final output's `review/`. The long-pause recovery needs the ASR change;
the accepted child aside additionally needs the interrupted-reading matcher path.

Windows runs 204 unit tests: 203 pass and one NeMo-only test is skipped; that
decoder-budget test passes separately in the installed WSL NeMo environment.
Two preliminary batches remain retained: the first stopped in preflight before
audio after ordinary-reading changes were found; v2 retains 29 audited streams
and any partial artifacts after the prior-negation confirmation issue appeared.
Final metrics use only `output/resumption-regression-v3-2026-11-03/`. These are
inspected regressions with reused sources, not new-speaker accuracy. Digital quiet
is handled without an amplitude threshold; nonzero noise and soft speech pass
through unchanged. Real microphone/room validation remains pending. The task's
ASR server has been stopped.

Pause/interruption listening and ASR investigation, 3 November: the user confirms
the long-pause rabbit phrase is clear (independently hearing "a small rabbit")
and wants the child phrase across the inserted aside to count. Both remain
misses. The synthetic overlapping case is somewhat unclear with optional success;
the child overlap is too chaotic to require a trigger. These labels apply to
`target` in the synthetic clips and `clever_bears` in the child excerpts, not to
the child recording's separate omitted `hibernate` checkpoint. Original trials
and omission controls remain unchanged. See the [user listening assessment](../benchmarks/results/pause-interruption-listening-2026-11-03.json).

A [fixed four-stream diagnostic](../benchmarks/results/pause-asr-diagnostic-2026-11-03.json)
crosses short/long inserted silence with two positions inside the same 560-ms
ASR chunks. All four use byte-identical sentence PCM and unchanged runtime,
model, hints and thresholds. Both short phases succeed; the original long gap
reproduces the missing "A small" and withheld target. Extending that long gap by
280 ms changes its chunk phase and restores the complete phrase and effect.
All 76.06 seconds pass full packet, EOF and app/observer/replay audits. Baseline
and original long-gap callback sequences reproduce exactly. This points to an
interaction of silence and chunk alignment for this input; it does not isolate
the decoder mechanism or justify a 280-ms production padding rule. General
silence/resumption handling and the accepted interrupted child phrase remain
open. The ASR server started for this diagnostic has been stopped.

User pronunciation review, 3 November: all five previously flagged close-word
recordings are accepted for the pod: coat/goat, fan/van, seal/zeal, pen/pin and
sink/zinc. The user wants pronunciation tolerance when the surrounding phrase
and reading context support the event. The current matcher already emits all
five; no ASR, matcher or threshold change is needed. These five are accepted
behavior, not unresolved pod false-trigger defects. The user separately
transcribed "goat"; the other four labels confirm acceptance without independently
transcribing the word. See the [listening assessment](../benchmarks/results/pronunciation-acceptance-review-2026-11-03.json).

Original strict-literal trial counts remain historical measurements, with the
later acceptance attached to the reports. Omitted essential words and unrelated
speech retain their expectations. These synthetic adult examples do not establish
child-accent accuracy or acceptance of every future substitution.

General prefix-confirmation repair, 3 November: the split matcher now records a
unique exact leading anchor prefix even before ordinary alignment can acquire
it. A later accepted ordinary candidate can use that prior vote only when the
complete exact anchor is present in the current ASR segment, with changed text,
newer audio and existing freshness bounds. Prefix acquisition does not advance
position, invent endpoint words, alter scores or reduce configured stability.
Only timely_matcher changes relative to the shared-reading policy baseline.
See [the contract](EFFECT_POLICIES.md#exact-prefix-confirmation-during-recovery).

The corrected implementation passes 190 unit tests: 189 pass and one unchanged
NeMo-only test is skipped. All 214 saved old ledgers reproduce exactly; the new
matcher adds eight effects with no losses, including Singapore left hand and
the adult-spoken coached hibernate. All 123 MPS reading outcomes remain unchanged.
Seven provider-deletion controls, omitted/negated challenge targets and unrelated
speech remain non-emitting; the five close-word emissions are now user-accepted.

The [completed prefix-confirmation regression](../benchmarks/results/prefix-confirmation-regression-2026-11-03.json)
runs 32 final fresh streams once each: one complete Singapore recording, the
same eighteen shared-reading inputs, nine reviewed MPS recordings and four
unrelated recordings (1324.82 seconds). Every ASR callback sequence is identical
to its original. All delivery, EOF, source/model/audio hashes and app/observer/
paired-replay checks pass. On the same fresh callbacks, effects increase from
54 to 58 with no losses or duplicates: left hand, adult-coached hibernate and
the later finish effects in the omitted-target and overlap cases are recovered.
All nine reviewed target assertions pass, including all three original omissions.
Four fresh unrelated timelines produce zero effects across six policy replays
each. Shared target goals move from fifteen to sixteen of eighteen, and complete
controlled goals from seven to eight of ten. At that evaluation, long-pause and
overlap target ASR misses remained; the later resumption repair above addresses
the accepted pause/aside cases. The five reviewed
close-word emissions are accepted under the later pronunciation policy above.

Singapore left hand uses a five-word prefix at callback 124.928 s and the complete
phrase at 125.440 s, with an ordinary alignment score of 100. Coached hibernate
uses four prefix words at 3.584 s and the complete phrase at 4.096 s, also score
100. These are callback markers, not verified word latency. The coached clip
contains the adult-spoken word and is not an omission control. Singapore's earlier
two checkpoints are skipped under existing recovery rules: one remains unclear
and the other remains an ASR error. The local 32-case listening review is under
`output/prefix-confirmation-regression-v2-2026-11-03/review/`.

The first batch is retained
under `output/prefix-confirmation-regression-2026-11-03/` with ABORTED.json: an extra
segmented-transcript check exposed re-acquisition of older segment words. The
corrected path captures only latest-segment text and does not refresh on older
context revisions. That first version completed fourteen streams before its
fifteenth was interrupted; those outcomes are excluded from the final batch.

Shared-reading policy, 3 November: the user chose to count supported story text
from either voice, including positive coaching. The guarded split matcher now
removes positive "say/repeat" vetoes from permission, prefix support, split-word
assistance and pending resolution. Explicit negation guards remain. Normal score,
coverage, word-presence, freshness, ambiguity, search and one-shot rules are
unchanged. A parent reading a later supported line can use existing forward-jump
rules and skip earlier checkpoints. The policy is documented in
[effect policies](EFFECT_POLICIES.md#shared-reading-and-coaching).

The complete old runtime was captured before edits and replayed in a separate
process. All 214 saved comparison ledgers reproduce their original outcomes.
The new policy adds eight effects, all on positive quoted/coaching cases, with
no losses. All 123 MPS reading outcomes remain unchanged (320 emitted, 33
suppressed, 16 unreached across 369 checkpoints); seven provider-deletion controls
and 24 unrelated comparisons stay off. Five positive quoted challenges now count;
five negated prompts and five literal omissions remain off. The five close-word
emissions are unchanged and subsequently user-accepted. Windows runs 179 tests: 178 pass and
one unchanged NeMo-only check is skipped. Six initial sandbox temp-folder errors
were resolved by using a verified workspace-local temporary directory.

The [completed policy regression](../benchmarks/results/shared-policy-regression-2026-11-03.json)
runs 31 fresh streams once each: the same 18 shared-reading inputs, nine reviewed
MPS recordings and four unrelated recordings, totaling 1129.40 seconds. All 31
ASR callback sequences are identical to their originals. Transport, EOF, source/
model/audio hashes and app/observer/replay checks pass. On the same fresh callbacks,
shared emissions increase from 32 to 35 with no losses: the controlled coached
sentence with/without a child repeat and the parent's riverside phrase now emit.
No repeated effect is emitted. Under the new policy for both implementations,
target goals move from 12 to 15 of 18; controlled complete-effect goals move from
five to seven of ten. Long pause, overlap and a coached hibernate phrase remain
target misses. That last phrase appears exactly in ASR but receives only one of
two confirmations; the policy does not bypass evidence requirements.

All nine reviewed assertions pass, including the three original omission cases;
their complete checkpoint outcomes remain unchanged (19 emitted, six suppressed,
two unreached). Four fresh unrelated recordings emit zero effects across six
policy replays each (24 comparisons, not 24 audio trials). Audio, ASR, model,
lexicon, thresholds, hints and checkpoint manifests remain fixed. The local
31-case listening review is under `output/shared-policy-regression-2026-11-03/review/`.
These are inspected regressions, not natural-family accuracy or room validation.
The original reports below remain historical and retain their previous
coaching-negative expectations. Those results alone did not resolve the Singapore
prefix-confirmation miss; the later repair above does. The five close-word
emissions are subsequently user-accepted, as recorded above.

Shared-reading stress test, 3 November: [18 frozen fresh streams](../benchmarks/results/shared-reading-2026-11-03.json)
run once each with unchanged ASR, matcher, model, lexicon, thresholds and disabled
book hints. Ten controlled cases use Microsoft Zira and David as two adult reading
roles; eight variants reuse two inspected MPS child recordings with inserted or
mixed synthetic adult speech. Total audio is 540.26 seconds. Selection, scripts
and composition recipes are fixed before synthesis/recognition. All samples,
interim responses, EOF and app/observer/replay audits pass. These are constructed
stress tests, with blank listening labels, rather than natural family reading,
new-speaker accuracy, Singapore speech, room testing or verified latency.

Six of ten controlled cases meet all declared effect goals: single voice, handoff
and handback, parent finishing, repeated line, unrelated aside and coaching-only.
Seven meet the target-only goal. Long pause, coaching followed by legitimate
reading, and overlap miss the target; omission and overlap also miss the final
effect. No target-negative case emits the target, and no target emits before its
legitimate reading begins. The repeat case emits every intended effect once.
The long-pause ASR drops "a small"; overlap corrupts the target transcript.

The clearest tracking failure is coaching consumption. In the controlled case,
ASR correctly retains both "Can you say [the target sentence]?" and the subsequent
legitimate reading. Permission blocks the coached effect, but tracking advances
past that checkpoint, so the real reading never gets its effect. Coaching before
the recorded sheep passage similarly suppresses riverside and skips hundred_sheep;
both baseline emissions are lost. It adds lost_sheep, whose correctness is not
human-confirmed. Normal handoffs succeed in these examples; speaker identification
would not address the quoted-coaching state transition.

The sheep source's aside/overlap variants preserve baseline emissions, but those
effects occur before the midpoint interruption and do not prove recovery after it.
The bears source's aside and overlap both lose clever_bears, which emits after the
midpoint in its fresh baseline. Its child-omitted hibernate stays off in all four
variants: three retain literal absence, while one contains the word only in an
adult coaching prompt. Child samples are preserved under common 0.4 gain; midpoint
insertions may split a word, and equal-RMS mixing does not reproduce room acoustics.
The local 18-case listening review is under `output/shared-reading-2026-11-03/review/`.
No runtime repair or tuning occurred during that frozen evaluation. The subsequent
shared-reading policy above accepts positive coaching as reading. Interruption
recognition remains open; the subsequent prefix repair above addresses the
confirmation issue. The five reviewed close-word emissions are accepted above.

Singapore CHILDES streaming diagnostic, 2 November: [four fresh streams](../benchmarks/results/childes-singapore-streaming-2026-11-02.json)
cover the one downloaded classroom recording, e5d6a.mp3 (195.42 seconds),
and its three previously selected context clips. These are one source recording
and three unique CHAT-derived anchors, with six checkpoint opportunities.
No checkpoints emit or are suppressed; all six opportunities remain unreached.
ASR, matcher, model, hints, thresholds and selected audio remain unchanged.

The full stream captures "you draw on her left hand" exactly at callback
125.440 seconds. Alignment scores 100 and gains one of two required confirmations;
the next changed hypothesis arrives at 165.888 seconds, beyond the 12-second
evidence window. Thus the tracker misses a phrase present in ASR. The other two
full-stream references are not recognized exactly. The first two cropped streams
return empty final transcripts; the third returns unrelated text. CHAT timestamps
are machine-aligned and unverified, and the full stream recognizes the third
target before its nominal crop begins. The crops therefore need listening/timing
review before they can establish recognition failures on audible target speech.

All audio samples are delivered, EOF completes and app/observer/replay agree.
Two streams produce interim text; the other two produce only empty EOF results.
The harness initially stopped on an assertion requiring interim text. A recorded
audit/resume amendment retains those first two trials without repeating audio,
then finishes the remaining clips. Runtime, audio and checkpoint hashes do not
change. The full-source ASR timeline replays against six existing MPS policies
with zero effects; these are six comparisons, not new audio trials or omission
controls. Three CHAT parser tests pass. The listening review is under
`output/childes-singapore-streaming-2026-11-02/review/`.

Post-evaluation user listening covers the three wider full-source excerpts.
The first phrase is unclear and remains unresolved, without an omission label.
The second is clear and accepted, establishing a full-stream false negative;
ASR retains "or in the cafe" in place of the transcript's carpet phrase. The
third is explicitly accepted as "you draw on her left hand", confirming the
full-stream tracking miss above. User marks place it around 0:07–0:10 in the
wider excerpt, approximately 120.44–123.44 seconds in the source, before the
original short crop starts at 127.125 seconds. That crop misses the target
because of timing and does not establish a target-speech recognition failure.
The other short crops were not separately reviewed; the second phrase's raw
approximate mark "0.7" is retained without assigning an exact onset/end. These
are two confirmed full-stream false negatives and one unresolved case; original
stream outcomes, runtime and model remain unchanged. Listening marks are not
verified word timing or a latency score.

The downloaded archive contains 168 transcripts but only one complete recording
is available locally. This is group conversation and an incomplete transcript of
actual speech, without an independent intended reading passage. These diagnostics
do not establish Singapore reading accuracy, speaker-disjoint performance or
word latency. The local archive/audio remain Git-ignored; the initial truncated
download is retained as a failed artifact. Access to the published Singapore
children's English reading corpus has not been obtained.

Historical strict-literal challenge, 2 November: [45 frozen synthetic adult-speech challenges](../benchmarks/results/false-trigger-challenges-2026-11-02.json)
test five anchors across correct readings, omissions, close/distant wrong words,
quoted/negated prompts, unrelated continuations, skips and rereading. The evaluated
default one-shot policy emits on all five close wrong words while ASR correctly
retains those words: coat/goat and seal/zeal already pass the previous spelling
rules; fan/van, pen/pin and sink/zinc are newly accepted after the phonetic/progress
repair. All 30 other negatives remain off. All ten correct/reread cases emit
once with no duplicate target effects. These are constructed adult counterexamples
under literal-word expectations, not child-reading accuracy observations.

A required-endpoint observer blocks these five cases, but that is a predeclared
policy comparison, not a production change or a general fix: stricter spelling
can also reject accepted ASR substitutions and cannot prevent ASR itself replacing
the wrong word with the book word. ASR, matcher, source/model/audio hashes and
all trials remain unchanged. On 3 November the user listened and accepted all
five close variants for the pod. Their listening labels are now recorded; the
required-endpoint observer would reject all five accepted cases. Broader child
pronunciation performance still needs evidence beyond these synthetic examples.

Untuned post-phonetic speaker check, 2 November: [24 fresh streams from 12 new MPS speaker IDs](../benchmarks/results/mps-heldout-phonetic-2026-11-02.json)
exclude all 57 previously used IDs. Selection, order, runtime, model, lexicon,
settings and 72 checkpoints were frozen before downloading audio. All original
WAVs completed once with full delivery, unchanged hashes and app/replay agreement.
Outcomes: 64 emitted, five suppressed, three unreached. All 46 provider-marked
correct anchors emit. There are no provider-deleted endpoints/essential words
in this batch, so it supplies no fresh omission-control evidence. The local
26-case listening queue has blank human labels. These are speaker-disjoint
results on six familiar texts, not word-correctness, new-book, microphone or
verified latency scores. ASR and matcher remain unchanged throughout testing.

Contextual phonetic/progress repair, 2 November: [phonetic-feature regression](../benchmarks/results/phonetic-feature-regression-2026-11-02.json)
keeps the ASR, model, lexicon, manifests and spelling thresholds unchanged.
A general feature comparison across the complete CMU phone inventory supports
bounded close-sound substitutions under an acquired next region and a complete
exact prefix of at least four distinct words. The same endpoint evidence can
supply a unique local progress candidate, with ordinary score, coverage,
ambiguity, independent-confirmation, required-word and prompt checks retained.
There is no word-pair alias or ASR transcript replacement.

All 99 saved reading timelines replay against the frozen previous matcher:
255 emissions become 256, with only the user-confirmed hundred_sheep added and
no losses. All seven provider-deletion controls remain non-emitting. Nine fresh
reviewed/omission recordings similarly add only that effect (18 to 19 of 27
checkpoints; six suppressed, two unreached). All nine ASR timelines are identical
to their saved counterparts; both user-confirmed omissions and the fresh
provider-omission control stay off. Four fresh unrelated recordings emit zero
effects across 24 passage comparisons. Windows runs 172 tests: 171 pass and one
unchanged NeMo-only check is skipped. These are inspected-data regressions;
the earlier frozen held-out results below retain their original outcomes.
Feature similarity is a text heuristic and cannot acoustically distinguish a
near-sounding intentional substitution from a recognition error.

Untuned post-pending speaker check, 2 November: [24 fresh MPS recordings from 12 new speaker IDs](../benchmarks/results/mps-heldout-pending-2026-11-02.json)
exclude all 45 previously used IDs. The full pipeline, model, lexicon, settings,
72 checkpoints, selection and trial order were frozen before audio download.
Every selected recording completed once with full delivery, unchanged hashes
and live-app/replay agreement. Runtime matches the completed pending-effect
repair exactly. Outcomes: 64 effects emitted, five suppressed, three unreached.
Of 40 provider-correct anchors, 39 emit. User listening confirms reader 3a4h's
hundred_sheep as an accepted reading and a false negative: ASR retains "hundred
chip", which fails the existing endpoint checks. The user's approximate excerpt
end at 0:10 maps to 11.36 seconds in the original, without verified word alignment.
The one provider-deleted endpoint remains unreached and
does not emit. No pending decisions activated on this batch, so it supplies no
additional evidence about pending recovery. Existing unrelated ASR callbacks
replay to zero effects in 24 comparisons; these are not new control streams.
Both replay ledgers use the same matcher and are agreement audits. The local
listening queue has 33 flagged cases, one with user confirmation. No ASR/matcher
tuning or sample replacement occurred. These are operational outcomes on six
familiar passages, not effect accuracy, new-book or microphone validation.

General provisional-rejection repair, 2 November: [75 saved-timeline regressions and 35 fresh streams](../benchmarks/results/pending-regression-2026-11-02.json)
preserve the ASR, model weights, permission rules, recordings, manifests and
thresholds. An acquired next endpoint can remain pending under an exact recent
prefix for at most two audio seconds/four fresh updates. A fresh supported
endpoint can then emit; completion, expiry, prompts or later scene progress
otherwise finalize suppression. Raw ASR text and reading progress remain intact,
with no word-specific exception. [The effect-policy contract](EFFECT_POLICIES.md)
describes pending status, completion and concurrent suppression reporting.

All 75 original callback timelines replay through both matchers: 190 emissions
before, 191 after, no losses, and all six omission controls remain non-emitting.
Thirty-one fresh matched streams cover the latest 24 readings plus seven reviewed
cases; emissions increase from 76 to 77 of 93 checkpoints, with 12 suppressed,
four unreached and none lost. The user-confirmed restart is the sole addition.
All five fresh omission controls stay off, and four fresh unrelated streams
emit zero effects across 24 passage policies. All eight focused assertions and
delivery/hash audits pass. Windows runs 164 unit tests: 163 pass and the one
unchanged NeMo-environment check is skipped. Its ASR code remains identical to
the previously verified WSL decoder test. These are inspected-data regressions,
not a new held-out accuracy score.

Final frozen post-EOF speaker check, 2 November: [24 fresh MPS recordings from 12 further speaker IDs](../benchmarks/results/mps-heldout-eos-2026-11-02.json)
exclude all 33 previously used IDs. Selection, order, 72 checkpoints, complete
pipeline sources, model, lexicon and settings were frozen before audio download.
All trials completed once with full audio delivery and unchanged hashes; runtime
sources match the completed EOF regression exactly. Outcomes are 62 emitted,
seven suppressed and three unreached. Of 42 provider-correct anchors, 41 emit;
the user confirms reader 5b4k's escape_enemies as a false negative with an
ene-enemies restart. ASR first returns enemy, triggering permanent suppression
at callback 21.504 s. At 22.016 s it returns enemy enemies, which passes the
unchanged permission rule, but the checkpoint has advanced and is not retried.
These are callback markers, not verified word timings. That evaluation's source
snapshot remains frozen; the diagnosis identified premature finalization of a partial hypothesis.
Both provider-deleted endpoints remain unreached and do not emit. Existing
repaired-ASR control callbacks replay to zero effects in 24 passage comparisons;
these are not new control streams. Both replay observers use the identical
matcher, so their agreement is an audit, not an improvement comparison. The
31-case listening queue has one user label. This holds out speakers on the
same six familiar passages; it does not establish effect accuracy, new-book
performance, or real microphone/environment behavior. No tuning occurred.

General NeMo end-of-stream repair, 2 November: [51 fresh reading streams and four unrelated controls](../benchmarks/results/eos-regression-2026-11-02.json)
use the original unpadded files and unchanged matcher, model weights, hints,
thresholds and checkpoints. Finalization now supplies complete chunk/right
context while decoding only remaining real frames, including a final partial
frame. Internal silence adds no client time or matcher callbacks. All 51
pre-EOF transcripts are identical to their prior runs, and all final timestamps
match source duration. Emissions increase from 126 to 128 of 153 checkpoints,
with 18 suppressed and seven unreached; none are lost. The original wing case
now emits. The user confirms the second added effect, reader 4b19g's begging_paws,
as correct and clearly hears holding out their paws; ASR changes its ending from
pus to paws. Both added effects have source-audio listening notes, retaining the
wing case's soft/possibly cut-off endpoint qualification. Both user-confirmed omissions
and the provider-annotated hibernate omission remain suppressed; the fourth
provider-deleted final endpoint remains unreached. No omission control emits.
All 24 unrelated-audio/passage comparisons emit zero effects. The Windows unit
suite passes 152 tests, with its one NeMo-only test passing separately in WSL.
These are inspected-data regressions; original held-out results remain intact.
See [end-of-stream semantics](SETUPS.md) and the local listening queue under
`output/eos-regression-2026-11-02/review/`.

Trailing-silence diagnostic, 2 November: [two fresh streams of the missed wing recording](../benchmarks/results/mps-tail-silence-2026-11-02.json)
compare the original 50.84-second source with an exact speech-preserving copy
plus two seconds of digital silence. The original again omits wing and does not
trigger; the padded stream recognizes the complete anchor and emits damaged_wing.
Both pass full delivery and app/audit checks with unchanged matcher, recognizer,
settings and model hashes. This supports trailing-context/end-of-stream sensitivity,
without isolating the model from finalization behavior. It is a diagnostic audio
change, with no production change or alteration of the original held-out totals.

Untuned post-split new-speaker test, 2 November: [24 more MPS streams from 12 new speaker IDs](../benchmarks/results/mps-heldout-split-word-2026-11-02.json)
exclude all 21 previously used IDs. Selection, order, 72 checkpoints, model,
matcher, lexicon and settings were frozen before audio download. All selected
trials completed with full delivery, unchanged hashes and app/audit agreement.
Both guards emit 63 effects, suppress five and leave four unreached: no added
or lost emissions, and no additional split-word recoveries were observed.
Of 47 provider-correct anchors, 46 emit. The user hears reader 5b15k's damaged_wing
phrase, but subsequently qualifies the final wing as soft and possibly cut off;
the earlier clean false-negative label is now qualified. Final ASR stops at a bit
of the, omitting wing, and the tracker stops at word 79/80. A synthetic saved-callback
diagnostic adding only that token triggers the unchanged matcher; this is not
real recognition or a new trial. The underlying ASR/end-of-stream cause remains
unverified. The full 50.84-second provider WAV was streamed, and the review excerpt
preserves its ending exactly. Wing is the final written word of the passage;
any provider trimming before publication is unknown. The one provider-deleted endpoint is unreached and
does not emit; this is not an isolated demonstration of the permission guard.
Saved unrelated ASR callbacks emit zero effects in 24 passage comparisons.
The local listening queue has 26 flagged cases and one user-confirmed label. This is
speaker-disjoint evidence on the same six passages, not an accuracy score or
validation on unseen books. No matcher tuning or sample replacement occurred.

General split-word repair, 2 November: [27 fresh streaming regressions](../benchmarks/results/split-word-regression-2026-11-02.json)
compare the pre-split guard and repaired matcher on identical ASR callbacks.
An authored word can consume one or two adjacent whole ASR tokens only when
their joined text is exact. The complete contiguous anchor is required, with
prior local acquisition and the existing prompt/confirmation checks. A unique
next-anchor candidate also handles a split endpoint without following words.
No word-specific exception, ASR rewriting, manifest or threshold change was added.
Across 81 checkpoints, emissions increase from 62 to 63; the user-confirmed
riverside reading is the sole addition, with none removed. Thirteen remain
suppressed and five unreached. Both user-confirmed omissions, plus the separate
provider-annotated hibernate omission, stay suppressed; scales still emits.
Four fresh unrelated streams produce zero effects in 24 passage comparisons.
All 31 streams pass delivery and frozen-source/model audits. All 150 unit tests pass.
These are inspected-data regressions over the previous
24 MPS recordings plus three reviewed cases, not a new held-out accuracy score.

Untuned held-out-speaker test, 2 November: [24 fresh MPS recordings from 12 new speakers](../benchmarks/results/mps-heldout-2026-11-02.json)
exclude all nine previously used MPS speaker IDs. Selection, order, model,
matcher, lexicon, thresholds and 72 checkpoints were frozen before audio
download. All selected trials completed with unchanged hashes and full audio
delivery. Both guards emit 56 effects, suppress 12, and leave four checkpoints
unreached. Four phonetic comparisons accept none, so no added recovery or
changed effect decisions were observed. Of 35 provider-correct anchors, 34
emit. Post-evaluation user listening confirms the riverside suppression as a
false negative: recognition produced river side as two tokens, while the
then-current permission guard required a single endpoint token. That evaluation's
source snapshot remains frozen;
the reported phrase location is not an exact word-end timing. Four earlier unrelated streams
replayed against the six frozen passage policies emit zero effects in 24
comparisons. No matcher tuning was performed. This holds out speakers on the
same six familiar passages; it is not an accuracy score or new-book validation.

Expanded local regression, 2 November: [all 15 available matched recordings](../benchmarks/results/local-phonetic-sweep-2026-11-02.json)
cover nine passage texts and 41 checkpoints. Twelve additional fresh streams
plus three existing source-identical verified streams compare both guards on
the same ASR callbacks: 32 effects before, 33 after, with small_scales the only
addition and no removed emissions. Seven effects remain suppressed and one
unreached. Phonetic assistance emitted an effect in only that one reading;
these are regression counts, not a held-out accuracy score. Four previously
streamed unrelated recordings replayed against all nine passage policies emit
zero effects in 36 comparisons. Tea and Little Mermaid retain unresolved
suppression cases. That sweep used eleven MPS readings and four supplied original
stories; private OCSC audio referenced elsewhere remains absent on this PC.

Human-reviewed follow-up, 2 November: the accepted scales/sales reading was
reproduced as a suppressed effect when streaming Parakeet recognized cells.
A general dictionary-based phonetic endpoint check now permits that reading
under exact local-context and prior-progress guards, with no checkpoint aliases
or manifest changes. [Three fresh focused streaming checks](../benchmarks/results/reviewed-endpoint-regression-2026-11-02.json)
confirm small_scales emits while the human-confirmed hibernate and enemies
omissions remain suppressed; later supported effects still emit. Four unrelated
streams produced zero effects in 12 current-matcher/passage comparisons. All 143 unit
tests pass. These runs used the RTX 4060 laptop and the same NeMo model/buffering;
they do not replace the historical 21-reading sweep or verify word-end timings.
Install the updated client requirements (`cmudict==1.1.3`) for phonetic lookup.
Independent word-pair tests exercise the rule outside this recording; broader
held-out reading accuracy remains unmeasured.

Implemented 2 November: split mode now gates one-shot effects separately from
reading progress and fixes the reproduced short-anchor ranking/confirmation
delay. [The complete guarded rerun](../benchmarks/GUARDED_PILOT_RESULTS.md)
covered 21 readings and four controls: 56 effects emitted, five withheld, two
unreached; zero effects in 36 unrelated-audio/passage comparisons. The affected
case improved from 5.543 s to 0.709 s on provisional timing. All 135 tests pass.
See [effect policies](EFFECT_POLICIES.md) and the
[Singapore microphone collection kit](pilot/singapore/README.md). Human listening
sign-off and actual Singapore microphone/enclosure testing remain pending.
The dated notes below retain the earlier, pre-guard evidence.

Flagged-case follow-up: [the evidence review](../benchmarks/FLAGGED_READING_REVIEW.md)
finds two omission/effect-policy risks and one reproducible candidate-ranking
delay. All original human listening fields remain unverified. Runtime matching
was reviewed but not changed.

2 November follow-up: [12 additional child-reading streams](../benchmarks/READING_EXPANSION_RESULTS.md)
from six new Indian speaker IDs activated 35/36 configured checkpoints, with zero
triggers in 16 unrelated-audio/passage comparisons. These are not Singapore or
Southeast Asian children. Seventeen checkpoints have extra review flags and no
timing is manually verified. All 122 unit tests pass. Runtime matching was not
changed; see [regional data findings](CHILD_READING_DATA.md).

31 October follow-up: application Python code now lives in `books_to_life/`.
Use `python -m books_to_life.cli.<module>` from the project root. See
[setups and tradeoffs](SETUPS.md) for the recommended explicit configuration and
[the fresh post-reorganization evaluation](../benchmarks/BEST_SETUP_RESULTS.md).

Updated 29 October 2026. This describes the implemented repository, including
experimental trackers developed in this chat. The older PROJECT_BRIEF.md is a
planning snapshot and should not be used as the current architecture/status.

Follow-up 30 October 2026: [passage-backed audio and hint comparison](../benchmarks/READING_CONTEXT_RESULTS.md)
records the MPS imports, published-text Kites/Billy/Tom rebuild, acoustic timestamp
estimates and eighteen fresh hinted streams. No hints caught 26/27 checkpoints;
moving hints 26/27; whole-passage hints 25/27 including a severely early Tom
activation. Keep `--no_book_context` explicit for the evaluated pilot configuration.
Guarded jumps and checkpoint-local effect evidence are proposals, not implemented
fixes. All 119 unit tests pass; automatic timestamps are not manually verified.

Latest changes: experimental `split` now includes boundary evidence carry and
scoped timely recovery. See [the latency evaluation](../benchmarks/TIMELY_TRACKER_RESULTS.md)
for measured gains and remaining delays. Recordings and matching transcripts
are organized under [recordings/library/](../recordings/library/README.md), with supplied passage text separate from spoken transcripts. OCSC inputs remain
local; [cross-PC setup and transfer commands](../recordings/OCSC_LOCAL_SETUP.md)
are committed so the same subset can be used on another personal PC.

## Current flow

```text
Select book manifest (full page text + checkpoint ranges + effect payloads)
        |
Microphone OR recording -> 16 kHz mono audio packets -> local WebSocket server
        |                                              |
        |                                  Whisper / Parakeet / Moonshine
        |                                              |
        +-------------------- partial/revised transcript snapshots
                                                       |
                            normalize text + replace revised ASR segments
                                                       |
                           align recent speech with nearby full book text
                                                       |
                        candidate position + coverage + ambiguity checks
                                                       |
                             confirmation / evidence / scene selection
                                                       |
                    [ALIGN] position, [SKIPPED] scenes, [TRIGGER] payload
                                                       |
                          terminal output + saved SRT when session ends
```

This is text alignment AFTER ASR, not direct audio-to-book forced alignment.
The full selected passage is the reference; each update searches a moving
window using recent recognized words. It is not merely searching for a
checkpoint sentence. The original tracker also uses approximate word similarity.
Checkpoints define effect locations in that book, rather than restricting all
matching evidence to the exact checkpoint phrase.

The manifest supplies page text, ordered checkpoint word ranges/anchors,
thresholds, and effect payloads. Without a checkpoint manifest the client only
transcribes. Restart the client with a new manifest to select a different book.
Each client invocation creates a new in-memory session.

The tracker advances confirmed progress, suppresses duplicate scene activations,
and can select a later scene while marking intervening scenes skipped. Reaching
completed does NOT prove that every scene fired. Current catch-up behavior is
suited to persistent ambience; there is no separate event policy for one-shot
sounds/animations. Effect filenames are placeholders and physical audio/video
playback/control is NOT wired to triggers yet.

## Recognition engines and hints

- Whisper: native Windows CUDA or documented Docker deployment. Supports book
  prompts and hotwords, including moving context through the server extension.
- Parakeet NeMo: original Unified model in Linux/WSL CUDA, with phrase boosting.
  No Whisper-style passage prompt. Default internal buffering is 560 ms chunk,
  560 ms right context and 5.6 s left context. The tested PC uses an RTX 3070 Ti.
- Native Parakeet/Moonshine adapters are also available; their buffering and hint
  capabilities differ. Latest tracker comparison used Whisper medium.en and
  Parakeet NeMo only; do not assign those results to Moonshine/native Vulkan.

A checkpoint manifest can automatically generate moving book hints. Explicit
`--hotwords`/`--initial_prompt` override their respective generated fields;
`--no_book_context` disables automatic book hints. The latest controlled test
used explicit fixed vocabulary or no hints, with automatic context disabled.
No automatic model fallback or production recognizer selection is implemented.

## Tracker modes

| CLI mode | Behavior | Status |
| --- | --- | --- |
| `alignment` | Original full-text word-sequence alignment and consecutive confirmation | Default |
| `evidence` | Holds candidates through bounded noisy updates; supports strong stable revisions/completion at the boundary | Experimental |
| `split` | Contextual split-token alignment, boundary evidence carry and scoped timely recovery | Experimental; see the latest latency report |
| `fuzzy` | Legacy checkpoint-phrase matching | Optional baseline |

The CLI model default is currently `base.en`; it is NOT automatically Parakeet
or medium.en. Use explicit model, port and matching mode in tests.

Evidence retention lasts at most 12 seconds of segment time or 12 fresh updates
since support. Ambiguity clears it; another accepted scene replaces it. New book
words can confirm progress but are not universally required: a strong match can
also survive a changed hypothesis over newer audio or utterance completion.
Duplicate callbacks and timestamp-only changes do not manufacture confidence.
A completed utterance is a stability signal, not new independent audio evidence.

Split assistance requires already-confirmed story progress, proximity to the
next checkpoint, at least two exact words on either side of one compound,
distinct supporting context, and the latest transcript tail. It uses a limited
spelling/consonant proxy, NOT a trained pronunciation model. This can connect
key pot/key put to teapot inside put the ... on the stove, without a global
Tea-specific replacement dictionary. Prefix support just before the boundary
can carry forward across a short partial-word update; later book words are not
required. Negation/prompt markers block split proposals but do not replace
speaker identification or semantic understanding in the ordinary aligner.
First-scene split assistance is intentionally unsupported.

For a second PC with limited disk space, see [LOW_STORAGE_TESTING.md](LOW_STORAGE_TESTING.md)
for client-only LAN testing and offline limitations.

## How to start the tested Parakeet + split setup on this PC

Requires the existing Windows .venv, WSL Ubuntu-24.04, CUDA and prepared NeMo
model. Installation details remain in README.md; these are startup commands for
the already-prepared PC. Use two terminals and leave the server running.

Terminal 1, inside Ubuntu/WSL:

```bash
cd /mnt/c/Users/heart/Speech-to-Text
/home/heart/.venvs/books-to-life-nemo/bin/python -m books_to_life.cli.run_nemo_server --model-path model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo --port 9097
```

Terminal 2, PowerShell in the repository, recorded Tea with the tested fixed hints:

```powershell
New-Item -ItemType Directory -Force output | Out-Null
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model parakeet-nemo --server 127.0.0.1 --port 9097 --matching_mode split --files recordings/library/stories/tea/readers/tea/audio.wav --mute_audio_playback --checkpoints recordings/library/stories/tea/readers/tea/checkpoints.json --no_book_context --hotwords "mouse, pot of tea, phone, teapot, stove, cups, little house, Toad" --transcript_file output/tea-split.srt
```

For microphone input, omit `--files recordings/library/stories/tea/readers/tea/audio.wav` and read that passage
aloud. Select a device using `--list_input_devices` then `--input_device` if
needed. Stop capture with Ctrl+C. Microphone packet size is configurable using
`--audio_chunk`; file playback uses the existing 4096-sample packets. Test a new
microphone configuration before expecting the recording results to reproduce.
For a direct original-tracker baseline change only `--matching_mode alignment`.

## Verification completed

### Fresh streaming comparison on 24 October

24 fresh audio streams covered all eight recordings: four matched books with
hints on/off, plus four off-book clips, for each of two recognizers. The original
and split trackers were evaluated online at each fresh ASR callback in the same
client. This controls recognition variability. Actual app split triggers matched
the split observer in all 16 matched-book runs.

| Recognizer, hints off/on combined | Original activations | Split activations |
| --- | ---: | ---: |
| Whisper medium.en | 9/16 | 9/16 |
| Parakeet NeMo | 12/16 | 16/16 |
| Total configured scene opportunities | 21/32 | 25/32 |

No original activations lost. The four added activations were Tea stove and house
in both Parakeet conditions. Seven configured opportunities remain unactivated,
all Whisper: Fat Cat both scenes without hints, Fat Cat hat scene with hints,
Tea stove/house without hints, and Tea initial tea/house with hints.

The stove fired at the first complete stove callback in both Parakeet runs,
without waiting for the next sentence. House recovery was still late. Of 21
shared activations, 16 had unchanged callback timing; five were 0.48â€“1.78 s later
with the new tracker. This is relative tracker delay, not measured delay from
the actual spoken word to an effect.

Zero activations for either tracker in 32 live off-book stream/book comparisons.
This does not establish a zero wrong-scene rate during related conversation.
Fat Cat's first exact anchor was reportedly skipped: its activation can be scene
catch-up rather than a correct spoken-phrase detection. The clips used to develop
the tracker were reused here; this is not independent held-out validation.

All samples were verified delivered in 256 ms packets. Delivery was approximately
4% slower than nominal recording duration. Partial text arrived while only early
audio had been sent; ASR was not given the full file upfront. Files bypass live
microphone acoustics. Fresh streaming tests are different from saved-transcript
replay and are separately documented in LIVE_TRACKER_RESULTS.md.

### Automated verification on 27 October

- Run `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`.
- 91 tests pass, covering original alignment and adapters plus evidence retention,
  duplicates, revisions, completion, expiry, split boundaries, partial words,
  prior acquisition, negation/prompting, wrong objects and stale/same-audio prefixes.
- `git diff --check` passes.
- CLI help exposes alignment/evidence/split/fuzzy; default remains alignment.
- Verified latest streaming result source hashes against the tested matcher and
  streaming harness files before publishing this handover. Historical hashes in
  the snapshot describe those tested files, not future edits.

The printed bad-audio traceback during the unit suite is from an intentional
mock error-path test; the suite reports OK. These checks do not replace on-device
integration testing. The full audio benchmark was not rerun on 27 October.

## Remaining TODOs and verification gates

### 1. Establish whether activations are correct AND on time

- [ ] Annotate each recording with actual spoken checkpoint ends, skipped text,
      speaker turns and the intended scene at each time.
- [ ] Label catch-up separately from exact event detection; resolve Fat Cat's
      skipped-anchor case before reporting precision/recall.
- [ ] Measure missed scenes, wrong scenes, duplicate activations, median/P95
      spoken-boundary-to-trigger delay, and eventual catch-up delay separately.
- [ ] Investigate the late Tea house recovery and extra 0.48â€“1.78 s confirmation
      delays. Avoid claiming the current 25/32 count is an accuracy score.

### 2. Test generalization and interruptions before choosing the default

- [ ] Use held-out books and fresh consented child recordings; keep development
      and evaluation sets separate. Repeat trials to measure ASR variability.
- [ ] Test repeated phonics, short books/final sentences, skipped lines,
      backwards rereading, pauses and alternate readings.
- [ ] Extend the frozen constructed prompt, negation, off-book, interruption and
      two-voice checks to held-out books and natural family readings. Either
      voice supplying supported story text counts under the chosen pod policy.
- [ ] Validate/tune the split proxy beyond key pot/key put; test ambiguous
      compounds and first-scene failures. Its conservative guards can miss valid
      readings as well as prevent wrong matches.
- [ ] Compare fixed vocabulary with automatic moving context separately, since
      tracker progress can change future recognition when moving hints are on.
- [ ] Decide whether to promote split mode only after those measurements. It is
      currently opt-in; do not silently change the default based on these clips.

### 3. Verify live microphone and target hardware

- [ ] Child reading through intended microphone, in the enclosure, with fan/noise
      and the pod's own soundtrack playing. Validate echo-cancellation routing.
- [ ] Test on the actual Jetson/mini-PC alongside media playback; log memory,
      thermals, sustained load and recovery. RTX GPU throttling is not a Jetson test.
- [ ] Confirm clean installation/model-cache setup on a teammate's machine;
      existing benchmark launchers use this Windows/WSL setup and cached models.
- [ ] Review file-client pacing drift and distinguish it from recognizer delay.

### 4. Integrate actual effects and session lifecycle

- [ ] Connect trigger payloads to preloaded projector/video and sound playback;
      replace placeholder assets, then measure real audio/video synchronization.
- [x] Define persistent ambience versus one-shot permission in split mode;
      suppressed one-shots advance progress without replay. Real actuator
      integration and component policies for mixed payloads remain pending.
- [ ] Add operator book selection/session reset and define rereading behavior.
      State is currently in memory and resets when the client restarts.
- [ ] Define disconnect/reconnect and restart recovery; add persistence if needed.
- [ ] Resolve current project scope (visuals/audio versus optional lighting) with
      the team before building the actuator layer; payload fields reflect prototype
      examples, not proof that every hardware subsystem is implemented.

### 5. Operational cleanup

- [ ] Bound production Whisper finalization: the live benchmark patches a 30 s
      maximum after audio ends, but normal run_client.py still uses upstream
      final-hypothesis settling. One excluded attempt waited until the 240 s
      benchmark timeout. Retained runs finished before the cap.
- [ ] Classify normal WebSocket code 1000 closes as successful finalization instead
      of ERROR when the transcript is complete; preserve real failure reporting.
- [ ] Replace the benchmark's raw TCP readiness probe with a suitable readiness
      check to avoid harmless WebSocket handshake warnings.
- [ ] Archive ignored raw benchmark logs/events/transcripts securely and preserve
      source/model/dependency versions for reproducibility. The committed JSON
      summary is portable; raw data and installed models are not pushed.
- [ ] Complete operator/sensory limits, rights/consent and deployment safety review
      before use in a public pod. These remain wider project tasks.

## Evidence and reproduction files

- `benchmarks/LIVE_TRACKER_RESULTS.md`: fresh audio results and caveats.
- `benchmarks/results/live-tracker-2026-10-24.json`: committed portable results,
  packet audit, trigger times and source/audio hashes; no raw transcripts.
- `benchmarks/SPLIT_REPLAY.md`: earlier saved-transcript split comparison.
- `benchmarks/EVIDENCE_REPLAY.md`: earlier evidence-only comparison.
- `benchmarks/live_tracker_probe.py`: live packet/ASR/tracker event logger.
- `benchmarks/run_live_tracker_comparison.py`: Windows benchmark runner, ports
  9096 (Whisper) / 9097 (Parakeet). Parakeet requires an external WSL server.
- `benchmarks/summarize_live_tracker.py`: summarizes the raw live artifacts.
- `benchmarks/replay_evidence.py`: scoped replay of the historical saved streams.
- `benchmarks/diagnose_*.py`: diagnostics; the stove diagnostic is an explicit
  alias experiment, not the production matching implementation.

From repository root, on the prepared Windows PC:

```powershell
.\.venv\Scripts\python.exe benchmarks/run_live_tracker_comparison.py --model medium.en
# Stop Whisper first; start the WSL Parakeet server on port 9097, then:
.\.venv\Scripts\python.exe benchmarks/run_live_tracker_comparison.py --model parakeet-nemo --external-server
.\.venv\Scripts\python.exe benchmarks/summarize_live_tracker.py
```

Use `--resume` only for interrupted runs belonging to the same protocol/source
version. The runner currently writes to output/live-tracker-2026-10-24; archive
that directory or change the output destination before a new independent run,
otherwise existing evidence may be overwritten. Replay/diagnostic scripts need
the local ignored historical artifacts; the committed summary can be read on a
fresh clone without those artifacts.
