# ASR-only model comparison

For independent file pacing with a recognition queue, run the same command with
`--delivery queued --dataset <earlier-run>/dataset.json` and choose a fresh output
directory. This preserves the recordings, ordering, 256 ms packet size and 1.5 s
silence tail. The producer puts packets into a FIFO on an absolute 1× clock. A
recognition worker takes them in order, including after capture ends if it has
fallen behind. The queue can hold the entire finite recording. This benchmark
therefore measures backlog without dropping input at the replay queue. An engine
can still fail or discard data in its own buffer.

Run `benchmarks.verify_asr_only` on the output directory to audit both packet
traces. `capture` records real-time audio availability, and `audio` records the
same packets as they are handed to the backend. Separate EOF events show when
capture finished and when the queue drained. Peak pending audio excludes the
in-flight packet. Queue wait stops at backend submission, so it does not measure
the decoder's own internal buffering or WebSocket buffering. Word latency still
runs from the estimated acoustic word ending through transcript arrival and
includes backlog. The original inline replay is available with `--delivery inline`.

For reviewed verbatim references, word endings and actual WER/word-delay tables,
see [the local reference reviewer](ASR_REFERENCE_REVIEW.md). Automatic drafts are
kept separate from reviewed ground truth.

This runner uses recorded PCM files directly. It does not load checkpoint manifests,
instantiate a tracker, send book hints, open a microphone, play sounds, or send MapMap
commands. A worker import guard rejects the application's matching/context modules.
The existing NeMo service is reused with an ordinary English transcription session;
no hint messages or checkpoint decisions are sent to it.

Every profile receives the same three complete recordings: Tea, Fat Cat and Little
Mermaid. The frozen dataset records file hashes, intended passage references and
available historical listening marks. Audio is 16 kHz mono, delivered in 4,096-sample
float32 packets at 1x speed, followed by the same 1.5 seconds of digital silence.
Late inference never causes input samples to be skipped. Recognition continues to EOF.

Profiles are NeMo CUDA via loopback WebSocket, Whisper Tiny/Base English CPU INT8
(optional CUDA F16 profiles require the Windows CUDA/cuDNN runtime DLLs),
native Parakeet Unified F16 Vulkan (560 ms chunk/right context, 5.6 s history),
native Moonshine Medium F16 Vulkan, and official Moonshine Medium quantized CPU.
These compare deployment configurations, not hardware-independent architectures.
Native/CUDA runtimes use existing local weights; downloads are disabled for Whisper.
KeenASR's separate licensed browser prototype and uncached Whisper Small/Medium
are outside this first batch.

## Run quietly

Use a Python environment containing the required recognition backends. On this PC,
the enclosing repository's `.venv` has faster-whisper and psutil, while the panel's
client-only `.venv` does not. End the panel's reading session before using NeMo,
which serves one session at a time. Start NeMo through the panel if necessary.

From the active checkout:

```powershell
Set-Location 'C:\Users\heart\Speech-to-Text\output\reading-pod-first-pipeline'
$python = 'C:\Users\heart\Speech-to-Text\.venv\Scripts\python.exe'
$cache = 'C:\Users\heart\Speech-to-Text\model-cache\asr-benchmark'
$run = Join-Path 'output\asr-only' (Get-Date -Format 'yyyyMMdd-HHmmss')
& $python -m benchmarks.asr_only --cache $cache --output $run `
  --profiles whisper-tiny-cuda whisper-base-cuda nemo-cuda `
  parakeet-vulkan moonshine-vulkan moonshine-cpu
```

The runner starts one isolated worker per profile/recording, sequentially. Use
`--profiles nemo-cuda whisper-base-cpu` to select configurations. Use `--resume`
only with the identical configuration and source files; completed **and failed**
trials are retained. Use a fresh directory for a retry or changed configuration.
`--summarize-only` regenerates reports without recognition. All results remain local.
The default profile list uses CPU Whisper; the explicit list above reproduces the
GPU comparison performed on this PC.

For Whisper CUDA, this PC now has pinned `nvidia-cublas-cu12==12.4.5.8` and
`nvidia-cudnn-cu12==9.1.1.17` in `model-cache/asr-benchmark/cuda-runtime`.
The worker adds only those DLL directories to its own process. It does not alter
system PATH or the panel environment. Select `whisper-tiny-cuda whisper-base-cuda`
explicitly for the GPU profiles. Setup failures and interrupted exploratory CPU
trials are retained in their original output directories.

## Measurements and limits

- Final transcript edits, separately labelled passage WER or verified-spoken WER.
  The default references are supplied printed passages, **not human-verified verbatim
  readings**. Passage WER includes genuine reading mistakes, omissions and repetitions.
  It must not be presented as pure recognition accuracy. A new dataset can supply
  independently reviewed verbatim references with `reference_kind: verified_spoken`.
- First nonempty text arrival from recording start. This includes leading silence
  and is not latency measured from the beginning of speech.
- Text revisions, including non-append changes. Snapshots replace earlier hypotheses.
- Post-run exact phrase first availability, persistent availability and final
  retention against historical listening marks. These are lexical ASR observations,
  not checkpoint matching or permission rules. A transient appearance can later
  disappear. Absent phrases retain unavailable latency and remain in coverage counts.
  Tea's marks are 20/54/77 s and Fat Cat's hat mark is 53 s; their whole-second
  precision does not establish millisecond accuracy. Fat Cat's reportedly skipped
  first anchor has no spoken-end timing mark. Little Mermaid has no verified marks.
- Audio-delivery lag, complete sample counts, EOF drain, model load or server handshake,
  backend/device/precision, local model hashes, process RSS and total-system GPU snapshots.
  Paced duration divided by recording duration is **not** inference real-time factor.
  Native synchronous feed/finalize time is recorded separately where available.
  The worker's `delivery.finalization_seconds` includes teardown and checksum work.
  For final transcript arrival, subtract the raw `end_of_audio.wall_seconds` from
  the final collected transcript event's `wall_seconds` instead. First-text and
  marked-phrase arrival scores use the raw callback clock, before that teardown.
  A Whisper buffer trim which removes audio before its committed timestamp is
  flagged as a failed trial. This is loss of uncommitted audio, not a measurement
  of GPU computation speed. Input delivery can be punctual while decoding or
  transcript commitment still fails to keep up. Trimming already committed audio
  is logged and permitted.
- NeMo's timer includes loopback WebSocket transport. In-process runtimes do not.
  NeMo's already resident weights differ from locally loaded workers; startup figures
  are labelled accordingly. There is no extra recognition warmup pass.
  NeMo's Windows worker RSS measures the client, not the WSL server's model RAM.

Outputs include dataset/run snapshots, per-trial raw JSONL callbacks and delivery,
transcripts, complete or failed trial JSON, logs, progress JSON, comparison CSV/JSON,
and a Markdown report. Existing results are never overwritten by a new run.
One run is one trial per recording/profile on development recordings, not a held-out
reader study. Other GPU applications remain open; memory snapshots include them.
Physical microphone, speakers and projector response need separate testing.

Audit the frozen run and its delivery logs after completion:

```powershell
& $python -m benchmarks.verify_asr_only $run
```

The audit reports successful complete streams separately from retained recognition
failures. An integrity pass does not mean every recognizer trial succeeded.

Run the benchmark's logic tests with:

```powershell
& $python -m unittest discover -s tests -p 'test_asr_only*.py'
```
