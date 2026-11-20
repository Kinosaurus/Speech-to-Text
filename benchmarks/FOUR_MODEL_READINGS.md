# Four-model child-reading pilot

The presentation table uses six recordings from six different children in the
[Maharashtra Primary Schools dataset](https://github.com/DAP-Lab/mps_dataset).
There are two readers per grade: Grade 3 reads the two paragraphs of The Lost
Sheep, Grade 4 reads Bears, and Grade 5 reads Butterflies. Each child reads one
paragraph. Individual ages are not supplied in the selected metadata.

The frozen selection covers both paragraphs per grade and different readers of
different provider-listed genders, selecting the shortest qualifying pair and
breaking ties by recording ID. Selection did not use recognition scores. The
recordings were already familiar development examples, not a new held-out study.
Total duration is 195.9 seconds; the provider transcript references contain 414
normalized words. Inputs and raw outputs remain local.

## Saved results

| Model and setup | Word error | Correctly read cues detected | Estimated average cue-decision delay |
| --- | ---: | ---: | ---: |
| Parakeet Unified NeMo, CUDA, checkpoint hints | 8.9% | 14/14 | 1.91 s |
| KeenASR Web SDK, supplied-passage graph | 16.7% | 10/14 | 0.34 s |
| Whisper Tiny English, CPU INT8, unhinted | 16.9% | 11/14 | 1.45 s |
| Moonshine Medium, CPU quantized, unhinted | 12.6% | 5/14 | 8.86 s |

The NeMo row is a later checkpoint-hint experiment. The other rows retain the
original replays. All four KeenASR misses were in the two Bears recordings.
These are configured-system comparisons, with different hardware and recognition
assistance; they do not isolate model architecture or establish performance for
American or Singaporean children.

Word error is measured against the provider's transcript of the actual reading,
not the ideal printed text. Provider transcripts include phonetic renderings of
miscues, so the metric follows those transcription conventions.

There are 18 authored checkpoints, of which 14 have all words labelled correctly
read in the provider alignment. The cue column counts detection of those 14
eligible readings. NeMo fired all 18 configured checkpoints with zero duplicates.
The four other triggers require a separate judgment against the application's
reading-tolerance policy; 14/14 coverage does not establish zero false triggers.

Delay is the software cue-decision timestamp minus an automatically estimated
phrase ending from Whisper Small. The average uses each system's detected
eligible cues, so the rows have different cue subsets. Misses are excluded from
delay and retained in the coverage column. Endings have not been manually
verified. Audible sound and projected first-frame onset are not measured here.

## NeMo checkpoint-hint follow-up

The experiment kept the six recordings, automatic endings, matcher, threshold 82,
stability 2, coverage 0.8, 160 ms chunks, 560 ms future context, boost 1, and 80 ms
input packets fixed. Delivery was paced at 1x with 1.5 seconds of appended silence,
using an isolated local CUDA server and one trial per recording/setting.

Two recordings screened full-passage, disabled, and checkpoint-only hints. The
selected checkpoint-only setting was then run on the other four recordings.
It supplied each recording's three authored checkpoint phrases rather than full
printed sentences. Requested hint hashes and buffer settings were acknowledged
before delivery.

Relative to the saved full-passage run, mean estimated delay over the same 14
eligible cues fell from 3.50 s to 1.91 s, approximately 45%. Median over all 14
fell from 1.72 s to 1.09 s; word errors fell from 54/414 to 37/414. Coverage
remained 14/14, with no duplicates. Two cues became substantially slower:
carried_home reached 4.55 s and damaged_wing reached 5.98 s. A fresh full-passage
screening baseline differed from the saved run, showing timing variability.

The live app now enables Reading hints at Medium by default. NeMo receives the
current checkpoint phrase and up to two ahead, retaining an unfinished pending
cue. The tracker still loads the full story for alignment and recovery. This
moving live hint window is not a rerun of the fixed three-phrase experiment, so
the 1.91 s result is not a validated live-performance guarantee.

Six familiar clips, one trial per setting, and unreviewed phrase boundaries support
a preliminary result. Broader paired tests, negative controls, and physical
output timing remain necessary for stronger reliability claims.

## Local evidence

The ignored directory `output/four-model-readings-20261120` contains the frozen
`dataset.json`, per-model callback timelines, and `cue-endings/latency-results.json`.
Its `hint-latency-20261120/FINDINGS.md` and experiment outputs preserve the follow-up.
Child audio, source transcripts, copied commercial story text, and raw captures
are not published with this summary. Local commercial comparison input text and
Night Tiger OCR-derived manifests must be supplied separately when reproducing
those unrelated experiments or reading sessions.
