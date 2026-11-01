# Additional child-reading evaluation

Current implementation follow-up: [guarded effect reruns](GUARDED_PILOT_RESULTS.md).
The 35/36 counts below describe the earlier, pre-guard emission behavior.

Follow-up: [the 17-case evidence review](FLAGGED_READING_REVIEW.md) identifies
two triggers without important anchor words in the annotated/recognized speech,
and a reproduced alignment-ranking delay. No auditory sign-off was performed;
35/36 activations must not be interpreted as 35 correct effects.

Date: 2 November 2026. **Twelve new recordings, six new reader IDs, 36 fixed checkpoints. The current tracker activated 35/36 configured checkpoints; four unrelated streams produced zero triggers in 16 audio/passage comparisons.**

**These children are from India, not Singapore or Southeast Asia.** Regional sources were investigated first; the user approved the Indian fallback. See [regional source findings](../docs/CHILD_READING_DATA.md). No Southeast Asian child-reading validation is claimed.

## Data and frozen protocol

- MPS Grade 4 Bears and Grade 5 Butterflies; three new speakers per grade, two original paragraph WAVs per speaker. Three female and three male speaker IDs. Individual ages are not supplied.
- 519.91 seconds of real audio (8 minutes 40 seconds), four paragraph passages from two additional texts. Full provider story text is preserved separately; two paragraph recordings were not joined to imply one continuous reading.
- Provider original promptText and manualTranscript are separate. Word-level miscue labels are preserved. Checkpoints use unique, ordered original-passage word ranges, not phrases rewritten to match ASR.
- Selection used fixed seed 20261102, sorted paired-paragraph candidates, and speaker IDs disjoint from the earlier three-reader MPS subset. No selection by reading score, recognition, duration, or checkpoint success. Every selected recording is retained.
- Selection IDs and anchors were frozen before decoding selected audio. The provider repository revision and audio/metadata/manifest hashes are saved. Every ideal-text checkpoint test passed before actual audio testing.
- Same pilot: WSL NeMo Parakeet Unified 0.6B, RTX 3070 Ti CUDA bfloat16, 560 ms chunk/right context, 5.6 s left history; Windows client split mode (TimelyEvidenceMatcher), no book hints; threshold 82, stability 2, min coverage 0.8.
- One fresh paced application stream per WAV, 16 kHz mono, 4096-sample packets. No separate inference warmup, model tuning, threshold adjustment, or anchor revision. Full source snapshots remained unchanged during streaming.

## Reading results

| Recording | Grade | Current activations / configured | Missing IDs |
| --- | ---: | ---: | --- |
| 4a18f_EN-OL-RC-426_1 | 4 | 3/3 | None |
| 4a18f_EN-OL-RC-426_2 | 4 | 3/3 | None |
| 4b25a_EN-OL-RC-426_1 | 4 | 3/3 | None |
| 4b25a_EN-OL-RC-426_2 | 4 | 3/3 | None |
| 4a35g_EN-OL-RC-426_1 | 4 | 3/3 | None |
| 4a35g_EN-OL-RC-426_2 | 4 | 2/3 | begging_paws |
| 5a28c_EN-OL-RC-538_1 | 5 | 3/3 | None |
| 5a28c_EN-OL-RC-538_2 | 5 | 3/3 | None |
| 5b2b_EN-OL-RC-538_1 | 5 | 3/3 | None |
| 5b2b_EN-OL-RC-538_2 | 5 | 3/3 | None |
| 5a21k_EN-OL-RC-538_1 | 5 | 3/3 | None |
| 5a21k_EN-OL-RC-538_2 | 5 | 3/3 | None |

The missed `begging_paws` endpoint belongs to reader 4a35g, Bears paragraph 2. Provider alignment marks substitutions in that anchor, including its last word; neither acoustic timing model located a supported ending. It remains a miss against the configured checkpoint, with no invented endpoint or latency. This is not enough evidence to attribute the entire failure to ASR or to the child.

| Observer on the same fresh ASR callbacks | Activated / configured |
| --- | ---: |
| original | 34/36 |
| split | 31/36 |
| boundary | 32/36 |
| timely | 35/36 |

The application split CLI uses the **timely** observer; the observer called split is an older implementation. These are tracker comparisons on shared recognition, not new model rankings.

Provider labels substitutions/deletions in **15/36 checkpoint anchors**. Extra inserted words, pronunciation interpretation, and effect catch-up still need review. Activated IDs are not automatically correctly timed effects, and 35/36 is **not an accuracy estimate**.

## Provisional timing and listening review

Two unprompted acoustic passes (faster-whisper small.en and medium.en CUDA float16) supported endpoints for **29/35 activated checkpoints**. Median estimated delay was **0.946 s**, range **0.465–5.543 s**. The remaining six activations and the missed checkpoint are latency-unscored.

- The 5.543 s estimate is `damaged_wing`, reader 5a21k; its automatic endpoint is flagged because recognition differs from the printed endpoint. It is a review warning, not a verified five-second measurement.
- Reader 5b2b black_circles has a 2.663 s estimate, and reader 5a21k wing_colours 2.073 s. Neither had extra automatic flags, but both still require human listening verification.
- **17/36 checkpoints have additional automatic review flags.** Nineteen have no extra flags; none of the 36 is manually verified. Two Whisper variants can share biases.
- The endpoint finder requires supported anchor endings and increasing checkpoint order. Failed or ambiguous endpoints remain unscored. Times map onto the actual fresh audio-packet clock, rather than using ASR snapshot ends as spoken word boundaries.
- Local review contains all 12 full recordings, original passages, provider transcripts, checkpoint results, 31 justifiable endpoint clips, and a 36-row manual-review CSV. Five endpoints have no defensible clip and point to the full recording instead.

## Controls and audit

- Four fresh unrelated streams (dog, dragon, nickel, recording_2), each compared to the four unique new paragraph manifests: **zero activations in 16 comparisons**, for all four observers.
- Controls reuse the previous unrelated audio and do not establish safety against near-book alternatives, adult prompts, actual skips, or interruptions.
- Every positive WAV sample arrived in a contiguous packet sequence; every stream produced ASR before EOF and STREAM_DONE; printed app trigger sequences agreed with the current observer.
- All four controls completed the sample-count, final-response, and normal-close checks. No duplicate triggers or unexpected checkpoint IDs occurred in the positive runs.
- All **122 unit tests** pass, including new checks for repeatable disjoint speaker selection and preservation of provider miscues. The library verifier validates **100 manifests** and **18 imported MPS recordings**, with no broken library links.

## Files and reproduction

- [Portable measurements](results/reading-expansion-2026-11-02.json): counts, flags, provisional times, country/grade labels, source hashes and runtime versions; no raw audio/passages/transcripts.
- Local entry point: `output/mps-expansion-2026-11-02/INDEX.md`.
- Local listening page: `output/mps-expansion-2026-11-02/review/index.html`.
- Local manual review sheet: `output/mps-expansion-2026-11-02/review/manual_review.csv`.
- Canonical audio and text: `recordings/library/stories/mps-bears-part-{1,2}/readers/` and `mps-butterflies-part-{1,2}/readers/`.
- Frozen selection, source metadata and results: `output/mps-expansion-2026-11-02/`; raw provider material remains Git-ignored. MPS usage terms refer licensing questions to the provider; no redistribution right is inferred.

```powershell
# Import the fixed provider selection (local data only; --download fetches source files):
.\.venv\Scripts\python.exe -X utf8 benchmarks/prepare_mps_expansion.py --download
# With the documented NeMo server running, choose a fresh destination:
.\.venv\Scripts\python.exe -X utf8 -u benchmarks/run_reading_expansion.py --output output/mps-expansion-repeat
# Stop the NeMo server before loading separate acoustic models into GPU memory:
.\.venv\Scripts\python.exe -X utf8 benchmarks/estimate_checkpoint_words.py --jobs output/mps-expansion-2026-11-02/jobs.json --output output/mps-expansion-2026-11-02/acoustic
# Score the original completed batch; estimates remain provisional:
.\.venv\Scripts\python.exe -X utf8 benchmarks/score_reading_expansion.py
```

This is broader evidence across new reader IDs and new texts in the same corpus. It does not test the actual Singapore microphone/enclosure, accents, preschool ages, soundtrack echo, or target board. ASR pretraining overlap is unknown. If these examples are used to tune the tracker later, reserve a new untouched evaluation set.
