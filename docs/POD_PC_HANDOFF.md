# Reading pod PC handoff

Use three separate folders so each checkout keeps its own setup. The Parakeet baseline is `main` at `90a8710`. The Keen browser prototype is `keenasr-first` at `21750e9`. This handoff branch contains the replay scripts and a Mermaid ambience experiment. Use the two baseline branches for scored comparisons. The ambience experiment allows scene progress to start an effect without the final-word check.

## Set up the other PC

1. Clone the repository and open PowerShell in the clone. For an existing clone, run `git fetch origin` and update `main` with `git pull --ff-only` while on that branch.

   ```powershell
   git clone https://github.com/Kinosaurus/Speech-to-Text.git
   cd Speech-to-Text
   git worktree add --detach ../Speech-to-Text-Keen origin/keenasr-first
   git worktree add --detach ../Speech-to-Text-Handoff origin/codex/pod-pc-handoff
   ```

2. Transfer and extract `pod-pc-transfer.zip` into a separate local data folder. It contains the eight paired timing WAVs and the results. For all 50 benchmark WAVs, also transfer the original `Books-to-Life-recordings.zip` and use its `recording-index.json`.
3. In `Speech-to-Text-Keen`, install Python 3.10 or newer, then run the commands below. Place the Keen Web SDK and English bundle obtained through Keen in `public/vendor/keenasr/`. See the [Keen branch setup](https://github.com/Kinosaurus/Speech-to-Text/tree/keenasr-first#quick-start). The SDK and model have separate licensing. Obtain written permission before using Keen for the supervised pilot.

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe server.py
   ```

4. Open [Mermaid](http://localhost:8000/) or [Tea](http://localhost:8000/?book=tea) in Chrome or Edge. Select **Recorded audio**, load a WAV, initialize Keen, then start reading. The guarded matcher uses stability 2. The browser displays cue events. Connect the installation's output player to those events before measuring physical output.
5. In the main checkout, follow [Parakeet NeMo setup](SETUPS.md). Use CUDA, split matching, `--no_book_context`, and `--checkpoint_stability 2`. For the paired test, run `parakeet.py` from the transfer ZIP as described in its README. It loads the Keen checkout's matcher and manifests.

## Verify the pod and compare Novel Effect

- Verify the actual projector and speakers respond to a test effect. MapMap is optional. For Sky Garden, copy the transfer ZIP's `Reading Pod MapMap/` folder to the main checkout and its `MapMap-Reading-Pod/` folder to `tmp/MapMap-Reading-Pod/` there. Follow `Reading Pod MapMap/Sky Garden/README.md` to relink the media for this PC and confirm the output screen and OSC port. Its spoken demo uses stability 1.
- Replay the eight Tea and Mermaid recordings. Check that each expected cue fires once and both conversation controls stay quiet. The software reference at stability 2 was 12 of 13 for Keen and 6 of 13 for Parakeet. Both missed Mermaid's second cue when the parent interrupted immediately before “speak.” Keen's median lead was 0.10 seconds on six shared triggers. See `results/paired-timing.json` in the transfer ZIP.
- Capture the WAV playback and speaker output together on the pod. Include the wall in the video if you also want projection timing. Mark the end of each spoken cue, the first transcript containing the cue word, the matcher trigger, and the first audible or visible effect. Use the same audio output and capture method for both recognizers.
- For Novel Effect, start with Robert Louis Stevenson's [The Cow](https://www.gutenberg.org/cache/epub/136/pg136.html.utf8) in the mobile app. Its [published catalog](https://docs.google.com/spreadsheets/d/1RM0Zy4uVEoqACLdv1CKxjkCgjQ70ewGdAtVdQFmRKfE/edit?usp=sharing) lists the poem as free in-app. Confirm access in the app. Record a clean read, find two or three sounds that reliably follow identifiable lines, then configure the same moments as Books to Life checkpoints. Replay the same takes with pauses, skipped lines, a parent handoff, and conversation alone. Compare missed or extra sounds and spoken cue to audible sound onset. The published catalog did not provide a verified match for our Mermaid recording.
