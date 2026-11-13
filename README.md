# Books to Life: KeenASR Reading Pod

A browser-based reading companion. A child reads a story aloud, the app
listens with on-device speech recognition ([KeenASR](https://keenresearch.com/)),
and **checkpoint phrases** in the text trigger events (the demo logs them;
the plan is to drive lighting, visuals and sound effects in a reading pod).

KeenASR runs in the browser. The local Python server receives transcript updates
for checkpoint matching. Audio stays on the device.

## Features

- Real-time oral-reading recognition with story-specific vocabulary
- Guarded checkpoint status and cue events at stability 2
- A 25-second listening window and a two-minute attempt limit
- Reading accuracy and word error rate after each attempt
- **Live microphone or recorded audio**: switch in the UI, handy for demos
  and repeatable testing
- Zero build step: plain ES modules and a local Python server

## Quick start

### 1. Requirements

- Python 3.10+ with `pip install -r requirements.txt`
- A recent Chrome or Edge (Safari is supported by KeenASR but less tested here)
- A microphone
- Internet access on first load (Preact is imported from `esm.sh`)
- The KeenASR Web SDK and an acoustic model, which you must obtain yourself
  (see below)

### 2. Add the KeenASR files

The SDK and model are proprietary and are **not** in this repository. Copy
them into `public/vendor/keenasr/` as described in
[`public/vendor/keenasr/README.md`](public/vendor/keenasr/README.md):

```
public/vendor/keenasr/
├── keenasr-web.js
├── KeenASRCore.js
├── KeenASRCore.wasm
├── KeenASRCore.aw.js
├── KeenASRCore.ww.js
└── models/keenAK3m-nnet3chain-en-us.tgz
```

### 3. Run

```bash
python server.py
```

Open <http://localhost:8000>, click **Initialize KeenASR**, allow the
microphone, then **Start Reading**. Open <http://localhost:8000/?book=tea>
for the Tea trial.

> Use `localhost` (or HTTPS). Browsers only allow microphone access and
> `SharedArrayBuffer` on secure origins, and `http://192.168.x.x` is not one.

## Live microphone or recorded audio

Use the **Audio source** box on the page.

- **Live microphone**: the default.
- **Recorded audio**: pick a file from your computer, or choose one listed in
  `public/test-audio/recordings.json` (see
  [`public/test-audio/README.md`](public/test-audio/README.md)).

How it works: the KeenASR web SDK has no "process a file" function; it
always listens to `getUserMedia()`. `src/audioSource.js` wraps
`getUserMedia()` so that, in recording mode, the SDK receives a stream that
plays your file instead of the microphone. Consequences:

- Recordings play **in real time** (a 30 s clip takes 30 s).
- You can switch source between attempts without re-initialising.
- In recording mode, "Stop Reading" stops playback and recognition. The next
  attempt plays the selected recording from the beginning.
- If you initialise in recording mode and later switch to the microphone,
  the browser asks for microphone permission at that point.
- This relies on how the SDK currently obtains audio, so re-test after
  upgrading the SDK.

Alternative with no code: start Chrome with
`--use-fake-device-for-media-stream --use-fake-ui-for-media-stream
--use-file-for-fake-audio-capture=path\to\file.wav`.

## Project structure

```
.
├── server.py                    dev server (adds the headers KeenASR needs)
├── requirements.txt
├── LICENSE
├── public/                      everything the browser loads
│   ├── index.html
│   ├── src/
│   │   ├── app.js               UI, KeenASR setup, start/stop flow
│   │   ├── checkpointEngine.js  decides when a checkpoint is triggered
│   │   ├── audioSource.js       live microphone <-> recorded audio switch
│   │   ├── textUtils.js         normalize() / getWords()
│   │   └── alignmentHelpers.js  word-highlighting helpers (not wired in yet)
│   ├── test-audio/              optional recordings (audio git-ignored)
│   ├── books/
│   │   └── little-mermaid/
│   │       ├── full_text.txt
│   │       └── checkpoints.json
│   └── vendor/keenasr/          proprietary SDK + model (git-ignored)
```

## How it works

KeenASR streams cumulative transcripts to the local server. The server uses the
guarded split matcher from main (`90a8710`) at stability 2 with the committed
story manifests. It returns reading position and checkpoint status to the
browser. Only an authorized matcher trigger produces a cue event in the display.

## Adding a book

Create a folder under `public/books/` with a guarded matcher manifest
(`checkpoints.json`) and the corresponding passage (`full_text.txt`). Use the
Tea and Little Mermaid manifests as examples. Register the book in
`public/src/app.js` and `guarded_sessions.py`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Specify a Cross-Origin Embedder Policy to stop this frame from being blocked" | The page isn't served by `server.py`, or the browser cached an old response. Run `python server.py`, hard-reload (Ctrl+Shift+R), and check `crossOriginIsolated` is `true` in the console. |
| "Failed to untar decompressed ASR Bundle" | The `.tgz` must be served with `Content-Encoding: gzip`. `server.py` does this; other servers need the same setting. |
| "Failed to fetch ASR bundle" / 404 on the model | The model isn't at `public/vendor/keenasr/models/`, or the file name differs from `MODEL_URL` in `app.js`. |
| 404 on `KeenASRCore.aw.js` | The file was renamed (e.g. `_aw`). Restore the dotted name. |
| "Decoding graph name … contains forbidden character '-'" | Graph names may only use letters, digits and `_`. `app.js` already sanitises `book_id`. |
| Page stuck on "Loading reading app…" | Preact is loaded from `esm.sh`; check your internet connection. |

## Roadmap

See the "Ideas" list in the project notes / issues. Effects (light, GIF,
sound) are defined in the JSON but not played yet.

## License

Code in this repository: MIT, see [`LICENSE`](LICENSE).
The KeenASR SDK and models are **not** included and are covered by Keen
Research's own license.

## Acknowledgements

- [KeenASR](https://keenresearch.com/) for on-device speech recognition
- [Preact](https://preactjs.com/) for the UI
