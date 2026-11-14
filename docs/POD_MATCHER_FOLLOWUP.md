# Pod matcher follow-up

This branch starts from the Parakeet baseline at `90a8710`. A short match far ahead in the passage needs evidence from the destination cue before it can advance past several cues. Either voice can supply the cue, including through positive coaching. The cue still needs its required words and endpoint. An explicitly negated cue needs matching book context before it can fire an effect.

## Results

- The forward-jump fix raised the earlier Keen callback replay from 169 to 175 of 184 cues. Five recoveries came from one gardening-session jump. This was an offline replay of the earlier 169-cue run.
- On the same 50-recording corpus, four-thread Parakeet Q8 CPU fired 161 of 184 expected cues and Parakeet NeMo CUDA fired 162. Both had zero unexpected or duplicate cues. On the i7-13620H and RTX 4060 Laptop GPU, unpaced streaming decoded 95.57 minutes of audio in 91.99 minutes on CPU and 10.44 minutes on GPU. Seven recordings fell below real time on CPU. On the eight clips replayed at 1×, CPU fired 7 of 13 and GPU fired 6. The six shared cues fired 0.47–0.80 seconds later on CPU. The extra CPU cue arrived 1.02 seconds after the clip ended. Runtime and precision differed between the two decoders.
- The initial quoted-prompt guard blocked ten scripted positive prompts that contained the full cue. It also blocked supported coaching and adult handoff, so the follow-up restores the shared-reading policy. Five sound-alike ending cases remain. A stricter endpoint experiment blocked those five but lost seven cues in the 50-recording replay, so it was reverted.
- The Keen replay applied the forward-jump change to the Keen checkout's matcher separately. The code on this branch is for the Parakeet checkout.
- Parakeet retains a verified near-complete cue for up to 30 seconds and checks it against the normalized transcript snapshot. On fresh 1× replays, the Mermaid cue fired once after “speak” in the 10-, 15-, and 20-second Singlish aside variants. All three matching stray-“speak” controls stayed quiet. The earlier eight clips and 50 recordings had identical cue decisions when their saved callbacks were rescored with the recovery change.

## On the other PC

1. Fetch this branch and check it out in a separate worktree. Keep the pinned original branches available for reproducing earlier scores.
2. Reuse the original `Books-to-Life-recordings.zip` for the full 50-recording corpus and `pod-pc-transfer.zip` for the eight paired clips. Keep the recordings and raw recognition logs local.
3. Start [Parakeet NeMo with CUDA](SETUPS.md). In the Windows client environment, replay the paired cases at 1× with `python -m benchmarks.replay_native path/to/pod-pc-transfer.zip --model parakeet-nemo --server ws://127.0.0.1:9097 --output gpu-results-private.json`. This uses split matching, stability 2, and book hints off. Check that the parent aside and stray “tea” produce zero cues, and that Mermaid's “speak” cue requires the endpoint.
4. For a CPU comparison, follow the [Linux Parakeet setup](PI4_SETUP.md#parakeet-cpu-replay-on-64-bit-linux) and run the same ZIP against the native server. Compare expected cues, cue times, callback lag, and final drain. ARM64 performance has yet to be measured on a Pi.
5. Verify cue-to-speaker and cue-to-projector onset on the physical pod. Record the input, speaker output, and projected wall together. The saved callback replay measures cue decisions.
6. Keep the five sound-alike endings as regression cases. For any proposed change, rerun the 50 recordings and test actual wrong-word utterances alongside recognition errors.
7. When Keen supplies its Linux SDK, test it in WSL with the same streaming client and matcher. Reuse the 50 recordings and compare cue accuracy, transcription error, and real-time trigger latency.
