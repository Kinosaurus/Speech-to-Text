# Bundled story sounds

These are original, procedurally synthesized test effects created for this
project. They contain no recorded speech or third-party samples. They are
stylized cues for trying the pod, rather than recordings of real animals or
finished production sound design. All files are mono 44.1 kHz, 16-bit PCM WAV,
with short fades and peak amplitude 0.55 (before the player's volume control).

| Story | Checkpoint sounds |
| --- | --- |
| Mila and the Sky Garden | Chime, rustling leaves, breeze, bell |
| Horse | Rhythmic hoofbeats |
| Fat Cat | Purr, playful tumble |
| Tea | Pouring tea, kettle, broom sweeping |
| Little Mermaid | Magical shimmer, soft mysterious tones |
| Maya and the Rainy Garden pilot | Rain, umbrella opening, pond splash, umbrella on a hook |

Manifests point here using paths relative to their own location. No
`--sound_dir` is needed. Each cue plays once; ambience does not loop yet.
The Sky Garden seed retains its authored one-second sound delay.

Preview any cue:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.play_sound assets/sounds/horse_hooves.wav
```

Rebuild the 16 story cues deterministically:

```powershell
.\.venv\Scripts\python.exe assets/sounds/generate_story_sounds.py
```

`demo_chime.wav` is the earlier standalone wiring-test cue and is not rebuilt
by this script. See [live reading instructions](../../docs/SOUND_PLAYBACK.md).
