# Books to Life Pod: current flow, handover and verification

Updated 27 October 2026. This describes the implemented repository, including
experimental trackers developed in this chat. The older PROJECT_BRIEF.md is a
planning snapshot and should not be used as the current architecture/status.

## Current flow

```text
Select book manifest (full page text + checkpoint ranges + effect payloads)
        |
Microphone OR recording -> 16 kHz mono audio packets -> local WebSocket server
        |                                              |
        |                                  Whisper / Parakeet / Moonshine
        |                                              |
        +-------------------- partial/revised transcript snapshots
                                                       |
                            normalize text + replace revised ASR segments
                                                       |
                           align recent speech with nearby full book text
                                                       |
                        candidate position + coverage + ambiguity checks
                                                       |
                             confirmation / evidence / scene selection
                                                       |
                    [ALIGN] position, [SKIPPED] scenes, [TRIGGER] payload
                                                       |
                          terminal output + saved SRT when session ends
```

This is text alignment AFTER ASR, not direct audio-to-book forced alignment.
The full selected passage is the reference; each update searches a moving
window using recent recognized words. It is not merely searching for a
checkpoint sentence. The original tracker also uses approximate word similarity.
Checkpoints define effect locations in that book, rather than restricting all
matching evidence to the exact checkpoint phrase.

The manifest supplies page text, ordered checkpoint word ranges/anchors,
thresholds, and effect payloads. Without a checkpoint manifest the client only
transcribes. Restart the client with a new manifest to select a different book.
Each client invocation creates a new in-memory session.

The tracker advances confirmed progress, suppresses duplicate scene activations,
and can select a later scene while marking intervening scenes skipped. Reaching
completed does NOT prove that every scene fired. Current catch-up behavior is
suited to persistent ambience; there is no separate event policy for one-shot
sounds/animations. Effect filenames are placeholders and physical audio/video
playback/control is NOT wired to triggers yet.

## Recognition engines and hints

- Whisper: native Windows CUDA or documented Docker deployment. Supports book
  prompts and hotwords, including moving context through the server extension.
- Parakeet NeMo: original Unified model in Linux/WSL CUDA, with phrase boosting.
  No Whisper-style passage prompt. Default internal buffering is 560 ms chunk,
  560 ms right context and 5.6 s left context. The tested PC uses an RTX 3070 Ti.
- Native Parakeet/Moonshine adapters are also available; their buffering and hint
  capabilities differ. Latest tracker comparison used Whisper medium.en and
  Parakeet NeMo only; do not assign those results to Moonshine/native Vulkan.

A checkpoint manifest can automatically generate moving book hints. Explicit
`--hotwords`/`--initial_prompt` override their respective generated fields;
`--no_book_context` disables automatic book hints. The latest controlled test
used explicit fixed vocabulary or no hints, with automatic context disabled.
No automatic model fallback or production recognizer selection is implemented.

## Tracker modes

| CLI mode | Behavior | Status |
| --- | --- | --- |
| `alignment` | Original full-text word-sequence alignment and consecutive confirmation | Default |
| `evidence` | Holds candidates through bounded noisy updates; supports strong stable revisions/completion at the boundary | Experimental |
| `split` | Evidence tracker plus context-dependent two-token-to-one-word proposals near the next boundary | Experimental; latest tested improvement |
| `fuzzy` | Legacy checkpoint-phrase matching | Optional baseline |

The CLI model default is currently `base.en`; it is NOT automatically Parakeet
or medium.en. Use explicit model, port and matching mode in tests.

Evidence retention lasts at most 12 seconds of segment time or 12 fresh updates
since support. Ambiguity clears it; another accepted scene replaces it. New book
words can confirm progress but are not universally required: a strong match can
also survive a changed hypothesis over newer audio or utterance completion.
Duplicate callbacks and timestamp-only changes do not manufacture confidence.
A completed utterance is a stability signal, not new independent audio evidence.

Split assistance requires already-confirmed story progress, proximity to the
next checkpoint, at least two exact words on either side of one compound,
distinct supporting context, and the latest transcript tail. It uses a limited
spelling/consonant proxy, NOT a trained pronunciation model. This can connect
key pot/key put to teapot inside put the ... on the stove, without a global
Tea-specific replacement dictionary. Prefix support just before the boundary
can carry forward across a short partial-word update; later book words are not
required. Negation/prompt markers block split proposals but do not replace
speaker identification or semantic understanding in the ordinary aligner.
First-scene split assistance is intentionally unsupported.

## How to start the tested Parakeet + split setup on this PC

Requires the existing Windows .venv, WSL Ubuntu-24.04, CUDA and prepared NeMo
model. Installation details remain in README.md; these are startup commands for
the already-prepared PC. Use two terminals and leave the server running.

Terminal 1, inside Ubuntu/WSL:

```bash
cd /mnt/c/Users/heart/Speech-to-Text
/home/heart/.venvs/books-to-life-nemo/bin/python run_nemo_server.py --model-path model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo --port 9097
```

Terminal 2, PowerShell in the repository, recorded Tea with the tested fixed hints:

```powershell
New-Item -ItemType Directory -Force output | Out-Null
.\.venv\Scripts\python.exe run_client.py --model parakeet-nemo --server 127.0.0.1 --port 9097 --matching_mode split --files examples/audio/tea.wav --mute_audio_playback --checkpoints examples/tea_story.json --no_book_context --hotwords "mouse, pot of tea, phone, teapot, stove, cups, little house, Toad" --transcript_file output/tea-split.srt
```

For microphone input, omit `--files examples/audio/tea.wav` and read that passage
aloud. Select a device using `--list_input_devices` then `--input_device` if
needed. Stop capture with Ctrl+C. Microphone packet size is configurable using
`--audio_chunk`; file playback uses the existing 4096-sample packets. Test a new
microphone configuration before expecting the recording results to reproduce.
For a direct original-tracker baseline change only `--matching_mode alignment`.

## Verification completed

### Fresh streaming comparison on 24 October

24 fresh audio streams covered all eight recordings: four matched books with
hints on/off, plus four off-book clips, for each of two recognizers. The original
and split trackers were evaluated online at each fresh ASR callback in the same
client. This controls recognition variability. Actual app split triggers matched
the split observer in all 16 matched-book runs.

| Recognizer, hints off/on combined | Original activations | Split activations |
| --- | ---: | ---: |
| Whisper medium.en | 9/16 | 9/16 |
| Parakeet NeMo | 12/16 | 16/16 |
| Total configured scene opportunities | 21/32 | 25/32 |

No original activations lost. The four added activations were Tea stove and house
in both Parakeet conditions. Seven configured opportunities remain unactivated,
all Whisper: Fat Cat both scenes without hints, Fat Cat hat scene with hints,
Tea stove/house without hints, and Tea initial tea/house with hints.

The stove fired at the first complete stove callback in both Parakeet runs,
without waiting for the next sentence. House recovery was still late. Of 21
shared activations, 16 had unchanged callback timing; five were 0.48–1.78 s later
with the new tracker. This is relative tracker delay, not measured delay from
the actual spoken word to an effect.

Zero activations for either tracker in 32 live off-book stream/book comparisons.
This does not establish a zero wrong-scene rate during related conversation.
Fat Cat's first exact anchor was reportedly skipped: its activation can be scene
catch-up rather than a correct spoken-phrase detection. The clips used to develop
the tracker were reused here; this is not independent held-out validation.

All samples were verified delivered in 256 ms packets. Delivery was approximately
4% slower than nominal recording duration. Partial text arrived while only early
audio had been sent; ASR was not given the full file upfront. Files bypass live
microphone acoustics. Fresh streaming tests are different from saved-transcript
replay and are separately documented in LIVE_TRACKER_RESULTS.md.

### Automated verification on 27 October

- Run `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`.
- 91 tests pass, covering original alignment and adapters plus evidence retention,
  duplicates, revisions, completion, expiry, split boundaries, partial words,
  prior acquisition, negation/prompting, wrong objects and stale/same-audio prefixes.
- `git diff --check` passes.
- CLI help exposes alignment/evidence/split/fuzzy; default remains alignment.
- Verified latest streaming result source hashes against the tested matcher and
  streaming harness files before publishing this handover. Historical hashes in
  the snapshot describe those tested files, not future edits.

The printed bad-audio traceback during the unit suite is from an intentional
mock error-path test; the suite reports OK. These checks do not replace on-device
integration testing. The full audio benchmark was not rerun on 27 October.

## Remaining TODOs and verification gates

### 1. Establish whether activations are correct AND on time

- [ ] Annotate each recording with actual spoken checkpoint ends, skipped text,
      speaker turns and the intended scene at each time.
- [ ] Label catch-up separately from exact event detection; resolve Fat Cat's
      skipped-anchor case before reporting precision/recall.
- [ ] Measure missed scenes, wrong scenes, duplicate activations, median/P95
      spoken-boundary-to-trigger delay, and eventual catch-up delay separately.
- [ ] Investigate the late Tea house recovery and extra 0.48–1.78 s confirmation
      delays. Avoid claiming the current 25/32 count is an accuracy score.

### 2. Test generalization and interruptions before choosing the default

- [ ] Use held-out books and fresh consented child recordings; keep development
      and evaluation sets separate. Repeat trials to measure ASR variability.
- [ ] Test repeated phonics, short books/final sentences, skipped lines,
      backwards rereading, pauses and alternate readings.
- [ ] Test parent prompts, quoted story sentences, negation, similar off-book
      wording and two speakers. An adult reading the expected sentence may look
      identical to child reading to this text-only tracker.
- [ ] Validate/tune the split proxy beyond key pot/key put; test ambiguous
      compounds and first-scene failures. Its conservative guards can miss valid
      readings as well as prevent wrong matches.
- [ ] Compare fixed vocabulary with automatic moving context separately, since
      tracker progress can change future recognition when moving hints are on.
- [ ] Decide whether to promote split mode only after those measurements. It is
      currently opt-in; do not silently change the default based on these clips.

### 3. Verify live microphone and target hardware

- [ ] Child reading through intended microphone, in the enclosure, with fan/noise
      and the pod's own soundtrack playing. Validate echo-cancellation routing.
- [ ] Test on the actual Jetson/mini-PC alongside media playback; log memory,
      thermals, sustained load and recovery. RTX GPU throttling is not a Jetson test.
- [ ] Confirm clean installation/model-cache setup on a teammate's machine;
      existing benchmark launchers use this Windows/WSL setup and cached models.
- [ ] Review file-client pacing drift and distinguish it from recognizer delay.

### 4. Integrate actual effects and session lifecycle

- [ ] Connect trigger payloads to preloaded projector/video and sound playback;
      replace placeholder assets, then measure real audio/video synchronization.
- [ ] Define persistent ambience versus one-shot event behavior. Late catch-up
      should set the current ambience without replaying every missed one-shot.
- [ ] Add operator book selection/session reset and define rereading behavior.
      State is currently in memory and resets when the client restarts.
- [ ] Define disconnect/reconnect and restart recovery; add persistence if needed.
- [ ] Resolve current project scope (visuals/audio versus optional lighting) with
      the team before building the actuator layer; payload fields reflect prototype
      examples, not proof that every hardware subsystem is implemented.

### 5. Operational cleanup

- [ ] Bound production Whisper finalization: the live benchmark patches a 30 s
      maximum after audio ends, but normal run_client.py still uses upstream
      final-hypothesis settling. One excluded attempt waited until the 240 s
      benchmark timeout. Retained runs finished before the cap.
- [ ] Classify normal WebSocket code 1000 closes as successful finalization instead
      of ERROR when the transcript is complete; preserve real failure reporting.
- [ ] Replace the benchmark's raw TCP readiness probe with a suitable readiness
      check to avoid harmless WebSocket handshake warnings.
- [ ] Archive ignored raw benchmark logs/events/transcripts securely and preserve
      source/model/dependency versions for reproducibility. The committed JSON
      summary is portable; raw data and installed models are not pushed.
- [ ] Complete operator/sensory limits, rights/consent and deployment safety review
      before use in a public pod. These remain wider project tasks.

## Evidence and reproduction files

- `benchmarks/LIVE_TRACKER_RESULTS.md`: fresh audio results and caveats.
- `benchmarks/results/live-tracker-2026-10-24.json`: committed portable results,
  packet audit, trigger times and source/audio hashes; no raw transcripts.
- `benchmarks/SPLIT_REPLAY.md`: earlier saved-transcript split comparison.
- `benchmarks/EVIDENCE_REPLAY.md`: earlier evidence-only comparison.
- `benchmarks/live_tracker_probe.py`: live packet/ASR/tracker event logger.
- `benchmarks/run_live_tracker_comparison.py`: Windows benchmark runner, ports
  9096 (Whisper) / 9097 (Parakeet). Parakeet requires an external WSL server.
- `benchmarks/summarize_live_tracker.py`: summarizes the raw live artifacts.
- `benchmarks/replay_evidence.py`: scoped replay of the historical saved streams.
- `benchmarks/diagnose_*.py`: diagnostics; the stove diagnostic is an explicit
  alias experiment, not the production matching implementation.

From repository root, on the prepared Windows PC:

```powershell
.\.venv\Scripts\python.exe benchmarks/run_live_tracker_comparison.py --model medium.en
# Stop Whisper first; start the WSL Parakeet server on port 9097, then:
.\.venv\Scripts\python.exe benchmarks/run_live_tracker_comparison.py --model parakeet-nemo --external-server
.\.venv\Scripts\python.exe benchmarks/summarize_live_tracker.py
```

Use `--resume` only for interrupted runs belonging to the same protocol/source
version. The runner currently writes to output/live-tracker-2026-10-24; archive
that directory or change the output destination before a new independent run,
otherwise existing evidence may be overwritten. Replay/diagnostic scripts need
the local ignored historical artifacts; the committed summary can be read on a
fresh clone without those artifacts.
