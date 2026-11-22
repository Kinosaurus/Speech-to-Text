# Interrupted reading with Nemotron 160 ms, 22 November 2026

The current RapidFuzz + CMU tracker handles the constructed silent pauses,
including a 90-second mid-cue pause. Spoken interruptions expose premature
effects with Low checkpoint hints. Turning hints off improves this batch but
still leaves a long-conversation miss and a pause-induced miss in Tea. These
results do not establish reliable interruption handling.

The production Nemotron WebSocket server and `TimelyEvidenceMatcher` (the
panel's `split` mode) ran unchanged: trained 160 ms `[70,1]` context, bfloat16,
threshold 82, stability 2, coverage 0.8, 80 ms input packets. Low supplies only
the next checkpoint phrase at boost 1.0; the comparator disables phrase hints.
Each configuration received exactly the same 25 WAVs, for 50 completed streams
and approximately 36.5 minutes of audio including the constructed silence.

| Synthetic check | Low hints | Hints off |
|---|---:|---:|
| Clean reads | 2/2 pass | 2/2 pass |
| Silent pauses: opening 2/15/90 s and acquired cue 15 s | 4/4 pass | 4/4 pass |
| Parent questions, asides, conversations, restart/reread | 0/7 pass | 6/7 pass |
| Omission, wrong ending, endpoint-only, prompt and skip controls | 3/6 pass | 6/6 pass |
| **All synthetic cases** | **9/19 pass** | **18/19 pass** |
| Premature target effects in positive cases | 7 | 0 |
| Unexpected effects in negative cases | 3 | 0 |
| Duplicate effects | 0 | 0 |

A passing synthetic case must emit every expected effect once, emit no other
effect, and never emit the interrupted target before its missing suffix audio
begins. This last condition is a conservative early-trigger check; it does not
measure the precise spoken word ending or effect latency. Later checkpoints
are also checked after the interruption.

With Low hints, Nemotron fills in authored cue words during off-book speech.
For example, the opening parent-question trial emits `seed_found` at 5.76 s,
although its missing suffix audio begins at 8.21 s. The ASR callback already
contains the complete cue while the generated audio is still the question.
The tracker then accepts that recognized cue. The seven spoken positive cases
all emit prematurely. The endpoint-only, omitted-ending and wrong-ending controls
also emit the interrupted cue incorrectly. Explicit negated/quoted prompts and
the skipped-cue control stay non-emitting for that cue.

With hints off, those premature and unexpected effects disappear on these
samples. The opening long-conversation case instead misses `seed_found`: the
resumed ASR says “seat” for “seed,” and the one-shot permission check suppresses
the cue. A separate diagnostic feeding the intended words directly through the
same tracker passes all 19 scripts. Its word-update times are interpolated and
are not recognition or acoustic measurements.

| Original recording | Original replay, either hint setting | Inserted 15 s pause, either hint setting |
|---|---:|---:|
| Horse | 1/1 configured cues | 1/1 |
| Tea | 3/3 | 2/3; stove cue lost |
| Little Mermaid | 1/2 | 1/2; same missing cue |

Every original speech sample is preserved. The pause is inserted at the fixed
recording midpoint, which can split a word; it is not a manually word-aligned
natural pause. Tea changes from recognizing “teapot” to “tea put” in the paused
run and skips `teapot_on_stove` in both configurations. Little Mermaid already
misses `mermaid_cannot_speak` in the original, so its miss is not a new lost cue.
These counts describe configured-cue coverage, not human-verified effect accuracy.

All 50 streams have full sample delivery, packet acknowledgements, final
transcripts and `STREAM_DONE`. Independent replay of saved callbacks reproduces
all recorded tracker decisions and progress positions. Input/source hashes and
the original-versus-paused PCM identity checks pass. The full Windows unit suite
also passed: 294 tests passed, one GPU-only test skipped. The fresh audio trials
use the real WSL GPU server. No matcher, threshold, model or panel setting was
tuned during this experiment.

The 19 synthetic cases use Microsoft Zira adult speech on the sample Sky Garden
passage, including the same voice for reader and interruption. The three original
recordings provide paired pause checks. This is a small constructed stress test,
not a live child/parent evaluation or a population false-trigger estimate.
The harness sends packets faster than real time and fences them with context
acknowledgements. Recognition and matching are real; the complete panel client,
microphone, speaker, projector and physical effect latency are not tested here.

The portable [audited aggregate](results/nemotron-interruptions-20261122.json)
contains the per-case outcomes without transcripts or audio. WAVs, SSML,
callbacks, manifests, validation details and frozen sources remain locally under
`output/nemotron-interruptions-20261122/`.

Reproduce with a fresh output directory and an already-ready Nemotron 160 ms
server. Use your installed WSL distro in place of `Ubuntu-24.04`:

```powershell
$repo = (Get-Location).Path
.\.venv\Scripts\python.exe benchmarks/run_nemotron_interruptions.py prepare --output output/interruption-retest
powershell -NoProfile -ExecutionPolicy Bypass -File benchmarks/synthesize_challenges.ps1 -OutputDirectory output/interruption-retest
.\.venv\Scripts\python.exe benchmarks/run_nemotron_interruptions.py assemble --output output/interruption-retest
wsl -d Ubuntu-24.04 --cd $repo --exec bash scripts/reading-pod/nemo-python.sh benchmarks/run_nemotron_interruptions.py run --output output/interruption-retest
wsl -d Ubuntu-24.04 --cd $repo --exec bash scripts/reading-pod/nemo-python.sh benchmarks/run_nemotron_interruptions.py run --output output/interruption-retest --hints-off
.\.venv\Scripts\python.exe benchmarks/summarize_nemotron_interruptions.py --output output/interruption-retest
```
