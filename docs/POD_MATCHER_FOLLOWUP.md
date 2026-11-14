# Pod matcher follow-up

This branch starts from the Parakeet baseline at `90a8710`. It adds two matcher changes. A short match far ahead in the passage needs evidence from the destination cue before it can advance past several cues. A quoted or negated cue needs matching book context before it can fire an effect.

## Results

- The forward-jump fix raised the earlier Keen callback replay from 169 to 175 of 184 cues. Five recoveries came from one gardening-session jump. This was an offline replay of the earlier 169-cue run.
- Parakeet's callback replay stayed at the same 162 of 184 cues after both changes. The original live run had 161.
- Quoted-prompt false triggers dropped from 10 to 0 in the scripted text checks. Five sound-alike ending cases remain. A stricter endpoint experiment blocked those five but lost seven cues in the 50-recording replay, so it was reverted.
- The Keen replay applied the forward-jump change to the Keen checkout's matcher separately. The code on this branch is for the Parakeet checkout.

## On the other PC

1. Fetch this branch and check it out in a separate worktree. Keep the pinned original branches available for reproducing earlier scores.
2. Reuse the original `Books-to-Life-recordings.zip` for the full 50-recording corpus and `pod-pc-transfer.zip` for the eight paired clips. Keep the recordings and raw recognition logs local.
3. Start Parakeet NeMo with CUDA and run the Windows client with split matching, stability 2, and book hints off. Replay the paired cases first, including the conversation controls and Mermaid's “speak” cue.
4. Verify cue-to-speaker and cue-to-projector onset on the physical pod. Record the input, speaker output, and projected wall together. The saved callback replay measures cue decisions.
5. Keep the five sound-alike endings as regression cases. For any proposed change, rerun the 50 recordings and test actual wrong-word utterances alongside recognition errors.
6. When Keen supplies its Linux SDK, test it in WSL with the same streaming client and matcher. Reuse the 50 recordings and compare cue accuracy, transcription error, and real-time trigger latency.
