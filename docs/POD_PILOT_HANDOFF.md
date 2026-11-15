# Pod pilot handoff

## Live microphone capture

The live client now writes the microphone stream as 16 kHz mono PCM to
`recordings/library/captures/<session>/audio.wav` by default. The client
writes `transcript.srt` alongside it on normal shutdown. Use
`--no-save-output-recording` to skip saving the microphone WAV, or
`--output_file` to choose its path. File replay uses the existing input file.

A physical Razer Seiren Mini run verified that both files were saved. On that
reading, standard Parakeet fired the Seed and Flower cues and missed Grass and
Clouds. Cue counts below measure software decisions.

## Replay results

| Test | Standard Parakeet | Passage-guided Parakeet | KeenASR | Vosk Small with book grammar |
|---|---:|---:|---:|---:|
| Mila microphone reading | 2/4 | 3/4 | 4/4 | 4/4 |
| Mermaid pause and interruption clips, both cues | 3/6 | 3/6 | 6/6 | 2/6 |
| Mermaid “cannot speak” cue across those clips | 0/3 | 0/3 | 3/3 | 2/3 |
| Parent-aside control, cues fired | 0 | 0 | 0 | 0 |

The recognizers used the original checkpoint matcher without fallback cues for
this comparison. Keen used its oral-reading graph. Passage-guided Parakeet
updates NeMo's phrase list from recently recognized words. Vosk used a grammar
built from the book's sentences and included an unknown-speech path. The Vosk
replays streamed chunks without pacing. The passage guide and Keen also had
1× runs.

On the 50-recording corpus, the guide fired 157/184 cues versus 162/184 for the
standard no-hints baseline. It recovered 12 cues and lost 17, with no unexpected
or duplicate cue IDs in either run. Tea improved from 1/3 to 3/3. Horse stayed
at 1/1 and the original Mermaid stayed at 2/2. The prototype was streamed
without pacing and the baseline used saved recognition updates rescored with
the same matcher.

Automatic hints at boost 1, 2, and 5 each left Mila at 2/4. An offline
fallback experiment on the saved boost-1 recognition updates recovered both
misses. Grass fired at 36.43 seconds using “across the floor” with a one-second
grace period. Clouds fired at 56.00 seconds using “their shadows moved gently.”
These rules were selected on the same recording and are not part of the live
client.

## Reproduce locally

Both benchmark commands accept a mono 16-bit 16 kHz WAV and the original
checkpoint manifest. Their JSON reports contain transcripts. Put the reports
under ignored local output storage.

- Set up the NeMo environment per [Running](RUNNING.md), including RapidFuzz and
  cmudict, then run `python -m benchmarks.replay_passage_guide --model-path MODEL.nemo --manifest CHECKPOINTS.json --wav INPUT.wav --output output/passage-guide.json --paced`.
- Install `vosk==0.3.45` into a test environment with the matcher dependencies
  and unpack [Vosk Small English](https://alphacephei.com/vosk/models). Run
  `python -m benchmarks.replay_vosk_reading --model-path MODEL_DIR --manifest CHECKPOINTS.json --wav INPUT.wav --output output/vosk.json`.
  Add `--control` for clips that should produce zero effects.

## To do

1. Follow up on a KeenASR production license and Linux/ARM64 availability.
   The Web trial has a 15-minute runtime limit per page load.
2. Keep standard CUDA Parakeet as the pilot default. Verify actual speaker and
   projector onset using one capture of the reader and both outputs.
3. Collect fresh readings with a parent interruption, page skip, and reread.
   Include off-book and wrong-ending controls alongside clean reads.
4. Evaluate one-shot page fallbacks on those fresh recordings before adding
   the rules to the live tracker. Compare recovery, false fires, and effect
   timing against the original checkpoints.
5. If Keen licensing remains blocked, validate Vosk Small on the full corpus
   and on actual Pi hardware before choosing it. Its current book grammar
   trades some missed speech-end cues for missed legs cues on Mermaid.
6. Run the [same Bear Snores On recording](https://www.kidlit.tv/2016/01/read-out-loud-bear-snores-on/)
   through Novel Effect and compare audible effect onset. The local Parakeet
   replay fired all three selected checkpoints. The Novel Effect run is pending.
