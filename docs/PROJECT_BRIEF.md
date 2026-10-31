# Books to Life Pod

## Project brief and technical direction

> Planning snapshot: August 2026. Prices and model availability should be
> rechecked before purchasing hardware.

## 1. Project overview

Books to Life Pod is a university capstone engineering project developed with
the National Library Board (NLB) and Singapore Book Council. It is intended for
children aged 5–10 and may be deployed in public libraries or at events such as
the Asian Festival of Children's Content (AFCC).

Team members:

- Finn Yap
- Thant Thiri Wai
- Kinson Gan
- Mohamed Danial
- Lee Yi Shuen

The pod is a semi-enclosed, comfortable reading space. A child reads a known
book aloud, and the system follows their progress in real time. Scripted points
in the story trigger synchronized projected visuals and audio soundscapes.

The current scope includes:

- Real-time speech recognition
- Story-progress tracking and session state
- Projected animations and environmental visuals
- Music, ambience and sound effects
- Solo and companion reading modes
- Adjustable brightness and volume
- Sensory-friendly operation

Scent, breeze effects and general-purpose LED ambience are outside the current
scope.

## 2. Recommended solution

Use a Raspberry Pi 5 running **sherpa-onnx with an INT8 streaming Zipformer
Transducer** as the primary speech engine. Match its partial transcript against
the known text of the selected book instead of treating the system as
unrestricted dictation.

Recommended processing flow:

```text
Child reads aloud
       |
       v
USB microphone array with AEC and beamforming
       |
       v
16 kHz mono audio
       |
       v
sherpa-onnx streaming Zipformer INT8
       |
       v
Partial transcript
       |
       v
Story-position matcher and event debouncer
       |                         |
       v                         v
Projected animation        Audio soundscape
```

Recommended initial model:

```text
sherpa-onnx-streaming-zipformer-en-2023-06-26
```

Benchmark it against the English model trained with both LibriSpeech and
GigaSpeech. The final model must be selected using recordings from children in
the real pod, not adult-speech benchmark results alone.

### Why use the known book text?

The system only needs to answer: "Where is the child in this story?" It does not
need a flawless transcript. The matcher should search a small window around the
current position, for example the previous 10 words and next 20 words.

It should tolerate:

- Mispronunciations
- Skipped words
- Repeated words or sentences
- Inserted comments
- Recognition substitutions
- Different reading speeds

Important effects should require a short sequence of matching words rather than
one common word. Each event should be idempotent: transcript revisions or
repetition must not fire it twice unless the story configuration explicitly
allows repetition.

## 3. Zipformer, sherpa-onnx and Whisper

These names refer to different layers:

- **sherpa-onnx** is the inference toolkit/runtime.
- **Zipformer** is a speech-recognition neural-network architecture.
- **Whisper** is a different speech-recognition model family.

Sherpa-onnx can run multiple model families, including Zipformer and Whisper.
The relevant choice for this project is streaming Zipformer versus Whisper.

| Requirement | Streaming Zipformer | Whisper |
| --- | --- | --- |
| Low latency on Raspberry Pi CPU | Better | Slower |
| Native incremental recognition | Yes | Usually simulated with overlapping windows |
| Known-book matching | Excellent | Good |
| Contextual hotwords | Supported | More limited prompting |
| Memory and compute requirements | Lower | Higher |
| Unrestricted transcript quality | Moderate to good | Usually better |
| Noise and accent robustness | Model-dependent | Usually better |
| Multilingual transcription | Model-dependent | Strong |
| Evidence for child-speech adaptation | Limited for public Zipformer models | Stronger |

For the pod, streaming Zipformer is the recommended primary engine because
trigger latency matters more than producing a publishable transcript. Whisper
`tiny.en` or `base.en` can optionally validate completed sentences in the
background if the Pi has enough spare capacity.

Children's speech remains a project risk. Public English Zipformer models are
largely trained on adult speech, while children differ in pitch, timing,
pronunciation and fluency. Accuracy must therefore be measured with the target
age group and Singaporean accents.

## 4. Expected latency

Do not specify sub-100 ms end-to-end speech-trigger latency. A streaming model
must first receive enough audio to identify the word.

Expected single-cue latency on a Raspberry Pi 5:

| Stage | Approximate delay |
| --- | ---: |
| Microphone and audio buffering | 10–30 ms |
| Waiting for a model audio chunk | Approximately 320 ms |
| Pi inference | Approximately 20–100 ms; must be measured |
| Story matching | Less than 10 ms |
| Starting preloaded audio/video | Approximately 20–100 ms |
| **Expected total** | **Approximately 400–700 ms** |

Waiting for two or three spoken words to improve confidence can produce an
overall delay of approximately 700–1,500 ms. Remember:

```text
100 ms    = 0.1 seconds
500 ms    = 0.5 seconds
1,000 ms  = 1 second
10,000 ms = 10 seconds
```

Real-time factor (RTF) is processing throughput, not end-to-end latency. An RTF
of 0.062 means one second of recorded audio takes about 0.062 seconds to
compute. The recognizer still has to wait for its audio chunk before that
computation begins.

Recommended acceptance targets:

- Median trigger latency below 500 ms for a single cue
- P95 trigger latency below 800 ms for a single cue
- Audio and video start within 20–30 ms of each other
- Fewer than 5% missed scripted events in the final test set
- Fewer than one false event per 15-minute session
- No duplicate effects after transcript revisions or ordinary repetition

Latency can also be hidden through story authoring. For example, recognize
"mysterious treasure" early enough that an effect becomes visible as the child
says "chest".

## 5. Projection system

Use a short-throw projector mounted above and behind the child. It should project
onto an internal matte-white panel or prepared surface without placing the beam
at the child's eye level.

Recommended minimum specifications:

- Native 1080p preferred; WXGA is acceptable for ambient illustration
- 3,000–4,000 ANSI lumens
- Throw ratio around 0.5:1–0.7:1
- HDMI input
- Eco-mode fan noise below approximately 30 dB
- Automatic power recovery after an outage
- Laser or LED light source preferred
- A mount that cannot be adjusted by visitors

The enclosure must provide airflow around the projector, prevent access to hot
surfaces and route cables through protected channels. Keep the projector fan as
far from the microphone as practical.

Use pre-rendered, hardware-decodable H.264 video loops instead of generating
visuals with AI in real time. Preload the next assets so a trigger does not wait
for disk or network access. Appropriate content includes:

- Forest, ocean, space and weather loops
- Colour and brightness transitions
- Character silhouettes
- Short story-event animations
- Slow idle motion while the child pauses

The Pi 5 should be able to decode ordinary 1080p H.264 video while running a
lightweight recognizer, but this must be load-tested with the final assets.

## 6. Audio system

Use two compact speakers mounted near the reading position. This creates a wider
sound field at a lower volume and reduces sound leakage into the library.

Recommended components:

- ReSpeaker XVF3800 or comparable USB microphone array
- Hardware acoustic echo cancellation (AEC)
- Beamforming and automatic gain control
- Two compact full-range speakers
- Small class-D amplifier
- Optional compact subwoofer at a conservative level
- USB audio interface or DAC if required

The microphone system must be tested while the pod is playing its own audio.
Verify that the selected AEC system receives the actual playback reference;
having an AEC feature does not guarantee correct cancellation if audio is routed
through an unrelated output device.

Volume and projection brightness must have simple operator limits. A child or
parent may be offered a limited quiet/normal intensity control, but should not
be able to exceed the operator-defined maximum.

## 7. Hardware budget

The SGD 6,000 cap is achievable if the team performs most integration and
fabrication. The estimates exclude team labour and should include GST, delivery
and replacement parts when purchase orders are prepared.

### Recommended allocation

| Subsystem | Allocation |
| --- | ---: |
| Speech computer and controllers | S$650 |
| Short-throw projector, mount and surface | S$1,600 |
| Microphone, speakers and audio electronics | S$600 |
| Pod enclosure, seating and acoustic treatment | S$1,700 |
| Electrical distribution and safety hardware | S$450 |
| Wiring and fabrication consumables | S$300 |
| Testing and replacement parts | S$300 |
| Contingency | S$400 |
| **Total** | **S$6,000** |

Expected completed cost is approximately S$4,200–5,500 if fabrication is mostly
performed by the team. Commercial carpentry, professional installation,
transport and venue certification may push the total above S$6,000.

### Representative component budget

| Component | Expected cost |
| --- | ---: |
| Raspberry Pi 5 8 GB | S$245–265 |
| Case, active cooling and 27 W power supply | S$40–90 |
| 256–500 GB SSD and adapter | S$60–110 |
| ReSpeaker XVF3800 microphone array | Approximately S$107 |
| Two or three ESP32 controllers | S$20–60 |
| Short-throw projector | S$1,050–1,450 |
| Lockable projector mount | S$70–220 |
| Projection surface and finishing | S$80–180 |
| Speakers, amplifier and optional subwoofer | S$290–540 |
| Cables, hub, mounts and protected wiring | S$100–220 |

Sherpa-onnx, Zipformer, MQTT and the normal ESP32 development tools are open
source, so the proposed offline design has no recurring speech-recognition fee.

## 8. Current repository assessment

This repository currently contains a thin WhisperLive server/client prototype:

- `books_to_life/cli/run_server.py` starts a WhisperLive transcription server.
- `books_to_life/cli/run_client.py` streams microphone or file audio to the server.
- The client enables VAD and displays transcription results.

Useful foundations:

- Live microphone input
- WebSocket transport
- Recorded-file testing
- Server/client separation
- Language and model selection

Important gaps:

- The default Whisper `small` model is not a low-latency Pi configuration.
- The server defaults to one OpenMP thread.
- There is no dependency lock file or reproducible installation process.
- The README requests Python 3.12, while the current development environment
  only exposes Python 3.10.
- There is no story definition format or story-position matcher.
- There is no callback/API for projection and audio events.
- There is no event deduplication or session persistence.
- There is no latency instrumentation or benchmark suite.
- There are no tests using child speech, pod noise or simultaneous playback.
- The server listens on all interfaces and does not enable authentication by
  default.

The existing code is useful as a Whisper comparison baseline. It should not be
treated as the production Books to Life architecture.

## 9. Proposed story format

Keep story content separate from recognition and playback code. One possible
JSON structure is:

```json
{
  "id": "sample-story",
  "title": "The Mysterious Cave",
  "language": "en",
  "text": "The little dragon entered the mysterious cave...",
  "events": [
    {
      "id": "cave-entry",
      "match": ["entered", "mysterious", "cave"],
      "minimum_matches": 2,
      "video": "assets/cave-entry.mp4",
      "audio": "assets/cave-rumble.wav",
      "repeatable": false
    }
  ]
}
```

The event engine should track pending, active and completed events and persist
the current reading position. It should expose a reset operation for the next
visitor.

## 10. Implementation roadmap

### Phase 1: Measurement baseline

1. Make the existing WhisperLive prototype reproducible.
2. Add dependency locking and a benchmark command.
3. Record timestamps at audio capture, recognition and event output.
4. Establish Whisper `tiny.en` and `base.en` latency baselines.

### Phase 2: Streaming recognizer

1. Add sherpa-onnx and the INT8 English streaming Zipformer model.
2. Consume stable partial hypotheses without waiting for sentence endpoints.
3. Benchmark thread counts and thermal throttling on the Pi 5.
4. Compare greedy search against hotword-enabled modified beam search.

### Phase 3: Story engine

1. Define the story JSON schema.
2. Normalize recognised and expected text.
3. Implement sliding-window fuzzy alignment.
4. Add confidence thresholds, cooldowns and one-shot events.
5. Persist session position and completed events.

### Phase 4: Audio and projection

1. Preload visual and audio assets.
2. Start both outputs from the same event timestamp.
3. Measure audio/video synchronization.
4. Test recognition while every soundtrack is playing.
5. Tune AEC, speaker placement and microphone position.

### Phase 5: Child testing

Build a consented evaluation set representing:

- Ages 5–10
- Different Singaporean accents
- Quiet and event-like background noise
- Solo and companion reading
- Slow reading, repetition, skipping and mispronunciation
- Multiple books and unfamiliar character names

Report trigger latency, missed-event rate, false-event rate and duplicate-event
rate. Normal word error rate can be reported as a secondary metric, but it is
not the primary product metric.

## 11. Key risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Child speech is recognised poorly | Known-text matching, page-level hotwords and child testing |
| Pod audio is transcribed as speech | Correctly routed AEC, close microphone placement and lower speaker volume |
| Projector fan contaminates audio | Physical separation, eco mode and acoustic isolation |
| Projector beam reaches a child's eyes | Above/behind mounting and fixed tamper-resistant geometry |
| Visuals start late | Preload H.264 loops and avoid network dependencies |
| Effects fire twice | Persist event state and debounce transcript revisions |
| Pi overheats or throttles | Active cooling and full-load thermal testing |
| Budget overrun | Purchase projector and microphone early; preserve contingency |
| Sensory overload | Operator maximums and accessible quiet/normal mode |

## 12. References

- [Sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- [Streaming Zipformer model documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html)
- [Sherpa-onnx contextual hotwords](https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html)
- [Sherpa-onnx keyword model latency example](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html)
- [Icefall streaming Zipformer documentation](https://github.com/k2-fsa/icefall/blob/master/docs/source/recipes/Streaming-ASR/librispeech/zipformer_transducer.rst)
- [Zipformer paper](https://arxiv.org/abs/2310.11230)
- [Whisper tiny.en Raspberry Pi benchmark](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/tiny.en.html)
- [WhisperLive](https://github.com/collabora/WhisperLive)
- [Kid-Whisper child-speech study](https://ojs.aaai.org/index.php/AIES/article/view/31618)
- [Raspberry Pi 5 Singapore reference price](https://sg.element14.com/raspberry-pi/rpi5-8gb-single/rpi-5-board-2-4ghz-8gb-arm-cortex/dp/4256000)
- [ReSpeaker XVF3800 Singapore reference price](https://sg.cytron.io/p-respeaker-xmos-xvf3800-with-case)
- [ViewSonic Singapore short-throw projectors](https://shop.viewsonic.sg/collections/projectors/short-throw)
