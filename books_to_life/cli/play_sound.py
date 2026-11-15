"""Preview an effect through the same audio output used by story triggers."""
import argparse
from pathlib import Path
from types import SimpleNamespace

from books_to_life.runtime.sound_player import SoundPlayer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sound', type=Path)
    parser.add_argument('--volume', type=float, default=0.5)
    parser.add_argument('--output_device', type=int, default=None)
    args = parser.parse_args()
    checkpoint = dict(id='preview', effect=dict(sound=str(args.sound.resolve())))
    try:
        player = SoundPlayer([checkpoint], Path.cwd() / 'preview.json',
                             volume=args.volume, output_device=args.output_device)
    except ValueError as error:
        parser.error(str(error))
    if not player.sounds:
        parser.exit(1, 'Sound could not be loaded.\n')
    try:
        player.handle_update(SimpleNamespace(triggered=True, checkpoint_id='preview'))
        player.close(drain=True)
    finally:
        player.close()
    if player.error is not None:
        parser.exit(1, f'Audio output failed: {player.error}\n')


if __name__ == '__main__':
    main()
