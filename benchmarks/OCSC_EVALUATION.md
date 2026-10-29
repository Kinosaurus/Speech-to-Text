# OCSC held-out tracker evaluation

Follow-up: the boundary carry fix and three-way fresh streaming results are in
[BOUNDARY_CONFIRMATION_RESULTS.md](BOUNDARY_CONFIRMATION_RESULTS.md). The
two-way results below are preserved as the pre-fix evaluation.

Status: completed fresh Parakeet streaming comparison on 28 October 2026.
Results and local provenance are under ignored `output/ocsc/`. No tracker
thresholds or behavior were changed during this evaluation.

## Results

| Recording | Reached scenes | Original caught / missed | New split caught / missed | Unexpected / duplicate (each) |
| --- | ---: | --- | --- | --- |
| 6008 | 3 | 2 / 1 | 2 / 1 | 0 / 0 |
| 7057 | 1 | 0 / 1 | 0 / 1 | 0 / 0 |
| Total | 4 | 2 / 2 | 2 / 2 | 0 / 0 |

Neither tracker triggered either of the two unread scenes in 7057. There were
no apparent premature triggers among the shared activations. This tests wrong
scenes within two on-book recordings, not a separate wrong-book/adversarial
control set. Zero observed wrong triggers here is not a general safety rate.

| Shared scene in 6008 | Original delay | New delay |
| --- | ---: | ---: |
| live_with_grandma | about 19.01 s | about 19.01 s |
| ambulance_hospital | about 2.83 s | about 2.83 s |

These are approximate delays from the CHAT utterance endpoint mapped onto the
sender's actual packet clock, removing accumulated pacing drift. Raw wall time
minus nominal clip position gives 22.81 s and 8.42 s respectively; both measures
are retained in `output/ocsc/results/scored.json`. Interpolation within packets
adds up to roughly one packet (256 ms) of uncertainty, in addition to the
unverified source timing. The split observer runs second, arriving 2.7 ms and
1.7 ms later on the same callbacks; that is instrumentation overhead, not an
independent recognition delay. The much larger shared late arrivals remain a
usability issue regardless of that small difference.

**Conclusion: no improvement on this held-out sample.** Both trackers catch the
same two of four reached scenes. The earlier gains on other recordings do not
establish reliable handling of these children's disfluencies and interruptions.

### Why the two scenes were missed

- 6008, `kind_boy`: online alignment advances through the final sentence, but
  confirmations belong to the preceding scene until the endpoint is crossed.
  At audio time 171.520 s, the final word produces one candidate for the new
  scene (score 100). Confirmation resets to 1; subsequent conversation supplies
  no second accepted candidate. The scene never triggers. This demonstrates
  that the earlier final-boundary fix is incomplete: it allows same-position
  support if another qualifying revision arrives, but does not guarantee usable
  pre-boundary evidence transfers into the newly reached scene.
- 7057, `live_with_grandma`: the child omits a reference word and then stops
  reading. At audio time 123.904 s the endpoint is accepted with score 88.89,
  but again only one confirmation belongs to the reached scene. Adult praise
  and task-transition speech follow, so no second qualifying match arrives.
  The contextual split-token rule cannot address an omitted word or this
  confirmation reset.

The late first activation in 6008 is catch-up after the child has moved into
the following paragraph. Both trackers fail to confirm promptly at the first
endpoint, then activate after later alignment recovers. A scene counted as
caught is therefore not necessarily an effect delivered at an acceptable time.

Potential next change: preserve bounded, ordered sentence-prefix evidence when
crossing a scene boundary, while requiring fresh support for the ending words.
Do not simply lower the confirmation count or start a timer. This requires
separate controls for partial sentences, abandoned reading, corrections,
adult prompts and wrong-book speech before claiming improved reliability.

### Streaming verification

- All 3,318,033 and 2,126,768 samples delivered, respectively, in packets of
  4,096 samples plus each final remainder, at 16 kHz mono.
- Audio durations: 207.377 s and 132.923 s. Measured delivery: 215.999 s and
  138.903 s, exposing ordinary sender scheduling drift rather than hiding it.
- First live recognition callbacks at 5.148 s and 4.171 s, before EOF.
- Original AlignmentMatcher and experimental SplitEvidenceMatcher processed
  the same fresh streaming callbacks, with no book hints and unchanged settings.
- Both clients exited 0. Final completed ASR segments covered all samples and
  sockets closed normally (1000). The existing client labels that normal close
  as an ERROR line; the final-segment and closure audits distinguish it from
  recognition failure.
- Application scene triggers exactly matched the split observer's triggers.
- Full existing unit suite: 94 tests passed. Temporary server stopped afterward.

Raw callback/packet logs, fresh transcripts, source hashes, original timestamps,
and the independently sourced book manifest remain local in `output/ocsc/`.
Reproduce scoring with `benchmarks/summarize_ocsc_streaming.py`; reproduce audio
streaming with `benchmarks/run_ocsc_streaming.py` while the installed server is
running. Neither command needs TalkBank credentials after the files are local.

## Follow-up: earlier first-paragraph checkpoints

At the user's request, a separate manifest adds four sentence endpoints that
both children reach. The original endpoint experiment above is preserved.

1. Grandma has a big house with lots of steps.
2. I like to help her.
3. Mama and I need to find a new home.
4. I want to live with Grandma.

The printed book text, source audio, clips, ASR settings and tracker thresholds
are unchanged. This is exploratory: checkpoints were selected after inspecting
the earlier runs, so it is not another independent held-out benchmark.

| Recording | Reached | Original caught / missed | New caught / missed |
| --- | ---: | --- | --- |
| 7057 | 4 | 1 / 3 | 3 / 1 |
| 6008 | 4 | 4 / 0 | 4 / 0 |
| Total | 8 | 5 / 3 | 7 / 1 |

For 7057, the original skips the first two checkpoints, catches `new_home`, and
misses `live_with_grandma`. The new tracker catches the first three and still
misses `live_with_grandma`. Approximate source-boundary delays adjusted for
sender pacing drift are 22.75 s, 16.19 s and 22.74 s for the new tracker's three
activations. The original's sole activation has the same approximately 22.74 s
delay. The first sentence is misread with a final-word substitution, followed
by adult correction and child repetition; its annotation marks the first
attempt. Even moving that boundary to the correction would leave a large delay.

In 6008 the new tracker catches `help_her` about 2.4 s sooner; the other paired
activations are on the same callback. New-tracker delays for its four scenes
are approximately 12.92 s, 10.16 s, 3.26 s and 19.05 s; original delays are
12.91 s, 12.55 s, 3.26 s and 19.05 s. More eventual activations do not establish
good effect timing: these include catch-up to an earlier scene after reading
has already moved on. Report such late activations separately from unexpected
scene IDs; neither result should be presented as a production-readiness score.

Both full clips completed with all samples delivered, live ASR before EOF,
completed final segments and normal socket closure. Application split triggers
matched observer triggers. Neither mode produced an unexpected scene ID or a
duplicate activation; all detected scenes were late against the approximate
annotations. The temporary server was stopped after the run.

Artifacts: `output/ocsc/subset-early.json`,
`output/ocsc/manifests/grandmas_house_early_story.json`, and
`output/ocsc/results-early/`. Run again with:

```powershell
.\.venv\Scripts\python.exe -u benchmarks/run_ocsc_streaming.py --subset output/ocsc/subset-early.json --results output/ocsc/results-early
.\.venv\Scripts\python.exe benchmarks/summarize_ocsc_streaming.py --results output/ocsc/results-early
```

The selected reading tasks are 6008 (age 6;04.28, 207.377 seconds) and 7057
(age 7;08.25, 132.923 seconds). Only the first child reads the whole reference;
the second reaches the first of three configured checkpoints. The two unread
checkpoints are excluded from missed-scene counts. This is two children and one
passage, not coverage of every age from 4 through 7.

The independently printed reference is Grandma's House in Appendix E, PDF page
97 (printed page 88), of Alana Oif's 2017 Ohio State thesis:
https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=osu149211825867405&disposition=inline
The printed page was visually checked. Its final sentence differs from an extra
sentence in 6008's audio; that continuation remains in the clip and is not added
to the book. CHAT utterance timings are automatically aligned and only provide
approximate latency annotations, not manually verified timing gold.

## Access and provenance

Official corpus: https://talkbank.org/childes/access/Eng-NA/OCSC.html
Browser: https://sla.talkbank.org/TBB/childes/Eng-NA/OCSC
Access rules: https://talkbank.org/childes/access.html
Paper: https://doi.org/10.1016/j.specom.2025.103206

Wagner et al. (2025), The Ohio Child Speech Corpus, Speech Communication 170,
103206. Follow TalkBank access/reuse rules and cite the corpus. Keep downloaded
media, transcripts and derived private manifests under ignored output/ocsc/;
do not publish source recordings or demographic tables in Git.

The official download endpoint returns the authentication interface, not a ZIP,
for an unauthenticated request. Sign-in must be completed normally. The media
endpoint also encountered a local certificate verification error during the
access check; do not disable TLS verification as a workaround. Browser access
can be checked after authentication; investigate certificate trust if needed.

## Selection protocol (before ASR output is inspected)

1. Inspect registered-access transcripts and minimal metadata for ages >=4 and
   <8 years and sections marked @G: Reading. Exclude sessions without actual
   passage reading; report unavailable age groups instead of silently using
   older children. Aim initially for 4â€“6 reading clips across different children
   and more than one passage, subject to availability and download size.
2. Identify the original intended reading card/passage. The source paper points
   to passages used in Cartledge et al. (2015); availability of the exact texts
   for selected sessions still needs verification. Do not reconstruct a perfect
   book from the child's transcript or ASR. If original text is unavailable,
   report that limitation rather than calling transcript-following a book test.
3. Preserve source identifiers, minimal age information, source URL, source-file
   hashes, passage source, section time ranges and conversion parameters in a
   local subset inventory. Retain original recordings and work on derived clips.
4. Extract only reading-task spans, keeping natural interruptions/prompts and
   retaining mapping to original timestamps. Convert to 16 kHz mono PCM WAV.
5. Author checkpoint word ranges from the intended passage BEFORE recognition,
   preferably several sentence boundaries spread through each passage. Record
   actual spoken boundaries/skips/parent utterances independently for scoring.

## Streaming comparison

Use the existing installed WSL Parakeet NeMo server, normal GPU settings, and
actual paced run_client.py file input. Original and split observers process the
same fresh ASR callbacks online. Primary comparison uses no book hints to isolate
tracking; any fixed-hint condition must be identical between observers and
reported separately. No threshold/heuristic tuning on this evaluation subset.
The probe now respects --checkpoints with an arbitrary explicit manifest path.

Template, once a verified clip and manifest exist:

```powershell
.\.venv\Scripts\python.exe -u benchmarks/run_ocsc_streaming.py

# Or a single clip:
.\.venv\Scripts\python.exe -u benchmarks/live_tracker_probe.py --model parakeet-nemo --server 127.0.0.1 --port 9097 --matching_mode split --files recordings/library/reading_sessions/CLIP/audio.wav --mute_audio_playback --checkpoints recordings/library/reading_sessions/CLIP/checkpoints.json --no_book_context --transcript_file output/ocsc/results/CLIP.srt
```

Create the result directory first. Run one session at a time. Verify complete
sample delivery, paced packet timestamps, partial ASR before EOF, successful
native finalization, and agreement of app split triggers with its live observer.

Report configured opportunities, actual scene arrivals, missed/wrong/duplicate
activations, late catch-up and delays separately. Compare paired trigger callback
arrival times; actual spoken-boundary delay requires annotations. No activation
rate should be reported as accuracy without that ground truth. Do not remove
child errors or parent prompts merely to improve measured scores.

## Preparation completed

- Generic explicit manifest resolution in benchmarks/observer_manifests.py.
- Live probe uses the supplied manifest path for both tracker observers.
- Three tests cover custom corpus paths, missing files and existing off-book
  defaults. Full suite: 94 tests pass. No matching thresholds were changed.
