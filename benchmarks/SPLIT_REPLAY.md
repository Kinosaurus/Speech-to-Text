# Context-dependent split-word replay

Use `--matching_mode split`. Original `alignment` and prior `evidence` remain
available. Default is still `alignment`. Reproduce with:
`.\.venv\Scripts\python.exe benchmarks/replay_evidence.py`.
Detailed results: `output/evidence-replay/comparison.json` (baseline,
prior_evidence, split). This report supersedes EVIDENCE_REPLAY.md for split mode.

## Implementation and scope

SplitEvidenceMatcher extends the prior evidence tracker. It proposes one split
compound within the upcoming checkpoint range only after a previous scene has
been confirmed, within 40 book words of confirmed progress. It requires two
exact book words on either side, at least three distinct exact supporting
words, and the candidate at the current transcript tail. No global replacement
of ASR words and no Tea-specific alias is installed.

Compound compatibility uses exact concatenation (credit .9), or a deliberately
limited consonant/spelling proxy (credit .7): consonant strings of equal length,
at least three consonants, all consonants except the first identical, and at
least 50% spelling similarity. This allows key pot/key put against teapot only
with the required surrounding context. It is not a trained phonetic model.
Unchanged coverage/score gates and competing-scene checks still apply.

A pre-boundary split candidate may support the same phrase when it extends to
the boundary within three fresh updates and six seconds of audio. Timestamped
streams require advancing audio. Ambiguity or an accepted incompatible match
invalidates that prefix; an unmatched partial word can be bridged. This avoids
requiring words after the effect point. Negation/prompt marker words in the last
16 transcript words block new split candidates (not the original aligner).
These guards are conservative heuristics, not speaker identification or semantic
understanding. First-scene split matching is intentionally unsupported.

## Timestamped results

16 matched-book streams, 32 configured scene opportunities:

| Metric | Original | Prior evidence | Split evidence |
| --- | ---: | ---: | ---: |
| Activations | 19 | 21 | 23 |
| Configured scenes not activated | 13 | 11 | 9 |
| Tea Parakeet, hints | 1/3 | 2/3 | 3/3 |
| Tea Parakeet, no hints | 1/3 | 2/3 | 3/3 |
| Wrong-book activations, 56 comparisons | 0 | 0 | 0 |

No original activations lost. Split matching adds the stove in both Parakeet
conditions, at the FIRST callback containing full word stove (audio endpoint
53.76 seconds). It does not fire at the preceding incomplete st update and
does not wait for the next she/sentence. This is zero extra tracker wait after
that available ASR update, NOT a measured spoken-word-to-effect delay. No audio
word-boundary annotation is available. Whisper Tea remains 0/3.

For 19 common original/split activations: 17 share the original callback, two
Parakeet Mermaid second scenes occur .548/.566 seconds later, inherited from
the evidence tracker. Split adds no timing change relative to prior evidence
for existing shared scenes. Recovered house scenes are still late.

## Older text-only logs and negative tests

Thirty comparisons cover all eight recordings. Matched-book activations:
original 14, split 20. Twenty off-book pairings (Dog, Dragon, Nickel, Recording 2
against four book manifests) produce zero activations for both. Older logs lack
segment timing and cannot establish delay. Do not pool them with timestamped
comparisons. These replay existing ASR output, not fresh audio inference.

91 automated tests pass, including boundary support across partial st,
key pot/key put, no prior acquisition, duplicates, stale prefix, same-audio
revision, negation, prompting, wrong objects and generic exact compounds.
The full original test suite still passes.

## What is not established

No new wrong-book activations were observed. On-book false-trigger rates and
precise effect timing remain unmeasured without annotated audio. Fat Cat's
skipped anchor remains a catch-up caveat. An adult reading an entire expected
sentence without prompt markers can still look exactly like child reading.
These recordings were used to develop this rule, so independent recordings
and live microphone tests are needed before promoting it to default. Counts
are scene activations, not verified correct spoken-phrase detections.
