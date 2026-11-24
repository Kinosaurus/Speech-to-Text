# Other-PC checklist: Nemotron in the panel

Use **first-pipeline** for the panel, portable setup, benchmark tools and latest
[comparison results](../benchmarks/NEMOTRON_RESULTS_20261122.md). The earlier
`codex/nemotron-asr-comparison` branch has been merged into this branch.

## Existing Windows pod

End any reading session and close the old panel terminal. In PowerShell, from
your existing repository root:

```powershell
git fetch origin
git switch first-pipeline
git pull --ff-only origin first-pipeline
npm.cmd --prefix operator-panel ci
npm.cmd --prefix operator-panel run build
```

Keep local layouts and recordings under `output/`; do not reset that folder.
If Git reports local edits, commit or stash those edits before switching/pulling.
The compiled panel is built locally and is not included in Git.

The existing NeMo WSL environment supports Nemotron. Download its pinned 2.47 GB
checkpoint once, or privately copy the already downloaded file into
`model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo`:

```powershell
$repo = (Get-Location).Path
wsl.exe -d Ubuntu --cd $repo --exec bash scripts/reading-pod/nemo-python.sh -m books_to_life.cli.prepare_nemotron_model
```

Use your installed distro name instead of `Ubuntu` if different. The download
helper reuses its local cache and verifies SHA256
`283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd`.
If you copied only the checkpoint without Hugging Face cache metadata, verify
with `Get-FileHash -Algorithm SHA256` rather than rerunning the downloader.
Do not install NeMo into the Windows client `.venv`.

Double-click **Start Reading Pod Panel.cmd**, then refresh any old browser tab.
Choose **Speech model → Nemotron · 160 ms**, click **Start recognition server**
under Preflight, and wait for **Ready** with a Nemotron 160 ms message. The first
load can take several minutes. End an experience before changing model; Start
loads the selected backend on the shared port 9097. The panel only exposes the
trained 160 ms Nemotron setting, not the experimental 320 ms benchmark setting.

## Fresh PC or missing WSL environment

Follow [Windows setup](READING_POD_SETUP.md), including NVIDIA GPU/WSL/CUDA,
Windows Python, Node and Qt prerequisites. Run `Setup-Reading-Pod.ps1` before
the Nemotron download command above. Setup already installs the shared NeMo
environment and Parakeet checkpoint. If only the client/projection installation
exists, rerun setup without `-SkipRecognition` to install recognition.

For a custom WSL interpreter/checkpoint path, see
[operator-panel configuration](../operator-panel/README.md).

## Checks still needed on this PC

1. Open MapMap from Preflight. Check projector output and intended speakers with
   a scene preview. Wait for its OSC connection on port 12346.
2. Select the microphone and try **Horse**, **Tea**, and **Little Mermaid** with
   Nemotron 160 ms. Run once with reading hints off, then with Low (next cue only).
   Leave **Save recording** off unless you want a local WAV. Transcripts and
   session logs remain under `output/operator-sessions`.
3. Try a clean read, a mid-cue pause, a skipped cue, a reread and off-book speech.
   Record misses, duplicates, early sounds and false triggers. Repeat with
   Parakeet on the same passages for a practical comparison.
4. For physical cue-to-sound latency, record the reader and the speaker together
   on one microphone/camera timeline. Measure sound onset minus the end of the
   spoken cue. Include misses and early events. For repeatability, privately
   transfer the same source WAVs and manifests and replay both models. The saved
   0.506/0.345 s Nemotron figures are digital loopback measurements on two
   synthetic stories, not a physical speaker target for this PC.

The first PC has verified the production saved-file client, split tracker,
four-of-four Moon cues and three changing-hint acknowledgements. Its focused
suite passed 53 tests with one Windows GPU-only skip; the actual WSL GPU replay
completed. The combined branch then passed the full Windows suite: 294 passed,
one GPU-only test skipped. A live microphone/speaker/projector trial is still
outstanding.

## Optional research work

- Double Metaphone remains an unimplemented A/B experiment. The current matcher
  uses RapidFuzz and CMU pronunciations. Replay identical ASR callbacks through
  both candidates, retaining the same one-shot guards. Include short cues and
  intentional close wrong words, and report false triggers as well as extra hits.
- The older 50-recording Nemotron runner is available in
  `benchmarks/replay_nemotron_corpus.py`. It needs the original private corpus and
  archive in the expected layout. Transfer those privately using
  [local data setup](../recordings/OCSC_LOCAL_SETUP.md); do not upload recordings,
  text references, callback logs or sound captures to the public repository.
- The exact authored source snapshots for the larger ASR test and sound-latency
  retest are [archived here](../benchmarks/experiments/20261122/README.md). Their
  original workspace/data layout is documented there. They are an audit archive,
  not a substitute for privately transferring the evaluation inputs.
