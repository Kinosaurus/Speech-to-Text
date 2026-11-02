# Books to Life Pod: current flow, handover and verification

Singapore CHILDES access inspection, 2 November: the user-downloaded archive
passes ZIP integrity checks and contains 168 CHAT transcripts. One matching
recording, e5d6a.mp3 (195.42 seconds), decodes successfully; three contextual
16 kHz mono clips and a blank listening sheet are prepared locally under
`output/childes-singapore-2026-11-02/`. This is classroom conversation with
transcripts of actual speech; an independent intended reading passage is absent.
Use it for separately labelled regional ASR/streaming diagnostics after listening
review. No Singapore streaming trials or human speech-quality labels are recorded
yet. The local archive/audio remain Git-ignored; the initial truncated audio
download is retained as a failed artifact. Access to the published Singapore
children's English reading corpus has not been obtained.

Known close-word false-trigger risk, 2 November: [45 frozen synthetic adult-speech challenges](../benchmarks/results/false-trigger-challenges-2026-11-02.json)
test five anchors across correct readings, omissions, close/distant wrong words,
quoted/negated prompts, unrelated continuations, skips and rereading. The current
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
all trials remain unchanged. Actual child pronunciation acceptance versus wrong-word
rejection needs an explicit policy and evidence beyond one ASR text hypothesis.
The five-case listening review has blank human labels. Resolve this risk before
treating the successful speaker check below as proof of precise event detection.

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
- [ ] Test parent prompts, quoted story sentences, negation, similar off-book
      wording and two speakers. An adult reading the expected sentence may look
      identical to child reading to this text-only tracker.
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
