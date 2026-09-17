# Books to Life Pod

Books to Life Pod is an interactive reading enclosure for a child aged 5–10
and a parent or caregiver. It follows a physical book locally and triggers
restrained lighting, sound and visual effects at approved story checkpoints.
The environmental response is intended to reward continued reading without
becoming more important than the book.

This repository currently contains the **WhisperLive speech-recognition
prototype** and the working product/architecture notes. The intended embedded
version—Moonshine streaming ASR, book-text matching and physical effect
control—is documented here but is not fully implemented yet.

## Project at a glance

| Item | Current direction |
|---|---|
| Users | One child and one parent/caregiver |
| Enclosure | Cozy segmented circular pod, approximately 198 × 196 × 115 cm |
| Interaction | Read the complete physical book aloud |
| Book identification | RFID/NFC |
| Runtime | Offline-first, with no cloud dependency during reading |
| Compute target | Raspberry Pi 5 4GB with active cooling |
| ASR target | Moonshine Small Streaming; Moonshine Tiny for early tests |
| Current ASR prototype | WhisperLive with `faster-whisper` |
| Text alignment | RapidFuzz against expected checkpoints |
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
RapidFuzz compares text with the expected checkpoint window
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
| `BOOKS_TO_LIFE_POD_NOTES.md` | Detailed enclosure, hardware, ASR, latency, matching and budget decisions |
| `README.md` | Project overview and prototype instructions |

## Current WhisperLive prototype

The included Python launchers are for evaluating microphones, child speech,
VAD settings and story prompts on a development computer. WhisperLive is not
the planned final Raspberry Pi runtime: it is expected to respond too slowly
on a Pi for tightly synchronized effects.

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
python -m pip install whisper-live
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

Give the recognizer only the short passage expected next, rather than the
entire book:

```powershell
python run_client.py `
  --initial_prompt_file .\current-passage.txt `
  --hotwords "NLB,Matilda,Trunchbull"
```

An inline prompt and a prompt file cannot be supplied at the same time. The
same rule applies to `--hotwords` and `--hotwords_file`.

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

The production path should replace WhisperLive with Moonshine streaming ASR
and add the modules below:

1. Audio capture at 16 kHz mono.
2. Local noise suppression and VAD.
3. Partial transcript callbacks from Moonshine.
4. Normalization of punctuation, case, contractions and common reading
   disfluencies.
5. A forward-only RapidFuzz matcher against a small expected text window.
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
- [ ] Implement book normalization and RapidFuzz alignment.
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
