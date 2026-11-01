# Supervised Singapore microphone pilot — collection kit

This is preparation, **not a completed Singapore evaluation**. The original
[passage](passage.txt), [four checkpoints](checkpoints.json), and
[blank session metadata](session-template.json) are ready. No child voice,
country, age, or human timing label has been generated or inferred. The passage
has not been calibrated to a reading age.

First do an adult equipment smoke test, then a small supervised child pilot.
Use participants whose guardian/site permissions cover the test and recording.
Use pseudonymous IDs and keep raw audio locally under ignored `output/`.

## Capture

Start the documented Parakeet NeMo server on port 9097. From the project root:

```powershell
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --list_input_devices
New-Item -ItemType Directory -Force output/singapore-pilot/reader-001/quiet-01 | Out-Null
.\.venv\Scripts\python.exe -m books_to_life.cli.run_client --model parakeet-nemo --server 127.0.0.1 --port 9097 --matching_mode split --no_book_context --checkpoints docs/pilot/singapore/checkpoints.json --save_output_recording --output_file output/singapore-pilot/reader-001/quiet-01/audio.wav --transcript_file output/singapore-pilot/reader-001/quiet-01/transcript.srt
```

Select the intended device using `--input_device` if the default is wrong.
Read through the actual microphone/enclosure; Ctrl+C ends capture. Check that
both files were saved. Copy the metadata template into the session folder and
fill in actual details. Terminal payloads are not proof of hardware actuation.

## Conditions

Collect quiet reading and a separate take with the intended pod soundtrack.
Keep microphone placement consistent and record soundtrack settings. Include
natural pauses and self-corrections. Retain all takes and label conditions.

Separately record adult controls: unrelated conversation; omission of `opened`,
`jumped`, or `hung`; quoted-anchor instructions; genuine skipping/resumption;
and reset/new-session behavior. Adult controls are not child-reading accuracy
observations. Do not join takes to manufacture a continuous reading. Reserve
untouched readers/takes for later evaluation.

## Human review

Record what was said, each audible checkpoint attempt's ending, whether its
effect should fire, and actual effect/log time. Mark omitted/unclear endpoints
explicitly. SRT stream bounds are not word timings. Record wrong, missed,
duplicate, early, and late effects separately.

The three one-shots require their action words. Rain ambience explicitly allows
catch-up. Suppressed/unreached one-shots are not successful effects.
