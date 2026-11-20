# Reading Pod operator panel

For this PC's complete launch sequence, including the selected-story MapMap
launcher on OSC port `12346`, use the [Reading Pod startup guide](../docs/READING_POD_STARTUP.md).
The commands below also cover standalone and legacy handoff configurations.

From the Speech-to-Text repository root in PowerShell, build the React app and start the local panel server.

```powershell
npm.cmd --prefix operator-panel ci
npm.cmd --prefix operator-panel run build
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel
```

Open [the operator panel](http://127.0.0.1:8765) manually. Under **Preflight**, **Start recognition server** starts the installed WSL Parakeet NeMo environment, and **Restart recognition server** ends an active reading session before reloading NeMo. Status changes from **Starting…** or **Restarting…** to **Ready** only after a Windows WebSocket client receives `SERVER_READY`. Existing ready servers are reused. Checks refresh automatically while the panel is open, and startup diagnostics stay local in `output/operator-server/nemo.log`. NeMo keeps running when the panel closes.

The default server controls use WSL distro `Ubuntu`, Python `/home/heart/.venvs/books-to-life-nemo/bin/python`, and the existing model cache. Use `--nemo-distro`, `--nemo-python`, and `--nemo-model` to configure another installed environment. These controls manage NeMo on Windows. For the other listed engines, follow the [runtime instructions](../docs/RUNNING.md). Under **Preflight**, **Open MapMap** runs the Reading Pod launcher with the selected-story project and configured OSC port. The panel shows **Opening…** until MapMap acknowledges the project and owns its UDP listener. Existing connected instances are reused. The launcher also installs any staged renderer update after MapMap has closed. Use `--mapmap-launcher` for a different copy of `Start-Reading-Pod-MapMap.ps1`.

| Model | Default port | Reading hints |
| --- | --- | --- |
| Parakeet NeMo | 9097 | Upcoming checkpoint phrases |
| Whisper Base, Tiny, Medium (English) | 9090 | Upcoming checkpoint phrases and passage text |
| Parakeet ONNX or Moonshine | 9091 | Unavailable |

Use `--nemo-port`, `--whisper-port`, or `--native-port` when your recognition server uses a different port. Low hints use the next checkpoint, Medium includes up to two more, and High includes up to four more, subject to the model's hint limits. For Whisper, the levels also increase the passage word budget. NeMo's phrase-boost weight is controlled by `--boost` on the NeMo server.

Reading hints start enabled at Medium for the default Parakeet NeMo selection. NeMo receives checkpoint phrases, with the current cue and up to two ahead, subject to the phrase budget. The tracker retains the full story text for alignment and interruption recovery. A cue awaiting its ending stays in the hint window until its permission decision resolves. Hints can be switched off for comparison. Whisper also uses its bounded passage prompt.

Choose the passage and model, configure hints and recording, then select **Start experience**. Wait for **Listening** before reading. The panel marks each checkpoint the matcher fires. **End experience** stops capture and waits for the client to finish. Transcripts are written locally under `output/operator-sessions`. Each session writes a WAV there only when **Save recording** is on.

In the Windows Reading Pod setup, start MapMap with **Start Reading Pod MapMap.cmd**. Selecting a passage loads its assigned projection scenes into the existing MapMap window. The shared media, checkpoint assignments, and saved wall geometry come from the master project. Use **Edit MapMap cues** to assign scenes from the entire library.

For a custom launch, point `--mapmap-story-dir` at a local runtime directory and keep `--mapmap-project` set to the master project. The panel prepares `Reading Pod - Selected Story.mmp` in that directory. Start the compatible MapMap build with that file and set the process environment variable `READING_POD_MAPMAP_PROJECT` to the same absolute file path.

## Sky Garden projector cue

Open **Start MapMap.cmd** from the handoff yourself. When the Sky Garden spoken-cue project is open, launch the panel with the path to the bundled bridge. For the handoff extracted under this checkout, use:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel --mapmap-bridge '.\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff\Reading Pod MapMap\Sky Garden\play_cue.py'
```

Start **Mila and the Sky Garden** and read the first checkpoint. When `seed_found` fires, MapMap receives the Silver Seed video and soundtrack cue by default. The beginning and end of each session send the calibration reset. Other passages start with checkpoint tracking and any local sound effects configured in their manifests. Set `--osc-port` if you started MapMap on a port other than 12345.

While the panel is idle, choose a passage and open **Edit MapMap cues** above its checkpoints. Choose a cue to assign it, or select **No MapMap cue** to restore the checkpoint’s ordinary local playback. Assignments save under `output/operator-mapmap` for the current project. A video with a soundtrack replaces the checkpoint’s local sound. Stills and silent videos keep it.

Set **Scene transition** under **Preflight** to change the default 450 ms crossfade or select **Cut**. This setting saves with the project’s assignments. With the Reading Pod launcher, each video opens when needed. The panel preloads the next expected video silently. If a reader skips ahead, it prepares the later cue, holds the current scene until MapMap confirms the first frame, and crossfades. Afterward it releases the old decoder and prepares the next expected video. The legacy MapMap path uses a short seek and decode lead-in. Replaying the same source keeps it visible while it restarts. Start, end, and manual reset restore the calibration grid.

With MapMap fullscreen on Windows, **Preflight → Output layout → Fit output** uses the current MapMap canvas size each time you click it. The wall editor uses the detected output dimensions and reopens with the latest Fit or wall-preview coordinates sent by this panel to the same MapMap process. Fit and wall previews apply a complete set of corners in one confirmed renderer operation. This avoids per-corner anti-folding constraints clipping a wall during a large move. Temporary previews leave both project files unchanged. **Reset draft** restores the saved master geometry. A new story load or MapMap process starts from its saved layout. Use **Manual dimensions** for a specific size or **Restore original** to apply the saved destination coordinates. Choose the physical monitor in MapMap under **View → Output screen**.

Use **Preflight → Output layout → Edit wall layout** to edit the calibration corners directly in the panel. Drag inside a wall shape to select and move the entire wall, preserving its shape. Drag a corner or nudge it with arrow keys to reshape it. **Ctrl+Z** undoes a drag or nudge, and **Ctrl+Y** or **Ctrl+Shift+Z** redoes it. Undo and Redo buttons are also available. Each drag is one undo step, and history lasts for the current editor session. The projector preview updates automatically after a 250 ms pause in dragging or arrow-key nudging. You can keep editing while a preview is sent. **Preview on projector** resends the current draft when needed. Click **Save and apply to all scenes** to save the shared master and update the open selected-story project in the same MapMap window. MapMap applies only destination vertices, keeps the current scene loaded, and confirms the coordinates before the panel reports success. Its selected-story file is updated too. An older renderer needs one launch through **Open MapMap** to install the live-layout update. If a live update fails after saving, the panel keeps the new master revision and shows a retry message. The editor updates compatible three-wall meshes and keeps media, source crops, and checkpoint assignments.

To import a batch, drop media into the shared [scenes folder](../scenes/README.md), save and close MapMap, then choose **Preflight → Import scenes**. The panel saves the updated project and refreshes its cue lists. You can assign scenes immediately and reopen the same project in MapMap when ready to project.

For a custom layout, add local image or video sources with visible mapping layers in MapMap. Set each cue source’s opacity to zero and video volume to zero before saving. Restart the panel after saving the project to refresh the cue list. To use a different saved project, open it in MapMap and start the panel with `--mapmap-project` set to that file as well as `--mapmap-bridge`.
