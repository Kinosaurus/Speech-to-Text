# Child-reading data for a Singapore pod

Checked 2 November 2026. The target is a real child reading a known English
passage, with the original written text kept separate from what the child said.
Country, age, and reading task must come from provider metadata. They are not
inferred from names, accents, photographs, or voice quality.

## Regional sources checked

| Source | Fit for this English passage test | Access / action |
| --- | --- | --- |
| [Singapore SCSMT](https://www.apsipa.org/proceedings/2025/papers/APSIPA2025_P102.pdf) | Singapore children aged 7–9, but the reading languages are Mandarin, Malay, and Tamil. It is not an English child-reading test for the current English-only Parakeet adapter. | [Provider repository](https://github.com/zbowen0225/SG-children-dataset). Relevant if the pod later supports mother-tongue reading. |
| [BK3AT, Philippines](https://aclanthology.org/2024.sigul-1.8/) | Stronger regional lead: includes an English child read-speech subset, recording prompts, and speaker metadata. Continuous passage suitability still needs inspection after access. | The paper says access is requested from DFAT Australia / the Ministry of Basic, Higher and Technical Education; CC BY-NC 4.0. No dataset access was obtained and no request was sent automatically. |
| [CHILDES English-Mandarin Singapore](https://talkbank.org/childes/access/Biling/Singapore.html) | Singapore preschool classroom conversations and self-talk, not a controlled printed-passage reading set. Could eventually help evaluate unrelated conversation and code-switching. | TalkBank access and reuse rules apply. Do not relabel transcripts as original story passages. Not imported as positive reading examples. |
| [MERLIon CCS](https://sites.google.com/view/merlion-ccs-challenge/datasets) | Singapore parent-child sessions, but parents narrate a wordless picture book. Child-directed speech is not the same as children reading a fixed script. | Provider registration/access instructions. Not used as child-read passage evidence. |
| [Malaysian early reading dataset](https://data.mendeley.com/datasets/3vjjzk5xnx/1) | The listed download is an SPSS assessment data file, not a matching child-audio/passage bundle. | Not imported as speech. |
| [Singapore English pronunciation research](https://arxiv.org/abs/2202.09108) | Describes Singapore child read speech and relevant pronunciation differences. A suitable directly downloadable, licensed passage/audio bundle was not located in this search. | A provider inquiry is a possible next step; the paper's existence is not dataset access. |
| [Common Voice Malaysian English](https://mozilladatacollective.com/datasets/cmrt71n6q001fmm07u64adwuv) | Accent-labelled scripted clips; the subset has no age filter and is not a verified set of children reading continuous passages. | Do not count it as child validation without documented child ages and the required task. |

This is a search/access finding, not a claim that no suitable Southeast Asian
data exists. No adult, synthetic voice, or spontaneous transcript was silently
substituted for a child reading an original passage.

## Additional readings acquired now

The user approved **Indian recordings as a fallback** while regional access
remains separate. The new local batch uses the
[Maharashtra Primary Schools dataset](https://github.com/DAP-Lab/mps_dataset):

- Twelve recordings from six previously unused speaker IDs, Grades 4 and 5.
- Three female and three male speaker IDs, each reading two paragraph sections.
- Two additional texts, Bears and Butterflies; four paragraph passages in total.
- Provider `promptText`, `manualTranscript`, and word-level miscue alignment are
  preserved separately. Individual age is not supplied; grade is not exact age.
- Original WAVs remain at 16 kHz mono PCM16. They are not joined to manufacture
  a continuous reading session.
- Three unique, ordered checkpoints per paragraph, fixed before live ASR.
- Fixed random seed and speaker selection saved before audio decoding; no
  filtering by recognition success or reading score, and no substitutions of
  easier readers after testing.

**India is South Asia, not Southeast Asia.** These results do not establish
performance for Singaporean children. MPS is the same corpus family as the
earlier Lost Sheep tests, so the expansion is speaker/text-disjoint from that
subset, not an independent recording-domain evaluation.

Provider terms say dataset use is governed by a license and refer questions to
the provider. No redistribution permission is inferred. Source audio, passage
text, transcripts, and raw results stay local and ignored by Git.

## What a proper test includes

1. Preserve the original passage independently of the child's actual reading.
2. Freeze checkpoints and selection before recognition; keep every selected
   reader, including difficult cases and missing endpoints.
3. Validate checkpoint word ranges and ideal-text behavior, then stream actual
   WAV samples through the same client/server used by the app.
4. Audit all samples, partial recognition before EOF, final completion, and
   agreement between app triggers and the comparison observer.
5. Report activations, missing IDs, wrong IDs, repeats, and unrelated-speech
   controls. An activation count alone is not a correctness score.
6. Preserve provider miscues near each checkpoint. A child omitting an endpoint
   is different from ASR failing to recognize a correctly read endpoint.
7. Keep automatic acoustic estimates separate from human-checked timestamps.
   Estimated delays are provisional; missing or ambiguous endpoints remain
   unscored rather than being assigned invented gold times.

Tools: `benchmarks/prepare_mps_expansion.py` imports the frozen selection;
`benchmarks/run_reading_expansion.py` runs the actual audio and controls.
The local batch starts at `output/mps-expansion-2026-11-02/jobs.json`.
See [the completed expansion results](../benchmarks/READING_EXPANSION_RESULTS.md)
and open `output/mps-expansion-2026-11-02/INDEX.md` for audio, passage and checkpoint
links. The local listening page and review CSV keep automatic estimates separate
from the still-pending human verification.

## Regional access request checklist

For BK3AT or a Singapore research group, request a small English **child-read**
evaluation subset with original prompts/passages, actual child transcripts,
speaker IDs, documented age/grade and recording country, recording conditions,
and explicit permitted uses for this university/pod project. Ask whether passage
audio is continuous or individual sentences, and whether endpoint timestamps
exist. Do not describe a research license as public redistribution permission.
No email or registration has been sent on the user's behalf.
