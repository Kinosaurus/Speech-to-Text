# Choosing and running a setup

Updated 31 October 2026. Run all commands from the repository root.

## Recommended setup for the current reading pilot

Use **Parakeet Unified NeMo 0.6B on CUDA, the `split` tracker, and no automatic
book hints**. This is the strongest configuration supported by this project's
recorded-reading evidence on the RTX 3070 Ti. It is not a universal model ranking.

The settings are explicit:

| Setting | Pilot value | Reason |
| --- | --- | --- |
| Speech engine | `parakeet-nemo` | Better checkpoint coverage than Whisper medium.en in the earlier paired application streams. |
| Server | Linux/WSL NeMo, CUDA bfloat16, port 9097 | This is the implemented and tested NeMo runtime on this PC. |
| Buffering | 560 ms chunk + 560 ms right context, 5.6 s left history | Preserves the evaluated configuration. Smaller chunks have not been shown better on these readers. |
| Tracker | `--matching_mode split` | Selects `TimelyEvidenceMatcher`, including split-token, boundary-evidence, and scoped recovery improvements. |
| Hints | `--no_book_context`, no explicit hotwords | Highest coverage with fewer severe regressions in the latest nine-recording hint comparison. |
| Matching settings | Manifest threshold 82, stability 2, minimum coverage 0.8 in the evaluated manifests | Keep the tested manifests; do not lower thresholds just to increase trigger counts. |
| Audio | 16 kHz mono; file playback sends 4096 samples per packet | Uses the actual application's paced audio transport. |

The normal CLI defaults are still `base.en`, `alignment`, and automatic book
context when a manifest is supplied. They do **not** select this pilot setup.

Terminal 1, inside the existing Ubuntu-24.04 environment:

```bash
cd /mnt/c/Users/heart/Speech-to-Text
/home/heart/.venvs/books-to-life-nemo/bin/python -m books_to_life.cli.run_nemo_server \
  --model-path model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo \
  --host 127.0.0.1 --port 9097 --chunk-ms 560 --right-ms 560 --boost 1.0
```

Terminal 2, Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model parakeet-nemo --server 127.0.0.1 --port 9097 --matching_mode split --no_book_context --files recordings/library/stories/little_mermaid/readers/little_mermaid/audio.wav --mute_audio_playback --checkpoints recordings/library/stories/little_mermaid/readers/little_mermaid/checkpoints.json --transcript_file output/mermaid-pilot.srt
```

Use the manifest and audio from the same reader/book folder. For a microphone,
omit `--files ...` and `--mute_audio_playback`, select a microphone with
`--list_input_devices` / `--input_device`, then stop with Ctrl+C. File results do
not measure microphone quality, background noise, or speaker separation.

Fresh post-reorganization runs and their limitations are in
[the 31 October report](../benchmarks/BEST_SETUP_RESULTS.md). Installation is in
[the running guide](RUNNING.md); the commands above assume prepared environments.

## Speech engines and deployment options

Model, runtime, device, tracker, and hints are separate choices. Docker is a way
to deploy a recognizer; it does not itself make recognition more accurate.

| Setup | When it is useful | Why choose it | Tradeoffs and evidence |
| --- | --- | --- | --- |
| **Parakeet NeMo + CUDA + split, no hints** | Current English reading pilot on this NVIDIA PC | Best supported checkpoint coverage and improved boundary timing in the project's live tests | Requires the separate Linux/WSL environment, CUDA, and the original `.nemo` model. English only; one client at a time. Not verified on Jetson. |
| **Whisper medium.en + native Windows CUDA** | A Windows-only GPU installation or a comparison recognizer | Avoids WSL and supports the project's prompt/hotword extension | Earlier matched streams caught fewer checkpoints than Parakeet. A larger model does not guarantee better effect timing. |
| **Whisper tiny.en / base.en / small.en** | Smaller deployment experiments and CPU fallback | Smaller Whisper variants reduce model resource demands; `base.en` is the current CLI default | No current held-out checkpoint comparison proves a smaller variant best for children. CPU real-time performance must be measured on the target device. |
| **Whisper via Docker GPU** | Reproducible laptop/desktop server environment | Keeps server dependencies separate from the Windows microphone client | Requires Docker and NVIDIA GPU support. Use `compose.gpu.yaml`; it is a Whisper server, not the NeMo server. Docker validation does not establish target performance. |
| **Whisper via Docker CPU** | No supported GPU, functional integration tests | CPU-only deployment is provided by `compose.yaml` | Lower hardware requirements do not establish sufficiently low latency for live effects. Start with a small model and measure backlog. |
| **Native Parakeet GGUF via Vulkan** | A Windows native alternative without NeMo/WSL | Uses the C++ runtime, shared model cache, and the same file/microphone client | Different decoder/precision/buffering from NeMo; no phrase hints in this adapter. Do not transfer NeMo scores to it. Default chunk/right context are 160 ms each. |
| **Native Moonshine via Vulkan or CPU** | Comparing another streaming recognizer through the same app | Prepared through the native benchmark/model cache | Separate recognition behavior and no hints in the application's native adapter. The official Moonshine CPU benchmark profile supports context, but that capability is not wired into this app adapter. |
| **Client-only PC / Pi, GPU server elsewhere on the LAN** | A pod device with little storage or compute | Keeps model files and inference on the GPU host; the client follows the book locally | Depends on server availability and network latency. Start with the [LAN guide](LOW_STORAGE_TESTING.md); WSL networking needs separate verification. |
| **Whisper on Raspberry Pi 4 CPU** | Standalone ARM64 prototype | Provided CPU container and USB microphone setup | No fresh Pi latency or accuracy validation in the current PC runs. Do not assume a model that runs will keep up with reading. See [Pi setup](PI4_SETUP.md). |
| **Whisper on Jetson CUDA** | Standalone NVIDIA board prototype | Dedicated JetPack/CTranslate2 build rather than an x86 image | A documented deployment target, not a measured reproduction of desktop results. Desktop GPU power limits do not emulate Jetson. See [Jetson setup](JETSON_SETUP.md). |

Whisper's upstream model table explains the general size/speed/resource tradeoff;
its published speed figures are not measurements of this application's streaming
pipeline. See the [official Whisper README](https://github.com/openai/whisper#available-models-and-languages).
The NVIDIA [Parakeet model card](https://huggingface.co/nvidia/parakeet-unified-en-0.6b)
describes English streaming and configurable context. Advertised model latency
is not the measured delay from a child's word to an app checkpoint.

## Why this pilot choice currently wins

In the 24 October paired application comparison, Parakeet plus the then-current
split tracker activated **16/16 configured checkpoint opportunities**, versus
**9/16 for Whisper medium.en**. These totals combine hints on/off for four
development stories; some activations may be catch-up. They are not scores on
the later nine-recording set. See [the original comparison](../benchmarks/LIVE_TRACKER_RESULTS.md)
and [its machine-readable summary](../benchmarks/results/live-tracker-2026-10-24.json).

Later boundary/timely improvements recovered checkpoints earlier without losing
the preceding tracker's detections in those tests. They reduced three distinct
late reading events, with a largest paired change of about 21.5 seconds. Some
other activations remained over 16 seconds late. See
[the timing report](../benchmarks/TIMELY_TRACKER_RESULTS.md).

The 29–30 October nine-recording comparison then favored no hints:

| Hint policy | Activated / configured | Median estimated delay among detected checkpoints | Important limitation |
| --- | ---: | ---: | --- |
| No hints | 26/27 | 0.830 s | Billy's final checkpoint missed. |
| Moving local book hints | 26/27 | 0.797 s | Same coverage; Billy's second checkpoint was about 6.08 s late. |
| Fixed whole-passage phrases | 25/27 | 0.874 s | Included a Tom activation roughly 19.8 s early, plus longer delays. |

The 0.033 s difference between the first two medians, from one run per condition,
does not establish a meaningful latency advantage. Whole-passage hinting can
bias recognition toward words not spoken yet, which can mislead position
tracking. Fixed hand-picked vocabulary helped particular earlier words but did
not establish a general improvement. Keep those experiments separate from the
no-hints pilot. The [hint report](../benchmarks/READING_CONTEXT_RESULTS.md) records
the regression and the proposed safeguards, which remain unimplemented.

## Tracker choices

| CLI mode / implementation | Purpose | Why use it |
| --- | --- | --- |
| `alignment` / `AlignmentMatcher` | Original full-book alignment with consecutive confirmation | Default and useful baseline. |
| `evidence` / `EvidenceAlignmentMatcher` | Retains supported candidates across some noisy updates | Experimental comparison; does not include all later split/timely behavior. |
| `split` / `TimelyEvidenceMatcher` | Full-book alignment plus contextual compound splitting, boundary carry, and scoped timely recovery | Current evaluated pilot choice. |
| `fuzzy` / `CheckpointMatcher` | Legacy checkpoint-phrase similarity | A simpler baseline; less context than full-book alignment. |

The observer labelled `split` in historical comparison JSON is the **older**
`SplitEvidenceMatcher`. Today's application `--matching_mode split` selects
the observer labelled **`timely`**. `BoundaryEvidenceMatcher` is an intermediate
comparison baseline, not an additional CLI mode.

Count, timing, and scene correctness are different measurements. A skipped
checkpoint can be marked passed or a scene can fire late via catch-up. Count
alone does not prove that the right effect played when the anchor was spoken.
The application currently emits effect payloads; physical projector, lighting,
and sound playback are not connected to those triggers.

## Other launch commands

Windows Whisper server, then the same client with Whisper's model and port:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_server --device cuda --host 127.0.0.1 --port 9090
# In a second terminal, use the pilot client command with:
# --model medium.en --port 9090
```

Native model server, then use `--model parakeet --port 9091` or
`--model moonshine --port 9091` in the client:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_native_server --model parakeet --device vulkan --port 9091
# For Moonshine, replace parakeet with moonshine. Use --device cpu for CPU tests.
```

Container alternatives and the offline checkpoint demo:

```powershell
docker compose -f compose.gpu.yaml up --build
# CPU alternative, run separately:
docker compose up --build
# No speech server or model required:
.\.venv\Scripts\python.exe -m books_to_life.cli.checkpoint_demo
```

Keep only the server you need running when comparing GPU configurations. Run
one client per server at a time. Setup scripts, dependency lists, cache
preparation, and hardware-specific requirements are in [RUNNING.md](RUNNING.md).

## Repeating the current evaluation

With the prepared NeMo server running and the locally acquired evaluation data
present:

```powershell
.\.venv\Scripts\python.exe -X utf8 -u benchmarks/run_best_setup.py --output output/best-setup-new-run
```

This runs six MPS and three published-passage recording trials, then four
unrelated recordings against the nine book manifests. It preserves raw logs,
transcripts, frozen manifests, packet audits, and source hashes locally. It also
checks app/observer trigger agreement and maps fresh trigger times onto the
previously frozen acoustic word-end estimates. The local published jobs index
and timing files come from the earlier passage evaluation; see
[the provenance/reproduction notes](../benchmarks/READING_CONTEXT_RESULTS.md).

The shared results contain only measurements and hashes. Restricted corpus
audio and passages stay local. These are development recordings with estimated,
unreviewed word endpoints, one repeat per recording, and no fresh microphone,
Jetson, or Pi measurements. Validate new readers, near-book conversation,
adult prompts, skips, and interruptions before treating the pilot as reliable
for unattended effects.
