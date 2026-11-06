# Benchmark child-reading recognition

Latest implementation:
[separate effect cues and bounded acquisition](results/effect-cue-regression-2026-11-06.json).
Optional authored `effect_cue` text sets an effect boundary inside the full
tracking checkpoint. Required words remain strict. Short cues use confirmed
book context, including an exact three-distinct-word suffix when only optional
leading words are absent. Bounded acquisition lets the next nearby cue use one
existing internal pronunciation comparison in a unique contiguous context run;
normal score, coverage, ambiguity, context length and independent votes still
apply. The model, ASR, lexicon, hints and numeric thresholds are unchanged. The
pilot lost-sheep cue explicitly requires `lost`; all manifests/results are
versioned and original full-anchor omission labels remain preserved.

All 383 saved legacy ledgers remain identical. Fifty-four same-authored-policy
comparisons add 13 emissions and remove none. Requiring an essential action is
a stricter book policy than the earlier whole-phrase tolerance: the accepted
3a8b source with ASR "locked" remains blocked under the authored cue. Fourteen
saved conditions repeat this one source; they are not fourteen independent
readers. It remains a visible ASR false negative, without a word replacement.

The final 42 real-paced streams deliver all 1329.32 seconds: 25 legacy cases,
nine authored cases and eight synthetic cases. Eight supported authored cases
and all four new synthetic positives emit. All seven declared-essential omission
targets and all thirteen word-omission targets remain off. Four fresh unrelated
timelines against six authored policies emit zero effects in 24 replays. All
previous reviewed, interruption/pause/phase and endpoint assertions pass. The
known ASR-essential-word case is retained as the one human-positive target miss.
All 33 required ASR callback sequences are identical. The extra historical
optional-prefix case is reported separately. Full delivery, interim/EOF, pacing,
hashes and app/observer/replay audits pass. Windows: 222 tests pass, one existing
NeMo-only test is skipped. The local ASR server is stopped.

`run_effect_cue_regression.py --stage prepare|preflight|inventory|run|verify` uses
the complete pre-edit runtime in `baseline-snapshot/` and `baseline.json`. For a
new batch, capture that complete baseline before changing production code.
`synthesize_shared_reading.ps1` generates the frozen synthetic scripts with two
installed adult voices. `summarize_effect_cue_regression.py` builds the portable
report and local listening page. The final output is
`output/effect-cue-regression-v4-2026-11-06/`; earlier preparation/preflight
directories retain `ABORTED.json` and zero fresh recognition trials. These are
inspected regressions, not untouched-reader, room or acoustic latency evidence.

Latest read-only investigation:
[MPS recognition/progress diagnosis, 6 November](results/mps-progress-investigation-2026-11-06.json).
All 147 existing original MPS histories (74 speakers, 441 checkpoints) are
replayed with the frozen current matcher. Instrumentation returns production
values unchanged and verifies every one of 8033 saved updates against a separate
vanilla tracker; all original ledgers reproduce. Seven fixed diagnostic cases
also stream unchanged original WAVs once (311.02 seconds, 376 callbacks). Every
checkpoint outcome repeats. The four latest ASR sequences are identical; three
historical sequences differ slightly under current streaming without changing
outcomes. No ASR/matcher/model/threshold/hint/manifest/audio changes are made.

The reported lost-sheep ASR supplies six supported words where seven are needed,
and progress stops before acquiring the anchor. Replaying prefixes of the user's
transcription at the same six final callback times makes the unchanged tracker
emit. This is an oracle-text diagnosis, not another audio or ASR accuracy trial.
Among 24 saved lost-sheep histories, 14 emit and ten remain unreached: five filter
all crossing candidates, three select another alignment, two lack sufficient
confirmation. Four missed ASR histories contain the exact four-word first
sentence; their checkpoint also includes the following sentence. Another recent
miss could pass current local permission aids but never acquires the anchor.
Eight provider-deleted essential/endpoint controls remain off. Some missing
following sentences are provider-annotated actual omissions, not decoder errors.

`investigate_mps_progress.py --stage prepare|replay|fresh|verify` preserves a fixed
diagnostic protocol, the original inputs and per-callback traces under
`output/mps-progress-investigation-2026-11-06/`. `summarize_mps_progress_investigation.py`
builds the report, separate oracle-text probe and local listening page with seven
unaltered PCM end crops. These cases are inspected diagnostics, not new holdout
accuracy; additional listening labels are not inferred. The server is stopped.

Latest untouched-speaker evaluation:
[frozen MPS streaming, 6 November](results/mps-frozen-streaming-2026-11-06.json).
The runtime matches the completed internal-pronunciation regression. A fixed
seed selects 12 new speaker IDs (24 paired-paragraph recordings), balanced over
grades 3–5 and provider gender labels, excluding 69 previously used IDs. The
source snapshot, manifests, selection/order, model and lexicon are frozen before
downloading audio or running recognition. No production code, model, thresholds,
book hints, checkpoint phrases or source audio change. The new audio hashes have
no overlap with 215 distinct hashes from prior result files.

All 24 original recordings stream once at their original pace (1014.48 seconds).
All 37 provider-marked correct anchors emit. The single provider-marked essential
word omission, `hibernate`, does not emit. Of all 72 checkpoints, 53 emit, 14 are
suppressed, one is skipped and four are unreached. All 19 non-emitting anchors
have provider-marked miscues, which still need human pronunciation/acceptance
review. Four saved unrelated timelines across six policies emit zero effects
in 24 callback replays. Full delivery, interim/EOF, pacing, app/observer/replay
agreement and all source/model/lexicon/manifest/audio hashes pass.

`output/mps-frozen-streaming-2026-11-06/` retains the frozen source and protocol,
original WAVs, callbacks, transcripts, per-checkpoint evidence and a listening
page with 35 flagged checkpoints. The ASR server is stopped. These are new
readers of six familiar MPS texts, not new books, human listening gold, room
validation or human-verified word-end latency. One reader gets zero effects in
one passage, so provider-correct coverage must not be called overall accuracy.

[Subsequent listening diagnosis](results/mps-listening-review-2026-11-06.json)
records the user's shorter river wording and lost-sheep wording separately from
the assistant's recommendation to accept both for the pod. The current ordinary
permission check accepts the reported lost-sheep wording in isolation, while
actual ASR corrupts several words and streaming never reaches that checkpoint.
The river's one-shot endpoint guard is a separate policy/authoring issue. The
first checkpoint remains unreviewed. Frozen trials/runtime/manifests are unchanged;
these inspected phrases cannot be reused as untouched holdout evidence after a fix.

Reproduction: `run_mps_frozen_streaming.py --stage prepare|download|run|summarize|verify`.
Preparation refuses an existing output folder; recognition refuses to overwrite
`streams/`. The completed batch uses the frozen seed/date in that helper and an
unchanged NeMo server at port 9097. `--stage verify` checks the completed freeze;
`--stage summarize` rebuilds the report and local listening page without rerunning
recognition. `FROZEN_VERSION.txt` in the output folder explains the snapshot.

Latest repair: [guarded internal pronunciation support](results/internal-phonetic-regression-2026-11-04.json).
The user accepts the sheep excerpt, confirming the prior changed effect as a
regression. The already-acquired next checkpoint may now gain one missing coverage
match from an observed internal word using the existing pronunciation rule. It
needs exact ordered neighbours, an exact endpoint, three distinct ordinary
supported anchor words and one unambiguous candidate. Required words keep stricter
spelling support. There are no token-gap credits, word exceptions, ASR rewrites or
changes to the model, candidate scores or numeric thresholds. Sheep/ship supplies
the seventh supported word out of eight; lost/locked remains unmatched.

All 25 fresh streams (844.94 seconds) reproduce the previous ASR callbacks exactly.
The confirmed coached phrase and the original uncoached reading now emit. Nine
reviewed MPS target assertions, the prior pause/aside fixes and all four phase
cases pass. Eight fresh word-omission controls stay off. Four unrelated recordings
yield zero effects across 24 policy replays. All 327 saved old ledgers reproduce;
no emitted effects are removed and all skips remain unchanged. Twelve saved
comparisons gain `lost_sheep` under repeated conditions for one underlying child
source; this is inspected regression evidence, not new-reader accuracy.
Windows: 210 unit tests pass, one is skipped; the unchanged NeMo decoder-budget
test has a verified passing WSL result. All transport, EOF, model/source/audio
hash and app/observer/replay checks pass. The ASR model and silence handling are
unchanged from the resumption version.

`run_internal_phonetic_regression.py --stage prepare|preflight|run --output <fresh-output>`
expects the pre-change `baseline.json` and `baseline-snapshot/` copied from the
completed output, existing local sources and the pinned NeMo server on port 9097.
`summarize_internal_phonetic_regression.py --output <output>` creates paired
fresh-callback comparisons and the portable report. Raw output is local under
`output/internal-phonetic-regression-2026-11-03/`; the directory keeps its start
label while the report records completion on 4 November.

Earlier repair: [general resumption regression](results/resumption-regression-2026-11-03.json).
The NeMo wrapper closes an utterance after one existing right-context of exact
digital zero PCM; later nonzero audio starts a fresh decoder while book/session
state continues. A unique observed prefix of the acquired next anchor can survive
a completed off-book aside, with normal alignment, coverage, required-word and
confirmation checks on its observed continuation. Old-utterance negation cannot
poison a new exact prefix. Model weights and all numeric thresholds are unchanged;
there are no word exceptions, new amplitude thresholds or phase-padding rules.

Final v3 runs 81 paced streams once each (1893.09 seconds), including the 32 earlier
inputs, all 45 synthetic challenges and four pause/phase inputs. Both accepted
misses emit. All four phase cases, nine reviewed MPS target assertions and the
Singapore left-hand regression pass. Three natural word-omission controls and five
synthetic endpoint omissions stay off; seven saved deletion controls stay off.
All 20 accepted challenge positives emit and all 25 negative targets stay off.
Their prior working effects are preserved. Four unrelated sources yield zero
effects across 24 policy replays. All 246 saved old ledgers reproduce and remain
unchanged; 81 fresh callback timelines are additionally paired across old/new
matchers. Packet, EOF, model/source/audio hashes and app/observer/replay audits pass.

Five effects are added versus original fresh inputs; one then-unreviewed `lost_sheep`
effect in the coached sheep variant is withheld after ASR changes lost to locked.
Both matching implementations withhold it on that ASR. Later user listening
confirms it should count, and the internal-pronunciation repair above recovers it.
The exact-PCM excerpt remains in the resumption output's `review/`.
Windows: 203 unit tests pass and one is skipped; the skipped NeMo decoder-budget
test passes separately in WSL. These are inspected reused-source regressions,
not child population accuracy or microphone/room evidence. Nonzero noise is not
classified as silence. Callback markers are not verified word latency.

`run_resumption_regression.py --stage prepare|preflight|run --output <fresh-output>`
expects the pre-change `baseline.json` and complete `baseline-snapshot/` copied
from the final output into the new directory before prepare. It requires the
existing local sources and pinned model, then the local NeMo server on port 9097.
`summarize_resumption_regression.py --output <output>` audits and creates the
portable report and the optional listening excerpt. Original trials/labels are
preserved. The preliminary preflight failure and 29-stream v2 batch remain in
their original output directories and are excluded from final v3 metrics.

Earlier pause investigation: [four fixed real-paced streams](results/pause-asr-diagnostic-2026-11-03.json)
cross short/long silence with two chunk phases, using identical target-sentence
PCM and unchanged ASR/matcher/model/settings. Both short cases recognize "A small
rabbit" and emit; the original long-gap phase loses "A small" and withholds the
effect. Extending the long gap by 280 ms restores recognition and the effect.
All 76.06 seconds pass delivery/EOF and app/observer/replay checks. The original
baseline and long-gap callback timelines reproduce exactly. This is a fixed
synthetic diagnostic, not a universal silence-reset explanation or padding fix.
`investigate_pause_asr.py --stage prepare|run --output <fresh-output>` freezes
the four inputs before streaming through the existing local NeMo server.

The [user listening assessment](results/pause-interruption-listening-2026-11-03.json)
accepts the long-pause rabbit phrase and the child `clever_bears` phrase across
an inserted aside. Both are required positive misses. The synthetic overlap is
unclear with optional success; the child overlap is too chaotic to require a
trigger. Those latter cases are not literal omission controls. Existing trial
ledgers and other checkpoint labels are preserved. Audio and the listening page
are local under `output/pause-interruption-review-2026-11-03/`.

Latest listening review: the user accepts all five contextual close-word
recordings (coat/goat, fan/van, seal/zeal, pen/pin, sink/zinc) for the pod.
The current matcher already emits them; no ASR, matcher or threshold change is
needed. They are accepted pronunciation tolerance, not five unresolved pod
defects. The [user assessment](results/pronunciation-acceptance-review-2026-11-03.json)
is attached to the reports separately from their original strict-literal counts.
Only "goat" has an independent user word transcription; all five have explicit
acceptance labels. Omission and unrelated-speech expectations remain unchanged.
These synthetic adult cases do not establish child-accent accuracy.

Earlier repair: generic exact-prefix confirmation during book-position recovery.
Only timely_matcher changes relative to the shared-reading policy. An unambiguous
exact leading prefix can supply one earlier vote; a later ordinary accepted
candidate must contain the complete exact anchor in the current segment. Scores,
coverage, accepted alignment length, stability, search bounds and ASR stay fixed.
The new path requires fresh text/newer audio within the existing bounds, does not
borrow retained older segment words, and does not refresh on older-context edits
or timestamp-only updates. It has no checkpoint/word exceptions.

All 214 saved ledgers match the complete old runtime before comparison. The fix
adds eight effects, including Singapore left hand, adult-coached hibernate and
six later finish events, with none lost. All 123 MPS outcomes stay unchanged;
seven deletion controls, omitted/negated targets and unrelated speech stay off.
The five reviewed close-word emissions are user-accepted. Windows: 189 unit tests pass and
one unchanged NeMo-only test is skipped.

[The completed prefix regression](results/prefix-confirmation-regression-2026-11-03.json)
runs 32 final fresh streams: one full Singapore source, eighteen shared inputs,
nine reviewed MPS recordings and four unrelated recordings (1324.82 seconds).
All ASR callbacks are identical to the originals. Effects increase from 54 to
58 with no losses/duplicates: left hand, coached hibernate and two later finish
events are added. All nine reviewed assertions pass and all three original
omissions remain non-emitting. Four fresh unrelated ASR timelines replay against
six policies each with zero effects. Shared target goals improve from 15 to 16
of 18; controlled complete-effect goals improve from seven to eight of ten.
Long-pause and overlap target recognition misses remained at that evaluation;
the later resumption repair above addresses the accepted pause/aside cases. The coached hibernate
contains an adult-spoken word and is a positive shared-reading case. Source,
model/audio hashes, full delivery, EOF and app/observer/paired replay all pass.
These are inspected regressions; callback markers are not verified word latency.
The local 32-case review is under `output/prefix-confirmation-regression-v2-2026-11-03/review/`.

The original prefix output directory retains an aborted first version: an extra
segmented-input check found prefix re-acquisition from older segment words. It
completed fourteen streams and interrupted the fifteenth. Final results exclude
that batch and preserve its artifacts/ABORTED.json. The corrected version adds
tests for that edge and for older-context revisions refreshing prefix age.

`run_prefix_confirmation_regression.py --stage prepare|preflight|run` uses the
complete shared-policy baseline captured before edits, the fixed local sources,
and the existing NeMo server on port 9097. `summarize_prefix_confirmation_regression.py`
creates the portable summary and local listening page. Saved replay imports each
complete matching stack in a separate process. `replay_policy_batch.py --prefix-evidence`
records actual prefix-vote uses, including already-working checkpoints, rather
than treating all helper calls as recovered effects. Fresh audio remains paced.

Current policy: supported story phrases from either voice count, including
positive coaching. The guarded split matcher retains explicit negation,
word-presence, normal alignment/confirmation and one-shot checks. The complete
old runtime is replayed in a separate process; 214 saved ledgers reproduce their
original outcomes before comparison. Eight effects are added on positive quoted
cases, with none lost; all 123 MPS readings remain unchanged. Seven provider
deletions and 24 unrelated comparisons stay off. The existing five close-word
emissions are subsequently user-accepted. Windows: 178 unit tests pass, one unchanged NeMo-only
test is skipped. [The completed shared-policy regression](results/shared-policy-regression-2026-11-03.json)
runs 31 fresh streams (18 shared, nine reviewed MPS, four unrelated), with all
ASR callbacks identical to the originals. Three coaching effects are added on
the same fresh callbacks with no losses or duplicates. Evaluating both versions
under the new policy gives 12 to 15 target goals met out of 18 shared cases, and
five to seven complete-effect goals met out of ten controlled cases. Long pause,
overlap and the one-confirmation coached hibernate case remain target misses.
All nine reviewed assertions pass; all three original omission cases stay off.
Four fresh unrelated timelines replay against six policies each with zero effects.
All transport/EOF/hash and app/observer/replay audits pass. These are inspected
regressions, not natural family reading, new-speaker or room validation. The
31-case listening review is local under `output/shared-policy-regression-2026-11-03/review/`.

`run_shared_policy_regression.py --stage prepare|preflight|run` and
`summarize_shared_policy_regression.py` preserve older reports. Preparation expects
the complete old `baseline-snapshot/` and `baseline.json` captured before editing;
for a repeat, copy those from the completed regression into a fresh output first.
Original local evaluation inputs/events and the unchanged model are also required.
`replay_policy_batch.py` imports the whole old matching stack from its snapshot
in a separate process. Fresh streams use the existing local NeMo server on port
9097. Positive quoted phrases now count; a composite that actually contains a
parent saying the formerly omitted word is not a literal-omission control.

Earlier pod-experience diagnostic: [shared-reading stress test](results/shared-reading-2026-11-03.json).
Eighteen inputs stream once each with frozen ASR/matcher/model/settings and no
book hints: ten controlled cases use two adult TTS voices; eight variants use two
previously inspected MPS children plus a synthetic adult. Composition recipes and
scripts are fixed before synthesis/recognition. All 540.26 seconds are delivered,
all streams produce interim text and EOF, and app/observer/replay agree.

Six of ten controlled cases meet all effect goals: baseline, handoff and handback,
parent finishing, repeated line, unrelated aside and coaching-only. Seven meet the
target-only goal. Long pause, coaching then reading, and overlap miss the target;
omission and overlap also miss the final effect. No target-negative case emits the
target, and no target emits before legitimate reading. Repetition produces no
duplicate effect. The long-pause ASR omits "a small"; overlap corrupts recognition.
Coaching has a separate state failure: a quoted target is suppressed but consumed,
so a subsequent exact legitimate reading cannot trigger it. This also loses two
baseline effects in the recorded sheep reading. The added lost_sheep emission has
no human correctness label. The bears aside/overlap lose clever_bears compared with
their fresh baseline. All four hibernate-source variants remain non-emitting;
three preserve literal omission, while one includes the word in quoted coaching.

These are constructed stress outcomes, not child accuracy or natural family/mic
validation. Every child sample is retained under common 0.4 gain; fixed midpoint
insertion can split a word, and equal-RMS overlay is digital mixing. The sheep
baseline has no emitted checkpoint after the midpoint, so its preserved effects
alone do not demonstrate interruption recovery. All 18 listening labels remain
blank under `output/shared-reading-2026-11-03/review/`. Runtime was unchanged
during that evaluation; the subsequent shared policy above accepts positive
coaching as reading. Interruption recovery remains open.

`run_shared_reading.py --stage prepare|compose|run` freezes scripts and sources,
assembles and hashes audio, then runs the paced app streams. Between prepare and
compose, run `powershell.exe -NoProfile -File benchmarks/synthesize_shared_reading.ps1
-OutputDirectory <output>`. Use the existing local NeMo server on port 9097 for run.
`summarize_shared_reading.py --output <output>` verifies completion/hashes and writes
the portable report plus local listening page/CSV. Choose a fresh `--output` for
new trials; existing composed files and streams are not overwritten. Source MPS
files and the frozen reference protocol/model must be available locally.

Latest regional diagnostic: [Singapore CHILDES streaming probe](results/childes-singapore-streaming-2026-11-02.json).
One complete 195.42-second classroom recording and its three existing context
clips run once each, with unchanged ASR/matcher/model/settings and no book hints.
The four streams are one source, three unique transcript-derived anchors and six
checkpoint opportunities. None emit; all six remain unreached. Full-source ASR
contains one exact target, "you draw on her left hand", but the matcher obtains
only one of two confirmations at callback 125.440 s. The next changed hypothesis
arrives 40.448 s later, after the 12-second evidence window. The first two context
clips return empty text; the third returns unrelated text. Post-evaluation user
listening to the wider full-source excerpts accepts the second and third targets,
confirming two full-stream false negatives. The first is unclear and remains
unresolved, without an omission label. User marks place the third target around
120.44–123.44 seconds in the source, before its original crop starts at 127.125:
that short crop has a timing problem. Other short crops are not separately
reviewed. Listening marks remain approximate; no population accuracy or verified
latency score is claimed. ASR and matcher stay unchanged after review.

All packets/EOF and app/observer/replay checks pass. The harness initially required
interim text even for an empty-text stream. A documented audit/resume amendment
retains the two already completed trials and streams only the remaining clips;
runtime/model/audio/manifests are untouched. Two streams produce interim text.
The same full-source ASR callbacks replay against six existing MPS passage
policies with zero effects; these are six replay comparisons, not additional
recordings or omission controls. Three CHAT parsing tests pass. Raw CHAT/audio,
ASR and the six-case listening review (three wider excerpts reviewed) remain local under
`output/childes-singapore-streaming-2026-11-02/`.

`run_childes_streaming.py --stage prepare|run` uses the existing local archive,
recording and selected clips, plus the frozen post-phonetic MPS protocol/model.
Choose a fresh `--output` for a new trial, prepare before recognition, start the
local NeMo server on port 9097, then run. `--stage resume` audits existing stream
artifacts and refuses to overwrite them; incomplete delivery still fails audit.
`summarize_childes_streaming.py --output <output>` verifies hashes, performs
off-book replay, and creates the portable summary and local listening page.
CHAT main-tier parsing excludes dependent morphology/alignment continuations,
preserves repetitions and negation, and removes annotation/unknown-span syntax.
These transcript-derived references describe conversation, without an independent
authored reading passage; no ASR/matcher tuning is performed.

Latest focused challenge: [45 full-stream synthetic adult cases](results/false-trigger-challenges-2026-11-02.json).
Five anchors each test correct reading, endpoint omission, close/distant wrong
words, quoted/negated prompts, unrelated continuation after an anchor prefix,
skipping and rereading. Every case uses offline Microsoft Zira speech and matched
constructed pauses, then the same real-paced app/ASR pipeline. All trials,
scripts, default/required observer policies and sources were frozen; no runtime
tuning or production-manifest edits occurred. All delivery, EOF, hash and
app/observer/replay checks pass.

Under the original strict-literal expectations, the default one-shot policy flags
all five close-word emissions, with the scripted variant present in ASR at the
trigger. The user subsequently accepted all five for the pod. Two already occur with
the previous matcher (coat/goat and seal/zeal); three are new (fan/van, pen/pin,
sink/zinc). All 30 other negatives stay off; all ten correct/reread cases emit
once without duplicates. The required-endpoint observer blocks these five
examples but can also reject valid ASR substitutions; it is not an automatic
fix: it rejects all five user-accepted examples. These are designed cases under
historical literal-word expectations, not child accuracy or population false-trigger
rates. The five-case audio review records the later user acceptance while
preserving original scripts, expectations, audio and observed outcomes.

`run_false_trigger_challenges.py` has `prepare`, `preflight`, `inventory` and
`run` stages. Use a fresh `--output`; local reference snapshots/model are needed.
After prepare, run `synthesize_challenges.ps1 -OutputDirectory <output>` and
inventory the generated WAVs. Preflight records constructed text diagnostics
separately from fresh audio trials. Run streams each case once; the summarizer
retains failures, compares the frozen prior matcher on the same ASR callbacks,
and creates the listening review. One failed setup before synthesis/ASR is
retained under the original output directory with an `ABORTED.json` marker;
the completed artifacts use `output/false-trigger-challenges-v2-2026-11-02`.

Latest frozen evaluation: [post-phonetic MPS speaker check](results/mps-heldout-phonetic-2026-11-02.json).
24 original-file streams from 12 unused IDs exclude all 57 prior IDs. Selection,
order, all runtime sources, model, lexicon, settings and manifests were frozen
before download. All trials completed once with full delivery and app/replay
agreement. Of 72 checkpoints, 64 emit, five are suppressed and three unreached.
All 46 provider-marked correct anchors emit. This batch has no provider-deleted
endpoints/essential words and adds no natural omission-control evidence. The
26-case listening queue is unlabelled. No ASR or matcher tuning occurred; these
are outcomes on six familiar texts, not a human accuracy or latency score.

Latest repair: [contextual phonetic-feature/progress regression](results/phonetic-feature-regression-2026-11-02.json).
A complete CMU phone-feature inventory supports bounded close-sound substitutions
under the existing exact-prefix, prior-progress and effect-permission guards.
Unique full phonetic anchors can supply local progress candidates; ordinary
scores, coverage, independent confirmations and required-word checks remain.
No word aliases, ASR changes, new hints, model changes or transcript replacements
are used. All 99 saved timelines add only the confirmed hundred_sheep effect,
with no losses and no emissions on seven provider-deletion controls. Nine fresh
reviewed readings add that same effect, from 18 to 19 of 27 checkpoints, with six
suppressed and two unreached. Their ASR timelines are identical to the saved
outputs; all three fresh omission assertions stay off. Four fresh unrelated
streams emit zero effects across 24 passage comparisons. Windows: 171 tests pass,
one unchanged NeMo-only test is skipped. These are inspected-data regressions;
close intentional word substitutions remain a limitation of lexical matching.

`run_phonetic_feature_regression.py --stage prepare|preflight|run` freezes the
current sources and unchanged recordings, verifies all 99 previous ledgers, then
runs the nine asserted readings and four unrelated controls. Its old matcher
loads the frozen old phonetic helper as well as permission and progress code.
The summarizer verifies delivery, hashes, assertions, callback agreement and
source-audio listening notes without rewriting earlier evaluation results.

Earlier frozen evaluation: [post-pending MPS speaker check](results/mps-heldout-pending-2026-11-02.json).
24 fresh real-paced streams from 12 new IDs exclude all 45 previously used IDs.
Selection, order, model, full pipeline, lexicon, settings and 72 checkpoints were
frozen before download. All trials completed once with full audio delivery,
unchanged hashes and app/audit agreement. Outcomes: 64 emitted, five suppressed,
three unreached. Of 40 provider-correct anchors, 39 emit; user listening confirms
the remaining hundred_sheep reading should emit. ASR retains "hundred chip",
which fails the existing endpoint checks. The approximate 0:10 excerpt endpoint
maps to 11.36 seconds in the original, without verified word alignment. The one
provider-deleted endpoint remains unreached and non-emitting. No pending
decisions were observed. Existing unrelated ASR callbacks replay to zero effects
in 24 comparisons. The local queue has 33 flagged cases, one with user confirmation. No ASR or
matcher tuning occurred. This holds out speakers on six familiar passages;
counts do not establish effect accuracy or real microphone performance.

Earlier repair: [general pending-effect regression](results/pending-regression-2026-11-02.json).
The matcher can briefly keep a locally acquired, exact-prefix endpoint pending
while ASR resolves an unfinished word. Existing permission rules still require
supported content; ASR, word matching, model and thresholds stay unchanged.
All 75 saved streaming timelines compare both matcher versions, adding only
the confirmed restart and losing no effects. All six replay omission controls
stay off. Thirty-one fresh matched streams add that same one effect, increasing
emissions from 76 to 77; 12 are suppressed and four unreached. All five fresh
omission cases remain non-emitting. Four fresh unrelated streams emit zero
effects across 24 passage comparisons. Windows: 163 unit tests pass, one
unchanged NeMo-only test is skipped. These are inspected-data regressions.

`run_pending_regression.py` has prepare, preflight and run stages. It freezes
source/manifests and the 75 recorded ASR timelines, verifies previous live ledgers,
then runs the latest 24 readings plus seven reviewed cases and four unrelated
controls once each. Use a new `--output` for another run. The summarizer verifies
completion, omission assertions, pending outcomes, hashes and live-app agreement,
and creates listening context without changing the historical source results.

Earlier frozen evaluation: [post-EOF MPS speaker check](results/mps-heldout-eos-2026-11-02.json).
24 fresh real-paced streams from 12 new speaker IDs exclude all 33 previously
used IDs. The complete repaired pipeline, model, settings, 72 checkpoints,
selection and order were frozen before audio download. All trials completed
once with full delivery and unchanged hashes. Outcomes: 62 emitted, seven
suppressed and three unreached. One of 42 provider-correct anchors does not
emit; user listening confirms a false negative on an ene-enemies restart. The
then-current matcher permanently suppresses intermediate enemy before ASR returns
the full enemy enemies, which would pass the permission rule. That batch's source
snapshot remains frozen. Both provider-deleted endpoints remain unreached and non-emitting. The
local review queue has 31 flagged cases, one with a user label.
Existing repaired-ASR control callbacks emit zero effects in 24 replay
comparisons. Both replay ledgers use the same matcher and are agreement audits.
No ASR/matcher tuning or sample replacement occurred. These operational counts
on six familiar passages are not accuracy, new-book or microphone results.

Earlier EOF repair: [general NeMo end-of-stream regression](results/eos-regression-2026-11-02.json).
51 fresh original-file streams and four fresh unrelated controls keep the matcher,
model weights, hints, thresholds and all 153 checkpoints unchanged. Finalization
uses full chunk/right context and caps decoding at the real remaining frames;
padding adds no client time or matcher callbacks. All 51 pre-EOF transcripts match
the earlier runs. Effects increase from 126 to 128, with 18 suppressed, seven
unreached and none lost. Wing now emits; the user confirms the second added paws
effect is correct. Both additions have listening notes, with the wing endpoint's
soft/possibly cut-off qualification retained. All four omission controls remain non-emitting, including
both user-confirmed omissions. Unrelated audio emits zero effects across 24
passage comparisons. Windows passes 152 unit tests; the one NeMo-only test passes
separately in WSL. These are inspected-data regressions, not new held-out scores.

`run_eos_regression.py --stage prepare` copies existing manifests and freezes
sources, original audio hashes, model, lexicon, order and saved baseline callbacks.
Its run stage freshly streams all 55 files, verifies real-duration completion and
compares original/repaired ASR through the identical matcher. Use a new `--output`
directory for another run. `summarize_eos_regression.py` checks the completed batch
and creates the portable report plus local listening clips. Added effects remain
review candidates, and historical held-out reports are preserved.

Latest diagnostic: [original audio versus two seconds of trailing silence](results/mps-tail-silence-2026-11-02.json).
Two fresh real-paced streams reproduce the unpadded wing miss and recover the
word plus damaged_wing after adding two seconds of digital silence. All original
speech samples, matcher, recognizer settings and model hashes are unchanged;
both streams pass full delivery and app/audit checks. The result supports
trailing-context/end-of-stream sensitivity without identifying the precise cause.
This inspected-recording diagnostic leaves the held-out results below unchanged.

Latest speaker test: [untuned post-split MPS speaker test](results/mps-heldout-split-word-2026-11-02.json):
24 fresh real-paced streams, 12 new speaker IDs, all 21 prior IDs excluded,
16m43s audio and 72 frozen checkpoints. Sources, model, lexicon and settings
remain unchanged from the completed split-word regression. Both guards emit
63 effects, suppress five and leave four unreached; no added/lost emissions or
new split-word recoveries were observed. One of 47 provider-correct anchors
does not emit. The user hears the damaged_wing phrase but subsequently qualifies
wing as soft and possibly cut off, so the earlier clean false-negative label is
qualified. The final ASR omits wing and tracker progress stops at 79/80. The full
provider WAV was streamed; the listening excerpt preserves its ending exactly.
The underlying
recognition/end-of-stream cause remains unverified; matcher code stays frozen.
The one provider-deleted endpoint remains unreached, with no effect. The 26-case
local listening queue has one user label. Saved unrelated ASR replay emits zero effects in 24 comparisons.
No matcher tuning or outcome-dependent sample changes occurred. The test holds
out speakers on the same six familiar passages; these are not accuracy scores.

For subsequent batches, give `run_mps_heldout.py` a new `--output` directory and
the intended `--baseline-snapshot` at prepare time. Selection excludes speaker
IDs from earlier local results. Pass the completed reference sweep's protocol
to `summarize_mps_heldout.py --reference-protocol`; portable result names follow
the output directory name, preserving earlier reports. The current batch's one
socket-permission startup failure delivered no audio and is archived separately;
each recording has exactly one completed streaming trial.

Previous: [general split-word regression](results/split-word-regression-2026-11-02.json):
27 fresh application streams compare the pre-split guard and repaired matcher
on identical ASR callbacks. Exact full-anchor matching permits each authored
word to consume one or two adjacent ASR tokens, without word-specific aliases
or transcript rewriting. Existing local acquisition, prompt and independent
confirmation guards remain. A complete unique next anchor can reach a split
endpoint without waiting for another sentence. Of 81 checkpoints, 63 emit
versus 62 before; riverside is the only addition and none are lost. Both
human-confirmed omissions and the separate annotated hibernate omission stay
suppressed; scales still emits. Four fresh unrelated streams produce zero effects
in 24 passage comparisons. All 31 streams pass delivery and integrity checks;
all 150 unit tests pass. The previous 24 MPS
recordings and three reviewed cases are regression coverage, not a new held-out
evaluation.

`run_split_word_regression.py` prepares a fresh output directory, freezes source,
model, lexicon and existing manifests, then streams the fixed 27-reading order
and four unrelated controls. `summarize_split_word_regression.py` checks completion,
delivery and hashes before writing the portable report. The initial interrupted
12-reading run is retained separately with its reason; the completed rerun uses
the final repair, including the generic end-of-audio regression test.

Earlier: [untuned held-out-speaker MPS evaluation](results/mps-heldout-2026-11-02.json):
24 fresh app streams from 12 new speaker IDs, balanced across Grades 3–5 and
provider gender labels. Matcher/model/lexicon hashes, six familiar passages,
72 checkpoints, settings, selection seed and trial order were frozen before
audio download. All trials were retained: both guards emit 56 effects, with
12 suppressed and four unreached. The phonetic fallback accepts none of its
four candidate comparisons; no improvement or changed effect decisions were
observed on this batch. Post-evaluation user listening confirms the riverside
suppression as a false negative caused by the recognized river side token split.
That evaluation's source snapshot remains frozen; other listening labels and exact word timings are
still unverified.

`run_mps_heldout.py` has separate prepare, download and run stages; it requires
pinned MPS metadata, the pre-phonetic source snapshot, and the documented NeMo
server. Use `--metadata`, `--baseline-snapshot` and a fresh `--output` as needed.
`summarize_mps_heldout.py` verifies the completed batch and creates the portable
summary plus local context audio and blank review CSV. Raw data stay in ignored
`output/`. Provider miscues are review evidence, not effect-accuracy gold.

Earlier: [guarded effect and timing evaluation](GUARDED_PILOT_RESULTS.md), 21
fresh reading streams plus four unrelated-speech streams. Suppressed effects
are reported separately from emitted and unreached checkpoints.

The [2 November additional-reader evaluation](READING_EXPANSION_RESULTS.md)
adds 12 Indian recordings, original passages, 36 frozen checkpoints, fresh
application streams and controls, with provisional endpoint review files.

For the current application pilot, see [setups and tradeoffs](../docs/SETUPS.md)
and [the fresh post-reorganization results](BEST_SETUP_RESULTS.md).
`run_best_setup.py` repeats that pilot through the actual client and WebSocket
server; the older `run.py` profiles below use a separate benchmark harness.

These scripts compare the existing Whisper base.en, small.en and medium.en GPU
setup with Parakeet Unified and Moonshine Streaming Medium. They are separate
from the reading application: the ASR server/client and matcher are unchanged.
Nemotron is a possible later test and is not downloaded by this benchmark.

The supplied samples include the 33-second Little Mermaid recording (two
checkpoints), 93-second Tea recording (three) and 57-second Fat Cat recording
(two). Each has its matching passage and manifest. Audible misreads, stutters,
prompting or omissions are not independently transcribed; these can affect WER.
The current runner is streaming only. Earlier results in `little-mermaid` and
`tea` came from a version that also performed whole-file warmup/diagnostic passes.
Those results remain separate from the fresh `*-streaming` runs.

## Comparison with the reading application

The benchmark is a separate streaming runner, rather than an exact replay through
`books_to_life/cli/run_client.py` and its WebSocket server. Whisper uses the same backend, VAD
settings, three-repeat segment threshold, BookContext and AlignmentMatcher, but
the runner feeds 64 ms audio packets and requests the last 100 transcript segments.
The application's default file playback feeds 256 ms packets and requests the
last 10 segments. The application also filters adjacent repeated transcript text
in its callback, while the benchmark joins the backend snapshot directly.

The benchmark adds 1.5 seconds of silence and a two-second Whisper settling wait.
The file client waits for pending responses before disconnecting. Delivery and
callback differences can change partial transcripts, checkpoint confirmation and
when book hints refresh. Their effect has not been isolated in a matched test.
These scores measure the benchmark configuration. Use recorded-file and microphone
tests through the actual application to evaluate its deployed behavior.

## Prepare on the current Windows PC

Use the existing `.venv` and start Docker Desktop. The existing
`books-to-life-asr-gpu:local` image and `speech-to-text_gpu-model-cache` volume
must contain base.en, small.en and medium.en. No new Docker image is built.

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps --no-cache-dir --target model-cache\asr-benchmark\moonshine-python moonshine-voice==0.1.5 sounddevice==0.5.2 google-crc32c==1.7.1
.\.venv\Scripts\python.exe benchmarks\prepare.py --official-moonshine
.\.venv\Scripts\python.exe benchmarks\run.py --resume
```

The native package uses the existing environment's numpy, requests, tqdm,
filelock, platformdirs and cffi. If these are absent, install only those small
dependencies into the isolated target directory. Do not install training extras.

All new model/runtime files live under the ignored `model-cache/asr-benchmark`
directory. The current prepared cache is about 2.15 GB. Preparation requires
8 GiB free before starting, pins the C++ models and checks their SHA-256 hashes,
and checks the official Moonshine model's declared 269 MB size and checksums.
Whisper's model volume is mounted read-only. No microphone or speaker is opened.

## What runs

- Whisper base.en/small.en/medium.en, CUDA float16: hints off and live hints on.
  This reuses the actual WhisperLive backend, its VAD and segment confirmation.
  An in-process socket captures updates, excluding WebSocket transport latency.
- Parakeet Unified F16, RTX 4060 through Vulkan: audio buffering settings of
  320 ms, 1.12 s and 2.08 s. These are audio waits, not disk budgets. Its C++
  runtime has no phrase hints, and retains a 5.6-second left-context window.
- Moonshine Streaming Medium F16, RTX 4060 through Vulkan, hints off.
  Both the native decoding cadence and an explicit 500 ms minimum decode
  interval are tested; input still arrives in 64 ms packets.
- The same Moonshine model family through its official Windows runtime,
  published quantized ORT files and CPU: hints off and hints on. The latter uses
  `set_context()` and `set_keyterms()` following the same BookContext selection.
  This is a different runtime/precision/device and is labelled separately.
  Default CPU threading and `MOONSHINE_ORT_SINGLE_THREAD=1` are tested separately.

Each profile loads its model before timing begins, then receives the recording
once, at the original audio speed, in 64 ms input packets. There is no whole-file
recognition pass, recognition warmup or automatic timing-reference pass.
The stream includes 1.5 seconds of trailing silence to flush the last words.
Whisper also gets two seconds to settle its final segment. Profiles run
sequentially. No audio is dropped when inference falls behind; maximum feed
lateness and total stream duration are recorded. Feed lateness measures whether
the input falls behind real time, not delay from a spoken checkpoint to an effect.

Every profile passes its actual transcript updates to the same unchanged
AlignmentMatcher. Changed snapshots replace previous text, avoiding duplicated
words caused by concatenating revisions. Streams keep listening after effects.

## Results and limitations

Read `output/benchmarks/tea-streaming/report.md`, `fat-cat-streaming/report.md`,
and their `results.csv` and `results.json` files. Each profile also saves its complete transcript/update timeline
and a log. WER ignores punctuation/case and normalizes common contractions.
It compares words to the supplied passage, not pronunciation quality.

Checkpoint counts describe triggers/skips in this replay. They do not establish
a false-trigger rate: separate off-book conversations and negative recordings
are needed. Exact checkpoint-delay ground truth also needs someone to mark the
end of each anchor in the audio. Missing endpoints produce unavailable delay
values and early-trigger counts, not fabricated ones. The reports still record
the exact stream-relative arrival time of each confirming ASR update.
The clock marks arrival of the ASR update used to confirm a checkpoint, before
matcher computation. It excludes microphone, WebSocket transport and physical
effect playback. It is not a measured speaker/projector response time.
Invalid ASR timestamp updates remain visible in the result files and ASR word
scoring. They cannot advance the unchanged checkpoint matcher. The recorder
reports their count separately instead of quietly treating them as good updates.

To supply verified anchor-end times, create `manual-checkpoint-times.json` in the
result directory with checkpoint IDs mapped to seconds, then update the report:

```powershell
.\.venv\Scripts\python.exe benchmarks\run.py --summarize-only
```

The Tea/Fat Cat results now have user-supplied whole-second listening marks:
Tea pot 20 s, stove 54 s, house 77 s; Fat Cat hat 53 s, first anchor skipped.
`manual-checkpoint-annotations.json` records their source, input hashes,
whole-second precision and explicitly skipped checkpoint IDs. A skipped anchor
has no spoken endpoint and no delay. Its activation may reflect scene catch-up
and is reported separately from direct detection of a spoken phrase.

Refresh these summaries without any recognition replay, then generate the
combined listening-mark report:

```powershell
.\.venv\Scripts\python.exe benchmarks\run.py --audio recordings/library/stories/tea/readers/tea/audio.wav --manifest recordings/library/stories/tea/readers/tea/checkpoints.json --output output\benchmarks\tea-streaming --summarize-only
.\.venv\Scripts\python.exe benchmarks\run.py --audio recordings/library/stories/fat_cat/readers/fat_cat/audio.wav --manifest recordings/library/stories/fat_cat/readers/fat_cat/checkpoints.json --output output\benchmarks\fat-cat-streaming --summarize-only
.\.venv\Scripts\python.exe benchmarks\checkpoint_latency.py --manual
```

Read `output/benchmarks/checkpoint-delays-manual.md` and its JSON companion.
These listening marks supersede the separate provisional ASR estimates for
these recordings; they do not establish subsecond endpoint accuracy.

For a separate **provisional** timing check of the Tea and Fat Cat fixtures,
the native streaming runtime can save token-aligned word times. These are ASR
estimates, not listening verification. No whole-file recognition, warmup,
model download or replay of all benchmark profiles is involved:

```powershell
.\.venv\Scripts\python.exe benchmarks\stream_timing.py --audio recordings/library/stories/tea/readers/tea/audio.wav --output output\benchmarks\tea-streaming\timing-reference-streaming-estimated.json
.\.venv\Scripts\python.exe benchmarks\stream_timing.py --audio recordings/library/stories/fat_cat/readers/fat_cat/audio.wav --output output\benchmarks\fat-cat-streaming\timing-reference-streaming-estimated.json
.\.venv\Scripts\python.exe benchmarks\checkpoint_latency.py
```

Read `output/benchmarks/checkpoint-delay-estimates.md` and its JSON companion.
The comparison checks input hashes and subtracts the same provisional phrase
ending from each saved profile's trigger time. Negative delays suggest early
firing; repeated or misheard words can still make these estimates incorrect.
The Tea stove/house endpoints match recognized phrase endings rather than exact
full anchors and require listening verification. Fat Cat's first exact anchor
is absent from the reference transcript, so its endpoint remains unavailable;
this does not establish that the child skipped it. The final Hat anchor matches
except its leading article. Verified reports and `manual-checkpoint-times.json`
are not changed by either script.

Run one profile or another supplied recording/manifest:

```powershell
.\.venv\Scripts\python.exe benchmarks\run.py --profiles parakeet-320ms parakeet-1120ms parakeet-2080ms --resume
.\.venv\Scripts\python.exe benchmarks\run.py --audio recordings/library/stories/horse/readers/horse/audio.wav --manifest recordings/library/stories/horse/readers/horse/checkpoints.json --output output\benchmarks\horse --resume
.\.venv\Scripts\python.exe benchmarks\run.py --audio recordings/library/stories/tea/readers/tea/audio.wav --manifest recordings/library/stories/tea/readers/tea/checkpoints.json --output output\benchmarks\tea-streaming --profile-timeout 900 --resume
.\.venv\Scripts\python.exe benchmarks\run.py --audio recordings/library/stories/fat_cat/readers/fat_cat/audio.wav --manifest recordings/library/stories/fat_cat/readers/fat_cat/checkpoints.json --output output\benchmarks\fat-cat-streaming --profile-timeout 900 --resume
```

`--resume` only reuses outputs whose input hashes, model, backend, hint setting,
buffering setting and streaming-only protocol match. Old warmed-up runs cannot
be resumed by the current runner. Streaming currently has one repeat. This is a laptop benchmark,
not evidence of Jetson or Raspberry Pi performance.
`--profile-timeout` allows longer recordings to finish loading and real-paced
replay. It defaults to 240 seconds per profile and does not
change audio buffering or recognition settings. Tea's supplied reference includes
the apparent typo "He a sang a little"; the benchmark retains the supplied text.

The cache can be removed when no benchmark worker is running. It contains only
these additional benchmark assets; preserve the original Whisper model volume.
