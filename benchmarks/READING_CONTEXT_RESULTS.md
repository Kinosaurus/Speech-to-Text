# Reading checkpoints: passage-backed audio and hint comparison

Evaluation dates: 29–30 October 2026. These are development results on inspected recordings, not production acceptance evidence. Runtime matcher behavior was not changed during these experiments.

## Current tested configuration

- Parakeet Unified English 0.6B via NeMo, CUDA bf16, RTX 3070 Ti; WSL Ubuntu-24.04 server and Windows client.
- 560 ms chunk, 560 ms right context, 5.6 s left context; phrase boost strength 1.0.
- Explicit `--matching_mode split`, which selects `TimelyEvidenceMatcher`. CLI default remains `alignment`.
- Threshold 82, stability 2, minimum coverage 0.8. Full passage available to the matcher in every condition.
- Recommended condition for this evaluated subset: **explicit `--no_book_context`**. Automatic book hints remain enabled by default when a manifest is supplied; that application default was not changed.

## Passage-backed no-hints tests

| Set | Recordings | Checkpoints fired | Estimated median delay |
| --- | ---: | ---: | ---: |
| MPS, The Lost Sheep | 6, three Grade 3 readers | 18/18 | 0.755 s |
| Kites, Billy, Tom, rebuilt published references | 3 | 8/9 | 0.962 s among detected checkpoints |
| Combined baseline | 9 | 26/27 | 0.830 s among detected checkpoints |

MPS metadata provides grade and gender, **not individual age**. No sample is described as a confirmed seven-year-old. The original provider prompts and human-reviewed spoken transcripts are separate. MPS use is governed by a license; the provider directs licensing inquiries to prao@iitb.ac.in. Local import does not establish permission to republish its contents.

The three OCSC manifests were rebuilt from independently published AIMSweb passage versions. Existing checkpoint IDs/settings were retained and normalized word ranges recomputed. Kites' dinosaur anchor now uses printed wording instead of the child's extra word. Full published Billy and Tom text is retained, including portions absent from the earlier transcript-derived references. The exact OCSC stimulus-card editions remain unverified. Earlier manifests/expected times are archived locally.

Billy's final cookies/chess checkpoint was missed. The live Parakeet transcript ended before the final word; two separate Whisper models recognized that last attempt differently from the printed word. No delay was assigned to the missing activation and no runtime substitution was added to force it.

## Moving versus whole-passage phrase hints

Eighteen fresh, paced real-audio streams covered both hint policies on all nine recordings. Baselines were the previously audited no-hints runs; no new no-hints replication was performed. Audio and manifest hashes matched the baselines.

| Condition | Checkpoint IDs fired | Median estimated delay | Latest estimated activation | More than 1 s early |
| --- | ---: | ---: | ---: | ---: |
| No hints | 26/27 | 0.830 s | 1.833 s late | 0 |
| Moving hints | 26/27 | 0.797 s | 6.083 s late | 0 |
| Whole-passage phrases | 25/27 | 0.874 s | 13.656 s late | 1 |

Fired IDs are not the same as correct/timely activations. Whole-passage counts include the severely early Tom activation below.

Moving uses the existing BookContext policy: next checkpoint plus two lookahead, refreshed with confirmed position. The automatic phrase limits and comma delimiters are unchanged. Whole-passage uses fixed phrase chunks covering both MPS paragraphs, or the full published Kites/Billy/Tom text. Adjacent short sentences are packed to at most 16 words, within the decoder's 32-phrase/200-character limits. NeMo receives phrase hotwords, not a Whisper-style full-text prompt. This compares two concrete policies, not context length alone.

Among checkpoints caught in both the baseline and hinted condition:

| Condition | Shared | Median paired change | Earlier by >50 ms | Within 50 ms | Later by >50 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Moving | 26 | +0.007 s | 3 | 21 | 2 |
| Whole | 25 | +0.014 s | 3 | 16 | 6 |

Neither policy recovered any baseline miss. Single-run differences of a few milliseconds should not be interpreted as meaningful gains.

### Regressions

- Billy's second checkpoint: 1.833 s late without hints, 6.083 s with moving hints, 13.656 s with whole-passage hints. The final checkpoint remained missed in all conditions.
- Kites' first checkpoint: 0.650 s late without hints versus 5.384 s with whole-passage hints; whole-hinted recognition contained repeated earlier phrases.
- Whole-passage Tom: the first checkpoint was skipped. The comic-books checkpoint fired after 11.264 s of audio had arrived, at 11.571 s from the first packet. Its independently estimated spoken endpoint is 30.160 s; drift-corrected delay is **-19.843 s**. This is an early-activation warning, not an improvement.

Tom's recognition joined an early occurrence of “secret place” with wording from a later sentence. The matcher accepted two successive updates aligned around words 99–106, jumping from confirmed position 24. It activated the comic-books scene via catch-up, even though the comic-books anchor itself was absent from that transcript update. The old baseline and comparison matchers also fired on the same misleading ASR input. This exposes a combined recognition/context and progress-inference failure; it does not isolate one component as the sole cause.

## Timing method and evidence limits

Actual WAV audio was independently transcribed using cached faster-whisper small.en and medium.en, CUDA float16, word timestamps, no passage prompt/hotwords and no VAD filtering. Anchor endpoints were matched to those word estimates and their median used. Recognized final-word attempts differing from print were explicitly flagged. These two models share a family and can share biases.

Delay is live trigger wall time minus the estimated endpoint mapped onto the run's recorded audio-packet clock. This removes cumulative sender pacing drift. Transcript word positions and ASR snapshot-end times are not speech endpoints. Model endpoint spread is sensitivity to model choice, not a confidence interval. **No manual listening verification was performed.**

All fresh streams delivered every WAV sample, produced ASR before EOF, received STREAM_DONE, and had application triggers identical to the timely observer. No duplicate triggers or unexpected IDs were observed; this does not establish absence of wrong activations. All 119 unit tests and the local library verifier passed.

The nine recordings cover six distinct readers and few texts. Conditions were run moving first, then whole, without counterbalancing or repeated trials. No unrelated-speech, adult-prompting, negation or interruption controls were added in this sweep. The full Tom ending was not read in the clip and has no configured checkpoint here. These findings should not be generalized to all readers, books, devices or phrase-boost settings.

## Proposed fixes — not implemented

1. Require checkpoint-local anchor/ending evidence before playing an effect; later-position evidence alone should not imply the checkpoint was spoken.
2. Hold large alignment jumps as tentative until distinct subsequent speech supports the new position. Successive extensions of one biased phrase are not independent confirmation.
3. Separate position recovery from effect policy: legitimate skipping can move the tracker without playing skipped one-shot effects. Give ambience an explicit catch-up policy.
4. Keep hints disabled for the controlled pilot; after guards are validated, test bounded local hints based on confirmed position.

Test these against both the Tom regression and genuine skips/repetitions/resumptions, then repeat all nine positive streams plus near-book alternatives, adult prompts and off-book controls. Raising a global similarity threshold alone does not address a wrong-location match that already scored 100.

## Local artifacts and reproduction

Restricted source audio, passages, spoken transcripts, prompts, word timings, frozen manifests and raw logs remain local and Git-ignored. They are deliberately not part of this publication. Unrelated `PROJECT_BRIEF.md` and `recordings.zip` are not part of the change.

Local detailed reports are under `recordings/library/evaluation/`: `live-2026-10-29-verified/`, `published-passages-live-2026-10-30/` and `hint-comparison-2026-10-30/`. Each reader folder has its source, text alignment, checkpoint and timing files. Review clips live under `recordings/library/reviews/`.

Tools require the existing locally obtained corpora and model runtimes; they do not grant dataset access or redistribution rights:

```powershell
# Import six locally downloaded MPS rows/WAVs from output/mps/source.
.venv/Scripts/python.exe benchmarks/import_mps_samples.py

# Fresh no-hints audio run, with the local NeMo server already running.
.venv/Scripts/python.exe benchmarks/run_mps_streaming.py --results output/mps/new-no-hints-run

# Rebuild published-text checkpoints, preserving the earlier manifests.
.venv/Scripts/python.exe benchmarks/rebuild_published_passages.py

# Acoustic word estimates for the published-passage jobs.
.venv/Scripts/python.exe benchmarks/estimate_checkpoint_words.py --jobs output/published-passages-2026-10-30/jobs.json --output output/published-passages-2026-10-30/acoustic

# Eighteen hinted streams; resume audits completed artifacts instead of replaying them.
.venv/Scripts/python.exe benchmarks/run_hint_comparison.py --resume
.venv/Scripts/python.exe benchmarks/summarize_hint_comparison.py
.venv/Scripts/python.exe benchmarks/verify_recording_library.py
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

Several analysis helpers intentionally use the dated local artifact paths above. Preserve those inputs for exact reproduction; a fresh dataset setup requires supplying the corresponding local source index and WAVs.
