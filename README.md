# Books to Life Pod

## Quickstart — test on a Windows PC with an NVIDIA GPU

Use **two terminals** in the project folder: Docker runs the speech-recognition
**server** on the GPU, while the Windows Python **client** sends microphone or
file audio to it. Both programs run locally on your PC.

For deployment on a board, follow [Jetson setup](JETSON_SETUP.md) or
[Raspberry Pi CPU setup](PI4_SETUP.md). A PC without a compatible NVIDIA GPU can
use the [native CPU instructions](#run-locally) below.

To compare Whisper, Parakeet Unified and Moonshine Streaming on the shared
child recordings, see the [isolated ASR benchmark](benchmarks/README.md).
It reuses the existing Whisper GPU image and keeps extra model downloads separate.

### 1. Prepare the Windows client once

If your `.venv` already runs `run_client.py`, skip this step. Otherwise, install
Python 3.12 and run these commands from the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-client.txt
.\.venv\Scripts\python.exe -m pip install whisper-live==0.10.0 --no-deps
```

These commands install the client dependencies. The server has its own
dependencies inside Docker; you do not need to activate `.venv` when using the
explicit Python path shown here.

### 2. Start the GPU server — Terminal 1

Open **Docker Desktop** and wait for its engine to start. Use Linux containers
with the WSL2 backend and a compatible NVIDIA driver, as described in
[Docker's Windows GPU setup](https://docs.docker.com/desktop/features/gpu/).
Stop any other server using port `9090` before continuing.

On the first run, execute these commands **one at a time**, waiting for each to
finish successfully:

```powershell
docker compose -f compose.gpu.yaml build
docker compose -f compose.gpu.yaml run --rm asr python run_server.py --device cuda --check_device
docker compose -f compose.gpu.yaml run --rm asr python prepare_models.py --model small.en --device cuda --verify_inference
```

The device check should report `Device=cuda` and your GPU name. Model preparation
downloads `small.en` and VAD, then should report `[VERIFY] ... passed on cuda`.
That check verifies inference works; its timing is not a reading-latency test.
The first build and download can take several minutes.

Start the server and leave this terminal running:

```powershell
docker compose -f compose.gpu.yaml up
```

For later sessions, open Docker Desktop and run just the `up` command. The
downloaded models remain in the `gpu-model-cache` volume.

### 3. Test recognition — Terminal 2

Open another terminal in the same project folder. **Choose one** of these tests.
Neither requires a checkpoint file.

**Read into your default microphone:**

```powershell
.\.venv\Scripts\python.exe run_client.py --model small.en --audio_chunk 1024 --n_display_segments 20 --enable_timestamps
```

**Transcribe a recording:** replace the quoted path with your own audio file.

```powershell
.\.venv\Scripts\python.exe run_client.py --model small.en --files "C:\Users\heart\OneDrive\Documents\Audacity4\KidDog1.wav" --mute_audio_playback --n_display_segments 20 --enable_timestamps
```

WAV, M4A and MP3 recordings can be decoded by the client. `--mute_audio_playback`
only stops playback through your speakers; recognition still receives the file
directly. Remove it if you want to hear the recording while testing.

The terminal normally shows only the latest four transcript segments. These
commands show up to 20, with timestamps. Older text scrolling out of view does
not mean it was deleted; the session transcript is saved to `output.srt` when
the client finishes. Partial recognition can also change as more audio arrives.

### Record computer audio with Audacity, including YouTube

You can use Audacity to capture **internal computer audio** for repeatable
recognition tests, instead of playing it through speakers into a microphone:

1. In Audacity's **Audio Setup / audio-device settings**, choose
   **Windows WASAPI** as the audio host.
2. Choose the speaker or headphone output you are listening through as the
   recording device, with **`(loopback)`** in its name.
3. Turn off input monitoring and keep other apps/notifications quiet: loopback
   can capture all sounds playing through that output.
4. Start the YouTube video or other audio, then click **Record** in Audacity.
   Click **Stop** when you have the passage you want to test.
5. Use **File → Export audio** (`Ctrl+Shift+E`). For a simple ASR test, export
   **WAV, Mono, 16000 Hz, Signed 16-bit PCM**, then pass that file to the command
   above. Recordings at 44100 or 48000 Hz also work; the client resamples them.
   Exporting at a higher rate does not add detail to the original recording.

See Audacity's official [desktop-audio recording guide](https://support.audacityteam.org/basics/recording-desktop-audio)
and [audio export guide](https://www.audacityteam.org/manual/getting-started/export-your-audio/).
Audacity `.aup4` / `.aup3` files are projects; **export an audio file** before
using them with this client.

### Use the shared test recordings

The [shared audio folder](examples/audio/README.md) contains eight resampled
WAV recordings that groupmates can test after pulling the repository. The files
are 16 kHz mono audio and can be supplied directly to `--files`:

```powershell
.\.venv\Scripts\python.exe run_client.py --model medium.en --files .\examples\audio\tea.wav --mute_audio_playback --checkpoints .\examples\tea_story.json
```

Use the matching checkpoint manifest listed in the shared audio instructions.
Dog, Dragon, Nickel and Recording 2 currently have no corresponding manifests;
test those without `--checkpoints`. Run one recording per client session.

Keep `--checkpoints` out of tests using unrelated videos or recordings. These
tests measure recognition; also test a child reading into the intended pod
microphone to assess the actual recording conditions.

### 4. Test checkpoint tracking when ready

Choose the manifest matching the passage being read. `--checkpoints` accepts
any compatible book JSON file, so switching passages does not require code
changes or restarting the ASR server. Restart the client with the new manifest.

| Passage | Checkpoint manifest | Checkpoints |
|---|---|---|
| [The Little Mermaid excerpt](examples/little_mermaid_passage.txt) | [little_mermaid_story.json](examples/little_mermaid_story.json) | 2 |
| [Mila and the Sky Garden](examples/sample_passage.txt) | [sample_story.json](examples/sample_story.json) | 4 |
| [Fat Cat phonics passage](examples/fat_cat_passage.txt) | [fat_cat_story.json](examples/fat_cat_story.json) | 2 |
| [Horse farm passage](examples/horse.txt) | [horse_story.json](examples/horse_story.json) | 1 |
| [Tea passage](examples/tea_passage.txt) | [tea_story.json](examples/tea_story.json) | 3 |

For the Little Mermaid excerpt, read the passage aloud while running:

```powershell
.\.venv\Scripts\python.exe run_client.py --model small.en --audio_chunk 1024 --checkpoints .\examples\little_mermaid_story.json
```

For your recording, replace the quoted audio path below with your file's path:

```powershell
.\.venv\Scripts\python.exe run_client.py --model small.en --files ".\recordings\LittleMermaid.wav" --mute_audio_playback --checkpoints .\examples\little_mermaid_story.json
```

Watch `[TRANSCRIPT]` for recognized speech, `[ALIGN]` for book tracking and
`[TRIGGER]` for a confirmed checkpoint's effect payload. The prototype prints
effects; physical lighting, speaker and projector control are not implemented.
The Little Mermaid sample has two checkpoints:

- **`mermaid_has_legs`**: "She had the prettiest legs on earth" — a warm,
  gentle daylight ambience after her transformation.
- **`mermaid_cannot_speak`**: "And the little mermaid could not speak" — a
  quieter blue ambience during her silent encounter with the prince.

The visual/audio filenames are placeholders. Surrounding book text helps
confirm progress even if an anchor is misread; triggers can occur just after
the anchor. Each checkpoint should trigger at most once per client session.
Look for two `[TRIGGER]` lines to verify both fired. Reaching the end can also
mean an earlier checkpoint was skipped, so check `[SKIPPED]` too.

Selecting a checkpoint manifest also enables **automatic book hints for
Whisper**: the next expected checkpoint and up to two future checkpoint
phrases become hotwords, with a short surrounding passage as the prompt.
The hint window moves with confirmed reading progress. Look for
`[BOOK_CONTEXT] Hotwords`, `Passage prompt`, and `Server supports live hint updates`.
Hints guide recognition; they do not verify pronunciation or count as a match.
Use a recording of the selected passage, since a different book would bias ASR
toward unrelated words.

For a comparison without automatic hints, add `--no_book_context` to the same
command. Explicit `--hotwords` / `--initial_prompt` options still apply and
override their respective generated field.

After updating the code, rebuild and restart the Docker GPU server once:

```powershell
docker compose -f compose.gpu.yaml up -d --build asr
```

An older server can use the startup hints but cannot receive the moving window;
the client reports this without sending incompatible update messages.

Stop the client and server with **Ctrl+C** in their respective terminals.
`docker compose -f compose.gpu.yaml down` removes the stopped containers while
keeping cached models; adding `-v` deletes the cache.

## About the project

Books to Life Pod is an interactive reading enclosure for a child aged 5–10
and a parent or caregiver. It follows a physical book locally and triggers
restrained lighting, sound and visual effects at approved story checkpoints.
The environmental response is intended to reward continued reading without
becoming more important than the book.

This repository contains the **WhisperLive speech-recognition prototype** and
word-sequence checkpoint tracking. The current deployment target is a **Jetson
Orin Nano Super 8GB running ASR on its NVIDIA GPU and matching on its CPU**.
[JETSON_SETUP.md](JETSON_SETUP.md) covers Jetson deployment and laptop testing;
[PI4_SETUP.md](PI4_SETUP.md) retains the Pi CPU alternative. The app code is
shared across these environments. The PC GPU container has been built and
tested on an RTX 4060 laptop; the Jetson GPU image and board performance remain
unverified. Moonshine and the Pi 5 hardware design below remain future
alternatives; physical effect playback is not yet implemented.

## Project at a glance

| Item | Current direction |
|---|---|
| Users | One child and one parent/caregiver |
| Enclosure | Cozy segmented circular pod, approximately 198 × 196 × 115 cm |
| Interaction | Read the complete physical book aloud |
| Book identification | RFID/NFC |
| Runtime | Offline-first, with no cloud dependency during reading |
| Current compute target | Jetson Orin Nano Super 8GB; JetPack 6.2 baseline |
| Current ASR deployment | Local WhisperLive/faster-whisper, GPU float16; start with small.en |
| Development PC | Same Python code; CPU or a separate NVIDIA GPU deployment |
| Pi alternative | Pi 4/5, 64-bit OS, CPU int8 inference |
| Future ASR candidate | Moonshine streaming, to be evaluated on hardware |
| Current ASR prototype | WhisperLive with `faster-whisper` |
| Text alignment | Local word-sequence alignment against book passages, with fuzzy word comparisons |
| Effects | Deterministic state machine controlling light, audio and visuals |
| Budget ceiling | S$4,000; current preliminary allocation is S$3,520 |

The full decision history, hardware comparison, latency estimates and bill of
materials are in [BOOKS_TO_LIFE_POD_NOTES.md](BOOKS_TO_LIFE_POD_NOTES.md).

## Experience principles

- The child keeps looking at and progressing through the physical book.
- Visuals provide atmosphere—grass, clouds, weather or colour—not another
  narrative that competes for attention.
- Effects happen at paragraph or page checkpoints, not on every word.
- Lighting transitions are slow, diffused and low in brightness.
- Environmental audio ducks while someone is reading.
- The reading experience continues working when internet access is poor or
  completely unavailable.
- The enclosure and electronics tray can be transported, serviced and copied.

## Intended architecture

```text
RFID/NFC book scan
        │
        ▼
Load approved book map and effect timeline

Child reads aloud
        │
        ▼
Directional wired USB microphone
        │
        ▼
Local noise reduction + voice activity detection
        │
        ▼
Local streaming ASR produces partial text
        │
        ▼
Word-sequence alignment tracks text within nearby book passages
        │
        ▼
Confidence + progress guards confirm the checkpoint
        │
        ▼
Deterministic state machine
        │
        ├── ambient lighting
        ├── spatial/ambient audio
        └── simple supporting visual
```

An ESP32 or Raspberry Pi Pico should handle RFID, buttons and electrical
control over USB serial. GPIO must only provide control signals; it must not
directly power LED strips, speakers, motors or the projector.

## Repository contents

| File | Purpose |
|---|---|
| `run_server.py` | Starts a locally hosted WhisperLive server configured for one long reading session |
| `run_client.py` | Streams microphone or file audio and exposes VAD, prompt and hotword tuning |
| `checkpoint_matcher.py` | Forward-only fuzzy checkpoint matcher shared by the demo and live client |
| `alignment_matcher.py` | Default passage tracker: word alignment, confirmation, ambiguity checks and recovery |
| `book_context.py` | Generates bounded passage/hotword hints from confirmed book progress |
| `book_context_client.py` | Streams audio and negotiates live book-hint updates |
| `book_context_server.py` | Applies live hints to the next Whisper inference without reloading its model |
| `checkpoint_demo.py` | Runs the sample checkpoints without a microphone or WhisperLive server |
| `examples/sample_story.json` | Original four-checkpoint sample story and safe placeholder effects |
| `examples/sample_passage.txt` | Short original passage to read during a microphone test |
| `examples/little_mermaid_story.json` | Two-checkpoint manifest for the supplied Little Mermaid excerpt |
| `examples/little_mermaid_passage.txt` | Exact supplied passage for live or recorded reading tests |
| `BOOKS_TO_LIFE_POD_NOTES.md` | Detailed enclosure, hardware, ASR, latency, matching and budget decisions |
| `README.md` | Project overview and prototype instructions |
| `JETSON_SETUP.md` | Jetson GPU setup, laptop testing, model preparation and hardware verification |
| `compose.jetson.yaml` | Both programs on Jetson: GPU ASR plus microphone/alignment client |
| `compose.gpu.yaml` | Laptop GPU server container, paired with a native Windows microphone client |

## Current WhisperLive prototype

The Python launchers evaluate microphones, speech recognition, VAD settings and
story prompts on a development computer, Jetson or Pi. Jetson runs recognition
on CUDA; the Pi alternative uses CPU inference. Both run matching on the CPU.
The Docker profiles package the same ASR engine with platform-specific
dependencies. Recognition speed and child-speech accuracy still require tests
on the intended hardware.

### Prerequisites

- Python 3.12
- PortAudio for live microphone input
- A wired USB microphone
- Enough storage to download the selected Whisper model on first use

Create and activate a virtual environment, then install the upstream package:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Linux, install the PortAudio development package first, following the
[WhisperLive installation instructions](https://github.com/collabora/WhisperLive#installation).

### Run locally

Open two terminals with the virtual environment activated.

Terminal 1—start the server:

```powershell
python run_server.py
```

Terminal 2—transcribe the default microphone:

```powershell
python run_client.py
```

Transcribe an audio file in real time without playing it through the speakers:

```powershell
python run_client.py --files .\sample.wav --mute_audio_playback
```

The defaults are tuned for one English reading pod:

- `base.en`
- English transcription
- VAD enabled
- one client
- four CPU inference threads
- a one-hour maximum connection

For lower latency, test `tiny.en`. If child-speech accuracy is insufficient,
compare it with `base.en` and `small.en` using the same recordings:

```powershell
python run_client.py --model tiny.en
python run_client.py --model base.en
python run_client.py --model small.en
```

### Story-aware recognition

With `--checkpoints`, book hints are generated automatically. By default,
the hotwords contain the next expected checkpoint plus two ahead, capped at
48 words / 320 characters. Each phrase is capped at 16 words / 100 characters.
The prompt contains up to 64 normalized book words / 480 characters, with an
eight-word lookback to retain context during corrections. Whisper's own token
limits still apply. These hints are soft guidance, not constrained decoding.

Hints refresh after a checkpoint advances or the confirmed word position moves
another 16 words. Tentative matches and unrelated speech do not move this
window. The final checkpoint's hints are retained for the remaining passage.
The client and server exchange bounded, revision-numbered controls separately
from audio. The server queues updates per session and applies each prompt and
hotword pair on the ASR thread before its next inference. `[BOOK_CONTEXT] Server
queued hint revision ...` acknowledges receipt; an inference already in progress
continues with its previous hints.

Use `--book_context_lookahead 0` to include only the next checkpoint, or adjust
`--book_context_words` within 8–128. Use `--no_book_context` for a baseline test.
ASR-only tests without `--checkpoints` receive no automatic book hints.

You can also supply manual hints. Each explicit field replaces its automatic
counterpart and stays fixed for that session:

```powershell
python run_client.py `
  --initial_prompt_file .\current-passage.txt `
  --hotwords "NLB,Matilda,Trunchbull"
```

An inline prompt and a prompt file cannot be supplied at the same time. The
same rule applies to `--hotwords` and `--hotwords_file`.

### Test the sample checkpoints

The included sample is an original four-page mini-story called *Mila and the
Sky Garden*. Its placeholder effects print to the terminal; they do not send
commands to real lights or speakers.

Test the matcher without running WhisperLive:

```powershell
python checkpoint_demo.py
```

The default tracker aligns recognized words with full page text. The demo
includes recognition mistakes such as `seed` → `seat` and `flower` → `flour`.
Each scene needs two consistent, distinct transcript updates before it triggers.
Identical text-only updates do not count twice. To type simulated transcripts:

```powershell
python checkpoint_demo.py --interactive
```

For example, enter `She carried it carefully into the quiet garden`, then
extend it with `and pressed it into the warm soil`. The first scene can be
confirmed from its surrounding passage even though its checkpoint phrase was
not read. Timestamped live updates also count a transition from partial to
finalized text as new evidence.

Keep the original phrase-only matcher available for comparison:

```powershell
python checkpoint_demo.py --matching_mode fuzzy
```

For a live microphone test, start `run_server.py` in the first terminal. In a
second terminal run:

```powershell
python run_client.py `
  --model base.en `
  --checkpoints .\examples\sample_story.json `
  --initial_prompt_file .\examples\sample_passage.txt
```

Read [examples/sample_passage.txt](examples/sample_passage.txt) aloud. The
terminal reports the current similarity score and prints `[TRIGGER]` with the
placeholder effect when a checkpoint is confirmed. Useful tuning overrides:

```powershell
python run_client.py `
  --model tiny.en `
  --checkpoints .\examples\sample_story.json `
  --checkpoint_threshold 78 `
  --checkpoint_stability 2
```

Lowering the threshold makes recognition more forgiving but increases false
triggers. Production values must be tuned using recordings from children in
the real enclosure.

If `[TRANSCRIPT]` contains unrelated sentences, troubleshoot speech recognition
before changing alignment thresholds. The client prints the requested model and
default microphone at startup. Check that the intended microphone is selected in
Windows Sound settings, mute other spoken audio, and test in a quiet environment.
For an accuracy comparison, restart the client with `--model small.en`; expect
more computation than `tiny.en` or `base.en`, especially on CPU. Keep the same
matching settings and compare the actual transcript. A larger model is not a
guaranteed fix for poor audio. Restarting both programs also clears the previous
session's buffered speech and recognition context.

### Checkpoint structure

A book manifest contains a `book_id`, full `pages` text, and a `checkpoints`
list. `checkpoint_text` marks an effect location inside that text; the alignment
tracker also uses surrounding words. The nested `effect` object defines the
response:

```json
{
  "book_id": 1,
  "pages": [
    {
      "page": 1,
      "text": "Mary had a little lamb. Its fleece was white as snow."
    }
  ],
  "checkpoints": [
    {
      "id": 1,
      "book_id": 1,
      "checkpoint_position": 1,
      "page": 1,
      "checkpoint_text": "mary had a little lamb",
      "word_start": 0,
      "word_end": 5,
      "effect": {
        "visual": "grass_and_lamb.gif",
        "visual_delay": 500,
        "sound": "lamb.wav",
        "sound_delay": 1000
      }
    }
  ]
}
```

Checkpoint IDs and positions must be unique within a book. Positions are
positive sequence numbers, independent of page numbers; the matcher sorts by
position even if records arrive out of order. Each checkpoint's `book_id` must
match its manifest. Page numbers are positive and unique; pages are sorted by
number. Lighting fields can be retained.

`word_start` and `word_end` are zero-based offsets in the full normalized book
word stream, with the end exclusive. They locate checkpoints independently of
their sequence number. When omitted, the tracker finds the unique normalized
checkpoint phrase within its `page` (or the entire book if page is omitted).
Repeated phrases require a page reference or explicit offsets. Explicit ranges
must contain the exact normalized phrase, follow checkpoint order, and not
overlap. Correct OCR text before exporting these offsets.

`visual` and `sound` may be omitted or set to `null`. Delays are non-negative
integer milliseconds measured from checkpoint confirmation, with omitted delays
meaning zero. The prototype validates and prints the effect payload; it does
not yet schedule playback. Sample media names are placeholders, without bundled
media files. The old `anchor` and `audio` field names have been replaced by
`checkpoint_text` and `sound` in checkpoint records.

Threshold, stability and coverage settings remain at manifest level, with
per-checkpoint overrides. Alignment scores measure matched word similarity
relative to the aligned speech/book spans; they differ from phrase-level
RapidFuzz scores. Re-tune thresholds with actual recordings. Session progress,
triggered IDs and skipped IDs stay in the tracker.

### Alignment and recovery behavior

The tracker uses local dynamic programming over word sequences. It tolerates
substitutions, extra words and missing words, while requiring enough supported
words and rejecting repeated generic words. It evaluates recent transcript
suffixes so an older matched sentence cannot dominate newer speech. The live
client passes timestamped segments: partial revisions replace old text, and
unchanged or merely shortened rolling responses do not add confirmations.
Text-only demo input uses a best-effort overlap/revision merge; use timestamped
segments for live ASR integration.

The scene associated with the latest fully passed checkpoint range is proposed
from the aligned position, even when only its following passage was recognized.
Similar matches in separate scene locations cause the tracker to wait. Confirmed
progress moves forward. A confirmed jump selects only the latest scene and marks
intervening checkpoints skipped, avoiding a burst of outdated effects.

Defaults in the optional `alignment` settings object:

| Setting | Default | Purpose |
|---|---:|---|
| `window_words` | 120 | Forward book-text window from confirmed progress |
| `backtrack_words` | 32 | Earlier context retained for repeats and revisions |
| `transcript_words` | 32 | Maximum recent spoken words used per update |
| `minimum_words` | 5 | Minimum supported words; must be at least 3 |
| `recovery_after` | 3 | Failed fresh updates before each doubling of the search window |
| `recovery_threshold` | 92 | Stricter score floor during recovery |
| `ambiguity_margin` | 4 | Score separation required between distinct scene locations |

After failed fresh speech updates, the forward window expands progressively up
to the remaining book. Silence and duplicate updates do not expand it. The wider
window remains available until a position is confirmed. This is a word window,
not a hard limit of three checkpoints. Wider recovery can take more computation.
Ambiguous repeated passages or poor ASR can still prevent recovery; an operator
page correction interface remains future work.

Run the tracker tests and matching-only benchmarks:

```powershell
python -m unittest discover -s tests -v
python checkpoint_demo.py --benchmark 30
python checkpoint_demo.py --matching_mode fuzzy --benchmark 30
```

Benchmark output excludes audio capture, ASR, waiting for confirmation updates,
asset loading and playback. Measure again on the Raspberry Pi with representative
books; this is not an end-to-end pod latency estimate. The speech recognition
backend remains WhisperLive; alignment does not install or replace the ASR model.

### Useful latency controls

| Option | Starting value | Effect |
|---|---:|---|
| `--same_output_threshold` | `3` | Lower values commit partial text sooner but may be less stable |
| `--min_silence_ms` | `160` | Lower values finish speech chunks sooner but may split hesitant reading |
| `--speech_pad_ms` | `120` | Preserves context immediately before and after detected speech |
| `--vad_threshold` | `0.5` | Higher values require stronger evidence of speech |
| `--no_vad` | off | Only use for controlled experiments |

For the server, begin with the number of physical CPU cores:

```powershell
python run_server.py --omp_num_threads 4 --max_clients 1
```

Do not enable batch inference for one pod; the batching window adds delay and
is useful mainly when serving multiple concurrent clients.

## Planned embedded runtime

The current deployment evaluates WhisperLive on Jetson. Moonshine remains an
alternative to benchmark if recognition or latency is inadequate. The earlier
Pi-oriented architecture below lists modules still needed for the complete pod:

1. Audio capture at 16 kHz mono.
2. Local noise suppression and VAD.
3. Partial transcript callbacks from Moonshine.
4. Normalization of punctuation, case, contractions and common reading
   disfluencies.
5. Word-sequence alignment against nearby book passages with recovery searches.
6. Checkpoint confirmation using similarity, coverage and stability rules.
7. A deterministic effect controller with cooldowns and replay protection.
8. USB serial messages to the ESP32/Pico and local playback/visual commands.

LangGraph is not recommended in the live audio-to-effect loop. A small Python
state machine is easier to test and introduces less complexity. An LLM or
cloud service may help prepare book content before installation, but it should
not decide live triggers.

### Suggested book package

Each licensed book should be converted in advance into a reviewed local data
package containing:

```text
book_id
metadata
ordered pages/paragraphs
normalized matching text
checkpoint phrases
effect identifiers
asset file paths
timing, cooldown and safety limits
```

Generated mappings must be reviewed by the content/design team before they
are deployed. Runtime progress should normally move forward and should never
jump several pages based on one weak match.

## Hardware baseline

The list below records the earlier Pi 5 budget/design. The current software
target is Jetson; revise compute cost, power, cooling and projector connections
using actual supplier quotes before updating the hardware budget.

- Raspberry Pi 5 4GB
- active cooler and official 27W power supply
- 64–128GB high-endurance microSD or NVMe storage
- directional/cardioid wired USB microphone on a short gooseneck
- two compact powered speakers or an amplifier with two speakers
- ESP32 or Raspberry Pi Pico
- PN532-compatible RFID/NFC reader and tags
- diffused RGB/RGBW ambient lighting with a separate fused power supply
- one limited visual surface using a monitor or tested projector
- master switch, strain relief, ventilation and accessible service panel

Place the microphone approximately 20–35 cm from the child, point it away from
speakers and fans, and conceal its USB cable inside the furniture. Ordinary
Bluetooth microphones are not recommended because pairing, charging and audio
profile behaviour add avoidable operational risk. If wireless input becomes a
hard requirement, use a dedicated digital 2.4 GHz microphone system with its
own USB receiver.

The inexpensive HY300 family can be used to prototype a small visual area in a
dark pod, but model specifications vary and it is not a short-throw solution.
Test the exact unit at 0.6 m, 0.8 m and 1.0 m before designing the enclosure
around it. One HY300 should not be treated as a wraparound projection system.

## Preliminary budget

| Subsystem | Planned amount |
|---|---:|
| Enclosure fabrication | S$1,400 |
| Seating and interior | S$220 |
| Raspberry Pi compute kit | S$260 |
| ESP32/Pico, RFID and wiring | S$50 |
| Microphone and mount | S$120 |
| Audio output | S$100 |
| Main projector | S$500 |
| Projector mounting/surface | S$100 |
| Ambient lighting | S$140 |
| Electrical protection and ventilation | S$150 |
| Cables and miscellaneous parts | S$80 |
| Contingency | S$400 |
| **Total** | **S$3,520** |

This is an early student-built estimate and excludes paid content licensing,
professional certification and large-scale deployment. Obtain Singapore
supplier quotations before freezing the design.

## Latency target

Measure latency from the final required checkpoint word to the first visible
or audible response. The working engineering estimates are:

| Runtime | Estimated response |
|---|---:|
| Pi 5 + Moonshine Tiny Streaming | about 0.43–0.53 s |
| Pi 5 + Moonshine Small Streaming | about 0.72–0.82 s |
| Current WhisperLive approach on Pi 5 | potentially several seconds |

These are planning estimates, not guarantees. Final performance depends on
the microphone, acoustic treatment, VAD settings, model build and real child
speech. Stable partial transcripts may allow an effect to start before the
final silence boundary.

## Required prototype tests

- Record consenting test readers in the actual enclosure.
- Compare Tiny, Base and Small recognition accuracy on identical recordings.
- Measure end-to-end checkpoint latency rather than ASR inference alone.
- Test parent interruptions, repeated lines, skipped words and page changes.
- Play pod audio while reading and verify echo rejection/audio ducking.
- Test microphone placement with the physical book in reading position.
- Measure projector focus, image size, brightness, fan noise and heat at the
  final throw distance.
- Run a complete book-length thermal and stability test offline.
- Power-cycle repeatedly and verify automatic recovery without pairing or
  network access.

## Privacy and safety

The live pipeline is designed to stay on the device. Do not retain children's
audio by default. If recordings are required for testing, obtain appropriate
consent, minimize identifying information, restrict access and define a short
retention period with the project partner.

Use diffusers over LEDs, secure the projector with a safety tether, keep hot or
powered components inaccessible, protect wiring with fuses and strain relief,
and provide ventilation without directing fan noise toward the microphone.
Formal electrical, fire, accessibility and child-safety review remains outside
the current software prototype and is required before public deployment.

## Roadmap

- [x] Define the problem, audience and enclosure constraints.
- [x] Create a tunable local WhisperLive prototype.
- [x] Establish the offline architecture and preliminary budget.
- [ ] Collect representative child-reading recordings with consent.
- [ ] Benchmark Moonshine Tiny and Small on Raspberry Pi 5.
- [x] Implement book normalization and passage word-sequence alignment in the prototype.
- [ ] Implement the deterministic checkpoint/effect state machine.
- [ ] Integrate RFID/NFC and ESP32/Pico control.
- [ ] Build one limited visual and lighting prototype.
- [ ] Complete acoustic, thermal, safety and full-book testing.

## Licensing

The repository launchers and upstream WhisperLive stack are intended for a
permissive open-source prototype. WhisperLive, faster-whisper, CTranslate2,
OpenAI Whisper and Silero VAD use permissive licenses; preserve all upstream
copyright and license notices. TensorRT is not MIT-licensed and should be
excluded if an all-MIT-compatible distribution is a strict requirement.

Book text, illustrations, NLB-provided data and audiovisual assets may have
separate rights and are not made reusable merely by being referenced by this
software. Confirm those permissions before committing any content or
distributing a pod image.
