"""Run the sample checkpoints without WhisperLive or a microphone."""

import argparse
import json
import math
from pathlib import Path
import statistics
from time import perf_counter

from checkpoint_matcher import CheckpointMatcher, MATCHING_ENGINE
from alignment_matcher import AlignmentMatcher


def show_update(text, update):
    print(f"\nTRANSCRIPT: {text}")
    if update.checkpoint_id is None:
        print("STATUS: story complete")
        return

    print(
        f"MATCH: {update.checkpoint_id} | position={update.checkpoint_position} | "
        f"score={update.score:.1f} | "
        f"confirmation={update.confirmations}/{update.confirmations_required}"
    )
    if hasattr(update, "tracked_word_position"):
        print(f"ALIGNMENT: words={update.alignment_start}:{update.alignment_end} | "
              f"confirmed_position={update.tracked_word_position} | "
              f"recovery={update.recovering} | ambiguous={update.ambiguous} | duplicate={update.duplicate}")
        if update.skipped_checkpoint_ids:
            print(f"SKIPPED: {', '.join(update.skipped_checkpoint_ids)}")
    if update.triggered:
        print(f"TRIGGER: {json.dumps(update.effect, ensure_ascii=False)}")
    if update.completed:
        print("STATUS: all checkpoints completed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoints",
        default="examples/sample_story.json",
        help="Path to a story checkpoint manifest.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Type transcript updates manually instead of using the demo sequence.",
    )
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--stability", type=int, default=None)
    parser.add_argument("--matching_mode", choices=("alignment", "fuzzy"), default="alignment")
    parser.add_argument("--benchmark", type=int, default=None, metavar="REPEATS",
                        help="Replay demo transcripts to measure matching-only time per update.")
    args = parser.parse_args()
    if args.benchmark is not None and (args.benchmark < 1 or args.interactive):
        parser.error("--benchmark requires a positive repeat count and cannot be used with --interactive.")

    manifest_path = Path(args.checkpoints)
    matcher_type = AlignmentMatcher if args.matching_mode == "alignment" else CheckpointMatcher
    matcher = matcher_type.from_file(
        manifest_path, threshold=args.threshold, stability=args.stability
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"BOOK: {matcher.title}")
    print(f"MATCHING ENGINE: {matcher.mode} ({MATCHING_ENGINE})")
    print(f"CHECKPOINTS: {len(matcher.checkpoints)}")

    if args.interactive:
        print("Type transcript updates. Press Ctrl+Z then Enter on Windows to stop.")
        try:
            while not matcher.completed:
                text = input("> ").strip()
                if text:
                    show_update(text, matcher.process(text))
        except EOFError:
            pass
        return

    demo_transcripts = manifest.get("demo_transcripts", [])
    if not demo_transcripts:
        raise ValueError("Manifest has no 'demo_transcripts' sequence.")

    if args.benchmark is not None:
        times = []
        for _ in range(args.benchmark):
            replay = matcher_type(manifest, threshold=args.threshold, stability=args.stability)
            for text in demo_transcripts:
                started = perf_counter()
                replay.process(text)
                times.append((perf_counter() - started) * 1000)
        times.sort()
        p95 = times[max(0, math.ceil(len(times) * 0.95) - 1)]
        print(f"TIMING: {len(times)} updates | median={statistics.median(times):.3f} ms | "
              f"p95={p95:.3f} ms | max={max(times):.3f} ms")
        print("Matching-only timing on this computer; excludes ASR, capture, confirmation waits and playback.")
        return

    for text in demo_transcripts:
        show_update(text, matcher.process(text))


if __name__ == "__main__":
    main()
