# Pi 4: recognition and checkpoint tracking on the device

Both programs run on the **same Pi 4**. There is no external recognition server.

```text
USB microphone -> Pi 4 CPU speech recognition -> transcript
              -> Pi 4 word alignment -> confirmed checkpoint -> effect payload
```

The packaged recognition backend is WhisperLive/faster-whisper using **int8 CPU
inference**. It does not use the Pi's built-in GPU. The checkpoint code currently
prints effect payloads; audio/visual playback and physical effects are still to
be implemented.

Use **64-bit Raspberry Pi OS** (`uname -m` must report `aarch64`), a wired USB
microphone and Docker Engine with the Compose plugin. The container supplies
Python 3.12, so the host Python version does not matter. A 4 GB or 8 GB Pi 4 is
a sensible starting point for this prototype; memory and latency have not yet
been measured on a Pi. Use cooling for sustained recognition.

## Move the project over

Copy this project folder to the Pi, excluding `.venv`, `.git`, `tmp` and any
private recordings. Keep the Python files, `tests`, the public `recordings/library/stories` sample folders, all requirements
files, Dockerfile, Compose files and `.env.pi4.example`. A Windows `.venv` cannot
be reused on Linux.

Run the following commands **on the Pi**, from the project folder. Docker must
already be installed and running, and your user must have access to it.

```bash
cp .env.pi4.example .env
docker compose -f compose.yaml -f compose.pi4.yaml build
```

The build uses ARM64 images on the Pi. It installs CPU-only Torch and just the
WhisperLive backend dependencies used here, avoiding NVIDIA and OpenVINO
packages. First build requires internet access and may take a while.

## Select the microphone

Plug in the USB microphone **before starting the containers**. List its input
devices inside the pod container:

```bash
docker compose -f compose.yaml -f compose.pi4.yaml run --rm --no-deps pod python -m books_to_life.cli.run_client --list_input_devices
getent group audio | cut -d: -f3
```

Edit `.env`: set `INPUT_DEVICE` to the microphone's listed index or a unique
part of its name, and set `AUDIO_GID` to the group number printed above. `default`
uses ALSA's default microphone if one is configured. Use the **container's**
device indexes; they can change after reconnecting USB devices. Docker passes
`/dev/snd` into the client container without privileged mode.

If no inputs appear, check the USB microphone on the host (`arecord -l`, supplied
by `alsa-utils`) and confirm that `/dev/snd` exists. If the device rejects 16 kHz
mono, select its ALSA `plughw` input if listed, or configure ALSA resampling on
the Pi and expose that configuration to the container. Actual microphone
compatibility still needs a hardware test.

## Download models once, then start reading

While connected to the internet, cache the same model selected in `.env`:

```bash
docker compose run --rm asr python -m books_to_life.cli.prepare_models --model base.en
docker compose -f compose.yaml -f compose.pi4.yaml up
```

Read `recordings/library/stories/sample/readers/demo/passage.txt` aloud. Logs should show the microphone, CPU
inference, `[TRANSCRIPT]`, `[ALIGN]` and `[TRIGGER]`. Press Ctrl+C to stop both
programs; `docker compose -f compose.yaml -f compose.pi4.yaml down` removes the
containers while retaining the models. Do not use `down -v` unless you intend
to delete the model cache.

After caching, set `HF_HUB_OFFLINE=1` in `.env` and repeat the test with Wi-Fi
disconnected. Book data is mounted locally and the two containers communicate
inside the Pi. Changing `ASR_MODEL` requires caching that new model first.

The default model is `base.en`, preserving the existing English profile. Compare
`tiny.en` if recognition falls behind the reader; it can sacrifice accuracy.
`small.en` may improve transcripts but costs more computation and RAM. The
startup wait is 180 seconds to allow CPU model loading. Recognition speed has
not been established on a Pi 4, and continuous speech can accumulate delay if
inference is slower than incoming audio.

Start with `ASR_THREADS=2`, then compare 3 or 4 on the Pi. The `AUDIO_CHUNK=1024`
setting sends 64 ms microphone packets at 16 kHz. This only reduces capture
packet buffering; ASR processing and checkpoint confirmation add their own
latency. It is not a 64 ms response-time guarantee.

## Test on this Windows laptop now

The same Python code works here. With the existing virtual environment, open
two terminals:

```powershell
# Terminal 1: force the CPU inference path used by the Pi.
.\.venv\Scripts\python.exe -m books_to_life.cli.run_server --device cpu --omp_num_threads 2
```

```powershell
# Terminal 2: microphone and checkpoint tracking.
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model base.en --audio_chunk 1024 --checkpoints recordings/library/stories/sample/readers/demo/checkpoints.json
```

For a packaging test, start Docker Desktop in Linux container mode, run
`docker compose up --build asr` instead of Terminal 1, and keep Terminal 2 native
on Windows. Windows microphone passthrough is different from Linux `/dev/snd`.
Stop the native server first so port 9090 is available. Docker builds AMD64
automatically here; the Pi overlay selects ARM64 later. Laptop CPU timings still
do not predict Pi 4 timings.

Verification commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m books_to_life.cli.run_server --device cpu --check_device
.\.venv\Scripts\python.exe -m books_to_life.cli.checkpoint_demo --benchmark 30
docker compose -f compose.yaml -f compose.pi4.yaml config --quiet
```

The demo benchmark measures matching only. To assess the pod, measure time
from the last required spoken word to `[TRIGGER]`, and check whether delays
grow across continuous reading. Re-test with the actual Pi, microphone and
representative books before deciding whether this ASR backend is fast enough.

## Scope and references

This package includes microphone capture, on-device ASR and the existing word
alignment/checkpoint logic. It does not implement book scanning, cloud catalogue
retrieval or effect playback. Only the stock English model path is packaged;
optional translation, diarization, TensorRT and OpenVINO are not included.

The deployment follows upstream [WhisperLive client dependencies](https://github.com/collabora/WhisperLive/blob/main/requirements/client.txt),
[CTranslate2 ARM64 CPU support](https://opennmt.net/CTranslate2/hardware_support.html)
and [Docker Compose device mappings](https://docs.docker.com/reference/compose-file/services/#devices).
