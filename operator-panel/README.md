# Reading Pod operator panel

For the complete Windows pod, follow the [setup guide](../docs/READING_POD_SETUP.md).
The commands below also support standalone and legacy projector installations.

From the Speech-to-Text repository root in PowerShell, build the React app and start the local panel server.

```powershell
npm.cmd --prefix operator-panel ci
npm.cmd --prefix operator-panel run build
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel
```

Open [the operator panel](http://127.0.0.1:8765) manually. The Windows pod launcher
opens this address for you. Under **Preflight**, use **Start recognition server**
for the installed WSL NeMo environment and **Open MapMap** for the configured
renderer. For other models, follow the [runtime instructions](../docs/RUNNING.md).

| Model | Default port | Reading hints |
| --- | --- | --- |
| Parakeet NeMo | 9097 | Upcoming checkpoint phrases |
| Whisper Base, Tiny, Medium (English) | 9090 | Upcoming checkpoint phrases and passage text |
| Parakeet ONNX or Moonshine | 9091 | Unavailable |

Use `--nemo-port`, `--whisper-port`, or `--native-port` when your recognition server uses a different port. Low hints use the next checkpoint, Medium includes up to two more, and High includes up to four more, subject to the model's hint limits. For Whisper, the levels also increase the passage word budget. NeMo's phrase-boost weight is controlled by `--boost` on the NeMo server.

For a custom NeMo environment, use `--nemo-distro`, `--nemo-python` and
`--nemo-model`. The default Python lives in the selected WSL user's home directory.

Choose the passage and model, configure hints and recording, then select **Start experience**. Wait for **Listening** before reading. The panel marks each checkpoint the matcher fires. **End experience** stops capture and waits for the client to finish. Transcripts are written locally under `output/operator-sessions`. Each session writes a WAV there only when **Save recording** is on.

## Projection and calibration

The Windows launcher prepares a selected-story project and opens it in MapMap
from **Preflight → Open MapMap**. It loads only the selected book's scenes, and
MapMap confirms the first video frame before the panel crossfades to the scene.
**Edit MapMap cues** assigns scenes to checkpoints. **Preflight → Import scenes**
adds new media from the [scenes folder](../scenes/README.md) to the master project
when MapMap is closed. Use the **Output layout** controls to fit the fullscreen
canvas, preview the three-wall geometry, and save it across all scenes.

## Legacy Sky Garden handoff

Open **Start MapMap.cmd** from the handoff yourself. When the Sky Garden spoken-cue project is open, launch the panel with the path to the bundled bridge. For the handoff extracted under this checkout, use:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel --mapmap-bridge '.\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff\Reading Pod MapMap\Sky Garden\play_cue.py'
```

Start **Mila and the Sky Garden** and read the first checkpoint. When `seed_found` fires, MapMap receives the Silver Seed video and soundtrack cue by default. The beginning and end of each session send the calibration reset. Other passages start with checkpoint tracking and any local sound effects configured in their manifests. Set `--osc-port` if you started MapMap on a port other than 12345.

While the panel is idle, choose a passage and open **Edit MapMap cues** above its checkpoints. Choose a cue to assign it, or select **No MapMap cue** to restore the checkpoint’s ordinary local playback. Assignments save under `output/operator-mapmap` for the current project. A video with a soundtrack replaces the checkpoint’s local sound. Stills and silent videos keep it.

Set **Scene transition** under **Preflight** to change the default 450 ms crossfade or select **Cut**. This setting saves with the project’s assignments. The panel holds the outgoing scene while preparing the next source and overlaps the two cues. The bundled OSC receiver provides no frame-ready message, so video cues get a short lead-in for the player to seek and decode. Replaying the same source keeps it visible while it restarts. Start, end, and manual reset still restore the calibration grid.

To offer more cues, add local image or video sources with visible mapping layers to the same MapMap project. Set each cue source’s opacity to zero so it stays hidden until triggered. Set video cue volume to zero before saving. Restart the panel after saving the project to refresh the cue list. To use a different saved project, open it in MapMap and start the panel with `--mapmap-project` set to that file as well as `--mapmap-bridge`.
