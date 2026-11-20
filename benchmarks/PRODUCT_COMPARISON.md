# Voice-reactive reading systems: measured pilot and product-test protocol

Updated 19 November 2026. The quiet synthetic pilot is complete for two
book-specific matched comparisons. It is exploratory, not a general accuracy
ranking, a human-reader test, or a full inventory of either vendor's cues.

Subsequent Pod tuning reduced measured response delay while retaining tested
checkpoint hits. See the [latency investigation](LATENCY_INVESTIGATION.md).
The commercial-comparison table below preserves its original 560/560 ms settings.

## Actual synthetic pilot results (estimated)

| Matched text | System | Median effect delay | Selected targets hit | Replays |
|---|---|---:|---:|---:|
| The Lion and the Mouse, 147-word excerpt | Reading Pod (NeMo + shared matcher) | 1.33 s | 8 / 8 | 2 |
| Same excerpt | Readmio 2.7.2 | 0.13 s | 8 / 8 | 2 |
| The Moon, R. L. Stevenson | Reading Pod (NeMo + shared matcher) | 1.80 s | 6 / 6 | 2 |
| Same poem | Novel Effect 4.2.9 | 0.20 s | 6 / 6 | 2 |

The excerpt pair has four targets per run; the poem pair has three. Counts pool
two replays of one identical locally synthesized recording within each pair.
Do not compare Novel Effect directly against Readmio across different texts.
Median delay pools detected events: captured digital sound onset minus estimated
spoken phrase ending. It is not ASR word latency or a physical speaker measurement.
Negative delays (early starts) are retained. Readmio's second run included a
2.72-second late event despite its low pooled median. Its per-run medians were
0.07 / 0.17 seconds, versus Pod's 1.80 / 1.25. The Moon per-run medians were
0.21 / 0.19 for Novel Effect and 1.80 / 1.79 for Reading Pod.

**The original four-candidate Pod poem result remains 6 / 8, not 6 / 6.**
Opening, cat and mouse fired twice each; dog missed twice despite appearing in
the final ASR transcript. Dog was excluded from BOTH systems' matched subset
because no distinct Novel Effect response could be verified from its controls.
It was not marked a Novel Effect hit or miss. The six matched Pod hits are the
same six events as before; only the explicitly labeled common denominator differs.

## Automatic Novel Effect annotation

The agent completed annotation without asking the user to listen. Byte-identical
prefixes of the 45.09-second synthetic master were cut immediately before and
after candidate phrases, followed by silence. New repeatable waveform components
had to match a separate original full calibration capture and be distinguishable
from negative controls. Opening, 'The squalling cat' and 'the squeaking mouse'
passed. These are phrase-associated component labels, not a claim that cat/mouse
sound identities were confirmed by listening. The session-start chime was
excluded. The clock candidate overlaps the opening response and was not counted
again. Dog remains unverified; there may be other vendor cues outside this scope.

The component templates, bands, onset offsets and threshold 0.55 were frozen and
SHA-256 hashed before evaluation output was inspected. Two separate full-read
captures then scored 3 / 3 each. The first capture already existed at freeze time;
neither evaluation waveform was used to fit the detector. Opening uses 10 ms
onset frames; cat/mouse leading-edge estimates use 80 ms windows with 20 ms steps.
Recorded native Android frame clocks verify complete 1x presentation: 45.0925
and 45.0923 seconds versus a nominal 45.09 seconds. This is not millisecond-exact
ground truth: component alignment and synthetic phrase endings are estimated.

Target discovery used calibration, and the Pod poem runs preceded the final
common-subset selection. This is an exploratory paired pilot, not a preregistered
held-out accuracy experiment. Complete cue coverage, duplicate/false-positive
rates and recovery from skipped/repeated text were not established.

## Common playback and measurement method

Source: local Microsoft David Desktop, rate 0. The same master WAV was replayed
at 1x to each member of a pair; hashes verify the phone resampled PCM. No existing
human or child recording was supplied to either product. NeMo used full-text
hints and its resident managed default boost. The production shared matcher was
unchanged: threshold 82, stability 2, coverage 0.8. Pod used the production
SoundPlayer with its native stream warmed, and existing short local marker sounds
for the poem, rather than imitating the vendor soundscape.

The Android apps ran on the Samsung A54 with verified unsilenced remote-submix
input (type 25), phone media volume zero, and Wi-Fi/cellular off during replay.
Their real digital output was captured. Pod ran on this Windows PC with resident
WSL CUDA NeMo. Windows process-only loopback captured the benchmark process;
physical output mute was restored to its original state. Native output timestamps
and SAPI estimated word/phoneme endings provide timing; a successful callback or
OSC send alone was never counted as sound playback.

Pod's estimated synthetic WER was 0 / 149 normalized words for the 147-word
excerpt and 3 / 105 (2.9%) for each poem run. Vendor WER is unavailable because
neither app exposed a usable recognition transcript. Cue hits do not imply WER.
The first Readmio replay calibrated its official-asset waveform detector; its
second replay used that same detector. This also limits held-out claims.

Ten focused scoring/annotation tests pass, including clock interpolation,
startup-chime exclusion, negative-control rejection and continuing-background
rejection. New evaluation scores use the frozen detector without tuning to their
results. Matcher file hashes still match the saved method audit.

## Cleanup, artifacts and remaining checks

The phone was restored and independently checked: media volume 6, cellular on,
Wi-Fi on (preserved from the user's current setting), USB stay-awake off, original
microphone AppOps retained, Novel Effect stopped and no test helper running.
All owned device temporary files were removed. Incomplete USB-disconnected and
splash-screen attempts remain archived locally and are excluded from scores.
Local transcripts/captures were not uploaded. Offline playback does not constitute
an audit of vendor telemetry after reconnection. Earlier catalog-only microphone
uncertainty is retained in the historical audit below.

Physical microphone acoustics, loudspeakers, projector output/delay and human
reader behavior remain untested here. The user has not confirmed any of them
for this benchmark. Next work should cover human readings with checked word
endings, noise, accents, pauses, unrelated speech, repeats and skipped cues.

Open `output/product-comparison-20261119/review.html` for the quiet-until-clicked
report, `comparison-canva.csv` for presentation import, and `comparison.json`
for per-event evidence. Annotation controls/templates/freeze are under
`output/novel-cue-annotation-20261119-results`. Novel evaluation captures are
`output/novel-cue-annotation-20261119-validation/full-01` and
`output/novel-cue-annotation-20261119-validation-repeat/full-01`. The final device
audit is `output/product-comparison-20261119/phone-restoration-final.json`.

Reproduce using `product_comparison/novel_isolate.py`, `annotate_novel.py`,
`score_novel.py`, `pod_replay.py`, `score.py` and `build_report.py`.
Preserve existing trial directories and failed attempts; choose fresh output
paths for new captures. Validate frozen hashes before evaluating or rebuilding.
The Windows output helper is `product_comparison/ProcessAudio.cs`; the Android
helper is `android/QuietAudioSession.java`.

A local PANNs sound classifier was tried and rejected for cue scoring because it
could not confidently identify the cat/mouse components. It did not determine
any reported hit or latency. Provenance is saved in the local audio-tagger folder.

## What has actually been compared

The local project also has recorded ASR, matcher and boost experiments. KeenASR is an
SDK tested with our recordings and matcher. Novel Effect names Keen Research and
other components in its recognition system, so an SDK result cannot stand in for
the product's full recognition, tracking, content or playback pipeline. No
completed commercial-app head-to-head test was found before this pilot.
The iteration report describes the Novel Effect replay as a proposal rather than
a completed experiment. Our current word-error and word-timing references remain
provisional ASR drafts. See [the local experiment method](ASR_REFERENCE_REVIEW.md).

## Documented capabilities

| Capability | Novel Effect | Readmio | Reading Pod prototype |
|---|---|---|---|
| Recognition | Vendor describes on-device recognition powered by Keen Research and other components [1] | Vendor describes on-device recognition [3], with offline recognition in its official app listing [5] | Local NeMo plus the shared checkpoint matcher; separate KeenASR SDK trials |
| Response | Music, sound effects and character voices follow the read-aloud [1] | Sounds and music respond to reading [3] | Local sound cues and MapMap wall projection |
| Content workflow | Curated soundscapes assembled by designers in Soundscape Studio [2] | Curated stories; PDFs can be printed and used with the app [4] | Editable checkpoint-to-scene assignments, shared media folder and wall layout |
| Evidence available here | Selected synthetic phrase responses measured | Selected synthetic excerpt responses measured | Saved local ASR callbacks, estimated WER/word delay, checkpoint replay and hardware observations recorded separately |

This table describes the cited workflows. It does not assert that either vendor
can never support projection or customization. Local speech recognition is
already present in existing products. The prototype's focus is operator-editable
checkpoints, visible match evidence and integration with mapped room projection.

Privacy scope needs care: a vendor's statement about on-device recognition does
not establish that every kind of telemetry stays local. Novel Effect's privacy
policy describes recognition-result logging and consent-dependent audio
collection [6]. Mobile and web configurations must be evaluated separately.
No existing child recordings or transcripts were sent to either product.

## Next: broader human-reader comparison

Use Novel Effect versus Reading Pod on an identical, supported printed edition.
Choose the book from the app's current catalog, then prepare the same passage in
our local manifest. Readmio needs its own matched-content pair if the same text is
not available in both catalogs. Do not compare different translations or editions
as if they were the same audio/text condition.

1. Calibrate once, identify observable story events both systems support, and
   freeze their expected positions before evaluation. Vendor cue IDs need not
   match our checkpoint IDs. Freeze our matcher settings and selected ASR boost.
2. Make fresh adult test recordings with exact spoken references and manually
   checked phrase endings. Do not silently repurpose the existing child audio.
3. Replay the same source at 1x to each system, through matched input and output
   paths. Record input plus captured output on one clock. Keep account/device,
   edition, app version, cached/offline state, microphone and output path in the log.
4. Test a clean read, slow read, pause with a question, repeated phrase, skipped
   phrase and unrelated speech. Repeat each condition for a reliability estimate.
5. Measure the actual app output as well as our internal trigger log. A cue being
   sent over OSC does not prove a sound or projection appeared.
6. Use an offline device configuration where verified, or new non-sensitive test
   speech under an explicitly agreed data route. Capture output to headphones or
   a virtual audio sink for quiet testing when supported. Physical microphone,
   speaker feedback and projector checks are a separate later stage.

| Metric | How the product comparison should work |
|---|---|
| Correct events / expected events | Both systems judged against predeclared observable story events |
| Misses, duplicates, false or early events | Report separately, including skipped phrases and unrelated speech |
| Median response delay | Audible output onset minus manually checked spoken event/phrase ending, on one clock |
| Recovery | Whether reading resumes correctly after pauses, repetition and skips |
| WER | Only if the product exposes a usable transcript against the same verified reference; otherwise unavailable |

Our ASR word delay is a different measure from a commercial app's audible effect
delay. WER must never be inferred from cue counts. P95 remains in detailed
internal reports, while the presentation can focus on median latency, WER where
observable, and correct event counts.

The synthetic pilot above covers selected verified responses in both matched pairs. Broader testing requires human recordings, checked phrase endings and complete observable event schedules.

## Initial physical-phone preflight history, 19 November 2026 (superseded status)

The following records earlier steps and limitations. Pending statements here
are historical; the completed measurements and cleanup above are current.

Inspected the installed catalogs on the authorized Samsung SM-A546E, Android
SDK 37: Novel Effect 4.2.9 and Readmio 2.7.2. Catalog navigation works in both;
paid-content entitlement and offline recognition have not yet been tested.
Novel Effect's Little Red Riding Hood is the Jerry Pinkney edition (public
catalog ISBN 9780316013550). Readmio's title credits Charles Perrault for the
story. Identical wording has not been verified, so these titles must not yet be
treated as one shared text. Readmio's Goldilocks search and Novel Effect's
Twinkle search returned no results. These searches do not establish that no
shared text exists anywhere in the catalogs.

The local Android helper `android/QuietAudioProbe.java` successfully initialized
app-specific loopback input and output objects for both apps using the existing
authorized ADB shell audio permissions. It did not play PCM, start capture, or
open a physical microphone. Initialization is not proof of correct signal
delivery, effective speaker suppression during playback, or app sound capture.
Those require a separate calibration before scoring any trials. No benchmark
recordings or transcripts were supplied to either app.

The phone's original media volume, microphone AppOps and USB stay-awake setting
were restored and checked after catalog inspection. Test app sessions were
stopped and our temporary device probe/XML files removed. Local evidence and
the still-empty product result fields are in
`output/product-comparison-20261119/preflight.json`. The content choice is
pending: keep searching for one exact shared text, or use two explicitly labeled
matched pairs, replaying identical audio to Reading Pod and one commercial app
within each pair. No median effect-latency or checkpoint-hit result is available
yet.

The user subsequently selected two matched comparisons. Novel Effect's free
in-app e-book of Robert Louis Stevenson's public-domain poem *The Moon* was
downloaded. Its full-poem page was inspected and transcribed to
`product_comparison/novel_effect_moon.txt`. The pair preparation record is
`product_comparison/pairs.json`. Readmio's catalog offers *The Lion and the
Mouse*, but that candidate's reading access and exact text are still unverified.
The existing benchmark recordings do not match these texts; the choice between
new local synthetic readings and fresh human recordings is pending. No synthetic
reading has been generated and no scored product replay has run.

The optional `QuietAudioProbe com.android.shell --self-test-output` calibration
successfully sent and captured a one-second generated 997 Hz tone solely through
the shell UID's loopback output route while media volume was zero. The captured
signal peaked at 1500 PCM16 units, with no read error; the record device type was
25 (remote submix). The final run released its audio objects, unregistered the
policy and exited with code zero. This confirms the shell output signal path,
not speech injection into either commercial app or capture of their soundscapes.
The earlier initialization-only probe description refers to its default mode;
the optional self-test starts digital output capture and plays the generated
tone, with no physical microphone. Phone navigation stopped when the foreground
changed to another app.

Microphone audit limitation: opening Novel Effect's e-book entered its listening
screen despite a requested UID-level RECORD_AUDIO ignore mode. The restoration
query showed a recent package-level allow interval of about 14 seconds. This
does not certify that ambient microphone input was blocked. The session was
stopped; no benchmark recording or reference transcript was supplied, but ambient
recognition and vendor telemetry cannot be independently ruled out from these
probes. The helper's verified remote-submix output capture is separate from the
commercial app's microphone behavior. Verify the effective input route before
starting any subsequent app listening session.

## Primary sources

[1] [Novel Effect FAQ](https://noveleffect.com/faq/): read-aloud behavior,
supported content and the named recognition components.

[2] [Novel Effect: Behind the Soundscapes](https://noveleffect.com/behind-the-soundscapes/):
designer-led audio production and Soundscape Studio.

[3] [Readmio](https://www.readmio.com/): sound-enhanced reading and the stated
on-device recognition route.

[4] [Readmio: Our Stories](https://www.readmio.com/our-stories): printing a story
PDF and using its QR code with the app.

[5] [Readmio's official App Store listing](https://apps.apple.com/us/app/readmio-kids-books-read-aloud/id1473021827):
offline speech-recognition claim.

[6] [Novel Effect privacy policy](https://noveleffect.com/privacy-policy/):
recognition-result logging and audio-data provisions. This is product-document
review, not an independent privacy audit.
