# Use the local OCSC subset on another PC

The OCSC recordings are deliberately kept locally, not removed. The repository
is public, and [TalkBank's redistribution rule](https://talkbank.org/0share/rules.html)
requires case-by-case permission from the corpus contributor before placing
media on the web. The user confirmed on 28 October 2026 that this permission
has not been obtained. Do not force-add OCSC WAVs, corpus/ASR transcripts or
transfer bundles to Git. A private Git repository or Git LFS is not a substitute
for permission. Revisit this choice if the contributor grants permission.

The eight original repo recordings and their selected ASR transcripts do ship
with Git. The four OCSC audio files and associated transcripts stay under the
same `recordings/` folder on this PC, ignored by Git.

## Recommended: transfer your local evaluation inputs

On this PC, from the checkout root:

```powershell
.\.venv\Scripts\python.exe benchmarks/ocsc_local_bundle.py export --output output/ocsc-private-transfer.zip
.\.venv\Scripts\python.exe benchmarks/ocsc_local_bundle.py verify --archive output/ocsc-private-transfer.zip
```

Copy that ZIP directly to your own other PC (for example, on a USB drive).
It contains the two full sessions, their reading clips, matching transcripts,
two checkpoint manifests, subset inventories, selected transcript history and
the independently obtained passage-reference PDF. It contains no account
credentials, models, conversion caches, or unrelated participants' transcripts.
The ZIP stays in ignored `output/`; do not attach it to GitHub issues/releases
or publish it. This is a local-analysis transfer, not redistribution to others.

On the other PC, clone or update this repository's `first-pipeline` branch,
prepare the client as in [LOW_STORAGE_TESTING.md](../LOW_STORAGE_TESTING.md),
then run from that checkout:

```powershell
git pull --ff-only origin first-pipeline
.\.venv\Scripts\python.exe benchmarks/ocsc_local_bundle.py verify --archive D:\Transfer\ocsc-private-transfer.zip
.\.venv\Scripts\python.exe benchmarks/ocsc_local_bundle.py import --archive D:\Transfer\ocsc-private-transfer.zip
```

Replace `D:\Transfer\...` with the actual copied file. Import checks every file's
SHA-256, confines extraction to the checkout and refuses to overwrite different
existing files. The paths in bundled job inventories are portable. Linux uses
the equivalent Python environment command instead of `.venv\Scripts\python.exe`.

The source WAVs total about 312 MiB. The bundle is compressed; retain extra
space for both the ZIP and extracted files. With only 10 GB free, run the light
audio client on the other PC and keep Parakeet/model dependencies on the GPU
host, following the low-storage guide.

## What to run

With the Parakeet server running on the GPU PC:

```powershell
.\.venv\Scripts\python.exe run_client.py --model parakeet-nemo --server GPU_PC_IP --port 9097 --matching_mode split --files recordings/7057_reading.wav --mute_audio_playback --checkpoints output/ocsc/manifests/grandmas_house_early_story.json --no_book_context --transcript_file recordings/transcripts/7057_reading/other-pc-no-hints.srt
```

Replace `GPU_PC_IP`. Use `6008_reading.wav` for the other clip. Both share the
same intended passage. The standard manifest has three later endpoints; the
early manifest has four endpoints within the first paragraph. The full-session
WAVs include other tasks and should not replace reading clips in comparisons.

For the complete localhost benchmark, use
`benchmarks/run_boundary_comparison.py` with the server at `127.0.0.1:9097`.
This script streams all recordings in real time and compares frozen original,
split, boundary-fixed and current timely trackers on the same ASR callbacks.
For a remote GPU host, the single-clip command above accepts its IP directly.

## Exact source subset and clip boundaries

Official corpus: [Ohio Child Speech Corpus](https://talkbank.org/childes/access/Eng-NA/OCSC.html).
Use your own TalkBank registration for a fresh source download. The official
corpus page links to authenticated transcripts and the media folder.

| Source session | Official media | Reading section in original session | Local clip |
| --- | --- | --- | --- |
| `6/6008` | [6008.wav](https://media.talkbank.org/childes/Eng-NA/OCSC/6/6008.wav?f=save) | 1118.003–1325.380 seconds | `6008_reading.wav` |
| `7/7057` | [7057.wav](https://media.talkbank.org/childes/Eng-NA/OCSC/7/7057.wav?f=save) | 1066.999–1199.922 seconds | `7057_reading.wav` |

Full files are 44.1 kHz mono PCM; reading clips are 16 kHz mono PCM. Keep
adult prompts and reading deviations. Timestamps come from automatic corpus
alignment, not manually verified timing gold. Use the bundle to preserve the
same clip conversion and checkpoint manifests; copying only raw source WAVs
does not recreate those derived inputs.

Source SHA-256 values:

```text
6008_full.wav    84c7459d0594df371a6a94bbad49a9be8a75d218455d91e85d6198adf429ce69
7057_full.wav    ee4eedfea36d31398d14bd13ef3ae3db60d81089afa174984c6144ff99b62eec
6008_reading.wav 156353ba271370267672ece30be10ea3751cda886c56bea901ebf302a4b8e7fe
7057_reading.wav 38528f325419f5aa3d3ef21fc1f2e05d158be2c7afb3f891901e6cf25d5cebe2
```

## Transcripts, passage text and results

- `<id>_reading.txt/.srt`: final no-hints Parakeet ASR from the latest full sweep;
  errors are retained. Older runs live in `recordings/transcripts/<id>_reading/`.
- `<id>_full.cha`: corpus transcript; `<id>_full.txt/.srt` are main-turn exports.
  The SRT uses corpus utterance timing and excludes untimed turns.
- `output/ocsc/subset.json` and `subset-early.json`: exact local inputs, timing
  annotations and expected/unread scenes. The bundle includes both.
- Passage text was verified independently against Alana Oif's 2017 Ohio State
  thesis, Appendix E, PDF page 97 (printed page 88), not reconstructed from ASR:
  [source PDF](https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu149211825867405&disposition=inline).
- Committed evaluation summaries:
  [initial OCSC results](../benchmarks/OCSC_EVALUATION.md),
  [boundary fix](../benchmarks/BOUNDARY_CONFIRMATION_RESULTS.md), and
  [latency investigation](../benchmarks/TIMELY_TRACKER_RESULTS.md).

Cite Wagner et al. (2025), *The Ohio Child Speech Corpus*, Speech Communication
170, 103206, and follow the official corpus citation and usage rules. Access to
the corpus and use of the evaluation subset do not establish production
readiness. Remaining recognition/reading-deviation delays are documented in
the latency report.
