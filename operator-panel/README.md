# Reading Pod operator panel

From the Speech-to-Text repository root in PowerShell, build the React app and start the local panel server.

```powershell
npm.cmd --prefix operator-panel ci
npm.cmd --prefix operator-panel run build
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel
```

Open [the operator panel](http://127.0.0.1:8765) manually. The panel does not open a browser or start MapMap or a recognition server. Start the recognition server for your selected model using the existing [runtime instructions](../docs/RUNNING.md).

| Model | Default port | Reading hints |
| --- | --- | --- |
| Parakeet NeMo | 9097 | Upcoming checkpoint phrases |
| Whisper Base, Tiny, Medium (English) | 9090 | Upcoming checkpoint phrases and passage text |
| Parakeet ONNX or Moonshine | 9091 | Unavailable |

Use `--nemo-port`, `--whisper-port`, or `--native-port` when your recognition server uses a different port. Low hints use the next checkpoint, Medium includes up to two more, and High includes up to four more, subject to the model's hint limits. For Whisper, the levels also increase the passage word budget. NeMo's phrase-boost weight is controlled by `--boost` on the NeMo server.

Choose the passage and model, configure hints and recording, then select **Start experience**. Wait for **Listening** before reading. The panel marks each checkpoint the matcher fires. **End experience** stops capture and waits for the client to finish. Transcripts are written locally under `output/operator-sessions`. Each session writes a WAV there only when **Save recording** is on.

## Sky Garden projector cue

Open **Start MapMap.cmd** from the handoff yourself. When the Sky Garden spoken-cue project is open, launch the panel with the path to the bundled bridge. For the handoff extracted under this checkout, use:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.operator_panel --mapmap-bridge '.\output\mapmap-other-pc\MapMap-Reading-Pod-Handoff\Reading Pod MapMap\Sky Garden\play_cue.py'
```

Start **Mila and the Sky Garden** and read the first checkpoint. When `seed_found` fires, MapMap receives the Silver Seed video and soundtrack cue. The beginning and end of each session send the calibration reset. The other passages use checkpoint tracking and any local sound effects configured in their manifests. Set `--osc-port` if you started MapMap on a port other than 12345.
