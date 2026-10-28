# Testing on another Windows PC with only 10 GB free

## Recommended: client-only PC, recognition on the existing GPU PC

The small PC captures microphone audio, sends packets to the speech server and
runs book alignment locally. The existing GPU PC runs the recognizer. No models,
Torch, CUDA, Docker or WSL are needed on the small PC. Budget roughly 1–2 GB
for Python, Git/source and a client environment (planning allowance, not a
measured clean installation). Avoid copying this PC's .venv or model-cache.
Both PCs must be on the same trusted local network, with the server awake.
This measures a networked pod, not a standalone offline small-PC deployment.

Install 64-bit Python 3.12 and Git if needed, then on the small PC:

```powershell
git clone --depth 1 --branch first-pipeline https://github.com/Kinosaurus/Speech-to-Text.git
cd Speech-to-Text
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-client.txt
.\.venv\Scripts\python.exe -m pip install --no-cache-dir whisper-live==0.10.0 --no-deps
.\.venv\Scripts\python.exe run_client.py --list_input_devices
```

Do not install the broad requirements.txt for this client-only setup: installing
WhisperLive's complete dependency set pulls server extras. `--no-deps` above is
intentional; requirements-client.txt supplies the client imports. A matching
Windows wheel/Python version is needed for PyAudio. The import/device command
checks the client environment before connecting.

## Simplest LAN server: native Windows Whisper

On the GPU PC in its existing prepared repository/environment:

```powershell
.\.venv\Scripts\python.exe run_server.py --device cuda --host 0.0.0.0 --port 9090
ipconfig
```

Find that PC's active Wi-Fi/Ethernet IPv4 address (for example 192.168.1.20).
Allow only the needed server connection on the Windows Private network/firewall,
preferably limited to the client PC. Use a trusted LAN, without public router
port forwarding: these example connections are unencrypted WebSockets and have
no authentication configured. Guest Wi-Fi/client isolation can block access.

On the small PC, replace SERVER_IP with the actual GPU PC's address:

```powershell
Test-NetConnection SERVER_IP -Port 9090
New-Item -ItemType Directory -Force output | Out-Null
.\.venv\Scripts\python.exe run_client.py --model medium.en --server SERVER_IP --port 9090 --matching_mode split --files recordings/tea.wav --mute_audio_playback --checkpoints examples/tea_story.json --no_book_context --hotwords "mouse, pot of tea, phone, teapot, stove, cups, little house, Toad" --transcript_file output/tea-lan-split.srt
```

Use alignment instead of split for the original baseline. For a microphone test,
omit `--files recordings/tea.wav` and read the selected passage aloud. Add
`--input_device` with a listed index/name if needed. Ctrl+C ends microphone
capture. Retain separate output filenames for each tracker. A server normally
accepts one client at a time. Choosing medium.en here uses the model on the GPU
server, not a model download on the small PC.

## Reproduce the best Parakeet + split configuration over LAN

The tested Parakeet NeMo environment remains on the GPU PC, inside WSL. Start
it there with `--host 0.0.0.0 --port 9097` using the prepared model and environment
from PROJECT_STATUS.md. Then use `--model parakeet-nemo --port 9097` in the small
PC's client command, leaving the same book/hints/matching mode.

WSL's Windows localhost forwarding does not automatically mean another PC can
reach it. Default WSL2 NAT generally needs a host-to-WSL port proxy plus firewall
configuration; mirrored networking is another supported option on applicable
Windows versions. Check the host's actual networking mode before changing it.
Microsoft's official instructions:
https://learn.microsoft.com/windows/wsl/networking

For NAT, the conceptual mapping is GPU_PC_LAN_IP:9097 -> WSL_IPV4:9097, with
Parakeet listening on the WSL network interface. Use the current WSL IP (which
can change on restart), a restricted firewall rule and only that port. Verify
`Test-NetConnection GPU_PC_LAN_IP -Port 9097` from the client first. Do not use
127.0.0.1 as --server on the small PC; that points back to itself.
No network/firewall settings are automatically changed by this guide.

## If the other PC must run everything offline

The full hinted Parakeet NeMo/WSL setup is not a good fit for 10 GB free. The
existing README plans 20 GB free for a fresh hinted Parakeet setup; its model
and Linux environment alone were measured around 9.1 GB before Ubuntu/caches.

A different, lighter native Parakeet/Moonshine runtime is available: README
reports about 1.85 GB for both models/runtime, plus the client environment. Its
installer requires at least 8 GiB free at preparation time, so 10 GB before
installing Python/client may be tight. It does not provide the tested NeMo
phrase boosting and will not reproduce that model's results. Check the remaining
space AFTER client setup before considering requirements-native.txt and
benchmarks/prepare.py. Model/runtime downloads still need temporary space.

Small CPU Whisper is another possible separate configuration, with different
recognition/latency tradeoffs, but it is not the environment measured in the
latest comparison. Choose a complete local setup only after checking the other
PC's CPU/GPU/RAM and available installation space. The remote client setup above
is the most direct way to test this tracker with the current large recognizers.

## Verify a test

- A listed input device confirms microphone access; the server connection must
  also succeed before recording can be recognized.
- Watch TRANSCRIPT, ALIGN, TRIGGER and SKIPPED; completion can include skipped
  scenes and does not prove every checkpoint activated.
- File tests send paced chunks; microphone tests capture live chunks. Neither
  sends a full recording upfront, but recognizers still buffer audio.
- Test both a shared recording and real microphone reading; LAN latency, room
  noise and speaker echo can change results. Do not expect identical transcripts.
- Latest comparison: benchmarks/LIVE_TRACKER_RESULTS.md. Split remains opt-in.
