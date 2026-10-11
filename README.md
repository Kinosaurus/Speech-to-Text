# Books to Life: KeenASR Reading Pod

A browser-based reading companion. A child reads a story aloud, the app
listens with on-device speech recognition ([KeenASR](https://keenresearch.com/)),
and **checkpoint phrases** in the text trigger events (the demo logs them;
the plan is to drive lighting, visuals and sound effects in a reading pod).

Everything runs locally in the browser: no audio leaves the device.

## Features

- Real-time oral-reading recognition with incremental word alignment
- Checkpoints defined in JSON by word range, so any story can be added
- Forgiving matching for young readers: partial credit for mispronounced
  words, tolerant of word endings ("pretty" / "prettiest")
- Skipped checkpoints are detected and **recovered** if the child re-reads them
- Reading accuracy and word error rate after each attempt
- Zero build step: plain ES modules, a tiny Python server

## Quick start

### 1. Requirements

- Python 3.8+ (standard library only, see `requirements.txt`)
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
microphone, then **Start Reading**.

> Use `localhost` (or HTTPS). Browsers only allow microphone access and
> `SharedArrayBuffer` on secure origins, and `http://192.168.x.x` is not one.

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
│   │   ├── textUtils.js         normalize() / getWords()
│   │   └── alignmentHelpers.js  word-highlighting helpers (not wired in yet)
│   ├── books/
│   │   └── little-mermaid/
│   │       ├── full_text.txt
│   │       └── checkpoints.json
│   └── vendor/keenasr/          proprietary SDK + model (git-ignored)
```

## How it works

1. `app.js` loads `full_text.txt` and `checkpoints.json` and validates that
   each checkpoint's word range really points at its `checkpoint_text`.
2. KeenASR builds an oral-reading decoding graph from the passage.
3. While the child reads, each partial result is aligned against the text
   (`TextAligner.incrementalAlign`).
4. `checkpointEngine.js` scores each checkpoint using the aligner's matched
   words plus a tolerant check of what was just said. A checkpoint becomes
   `triggered` after a couple of consecutive passes, or on the final result.
5. If the reader moves on without triggering one it becomes `skipped`,
   and it can still be `triggered` (flagged `recovered`) if re-read nearby.

## Adding a book

Create `public/books/<name>/` with two files, then set `BOOK_NAME` in
`public/src/app.js`.

`full_text.txt`: the exact text to be read.

`checkpoints.json`:

```jsonc
{
  "book_id": "my-book",            // letters/digits/-/_ ; used in the graph name
  "title": "My Book",
  "min_coverage": 0.6,             // share of checkpoint words needed
  "stability": 2,                  // consecutive passes needed
  "alignment": {
    "recovery_after": 3,           // words past a checkpoint before "skipped"
    "backtrack_words": 32          // how far back a re-read can still recover
  },
  "checkpoints": [
    {
      "id": "unique_id",
      "checkpoint_position": 1,    // order in the story
      "checkpoint_text": "She had the prettiest legs on earth",
      "word_start": 10,            // inclusive, counted in whitespace-separated words
      "word_end": 17,              // exclusive
      "effect": { "...": "reserved for lighting/sound, not used yet" }
    }
  ]
}
```

`word_start`/`word_end` count whitespace-separated words from 0, so the
validator can tell you when the text and the positions disagree.

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
