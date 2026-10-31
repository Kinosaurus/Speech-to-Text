# Books to Life Pod — Working Design Notes

Last updated: 10 October 2026

This document consolidates the project discussion so the team does not need to
search through the conversation history. Figures marked as estimates must be
validated with recordings made inside the actual pod.

Current software deployment target: **Jetson Orin Nano Super 8GB**, with local
GPU WhisperLive/faster-whisper recognition and CPU word-sequence alignment.
See [JETSON_SETUP.md](JETSON_SETUP.md) for the JetPack 6.2 deployment baseline
and laptop testing. The Pi CPU profile remains available. Earlier Pi hardware
budgets and Moonshine estimates below are retained as alternatives; they are
not measured Jetson results. GPU builds and real-board latency remain unverified.

## 1. Project objective

Books to Life Pod is an interactive physical reading enclosure for children
aged 5–10, normally used by one child and one parent.

Primary goals:

- Encourage the child to finish reading a physical book.
- Make reading feel immersive without allowing effects to compete with the book.
- Support reading engagement and comprehension.
- Use NLB-provided book/content data.
- Operate reliably in locations with weak or unavailable internet.
- Be transportable and straightforward to duplicate.

Approximate enclosure dimensions:

- Height: 198 cm
- Width: 196 cm
- Depth: 115 cm

Overall budget: approximately S$4,000.

## 2. Experience and enclosure direction

The pod can be circular or C-shaped, but a perfectly continuous circular shell
is more difficult and expensive to fabricate. A faceted or segmented curved
shell can create the same visual impression while being easier to manufacture,
transport and repair.

Recommended experience:

- Physical book remains the primary focus.
- Environmental visuals remain slow, simple and peripheral.
- Use scenery such as grass, clouds, forest silhouettes, stars or water.
- Avoid rapidly moving images, high contrast animation and constant scene cuts.
- Use restrained brightness and slow transitions.
- Use spatial/ambient sound at low volume.
- Reduce or duck the pod audio while the child is speaking.
- Avoid a full wraparound conventional screen because it can become the main
  attraction and compete with the book.

A useful compromise is a visually continuous environment created through a
combination of:

- One main display or projection surface
- Diffused ambient LED lighting
- Printed/translucent scenic panels
- Directional or spatial ambient sound

LEDs are not inherently distracting. They become distracting when they are
bright, individually visible, animated quickly or change constantly. Hide LED
strips behind diffusers and use them for broad colour washes rather than pixel
animations.

## 3. Projection and display considerations

Short-throw and ultra-short-throw projectors can consume too much of the total
budget. Circular projection is also difficult because it may require multiple
projectors, geometric warping, edge blending and careful control of shadows.

For this project:

- Do not make full 360-degree projection a requirement for the first prototype.
- Use one main visual surface or limited curved projection area.
- Keep visuals complementary to the book.
- Test throw distance using the exact projector model before final fabrication.
- Leave physical access for projector alignment, ventilation and maintenance.

Simple 2D graphics and looping video do not require a powerful GPU.

### HY300-type mini projector

The inexpensive HY300 shown in the Carousell listing is suitable only as a
low-cost prototype for a small front or ceiling visual, not as a close-range
wraparound projector. HY300 is used for several different hardware variants,
with published minimum projection distances ranging from roughly 0.6 m to
1.2 m and commonly a native resolution of 1280 x 720. At the pod's limited
throw distance, expect a relatively small image rather than a wall-filling
one. Curved projection, off-axis keystone correction and occupants blocking
the light will further reduce usable quality.

Before relying on one in the enclosure, test the exact purchased unit at
0.6 m, 0.8 m and 1.0 m on a sample of the final surface. Check whether the
whole image focuses, measure image width and fan noise, and confirm that the
advertised resolution is native rather than merely an accepted input format.
Use HDMI from the Raspberry Pi instead of depending on the projector's built-in
Android software. Treat a S$50 unit as an inexpensive prototype, not a final
installation component until it passes this test.

## 4. Microphone and audio arrangement

Use a directional/cardioid USB microphone positioned near the child rather than
an omnidirectional microphone in the ceiling.

Suggested placement:

- Approximately 20–35 cm from the child's mouth
- Mounted near the reading position or integrated into a small gooseneck
- Pointed toward the child and away from speakers and cooling fans
- Positioned so the book does not block it

The parent may also be captured by the microphone. Text matching alone cannot
reliably distinguish whether the child or parent spoke the words. If this
distinction becomes essential, consider a child-positioned microphone or a
press-to-read control instead of complex speaker identification.

Keep computer cooling fans in a ventilated service compartment outside the
main acoustic cavity where possible.

### Wired versus wireless microphone

Use a permanently mounted **wired USB microphone** by default. The child reads
from a fixed position, so the cable can be hidden inside the pod. This avoids
pairing failures, batteries, charging, loss/theft and changes in the selected
audio device after reboot.

Do not use an ordinary Bluetooth headset or Bluetooth microphone for the main
reading input. Bluetooth microphone input normally relies on a headset/hands-
free audio profile, and its quality, buffering and reconnection behaviour can
vary between devices and operating-system updates. Codec delay is only one
part of the end-to-end delay, so the complete pipeline must be measured on the
actual hardware.

If the design genuinely requires cable-free use, choose a dedicated digital
2.4 GHz wireless microphone kit with its own USB receiver rather than a direct
Bluetooth connection. The receiver remains connected to the Raspberry Pi and
appears as a USB audio device. This is easier to operate reliably, but it still
adds transmitter charging and battery management. Prefer a directional mic;
many wearable wireless transmitters are omnidirectional and will capture more
of the parent, speakers and room reflections.

## 5. Speech-recognition terminology

### Local VAD

Voice Activity Detection identifies when speech begins and ends. It prevents
silence and background noise from being sent continuously into the speech
recogniser.

### Local streaming ASR

Automatic Speech Recognition converts microphone audio into text. A streaming
model produces partial text while the person is still speaking instead of
waiting for the full recording.

Moonshine is the proposed ASR component. It is responsible only for converting
audio into text. It does not select or control effects.

## 6. Recommended live processing pipeline

```text
Child speaks
    ↓
Directional microphone
    ↓
Local noise reduction and VAD
    ↓
Moonshine streaming ASR produces partial text
    ↓
Word-sequence alignment compares it with nearby book passages
    ↓
Checkpoint is confirmed
    ↓
Deterministic controller triggers approved lighting/audio/visual effect
```

When every component and asset is installed locally, this pipeline requires no
cloud access during use. Initial software/model installation may require an
internet connection.

## 7. Local versus cloud processing

The complete reading experience should work offline.

Cloud-only ASR is risky because it introduces:

- Variable network latency
- Failure when internet service is weak or unavailable
- Ongoing API expenses
- Additional privacy and consent considerations for children's voices
- Effects that may arrive too late to feel synchronized

The cloud may be used for optional, non-time-critical features such as approved
analytics or post-session summaries. Lighting, sound and visual triggers must
not depend on a cloud connection.

## 8. Latency estimates

Latency is measured from the final required checkpoint word to the start of the
environmental response. These are engineering estimates rather than guarantees.

### Raspberry Pi 5 with Moonshine

Moonshine Tiny Streaming:

```text
Microphone frame:          20–40 ms
VAD silence confirmation: 160 ms
ASR response:             ~237 ms
Matching/effect command:   11–90 ms
Estimated total:          ~428–527 ms
```

Moonshine Small Streaming:

```text
Microphone frame:          20–40 ms
VAD silence confirmation: 160 ms
ASR response:             ~527 ms
Matching/effect command:   11–90 ms
Estimated total:          ~718–817 ms
```

When a sufficiently stable partial transcript confirms a checkpoint, the
system may respond before waiting for the final silence boundary.

### Existing WhisperLive configuration

The current client uses 4,096 samples at 16 kHz, which corresponds to a 256 ms
microphone block. WhisperLive also waits for at least one second of audio before
starting an inference pass.

Whisper/faster-whisper on a Raspberry Pi 5 is expected to be substantially
slower than Moonshine Streaming. A rough budget for stable results is several
seconds, potentially around 6–10 seconds depending on model and configuration.
This is too delayed for tightly synchronized pod effects.

### LattePanda Mu N100 with Moonshine

Estimated Moonshine Small response: approximately 0.4–0.6 seconds. This should
be benchmarked on the final device.

## 9. Compute hardware comparison

### Raspberry Pi 5

Recommended configuration:

- Raspberry Pi 5 with 4GB RAM
- Active cooler
- Official 27W power supply
- High-endurance 64–128GB microSD, or preferably NVMe storage
- Raspberry Pi OS/Linux
- Moonshine Small Streaming

Advantages:

- Lowest complete system cost
- Small, lightweight and power efficient
- Strong GPIO and maker ecosystem
- Easy to clone an OS image for multiple pods
- Suitable for simple graphics, audio and one ASR stream
- Raspberry Pi 5 production is promised until at least January 2036

Disadvantages:

- Slower than an x86 system
- ARM compatibility can require extra work
- VideoCore VII GPU does not provide NVIDIA/CUDA-style ASR acceleration
- Active cooling is required for sustained performance
- Cheap microSD cards are vulnerable to corruption after abrupt power loss
- Existing WhisperLive `base.en` is not the ideal low-latency model

All Raspberry Pi 5 memory variants use the same VideoCore VII GPU. More RAM
does not provide a different or faster GPU.

### LattePanda Mu N100

Relevant configuration:

- Intel N100 CPU
- 8GB LPDDR5
- 64GB eMMC
- Carrier board
- Active cooler
- 9–20V power supply
- Ubuntu or Windows

Advantages:

- Faster x86 CPU
- Easier compatibility with standard Python/x86 packages
- Better performance with the existing WhisperLive software
- Built-in eMMC is more robust than a basic microSD card
- Up to three display outputs, depending on the carrier board
- More future performance headroom

Disadvantages:

- Higher complete cost
- Requires a carrier board, cooler, power supply and mounting solution
- Higher heat and power consumption
- Smaller community than Raspberry Pi
- GPIO configuration is more complicated and electrically vulnerable
- Intel N100 has no NPU
- Intel graphics do not automatically accelerate faster-whisper

### Framework Ryzen AI 5 340 mainboard

The Framework board is much more powerful than required. The advertised price
covers only the mainboard; RAM, SSD, cooling components, power supply, ports and
a safe enclosure add significantly to the cost. It is not recommended as the
budget option for this pod.

### Recommended decision

Use a Raspberry Pi 5 4GB when the system uses Moonshine Small Streaming. It is
the best overall fit for cost, transportability and duplication. Consider the
LattePanda Mu N100 if the team must retain WhisperLive, requires more displays
or needs additional computing headroom.

Build the electronics as a removable tray with standard connectors so the
compute board can be replaced later without rebuilding the pod.

## 10. GPIO and physical control

GPIO means General-Purpose Input/Output. GPIO pins allow a computer to receive
signals from buttons/sensors and send small control signals to other hardware.

GPIO pins must not directly power LED strips, speakers, motors or projectors.
Those loads require separate power and suitable drivers/controllers.

Recommended arrangement:

```text
Raspberry Pi or LattePanda
        │ USB serial
        ▼
    ESP32 or Pico
      ├── RFID reader
      ├── LED controller
      ├── Buttons
      └── Sensors
```

Using an inexpensive microcontroller protects the main computer from electrical
damage and makes the physical control system replaceable.

## 11. Book-text alignment and checkpoint matching

The prototype now defaults to `AlignmentMatcher`: local dynamic programming
aligns recent recognized word sequences with nearby full page text. RapidFuzz
provides fuzzy word comparisons inside that alignment. It does not transcribe
speech or choose effects. The original phrase-only matcher is retained behind
`--matching_mode fuzzy` for comparison.

Example:

```text
Expected:
"the rabbit stepped quietly into the dark forest"

Moonshine output:
"the rabbit step quietly in the dark forrest"

Word alignment:
Locate these words in the passage → propose its checkpoint's ambience
```

Recommended matching rules:

- Align against nearby full passages, retaining recent spoken context.
- Use distinctive checkpoint phrases as book-position markers.
- Begin testing around an 82/100 similarity threshold.
- Require at least 5–6 detected words.
- Require two consistent, distinct transcript updates; identical callbacks do
  not add confirmation. Timestamped partial-to-final updates can confirm.
- Trigger every checkpoint only once.
- Select the latest confirmed ambience after a jump; skip earlier missed effects.
- Widen the forward word window after failed fresh updates, using stricter
  recovery scoring. Hold progress for ambiguous matches in separate scenes.
- Do not use generic anchor phrases.
- Provide a parent/operator page correction control.
- Tune thresholds using recordings of actual children inside the pod.

Nearby passage searches reduce accidental distant matches. Recovery can search
farther ahead but still requires clear and stable evidence. Text matching cannot
distinguish whether the child or parent is reading.

RapidFuzz is MIT-licensed. Matching-only timings can be measured with
`python -m books_to_life.cli.checkpoint_demo --benchmark 30`. Pi performance and end-to-end
response latency have not yet been measured for this tracker.

## 12. Book parsing and reusable state machine

Do not generate a new Python application for every book. Create one reusable
Python state machine and generate a structured JSON story manifest for each
book.

Offline authoring flow:

```text
NLB text/PDF/EPUB
      ↓
Extract page and paragraph structure
      ↓
Identify appropriate checkpoints
      ↓
Suggest approved effect categories
      ↓
Human review
      ↓
Export book_manifest.json
```

Example manifest:

```json
{
  "book_id": "rabbit-forest",
  "title": "The Rabbit's Journey",
  "pages": [
    {
      "page": 3,
      "text": "The rabbit stepped quietly into the dark forest. Tall trees covered the path."
    },
    {
      "page": 7,
      "text": "Thunder rolled across the darkening sky. Gentle rain settled over the garden."
    }
  ],
  "checkpoints": [
    {
      "id": "enter_forest",
      "book_id": "rabbit-forest",
      "checkpoint_position": 1,
      "page": 3,
      "checkpoint_text": "the rabbit stepped quietly into the dark forest",
      "effect": {
        "effect_id": "forest_calm",
        "visual": "forest_loop.mp4",
        "visual_delay": 0,
        "sound": "forest_birds.ogg",
        "sound_delay": 0
      }
    },
    {
      "id": "storm_starts",
      "book_id": "rabbit-forest",
      "checkpoint_position": 2,
      "page": 7,
      "checkpoint_text": "thunder rolled across the darkening sky",
      "effect": {
        "effect_id": "gentle_storm",
        "visual": "gentle_storm_loop.mp4",
        "visual_delay": 500,
        "sound": "soft_rain.ogg",
        "sound_delay": 1000
      }
    }
  ]
}
```

`checkpoint_position` is the positive sequence number within the book. IDs and
positions must be unique, and each checkpoint's `book_id` must match the manifest.
The tracker orders checkpoints by position and locates their text in full pages.
Optional `word_start` and exclusive `word_end` locate repeated phrases in the
normalized full-book word stream. The example above omits intervening pages for
brevity; actual book packages should include all readable pages. Visual and
sound delays are non-negative integer milliseconds after confirmation; omitted
delays mean zero. Either asset may be `null`. Current effects are printed as
payloads; playback and delay scheduling are planned controller responsibilities.

The effect controller should load only pre-approved effect definitions. An
optional `effect_id` can identify a reusable reviewed preset, for example:

```json
{
  "forest_calm": {
    "visual": "forest_loop.mp4",
    "lighting_colour": "#567A46",
    "brightness": 0.18,
    "fade_ms": 1500,
    "sound": "forest_birds.ogg",
    "volume": 0.20
  }
}
```

Automatic tooling may suggest effect identifiers but must never generate
unrestricted hardware commands. Human review is required before a book package
is installed, particularly because the audience is children.

## 13. State machine

A reusable state machine can be very small:

```text
WAITING_FOR_BOOK
       ↓ RFID scan
BOOK_LOADED
       ↓ speech
READING
       ↓ checkpoint confirmed
ADVANCE_CHECKPOINT
       ↓
READING
       ↓ final checkpoint
BOOK_COMPLETED
```

State to retain:

- Current book identifier
- Current page/checkpoint index
- Set of already-triggered checkpoints
- Session status
- Optional progress record

Save progress only at confirmed checkpoints rather than on every partial ASR
update.

## 14. LangGraph decision

Do not put LangGraph in the live reading/effect path. The sequence is ordered
and deterministic, so a small Python state machine is faster, easier to debug
and easier to duplicate.

LangGraph could be useful in a separate offline content-authoring workflow:

```text
Extract book text
  → propose checkpoints
  → assign approved effect tags
  → validate anchors
  → request human approval
  → export manifest
```

LangGraph may also be used asynchronously for optional post-session summaries
or analytics. The pod must never wait for it before triggering an effect.

## 15. Software/licensing notes

The intended local stack uses permissive licences:

- Moonshine streaming code/models: MIT by default; check any model-specific
  exceptions before distribution
- RapidFuzz: MIT
- WhisperLive: MIT
- faster-whisper: MIT
- CTranslate2: MIT
- OpenAI Whisper code/model weights: MIT
- Silero VAD: MIT
- LangGraph: MIT, if used in offline authoring

TensorRT is proprietary and should be avoided if an entirely MIT-licensed stack
is required.

## 16. Recommended first prototype

Hardware:

- Raspberry Pi 5 4GB
- Active cooler and ventilated electronics compartment
- Official 27W power supply
- Reliable storage
- Directional USB microphone
- Speakers/amplifier with independent power
- ESP32 or Pico for LEDs/RFID/buttons
- One display or limited projection area
- Diffused ambient LED lighting

Software:

- Raspberry Pi OS/Linux
- Local noise reduction and VAD
- Moonshine Small Streaming
- Passage word-sequence tracker with fuzzy word comparisons and recovery
- Generic Python state machine
- JSON book and effect manifests
- Local media assets

## 17. Tests required before committing to production

1. Record children aged 5–10 reading representative passages.
2. Test with a parent sitting in the expected position.
3. Repeat inside the physical pod with speakers and fans operating.
4. Measure checkpoint-to-effect latency.
5. Measure false triggers and missed checkpoints.
6. Tune microphone position and audio ducking.
7. Tune RapidFuzz thresholds and anchor lengths.
8. Test abrupt power loss and automatic recovery.
9. Confirm the complete experience works with networking disabled.
10. Observe whether visuals support reading or distract from the book.

## 18. Current key decisions

- Offline-first operation
- Physical book remains the primary focus
- Subtle, peripheral effects instead of full wraparound screens
- Raspberry Pi 5 4GB is the leading compute choice
- Moonshine Small Streaming is the leading ASR choice
- RapidFuzz performs deterministic checkpoint matching
- ESP32/Pico controls electrical peripherals
- One generic state machine loads per-book JSON manifests
- LangGraph stays outside the real-time path
- Human approval is required for automatically proposed book effects

## 19. Preliminary bill of materials and budget

Pricing below is a Singapore-dollar planning estimate for one student-built
prototype. It is not a supplier quotation. Allow for GST, delivery and price
changes. Professional fabrication labour can increase the total substantially.

### Recommended S$4,000 allocation

| Category | Included components | Planning amount |
|---|---|---:|
| Enclosure | Segmented plywood/timber structure, removable panels, paint/fabric, fasteners and cutting | S$1,400 |
| Seating/interior | Two wipe-clean cushions, floor padding and small book support | S$220 |
| Main computer | Raspberry Pi 5 4GB kit, cooler, 27W PSU, storage and HDMI cable | S$260 |
| Physical controller | ESP32/Pico, PN532 RFID reader, tags and prototype wiring | S$50 |
| Microphone | Directional USB microphone, mount/gooseneck and windscreen | S$120 |
| Audio output | Two compact powered speakers or small amplifier and speakers | S$100 |
| Main visual | One budget short-throw projector | S$500 |
| Visual mounting | Secure mount, safety tether and projection/diffusion surface | S$100 |
| Ambient lighting | Diffused RGB/RGBW strip, controller, power supply and wiring | S$140 |
| Electrical/safety | Fused distribution, master switch, power strip, strain relief and ventilation | S$150 |
| Cables/miscellaneous | USB cables, connectors, brackets and spare consumables | S$80 |
| Contingency | Approximately 10–15% reserve | S$400 |
| **Planned total** |  | **S$3,520** |

This leaves approximately S$480 within the S$4,000 ceiling for unexpected
fabrication or delivery charges.

### Expected ranges by subsystem

| Subsystem | Expected range |
|---|---:|
| Pi compute kit | S$230–300 |
| ESP32/Pico, RFID and tags | S$25–60 |
| Directional USB microphone and mount | S$80–180 |
| Audio output | S$70–180 |
| One 24-inch monitor and mount | S$130–240 |
| One budget short-throw projector and mount | S$500–750 |
| Ambient lighting system | S$100–220 |
| Student-built enclosure | S$900–1,700 |
| Professionally fabricated enclosure | S$1,500–2,500+ |
| Seating/interior padding | S$150–300 |
| Electrical protection/ventilation | S$100–220 |

### Visual options

Choose one primary visual option:

- Budget/display prototype: 24-inch monitor and mount, approximately S$130–240.
- Immersive prototype: one short-throw projector plus mount/surface,
  approximately S$500–750.
- Full 360-degree projection: not recommended within the S$4,000 budget because
  it requires multiple projectors, warping, edge blending and additional mounts.

Do not purchase a projector based only on the words "short throw". Verify its
actual throw ratio, required image width at the available distance, brightness,
fan noise and return policy using a physical mock-up first.

### Lighting notes

The lighting allowance should include the LED strip, aluminium diffuser,
dedicated enclosed power supply, fuses, suitable wire and an ESP32/Pico control
interface. Do not power the strip through the Raspberry Pi. A high-density
RGBW or COB-style strip behind a diffuser will produce a calmer continuous glow
than exposed individual pixels.

### Fabrication assumptions

The student-built enclosure estimate assumes the team performs assembly,
finishing and some cutting itself. The structure should use segmented ribs and
removable lightweight panels instead of trying to bend thick 18mm plywood into
a perfect circle. Professional fabrication should be quoted before electronics
are purchased because it is the largest source of budget variation.

### Items not included in the estimate

- Paid professional software development
- Commercial animation or audio licensing
- NLB content licensing or data-preparation fees
- Delivery van or long-term storage
- Institutional electrical/fire certification
- Multiple complete pods
- Multiple-projector 360-degree projection
