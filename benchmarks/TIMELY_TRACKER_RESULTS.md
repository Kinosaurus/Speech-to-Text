# Late-scene investigation and fresh streaming comparison

Date: 28 October 2026. The complete 14-stream tracker-only sweep is saved under
`output/timely-streaming-2026-10-28/`. All 107 unit tests pass. All samples were
delivered, recognition arrived before EOF, final coverage completed, application
decisions agreed with the timely observer, and tracker source hashes stayed
unchanged during the sweep. All four baseline source files also match their
hashes from the preceding boundary experiment.

## Complete tracker-only results

| Caught / reached or configured | Original | Pre-boundary split | Current boundary-fixed | New timely |
| --- | ---: | ---: | ---: | ---: |
| Children, standard checkpoints | 2/4 | 2/4 | 4/4 | 4/4 |
| Children, earlier checkpoints | 5/8 | 7/8 | 8/8 | 8/8 |
| Earlier stories, both hint conditions | 12/16 | 16/16 | 16/16 | 16/16 |

No activations caught by current boundary-fixed are lost. Both OCSC checkpoint
sets share audio, and the story figure includes both hint conditions and the
disputed Fat Cat anchor; these are not independent accuracy observations.

All four trackers produce **zero triggers in 16 unrelated-audio/book controls**.
No duplicate activations, unexpected scene IDs, or apparent premature OCSC
activations were observed. Expected scene IDs that fire late remain a separate
usability problem; zero off-book activations is not proof of universal safety.

Versus current boundary-fixed, timely fires earlier in 4 shared
scene/manifest/condition comparisons, at the same callback in 24, and later in
0. The four improved comparisons correspond to three distinct reading events
because 6008's paragraph endpoint is present in both OCSC manifests. Largest
improvement: 21.51 s; median change: 0 s.

Versus pre-boundary split, 14 shared comparisons are earlier, 11 identical, and
0 later. Versus original, 14 are earlier, 3 identical and 2 later: the same
mermaid scene in two hint conditions, about 0.53 s later. That delay already
exists in current boundary-fixed; this latency change adds no delay to it.

## Causes found in the previous live logs

1. Recovery can override valid local acquisition. After several noisy updates,
   a scene needs score 92. A recent prefix belongs to the preceding scene under
   the scene-position mapping, so its evidence does not restore the normal
   configured threshold of 82 for the upcoming checkpoint. In 6008's paragraph
   ending, a valid prefix scores 100; the ending containing an extra word scores
   85.7 and gets rejected. The tracker later recovers in the following paragraph
   and fires the old scene about 19 seconds late.
2. Adjacent repetitions inflate the alignment denominator. In 7057's first
   sentence, the ASR contains a repeated function word and an article insertion,
   plus a close-spelling final-word substitution. The candidate scores 78.7.
   Collapsing only the adjacent repetition yields a candidate around 86.6,
   above normal threshold. This needs a recent specific prefix to be usable
   while recovering; it is not a reason to relax all book searches.
3. ASR chunks sometimes jump from fewer than five useful words to a clean
   prefix plus fillers. A word-tail-only search never records that prefix,
   despite five exact book words being present immediately before the fillers.
   This contributes to 6008's initial sentence delay.
4. Some late scenes have unsupported recognition or an actual reading
   deviation, rather than just rejected evidence. In 7057, the help sentence is
   recognized with two different ending words. The new-home sentence ends with
   different words in both ASR and the corpus's child transcript: it should not
   be described solely as a recognition error. There is not enough matching
   anchor evidence for an immediate decision. Later reading produces scene
   catch-up. This fix does not invent those words or silently treat those
   delayed detections as timely effects.

These causes were diagnosed using saved callback logs. That diagnostic replay
is distinct from the fresh audio streaming used for the final comparison.

## Change

`TimelyEvidenceMatcher` extends the unchanged boundary-fixed tracker:

- A recent independent prefix of the NEXT checkpoint permits its normal
  configured score threshold for a recognizably similar ending. Other scenes
  and unacquired/recovery searches retain the existing threshold rules.
- Adjacent duplicate tokens can supply an additional candidate ending exactly
  at that checkpoint. The original ASR text is retained and no global book
  progress is created by this transformation.
- A unique exact five-word anchor prefix immediately before at most two extra
  tokens can be retained for a later callback. It cannot confirm the same
  hypothesis twice. Prefixes need distinct words and must be near the endpoint.
- A close spelling ending uses the same >=75 word similarity already used by
  the underlying aligner; arbitrary different endings do not get extra credit.
- Time/update expiry, fresh audio/text, coverage, ambiguity, prompt/negation,
  duplicate and checkpoint-order guards remain in effect. No book-specific
  misrecognition aliases or global threshold reductions were added.

The original, pre-boundary split, and boundary-fixed classes remain unchanged
as online baselines. Experimental `--matching_mode split` uses the new timely
tracker. Original alignment remains the default application mode.

## Evaluation protocol and limits

### Completed children: tracker-only condition

| Approximate source-boundary delay | Current boundary-fixed | New timely |
| --- | ---: | ---: |
| 6008 first early checkpoint | 12.78 s | 0.59 s |
| 6008 paragraph-ending checkpoint | 19.11 s | 0.90 s |
| 7057 first early checkpoint | 22.70 s | 1.18 s |
| 7057 help checkpoint | 16.29 s | 16.29 s |
| 7057 new-home checkpoint | 22.79 s | 22.79 s |

The first three are actual streamed improvements, not transcript-replay
estimates. The remaining two still have ASR-unsupported endings. Detection
counts remain 4/4 for standard checkpoints and 8/8 for earlier checkpoints for
both boundary-fixed and timely; identical counts conceal these timing changes.

A separate follow-up condition tests the existing fixed book-phrase hints on
7057 and on all four unrelated clips with exactly the same hints and both OCSC
manifests. Its protocol is `output/timely-hints-jobs.json`; its results are kept
in a separate directory. This must not be mixed into the no-hints tracker-only
comparison or represented as a tracker-only gain.

### Completed phrase-hint follow-up

All five supplementary streams completed and passed the same coverage,
live-callback, source-hash and application-agreement checks. Artifacts:
`output/timely-book-hints-2026-10-28/`.

| 7057 early checkpoint, timely tracker | No hints | Fixed book phrases |
| --- | ---: | ---: |
| First sentence | 1.18 s | 0.66 s |
| Help sentence | 16.29 s | 2.04 s |
| New-home sentence | 22.79 s | 22.66 s |
| Paragraph ending | 1.12 s | 4.63 s |

The hint condition retains all four early scenes. It improves the help-word
recognition but leaves the actual reading deviation, and delays the paragraph
ending. It is not adopted as a blanket latency fix. The application's existing
hint behavior is unchanged; the test used a fixed list so each tracker received
identical recognition input, not tracker-driven moving vocabularies.

The four unrelated recordings with those same hints produce zero activations
against either OCSC manifest: eight supplementary clip/manifest controls per
tracker. No duplicate or apparent premature OCSC activation was observed. These
controls are separate from the 16 primary off-book comparisons, not a new large
independent validation population.

### Remaining work and outcome

The avoidable first-sentence and recovery-threshold delays above are fixed in
the experimental tracker and verified by fresh audio streaming. This does not
claim to eliminate every delay: without hints, 7057's help and new-home scenes
remain around 16 and 23 seconds late, and 6008's help scene remains around
10 seconds late. Mapping either unsupported ending directly to the expected
book words would require a separately validated error-tolerant inference rule;
it must be tested against near-book alternative sentences and interruptions,
not justified solely by zero triggers on unrelated recordings. Book hints help
one case but have a measured timing tradeoff on another endpoint.

All 19 streams are complete. The temporary Parakeet server was stopped after
testing. No source media, child transcripts or private manifests are published.

All ten local recordings are streamed through the installed Parakeet NeMo
server using the application's paced audio client. The four earlier stories
run with and without identical fixed hints, both children run without hints,
and four unrelated clips are compared against all four story manifests. This
is 14 actual audio streams and 16 off-book clip/book controls per tracker.

Four observers process the same live ASR callbacks: original, pre-boundary split,
boundary-fixed (the current tracker before this change), and timely. Both OCSC
checkpoint manifests run on the same child's stream and are correlated. The
previous experiment's results remain in their original output directories.

Checks require all audio samples delivered, live ASR before EOF, completed final
coverage, no server error and agreement between application and timely observer.
Paired timing uses callback arrival, excluding observer-order compute overhead.
OCSC source-boundary delays are approximate automatic CHAT annotations mapped
onto actual sender clocks; development recordings lack manually verified ending
times. A reported skipped Fat Cat anchor remains an unresolved catch-up case.

This is a development/regression evaluation on inspected recordings. No finite
control set can establish that a change will never cause a wrong trigger. Late
expected scene IDs are reported separately from unrelated-book activations.

## Reproduce

With the installed Parakeet server running:

```powershell
.\.venv\Scripts\python.exe -u benchmarks/run_boundary_comparison.py
.\.venv\Scripts\python.exe benchmarks/summarize_boundary_comparison.py
```

The runner now writes to the timely output directory. `--resume` validates
completed live logs rather than running saved transcripts through trackers.
