# Mila and the Sky Garden demo

The first checkpoint from the existing sample passage reveals a preloaded garden panorama across the three walls and plays a 2.2-second chime. The demo starts both effects as soon as it receives `seed_found` so you can compare their timing.

## Trigger the video from the passage

Open `Sky Garden - Spoken Cue.mmp` in the updated MapMap build and go fullscreen on the projector. It starts on the calibration grid. Run the Parakeet speech-test commands below. When the client confirms `seed_found`, MapMap reveals the video and plays it from the beginning with its own soundtrack. It holds on the closing image.

On Windows, double-click `Start Sky Garden.cmd` to start the speech client with the video cue. To repeat a reading, close that command window and double-click it again. MapMap receives the cue on port `12345`, which you can check under **Edit → Preferences → Controls → OSC Setup**.

For a manual playback check, run `play_cue.py --video` from the project folder using the Python command below. Use `--video --reset` to return to the grid. On Jetson, add `--video` to both the `--relink` and `--listen` commands and open `Sky Garden - Spoken Cue.mmp`.

## Test the effects on Windows

1. Open `Sky Garden.mmp` in `tmp/MapMap-Reading-Pod/MapMap.exe`. Leave MapMap open on the calibration grid. Use **View → Output screen** to pick the projector and **Ctrl+F** to enter fullscreen.
2. From the `Speech-to-Text` folder, run the command below. The garden should replace the grid and the chime should play through the default speakers.

```powershell
.\.venv\Scripts\python.exe 'Reading Pod MapMap\Sky Garden\play_cue.py'
```

Run the same command with `--reset` to show the grid again. The bridge uses MapMap's local OSC port `12345`. If you set another port in MapMap's OSC Setup, pass `--port` with the same number.

## Test with Parakeet NeMo on Windows

Leave MapMap open on the grid. If the Parakeet server is stopped, enter Ubuntu from Windows PowerShell with `wsl.exe -d Ubuntu`, then start the server in that terminal. Wait for `[READY] ws://127.0.0.1:9097` before starting the client.

```bash
cd /mnt/c/Users/heart/Speech-to-Text
/home/heart/.venvs/books-to-life-nemo/bin/python -m books_to_life.cli.run_nemo_server \
  --model-path model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo --port 9097
```

From the `Speech-to-Text` folder in Windows PowerShell, run the microphone client and effect bridge.

```powershell
.\.venv\Scripts\python.exe 'Reading Pod MapMap\Sky Garden\play_cue.py' --video --read
```

Read the first sentence of *Mila and the Sky Garden* aloud, then pause.

> Mila found a tiny silver seed beside the old gate.

The demo uses one confirmation. The bridge fires once when the client prints `[TRIGGER] seed_found`. Restart the client to arm a new test. For the still-image project, open `Sky Garden.mmp` and omit `--video`.

## Test with the Jetson Compose setup

Follow the [Jetson setup](../../docs/JETSON_SETUP.md) for the GPU server, microphone, and model. Copy the MapMap checkout to the Jetson and apply [the Qt 6 preview patch](mapmap-qt6-preview.patch) from the MapMap source directory with `git apply /path/to/mapmap-qt6-preview.patch`. Follow the Ubuntu instructions in MapMap's `INSTALL.md` to build it for Linux ARM64, then run it in the Jetson desktop session. For an HDMI projector, use a DisplayPort-to-HDMI adapter.

After copying the demo folder to the Jetson, update its asset paths from the project root.

```bash
python3 'Reading Pod MapMap/Sky Garden/play_cue.py' --relink
```

Open the relinked `Sky Garden.mmp` in MapMap. Run the bridge without `--listen` to check the picture and chime once. The bridge uses `pw-play`, `paplay`, or `aplay` on Linux. With the grid reset, run the configured Jetson services and pipe the pod client's output into the bridge on the host.

```bash
docker compose -f compose.jetson.yaml up -d asr
docker compose -f compose.jetson.yaml run --rm -T pod | python3 'Reading Pod MapMap/Sky Garden/play_cue.py' --listen
```

Read the whole paragraph so the default two-confirmation matcher can fire as the transcript grows. The host bridge sends the cue to local MapMap and plays the WAV. Record the reader, projected grid, and speakers together to measure the time from the last word of the cue to the visible reveal and audible chime.
