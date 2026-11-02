# Benchmark child-reading recognition

Latest focused challenge: [45 full-stream synthetic adult cases](results/false-trigger-challenges-2026-11-02.json).
Five anchors each test correct reading, endpoint omission, close/distant wrong
words, quoted/negated prompts, unrelated continuation after an anchor prefix,
skipping and rereading. Every case uses offline Microsoft Zira speech and matched
constructed pauses, then the same real-paced app/ASR pipeline. All trials,
scripts, default/required observer policies and sources were frozen; no runtime
tuning or production-manifest edits occurred. All delivery, EOF, hash and
app/observer/replay checks pass.

The default one-shot policy falsely emits on all five close wrong words with
the scripted wrong phrase present in ASR at the trigger. Two already occur with
the previous matcher (coat/goat and seal/zeal); three are new (fan/van, pen/pin,
sink/zinc). All 30 other negatives stay off; all ten correct/reread cases emit
once without duplicates. The required-endpoint observer blocks these five
examples but can also reject valid ASR substitutions; it is not an automatic
fix. These are designed counterexamples under literal-word expectations, not
child accuracy or population false-trigger rates. The five-case audio review
keeps human labels blank.

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
