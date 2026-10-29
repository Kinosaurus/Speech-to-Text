# Benchmark child-reading recognition

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
`run_client.py` and its WebSocket server. Whisper uses the same backend, VAD
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
