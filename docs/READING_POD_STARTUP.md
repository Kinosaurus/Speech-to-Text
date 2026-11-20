# Start and use the Reading Pod

This guide describes the Windows PC configured on 19 November 2026. It covers speech recognition, the operator panel, MapMap, projection, scene assignments and calibration. For a fresh installation or another platform, use [Install and run](RUNNING.md) and [Setup choices](SETUPS.md).

## The folders on this PC

| Item | Location |
| --- | --- |
| Active panel checkout | `C:\Users\heart\Speech-to-Text\output\reading-pod-first-pipeline` |
| Windows Python client | `.venv\Scripts\python.exe` inside that checkout |
| Shared projection scenes | `scenes\` inside that checkout, with `Sky Garden\` and `Night Tiger\` subfolders |
| Book passages, checkpoints and local sounds | `recordings\library\stories\` inside that checkout |
| MapMap handoff | `C:\Users\heart\Speech-to-Text\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff` |
| Master project with all scenes and saved wall layout | `Reading Pod MapMap\Sky Garden\Sky Garden - Two Scenes.mmp` inside the handoff |
| Generated selected-story project | `output\operator-mapmap\live\Reading Pod - Selected Story.mmp` inside the active checkout |
| NeMo environment inside Ubuntu WSL | `/home/heart/.venvs/books-to-life-nemo` |
| Shared NeMo model | `C:\Users\heart\Speech-to-Text\model-cache\parakeet-nemo\parakeet-unified-en-0.6b.nemo` |

The working pod features and media are spread across these folders. On another PC, provision the client, model, compatible MapMap build, project, scene files and cue assignments together. The [iteration report](READING_POD_ITERATION_REPORT.md) records which work is still local.

## Everyday startup

Start the panel, open MapMap, then start recognition from the panel. Keep the panel running during the session.

### 1. Start the panel

In a second PowerShell tab, run the complete block. These paths match the installed setup, including the selected-story runtime directory and OSC port.

```powershell
Set-Location 'C:\Users\heart\Speech-to-Text\output\reading-pod-first-pipeline'
$handoff = 'C:\Users\heart\Speech-to-Text\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff'
$bridge = Join-Path $handoff 'Reading Pod MapMap\Sky Garden\play_cue.py'
$master = Join-Path $handoff 'Reading Pod MapMap\Sky Garden\Sky Garden - Two Scenes.mmp'
$storyRuntime = Join-Path (Get-Location) 'output\operator-mapmap\live'

.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel --mapmap-bridge $bridge --mapmap-project $master --mapmap-story-dir $storyRuntime --osc-port 12346
```

Open **[http://127.0.0.1:8765](http://127.0.0.1:8765)** on this PC. Leave the server tab open. If the panel is already serving at that address, reuse it.

### 2. Start Reading Pod MapMap

In the panel, click **Preflight → Open MapMap**. It uses the selected-story project, configured OSC port and Reading Pod launcher. Wait for **Running · OSC connected**. Existing connected instances are reused.

To open it manually, run the launcher below in another PowerShell tab, or double-click **Start Reading Pod MapMap.cmd** in the handoff folder.

```powershell
& 'C:\Users\heart\Speech-to-Text\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff\Start Reading Pod MapMap.cmd'
```

The launcher opens the generated selected-story project in the compatible MapMap build on OSC port `12346`. If MapMap is already open with this setup, reuse its window. If you need to relaunch it, save any layout edits and close it normally first.

### 3. Start recognition from the panel

Under **Preflight**, click **Start recognition server**. The panel shows **Starting…** while NeMo loads the cached model, then **Ready** after a Windows client receives `SERVER_READY`. A ready server is reused. **Restart recognition server** ends an active reading session before reloading NeMo.

The controls use the existing Ubuntu environment and downloaded model. Initialization may take several minutes. Errors appear in the panel, and logs stay local in `output\operator-server\nemo.log`. The panel refreshes readiness automatically.

### 4. Choose the projector and check connections

1. Connect the projector and set Windows Display Settings to **Extend**.
2. In MapMap, choose the projector under **View → Output screen**, then press **Ctrl+F** for fullscreen.
   The updated Windows build keeps the fullscreen output visible when you minimize the editor. A staged renderer update is installed automatically the next time you use **Start Reading Pod MapMap.cmd** after closing MapMap.
3. In the panel, choose a **Passage**. Wait for its projection scenes to finish loading. Story changes reuse the same MapMap window.
4. Click **Preflight → Check setup**. NeMo should report `SERVER_READY`; MapMap should report **Listener found** on UDP `12346`.
5. Use **Reset to grid** and check the calibration on the actual walls. Under **Output layout**, **Fit output** detects the current fullscreen MapMap canvas. **Manual dimensions** and **Restore original** are available if needed.

The Windows audio output determines where sound plays. A recognized OSC listener confirms the socket. Click a **Show …** scene button when ready to check the real projector and speakers. These buttons can play media and sound.

## Start recognition manually

The panel checks NeMo automatically and provides **Start recognition server** and **Restart recognition server** under **Preflight**. A ready server is reused. To start it manually, open PowerShell and run this command. It uses the installed Ubuntu environment and cached model.

```powershell
wsl.exe -d Ubuntu --cd /mnt/c/Users/heart/Speech-to-Text/output/reading-pod-first-pipeline --exec env TMPDIR=/tmp TEMP=/tmp TMP=/tmp /home/heart/.venvs/books-to-life-nemo/bin/python -u -m books_to_life.cli.run_nemo_server --model-path /mnt/c/Users/heart/Speech-to-Text/model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo --host 127.0.0.1 --port 9097 --chunk-ms 160 --right-ms 560 --boost 1.0
```

Wait for `[READY] ws://127.0.0.1:9097`. Loading the model can take a while. Leave this tab open. For live use, the GPU and CUDA in WSL must be available.

The tested NeMo default uses 160 ms updates, 560 ms future context and 80 ms microphone packets from the panel. Startup includes a silent CUDA warmup; readiness reports the actual buffering. After updating an already running installation, use **Restart recognition server** once to apply the new defaults. Legacy server buffering remains available with `--chunk-ms 560 --right-ms 560`; the legacy client packet was `--audio_chunk 4096`. See the [latency investigation](../benchmarks/LATENCY_INVESTIGATION.md) for measured gains, provisional WER tradeoffs and physical checks.

## Read a story

1. Select **Mila and the Sky Garden**, **Parakeet NeMo**, and your actual **Microphone**.
2. Keep **Reading hints** on at **Medium** for Parakeet NeMo. It receives upcoming checkpoint phrases while the tracker follows the full story. Leave **Save recording** off for the first test.
3. Click **Start experience** and wait for **Listening**. Check **Input in use** identifies the intended microphone.
4. Read “Mila found a tiny silver seed beside the old gate.”
5. Check that the transcript updates and `seed_found` fires once. Look at the projected Silver Seed clip and listen for its soundtrack.
6. Continue through the remaining pages. Confirm the local checkpoint sounds and any assigned projection changes.
7. Click **End experience**. Capture should stop and the projection should return to the grid.

The live match evidence explains support for the current checkpoint, including sound-alikes, missing words and forgiven articles. The same matcher decides whether a cue can fire. An accepted checkpoint fires once during the session.

## Preview without a projector

Choose **The Night Tiger** and click **Test cue** beside a media checkpoint. The browser preview plays its scene and sound together. **Close preview** stops it. Playback starts when you click. A browser preview checks the media independently of MapMap projection and speech recognition.

The story has 28 narration checkpoints and eight media effects. Check the OCR-derived words against the physical book. [Night Tiger page and cue list](../recordings/library/stories/night_tiger/README.md)

## Import scenes and assign them to checkpoints

1. Put new MP4, MOV, WebM, PNG or JPEG files under the active checkout's `scenes\` folder. Subfolders are supported. Keep the files there after import.
2. End the reading session. Save any MapMap edits and close MapMap normally so it can release the master before the panel updates it.
3. Click **Preflight → Import scenes**. Imported cues reuse the saved three-wall layout. Media is centered and cropped to fill it; a 2.4:1 asset fills the current layout without a crop.
4. Above the checkpoints, click **Edit MapMap cues**. Assign an imported scene to each desired checkpoint. Assignments save locally as you make changes.
5. Start **Start Reading Pod MapMap.cmd** again. Select the story in the panel, then preview an assigned scene when ready.

**No MapMap cue** restores ordinary local playback for that checkpoint. Stills and silent videos retain the checkpoint's local sound. A video with its own soundtrack replaces the local sound. A checkpoint that only plays local sound leaves the current projected scene up.

The master keeps the full library. The generated project contains the selected story's assigned projection scenes and calibration grid. The renderer prepares video players when needed, holds the current scene until the incoming frame is ready, and releases the old player after the transition. Choose the crossfade duration or **Cut** under **Scene transition**. Start, end and manual reset return to the grid. [Scene library guide](../scenes/README.md)

## Edit the wall layout

1. End the session and open **Preflight → Output layout → Edit wall layout**. The editor uses the detected fullscreen MapMap output size and the latest Fit or wall preview sent from the panel. If fullscreen output is unavailable, it falls back to an area based on the saved layout. Editor width and height set the coordinate area displayed in the browser.
2. Drag inside a wall shape to select and move the whole wall. Drag its corner handles to reshape it. Use **Ctrl+Z** to undo and **Ctrl+Y** or **Ctrl+Shift+Z** to redo. Each full drag is one undo step. Undo and Redo buttons are also available. History lasts for the current editor session.
3. With MapMap open, the projector preview updates automatically after you pause dragging or nudging a corner for 250 ms. **Preview on projector** resends the draft when needed.
4. Click **Save and apply to all scenes**. The panel saves the master, and MapMap confirms that it applied and persisted the new corners in the existing window.
5. Check the alignment on the physical walls. If the panel reports that the renderer needs its live-layout update, save any MapMap edits and restart it once through **Open MapMap**. Subsequent layout saves work with MapMap open.

The saved geometry is applied to compatible three-wall meshes in the master project while retaining source crops. Generated story projects reuse that layout. Verify it on all three physical walls after moving a projector or changing Windows output settings.

## Where settings and recordings go

All paths below are relative to the active checkout.

| Path | Contents |
| --- | --- |
| `output\operator-sessions\` | Local session transcripts and logs, plus a WAV when **Save recording** is enabled |
| `output\operator-mapmap\` | Per-master-project checkpoint assignments and transition settings |
| `output\operator-mapmap\live\` | Generated selected-story project and MapMap readiness/status files |
| `output\operator-server\nemo.log` | Local NeMo startup and server diagnostics |
| `scenes\` | Shared projection media |
| `recordings\library\stories\` | Book manifests, full text, local sounds and browser previews |

Assignments are keyed to the master project's path. Moving the master can require transferring or reassigning those settings. Preserve the master and shared media when copying the setup. Keep transcripts and recordings local.

## Shut down

1. Click **End experience** and wait for capture to finish and the grid to return.
2. Save any intended MapMap edits and close its window.
3. Press **Ctrl+C** in the panel terminal.
4. Press **Ctrl+C** in the NeMo terminal if you started it there. NeMo launched from the panel stays running when the panel closes and can be reused next time.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Open MapMap reports a launch error | Read the message under MapMap OSC. Save and close an existing MapMap instance if requested, then retry. The launcher path can be configured with `--mapmap-launcher`. |
| Panel page will not open | Start the panel from the active checkout and check its terminal. Default HTTP port is `8765`. |
| Port already in use | Open the existing panel or reuse the existing NeMo server. Identify the existing process before deciding whether to stop it. |
| NeMo is unavailable | Click **Start recognition server** and wait for **Ready**. Use **Restart recognition server** to reload a running server. Errors appear in Preflight; startup logs are in `output\operator-server\nemo.log`. Check installed distros with `wsl.exe --list --verbose`; this PC uses `Ubuntu`. |
| Model or WSL environment missing | Follow [Install and run](RUNNING.md). The startup command expects the installed paths listed above. |
| NeMo reports busy | End any existing reading or test client. NeMo serves one recognition session at a time. |
| MapMap launcher asks for the selected-story file | Start the panel with the complete command above first, including `--mapmap-story-dir`. |
| MapMap is listening but a scene does not change | Check both sides use `12346`, the Reading Pod launcher opened the selected-story project, and the checkpoint has an assigned scene. Watch for story-load errors. Test with a **Show …** button when ready. |
| Calibration is cropped | Check Windows Extend, MapMap's output screen and fullscreen state. Use **Fit output**, then inspect the wall layout and physical projector alignment. |
| MapMap or Windows feels choppy | Use the Reading Pod launcher and a selected-story project. The connected-projector lag comparison is still pending. Record the active story and display mode when reproducing it. |
| Microphone is missing or silent | Connect it, refresh the page, select the correct device and check Windows microphone permissions. Confirm **Input in use** after starting. |
| New scene is missing | Close MapMap, import the scene through the panel and assign it. Reopen MapMap and reselect the story. |
| Panel says to build React | Run the build commands below from the active checkout. |

## First install or rebuild

The everyday commands reuse the installed environment and built panel. After UI source changes, rebuild from the active checkout.

```powershell
Set-Location 'C:\Users\heart\Speech-to-Text\output\reading-pod-first-pipeline'
npm.cmd --prefix operator-panel ci
npm.cmd --prefix operator-panel run build
```

For a fresh Windows client, install Python 3.12 and Node.js/npm, then run the following before building React.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements/requirements-client.txt
.\.venv\Scripts\python.exe -m pip install whisper-live==0.10.0 --no-deps
```

For NeMo provisioning, model downloads and other speech engines, follow [Install and run](RUNNING.md). Check the installed WSL distro name before using a command copied from another PC. Provision the compatible MapMap runtime and handoff media as well.

## More detail

- [Operator panel options](../operator-panel/README.md)
- [Scene library and import workflow](../scenes/README.md)
- [Iteration report, models and benchmark results](READING_POD_ITERATION_REPORT.md)
- [Pending physical checks](READING_POD_TODO.md)
- [Shared matcher and effect policies](EFFECT_POLICIES.md)
