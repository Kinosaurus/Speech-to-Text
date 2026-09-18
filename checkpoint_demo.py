"""Run the sample checkpoints without WhisperLive or a microphone."""

import argparse
import json
from pathlib import Path

from checkpoint_matcher import CheckpointMatcher, MATCHING_ENGINE


def show_update(text, update):
    print(f"\nTRANSCRIPT: {text}")
    if update.checkpoint_id is None:
        print("STATUS: story complete")
        return

    print(
        f"MATCH: {update.checkpoint_id} | score={update.score:.1f} | "
        f"confirmation={update.confirmations}/{update.confirmations_required}"
    )
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
    args = parser.parse_args()

    manifest_path = Path(args.checkpoints)
    matcher = CheckpointMatcher.from_file(
        manifest_path, threshold=args.threshold, stability=args.stability
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"BOOK: {matcher.title}")
    print(f"MATCHING ENGINE: {MATCHING_ENGINE}")
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

    for text in demo_transcripts:
        show_update(text, matcher.process(text))


if __name__ == "__main__":
    main()
