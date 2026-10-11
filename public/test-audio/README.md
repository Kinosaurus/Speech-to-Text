# Test recordings

Drop WAV/MP3 recordings here to replay them through the app instead of a
live microphone. Audio files in this folder are **git-ignored** (they may
contain children's voices); only this README and `recordings.json.example`
are committed.

To list recordings in the app's dropdown, create `recordings.json`:

```json
[
  { "label": "Good reader",       "file": "good_reader.wav" },
  { "label": "Skips line 2",      "file": "skips_line.wav" },
  { "label": "Re-reads line 2",   "file": "rereads_line.wav" }
]
```

Tips:
- Mono, 16 kHz or 44.1 kHz WAV works best.
- Recordings play in real time (a 30 s clip takes 30 s).
- You can also pick any file from your computer with the file chooser.
