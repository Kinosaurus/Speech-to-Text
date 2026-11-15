# Story effect sounds

The reading client now plays each emitted checkpoint's `effect.sound` WAV.
Pending, suppressed and skipped effects stay quiet. Each checkpoint plays once
per client session. Sounds preload before reading and mix on a separate output
thread, so overlapping effects do not queue behind each other or block ASR.

Try the bundled original synthesized chime without a microphone or ASR server:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.checkpoint_demo --checkpoints docs/sound-demo/checkpoints.json --play_sounds
```

This runs a real matcher update through the sound trigger. To preview just audio:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.play_sound assets/sounds/demo_chime.wav
```

For live reading, use the same manifest with the NeMo server running:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model parakeet-nemo --port 9097 --matching_mode split --no_book_context --checkpoints docs/sound-demo/checkpoints.json
```

Read “The small frog jumped into the pond.” The demo uses one confirmation for
a quick wiring check; use the normal story's stability settings for pod trials.

## Read an existing story with sounds

All five existing story manifests now include bundled, original synthesized
test effects, as does the Maya rain-and-frog pilot. No sound-folder argument or
downloads are needed. With the NeMo server running, try Horse:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model parakeet-nemo --port 9097 --matching_mode split --no_book_context --checkpoints recordings/library/stories/horse/readers/horse/checkpoints.json
```

Read the complete [Horse passage](../recordings/library/stories/horse/readers/horse/passage.txt)
aloud at a natural pace, continuing after the checkpoint. Hoofbeats should play
after “I saw a big horse at the farm.” To hear every Horse cue without a server:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.checkpoint_demo --checkpoints recordings/library/stories/horse/readers/horse/checkpoints.json --play_sounds
```

For another story, replace the manifest path:

| Story | Manifest | Sounds |
| --- | --- | --- |
| Tea | `recordings/library/stories/tea/readers/tea/checkpoints.json` | Pour, kettle, broom |
| Fat Cat | `recordings/library/stories/fat_cat/readers/fat_cat/checkpoints.json` | Purr, playful tumble |
| Little Mermaid | `recordings/library/stories/little_mermaid/readers/little_mermaid/checkpoints.json` | Magical shimmer, mysterious tones |
| Mila and the Sky Garden | `recordings/library/stories/sample/readers/demo/checkpoints.json` | Chime, leaves, breeze, bell |
| Maya and the Rainy Garden | `docs/pilot/singapore/checkpoints.json` | Rain, umbrella, splash, hook |

Story passages live alongside their manifests as `passage.txt`; the Maya pilot
uses `docs/pilot/singapore/passage.txt`. These are stylized synthesized test cues,
not natural animal recordings. Restart the client to replay a story from the
beginning. See the [asset notes](../assets/sounds/README.md) for cue details.

## Add story sounds

Set a checkpoint's payload, for example:

```json
"effect": {
  "effect_id": "frog_jump",
  "sound": "sounds/splash.wav",
  "sound_delay": 0
}
```

Paths resolve relative to the checkpoint manifest, or to `--sound_dir` when
provided. Absolute paths also work. `sound_delay` is **milliseconds** (1000 is
one second). Files must be uncompressed 16-bit mono or stereo WAV; sample rates
are converted to 44.1 kHz stereo in memory. MP3 and compressed WAV are not supported.
The client uses the existing PyAudio, NumPy and SciPy dependencies.

Playback is enabled automatically in `run_client`. Options:

- `--sound_dir C:\pod\sounds`: asset folder for the manifest's sound paths.
- `--sound_volume 0.5`: amplitude from 0 to 1; default 0.5. The mixer clips the
  combined output if overlapping sounds exceed full scale.
- `--sound_output_device 3`: PortAudio output device index; otherwise OS default.
- `--mute_effects`: disable effect audio for benchmarks or silent tracking.
  `--mute_audio_playback` only mutes the input recording, not story effects.

Missing or invalid sounds log a warning and leave speech tracking running.
Payloads with only `effect_id` have no audio. The five existing stories and
Maya pilot now point to bundled WAVs. Additional imported/local manifests may
still have placeholder filenames; supply their files or update their `sound`
paths. Bundled sounds are test cues, not finished story sound design.

Normal file/demo completion finishes scheduled sounds; ending microphone capture
or a propagated interruption cancels playback.
A speaker/output failure logs an error while speech tracking continues. The
standalone preview exits unsuccessfully on output failure. Ambience currently
plays once too: looping, fades, ducking, and scene-based stop controls are future work.
No visual or lighting control is connected. Test with the actual pod speakers
and microphone to check how effect audio affects recognition.
