# Jetson Orin Nano Super: local GPU recognition

The same Python application runs on the laptop and Jetson. The deployment
dependencies differ: the Jetson uses ARM64, JetPack and an NVIDIA GPU runtime;
the Windows development PC uses native Python or an AMD64 GPU server container.

```text
USB microphone -> local WhisperLive server -> GPU speech recognition
               -> timestamped transcript -> CPU word alignment
               -> confirmed checkpoint -> effect payload
```

There are still two programs. On Jetson, Compose starts both on the same board.
The checkpoints, full-page text and effect JSON format do not change. The
prototype prints effects; projector/audio playback and physical control remain
future work.

## What changed in the code

- `compose.jetson.yaml` runs the server with `--device cuda` and starts the
  microphone/alignment client with `small.en` by default.
- `Dockerfile.jetson` retains NVIDIA's CUDA-enabled Torch and builds CTranslate2
  4.8.2 with CUDA and cuDNN for the Orin GPU (SM 8.7).
- `asr_runtime.py` checks both Torch and CTranslate2 for GPU support and the
  required precision. Missing support causes an error instead of CPU fallback.
- `prepare_models.py` accepts `medium.en`, CPU/GPU selection and a synthetic
  inference check, so model caching also checks the ASR kernels.
- `compose.gpu.yaml` and `Dockerfile.gpu` provide a separate laptop GPU server
  profile. The Pi CPU files remain available.

## Jetson baseline

Use the **Orin Nano Super 8GB developer kit**, **JetPack 6.2**, Docker Engine and
NVIDIA Container Runtime. Update factory firmware if required by NVIDIA's
setup guide. `uname -m` should report `aarch64`; inspect `/etc/nv_tegra_release`
and `apt-cache policy nvidia-jetpack` to identify the installed Jetson software.

The GPU image uses NVIDIA's `25.02-py3-igpu` PyTorch container, which NVIDIA lists
against JetPack 6.2. The ARM64 base manifest was checked and is pinned by digest
in `Dockerfile.jetson`. A different JetPack release requires choosing a
compatible base and re-running the checks below. Do not use the Pi CPU image,
and do not replace the NVIDIA Torch package with a generic CPU wheel.

We have verified the base-image metadata, app tests and Compose configuration
on the development PC. The Jetson image has not been built or executed on a
Jetson yet. Its native CUDA build, microphone compatibility, accuracy and
latency must be verified on the board. Building CTranslate2 uses two parallel
jobs by default to reduce memory pressure on the 8GB device. The NVIDIA base
and development tools require substantial disk space; NVMe storage is useful
for builds and models.

## Copy, configure and build on Jetson

Copy/extract the project onto the Jetson, excluding Windows `.venv`, `.git`,
temporary files and private recordings. Keep all source, Dockerfiles,
requirements, Compose files, examples and `.env.jetson.example` together.

Docker Engine and the NVIDIA runtime must already be installed and configured.
Run from the project folder on the Jetson:

```bash
cp .env.jetson.example .env
docker compose -f compose.jetson.yaml build
docker compose -f compose.jetson.yaml run --rm --no-deps asr python run_server.py --device cuda --check_device
```

The check must report `Device=cuda, precision=float16` and the GPU details.
`--device cuda` requires a working GPU environment. If it fails, check the
JetPack/runtime compatibility and CTranslate2 build before starting a reader
session. GPU detection alone does not verify cuDNN execution; perform the
model preparation check below too.

Use **only `compose.jetson.yaml`** for this deployment. It is a standalone
configuration; merging the Pi/CPU file can reintroduce CPU-only settings.

## Select the microphone and prepare the model

Plug in the wired USB microphone, then list devices inside the client container:

```bash
docker compose -f compose.jetson.yaml run --rm --no-deps pod python run_client.py --list_input_devices
getent group audio | cut -d: -f3
```

Set `INPUT_DEVICE` in `.env` to the listed input index or a unique part of its
name. Set `AUDIO_GID` to the audio group number printed by the second command.
`default` uses the configured default input. Device indexes can change after
reconnecting a microphone. The client captures 16 kHz mono; select an ALSA
resampling input if your USB microphone does not directly support that format.
Only the client container receives `/dev/snd`; no privileged mode is required.

While online, cache and verify the model selected in `.env`:

```bash
docker compose -f compose.jetson.yaml run --rm --no-deps asr python prepare_models.py --model small.en --device cuda --verify_inference
docker compose -f compose.jetson.yaml up
```

The synthetic check verifies loading and inference with silent input. It does
not measure reading accuracy or end-to-end latency. Read
`examples/sample_passage.txt` and watch `[TRANSCRIPT]`, `[ALIGN]` and `[TRIGGER]`.
Use Ctrl+C to stop. `docker compose -f compose.jetson.yaml down` retains the
model cache; adding `-v` deletes it.

To compare `medium.en`, prepare that model with the same command's `--model`
changed, set `ASR_MODEL=medium.en` in `.env`, then restart both programs. Start
with `small.en` and compare the same recordings; bigger models may improve
recognition but can increase memory use and delay. No sub-second response time
has been established on this hardware.

After caching the chosen model and VAD, set `HF_HUB_OFFLINE=1` and test with
Wi-Fi disconnected. Both programs communicate within the Jetson and the
sample book is local. Keep the `jetson-model-cache` volume. Changing models
requires caching the new selection before going offline.

## Test the same application on your current PC

The existing Windows virtual environment currently contains CPU-only Torch.
You can test the same app immediately with CPU recognition. Open two terminals:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe run_server.py --device cpu --omp_num_threads 2
```

```powershell
# Terminal 2
.\.venv\Scripts\python.exe run_client.py --model small.en --audio_chunk 1024 --checkpoints examples/sample_story.json
```

For a laptop GPU test, use Docker Desktop's Linux engine with NVIDIA GPU support
through WSL2. Stop the native server first to free port 9090:

```powershell
docker compose -f compose.gpu.yaml build
docker compose -f compose.gpu.yaml run --rm asr python run_server.py --device cuda --check_device
docker compose -f compose.gpu.yaml run --rm asr python prepare_models.py --model small.en --device cuda --verify_inference
docker compose -f compose.gpu.yaml up
```

Run Terminal 2 natively on Windows so it can access the Windows microphone.
The GPU container contains its own CUDA-enabled Torch; it does not modify the
existing Windows `.venv`. The PC profile uses CUDA 12.3/cuDNN 9 and a separate
CUDA-enabled Torch wheel, rather than the Jetson iGPU image. Driver and WSL2
compatibility still need the actual GPU checks above.

Docker Desktop's engine was unavailable during preparation, so neither GPU
container was built or tested on this PC. Laptop results validate software
behaviour but do not predict Jetson timings or memory consumption.

## Verification and remaining integration

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
docker compose -f compose.jetson.yaml config --quiet
docker compose -f compose.gpu.yaml config --quiet
```

On the Jetson, test continuous reading, skipped/repeated words, silence and
parent interruptions. Measure delay from the last required spoken word to the
confirmed effect, and check whether delay increases over a full session. GPU
acceleration does not by itself fix misheard speech; compare captured audio
and transcripts before changing alignment thresholds.

Projector and speaker output will need host multimedia access or a dedicated
player container once effect playback is implemented. The current ASR
container only needs GPU compute access. Use DisplayPort-to-HDMI for an HDMI
projector and Linux-compatible USB audio devices for microphone/speakers.

Sources: [NVIDIA Jetson/PyTorch compatibility matrix](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform-release-notes/pytorch-jetson-rel.html),
[CTranslate2 source-build options](https://opennmt.net/CTranslate2/installation.html#install-from-sources),
[NVIDIA Jetson hardware guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html).
