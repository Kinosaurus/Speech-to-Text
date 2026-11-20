# Verbatim references and word-ending review

Open the local reviewer at **http://127.0.0.1:8766**. It starts silent, without
autoplay or microphone access. Enable sound and press Play only when ready.
The Reading Pod panel remains on 8765; this reference editor is separate.

## Estimated comparison using provisional drafts

The page also shows a clearly labelled **ESTIMATED** table using the current
separate offline Whisper Small English drafts and their automatic word endings.
The same draft is used for every candidate on each recording; references are not
picked to minimize a candidate's errors. The Small model is outside this six-profile
comparison, but shared Whisper-family errors can still bias Tiny/Base comparisons.
Draft quality and word-ending precision are unverified.

The main estimated table uses only recordings all six configurations completed
(currently Mermaid). Its median and P95 compare the same correctly and
unambiguously timed word IDs across all configurations. The coverage column shows
each model's own matched words. Missing words have no fabricated delay; zero-duration
draft timings are excluded from latency without deleting the words from WER.
Per-recording estimated WER and full-corpus estimates are shown separately, with
incomplete trials explicitly retained.

Provisional scoring does **not** write review approvals or fill the listening-verified
columns. It reuses saved benchmark outputs without recognition, microphone capture
or playback. The separate listening-verified table stays pending until reviewed.

Estimated exports in the local project folder are `estimated-comparison.md`,
`estimated-comparison.csv` and `estimated-comparison.json`. JSON records fixed
reference text/timing hashes, the draft model identity and every word-arrival match.
No listening verification or numeric timestamp error bound is implied.

## What is prepared

Tea, Fat Cat and Little Mermaid have **ASR-assisted draft transcripts and word-time
proposals**, produced locally with a separate Whisper Small English CUDA model.
The recognizer received no book text, hints or prompt. Alternate Parakeet drafts
are shown where saved estimates have the identical audio hash. Waveform envelopes
have 5 ms spacing; this does not establish 5 ms annotation accuracy.

These drafts are **not human-verified verbatim references**. Multiple recognizers
can omit the same speech or agree on the same incorrect word. This tool session
cannot independently listen to the recordings, so it does not claim that machine
transcripts or boundaries were heard and verified. No genuine benchmark reference
has been approved automatically. Synthetic unit-test approvals only exist in
temporary fixture directories.

The current local review project is:

`output/asr-only-reference-review/20261119-01`

Original draft JSON, word proposals, alternate hypotheses, waveform data and all
subsequent review backups remain local. Original recordings, supplied book passages
and the frozen recognition benchmark are not rewritten.

## Review each recording

1. Listen to the complete original recording. Preserve what was actually said:
   repetitions, fillers, misreadings, partial words and intelligible speech from
   other voices. Do not repair the wording to match the printed book. Check for
   words the draft omitted. Use one spoken word per row; put non-speech events
   and uncertainty explanations in notes. Unresolved `[unclear]` words can be saved
   in a draft but cannot establish full-recording WER.
2. Correct, insert or remove word rows and check **Text checked** as each word is
   reviewed. Enter the human reviewer name and confirm that the whole recording
   was checked. **Approve reviewed transcript** records a content hash and date.
3. Select a word, use the waveform and context playback, and adjust its start/end
   fields or drag its markers. Mark the acoustic end of the spoken word rather
   than a trailing silence. Review pauses, coarticulation, partial words and
   adjacent voices carefully. Mark **Boundary checked** after review, and declare
   estimated boundary uncertainty, for example ±0.10 s only if justified.
4. **Approve reviewed boundaries** is available after transcript review. Editing
   wording invalidates text/timing approvals; editing times invalidates timing
   approval. Stale revisions cannot overwrite another window's saved edits.

Saving a draft never makes it ground truth. Every approval is explicitly attributed
to the person who reviewed the audio. Before approval, actual WER and word-latency
columns display **Pending review**.

## Comparison table and method

The table re-scores the already recorded ASR hypotheses and callback timelines.
It does not rerun recognition or allow a model to use the reviewed transcript as
a prompt. Failed/incomplete recognition trials remain reported separately.

| Measurement | Reference | How it is compared |
|---|---|---|
| Actual word error rate | Reviewed words actually spoken | `(substitutions + deletions + insertions) / reference tokens`; same fixed case/punctuation/contraction normalization for every model |
| Per-recording WER | Reviewed text for that recording | Each completed model result is scored separately; incomplete trials have no fabricated full-recording WER |
| Comparable WER table | Same reviewed recordings completed by every configuration | Currently Mermaid is the only shared complete recording; this is a post-selected development subset, not a held-out ranking |
| Full-corpus WER | All three reviewed spoken references | Published only for configurations which completed all three; never mix two-file and three-file averages |
| First correct word availability | Reviewed word end and callback wall clock | First exact, unambiguous token alignment after recognition; no fuzzy credit, checkpoint rules or book tracker |
| Stable correct word availability | Same word end and subsequent callbacks | Arrival when the correct alignment stays present through the final snapshot |
| Delay | Reviewed end relative to original recording start | `callback arrival − acoustic word end`; retain signed values, including early predictions |
| Coverage | All eligible reviewed words | Count timed exact words, missing words and ambiguous repeated-word alignments; do not silently discard failures |
| Same-word timing | Word IDs correctly and unambiguously timed by every configuration | Compare medians on the same exact words; do not let a model look faster merely by missing difficult words |
| P95 | At least 20 observed word delays | Nearest-rank sample P95; unavailable for smaller counts; not a population confidence claim |

The offline evaluation aligns each full transcript snapshot to the reviewed words
whose audio has begun arriving. It keeps only exact token pairs shared by **every**
minimum-edit alignment; ambiguous repeated words receive no invented identity.
Future words from undelivered audio cannot receive timing credit. Contractions
may normalize to several tokens; one orthographic word retains one reviewed end.
These are evaluation alignments, not runtime reading progress or effect decisions.

Word-end uncertainty and matched-word coverage accompany the results. Microphone,
OSC, projector and speaker latency are outside this test. First text after file
start and input-delivery backlog remain separate measurements.

Exports update locally as reviews are saved:

- `reviewed-comparison.md`: table and method summary.
- `reviewed-comparison.csv`: model-level metrics.
- `reviewed-comparison.json`: approvals, per-case scores, edit counts and word-arrival ledgers.

## Start or prepare again

### Full supplied-text NeMo and the combined table

The reviewer also displays `all-models.json` from its configured
`book_comparison_run`. The combined table includes KeenASR, NeMo without hints,
NeMo with checkpoint hints, NeMo with all supplied printed text, and the previously
tested Whisper, native Parakeet and Moonshine CPU/GPU configurations. Incomplete
and unrun files stay visible. The shared-file WER and same-word timing columns use
the same recordings and word occurrences; all-three-file WER is separate.

The full-text NeMo trial uses exactly the `keen_book_text` saved for Keen, split
at sentence/line boundaries into phrases of at most 200 characters, within the
server's 32-phrase limit. Every normalized printed word must be retained, or the
trial is rejected. This is all available printed text for each benchmark excerpt,
not missing pages from an entire published book. NeMo's boost stays 1.0. A boosted
phrase vocabulary and Keen's oral-reading graph remain different mechanisms.

The new trial is under `output/asr-only/20261119-nemo-full-book`; the earlier Keen
and checkpoint-hint trials were copied unchanged with provenance, not rerun.
To regenerate reports from the saved local callbacks, without playback or ASR:

```powershell
& $python -m benchmarks.compare_book_asr report `
  --output output/asr-only/20261119-nemo-full-book
& $python -m benchmarks.combine_asr_trials `
  --book-run output/asr-only/20261119-nemo-full-book `
  --queued-run output/asr-only/20261119-queued-01 `
  --cpu-run output/asr-only/20261119-baseline-02
```

`all-models.md`, `.csv` and `.json` preserve the combined comparison and per-file
statuses. Earlier CPU Whisper trials used inline delivery; the table labels this
because buffering and delivery are part of the tested configuration. These remain
estimated scores against frozen unverified drafts. Cue counts use offline replay
of the same matcher and exclude projection/sound hardware.

### Local service

### Full-text boost sweep

`benchmarks.sweep_nemo_boost` tests boosts 0, 0.5, 1, 2, 3 and 5 on each of the
same three recordings. All 18 trials replay the original audio at 1x speed with
queued input and no audio output. Trial order rotates by recording. The dedicated
`benchmarks.nemo_boost_server` reuses one resident NeMo model and returns the actual
applied session boost and full-hint hash with SERVER_READY. The client refuses to
start audio if either acknowledgement differs from its request. Production server
defaults and shared matcher rules are unchanged.

The sweep files are under `output/asr-only/20261119-nemo-boost-sweep`:

- `boost-comparison.md`, `.csv` and `.json`: all-three-file estimates on the same
  correctly aligned word occurrences, plus per-checkpoint callback times.
- `nemo-full-boost-<level>--<recording>.json` and `.events.jsonl`: exact text, boost
  acknowledgements, full-delivery evidence and original callback timelines.
- `provenance.json`: audio protocol, code/model hashes and order/variation caveats.
- `canva-asr-tables.html`: aggregate-only editable tables for Canva import, using
  the supplied slide's cream, blue, navy, green and red palette.
- `canva-boost-table.tsv`: values for pasting into a native Canva table.

Regenerate the result and presentation artifacts from the saved trials:

```powershell
& $python -m benchmarks.sweep_nemo_boost report `
  --output output/asr-only/20261119-nemo-boost-sweep
& $python -m benchmarks.combine_asr_trials `
  --book-run output/asr-only/20261119-nemo-full-book `
  --queued-run output/asr-only/20261119-queued-01 `
  --cpu-run output/asr-only/20261119-baseline-02 `
  --sweep-run output/asr-only/20261119-nemo-boost-sweep
& $python -m benchmarks.export_asr_slides `
  --sweep output/asr-only/20261119-nemo-boost-sweep `
  --all-models output/asr-only/20261119-nemo-full-book/all-models.json
```

This is a development sweep with one replay per level/recording, not a held-out
validation or a precise latency ranking. Checkpoint firing counts alone do not
establish correct timing or rule out false activations. One configured Fat Cat
anchor was reportedly skipped. The UI separately shows each cue callback time.
Only aggregate tables are supplied to Canva. Recordings and transcripts stay local.

### Launch the local service

```powershell
Set-Location 'C:\Users\heart\Speech-to-Text\output\reading-pod-first-pipeline'
$python = 'C:\Users\heart\Speech-to-Text\.venv\Scripts\python.exe'
& $python -m benchmarks.asr_reference_review `
  --project output/asr-only-reference-review/20261119-01 --port 8766
```

To create a new automatic draft set, use a fresh output directory:

```powershell
& $python -m benchmarks.prepare_asr_annotations `
  --run output/asr-only/20261119-baseline-04 `
  --output output/asr-only-reference-review/new-draft `
  --cache C:/Users/heart/Speech-to-Text/model-cache/asr-benchmark
```

Only model weights are downloaded when absent; audio is never uploaded. Existing
draft/review files are not overwritten. The comparison requires no new model run
after a human corrects the transcript or boundaries.
