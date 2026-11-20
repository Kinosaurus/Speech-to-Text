# Set up the Reading Pod on Windows

The `first-pipeline` branch contains the operator panel, the calibrated three-wall
project, the Sky Garden demo, and the source patch for its MapMap renderer.

## Prerequisites

- Windows x64, Git for Windows, Python 3.12 with the `py` launcher, and Node.js 22 with npm.
- Qt 6.12.0 for MinGW 64-bit, Qt Multimedia, and the MinGW toolchain. The
  setup defaults match the tested installation under `C:\Qt`. Pass `-QtBin`
  and `-MinGWBin` with the directories containing `qmake.exe` and
  `mingw32-make.exe` if your installation uses different paths.
  [Qt for Windows](https://doc.qt.io/qt-6/windows.html)
- For live Parakeet, install Ubuntu 24.04 in WSL 2 with a working NVIDIA CUDA
  driver and roughly 20 GB free for the WSL runtime, environment and model.
  Install the following packages inside Ubuntu before running setup.

  ```bash
  sudo apt update
  sudo apt install python3-venv python3-dev libsndfile1 build-essential
  ```

## Clone and install

Run these commands in PowerShell from a writable folder.

```powershell
git clone --branch first-pipeline https://github.com/Kinosaurus/Speech-to-Text.git
Set-Location Speech-to-Text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup-Reading-Pod.ps1
```

In an existing clone, switch to `first-pipeline` and run `git pull --ff-only`
before setup. Add `-Distro Ubuntu-24.04` if that is the name reported by
`wsl.exe --list --verbose`. For panel and projection setup on a PC without CUDA,
add `-SkipRecognition`. Rerun setup after pulling updates to refresh the panel
and rebuild MapMap when its patch changes.

Setup builds the panel and the MapMap runtime locally. It fetches MapMap at
`cc29e940385aa85c14a28832b20315dc2378b89d`, applies the [renderer patch](../pod/mapmap/reading-pod.patch),
and deploys the matching Qt libraries into `output/reading-pod`. When recognition
is enabled, it installs NeMo into the Ubuntu user's `~/.venvs/books-to-life-nemo`
and downloads Parakeet into the checkout's `model-cache`.

## Start and check the pod

1. Double-click **Start Reading Pod Panel.cmd**. Keep its terminal open. The panel
   listens on [127.0.0.1:8765](http://127.0.0.1:8765).
2. Under **Preflight**, choose **Open MapMap**. Wait for the selected story and
   UDP port `12346` to be ready. Choose **Reset to grid**, then test a Sky Garden
   scene to check the picture and the default Windows audio output.
3. Connect the projector and set Windows to **Extend** displays. In MapMap,
   select the projector under **View → Output screen** and press **Ctrl+F**.
   Use **Preflight → Output layout → Fit output** and the wall editor to align
   the three walls. **Save and apply to all scenes** saves the local layout.
4. For live reading, click **Start recognition server** and wait for **Ready**.
   Select *Mila and the Sky Garden*, your microphone and Parakeet NeMo. Click
   **Start experience** and wait for **Listening**. Read “Mila found a tiny
   silver seed beside the old gate.” Confirm the Silver Seed video and its
   soundtrack play once. **End experience** returns projection to the grid.

The panel initializes a writable `output/reading-pod/Reading Pod.mmp` from the
tracked template. Scene and calibration paths are relative to the checkout.
Saved layouts and cue assignments under `output/` survive setup and pulls. The
first run seeds the current Sky Garden cue assignments and 250 ms crossfade.

## Load a locally supplied book

The *Night Tiger* projection clips, audio, previews and cue assignments are
included. Its print-derived passage and checkpoint wording are supplied separately.
Place your authorized `checkpoints.json` at
`recordings/library/stories/night_tiger/readers/night_tiger/checkpoints.json`
and restart the panel. The import preserves the existing cue IDs and media paths.

For scene import, calibration editing and custom ports, see the
[operator panel guide](../operator-panel/README.md). Session transcripts and
optional recordings are written to `output/operator-sessions`.
