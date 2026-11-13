"""Replay the transfer ZIP's WAVs on Parakeet with the Keen checkout's tracker."""
import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path


def run_case(main, keen, case, results):
    transcript = results / (case['name'] + '.srt')
    command = [sys.executable, '-u', str(Path(__file__).resolve()),
               str(main), str(keen), '--worker', case['book'],
               '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
               '--matching_mode', 'split', '--no_book_context', '--checkpoint_stability', '2',
               '--files', str(Path(__file__).resolve().parent / case['audio']),
               '--mute_audio_playback', '--checkpoints',
               str(keen / 'public/books' / case['book'] / 'checkpoints.json'),
               '--transcript_file', str(transcript)]
    print(f'Replaying {case["name"]}', flush=True)
    subprocess.run(command, cwd=main, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('main_checkout', type=Path)
    parser.add_argument('keen_checkout', type=Path)
    parser.add_argument('--worker', choices=['tea', 'little-mermaid'])
    args, client_args = parser.parse_known_args()
    main_checkout, keen_checkout = args.main_checkout.resolve(), args.keen_checkout.resolve()
    bundle = Path(__file__).resolve().parent
    if args.worker:
        sys.path.insert(0, str(main_checkout))
        import books_to_life
        books_to_life.__path__.insert(0, str(keen_checkout / 'books_to_life'))
        from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

        matcher_module = sys.modules[TimelyEvidenceMatcher.__module__]
        if not Path(matcher_module.__file__).is_relative_to(keen_checkout):
            raise RuntimeError('Could not load the Keen checkout matcher')
        if args.worker == 'tea':
            original_init = TimelyEvidenceMatcher.__init__

            def init(self, *positional, **keywords):
                original_init(self, *positional, hold_cumulative_endpoint=True, **keywords)

            TimelyEvidenceMatcher.__init__ = init
        sys.argv = [str(bundle / 'probe.py'), '1', *client_args]
        runpy.run_path(sys.argv[0], run_name='__main__')
        return

    cases = json.loads((bundle / 'cases.json').read_text(encoding='utf-8'))
    from tempfile import mkdtemp

    results = Path(mkdtemp(prefix='parakeet-replay-', dir=bundle))
    print(f'Writing logs and transcripts to {results}', flush=True)
    for case in cases:
        run_case(main_checkout, keen_checkout, case, results)


if __name__ == '__main__':
    main()
