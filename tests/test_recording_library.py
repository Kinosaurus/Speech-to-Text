import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from recording_library import resolve_recording_path, session_outputs


class RecordingLibraryTests(unittest.TestCase):
    def test_old_audio_job_works_without_a_machine_specific_migration_file(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            target=root/'recordings/library/reading_sessions/6008/audio.wav'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'example')
            self.assertEqual(resolve_recording_path('recordings/6008_reading.wav',root),target)

    def test_migration_and_audio_aliases_cannot_escape_library(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            library=root/'recordings/library'
            library.mkdir(parents=True)
            (library/'migration.json').write_text(json.dumps({'paths':{'old.wav':{'destination':'outside.wav'}}}))
            with self.assertRaises(ValueError):
                resolve_recording_path('old.wav',root)
            (library/'audio.json').write_text(json.dumps({'library_path':'../../outside.wav'}))
            with self.assertRaises(ValueError):
                resolve_recording_path(library/'audio.json',root)

    def test_file_runs_do_not_collide_between_readers_named_audio_wav(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            first=root/'recordings/library/reading_sessions/5004/audio.wav'
            second=root/'recordings/library/reading_sessions/5045/audio.wav'
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.touch();second.touch()
            _,one=session_outputs([first],'same-session',root)
            _,two=session_outputs([second],'same-session',root)
            self.assertNotEqual(one,two)
            self.assertEqual(one.parent,first.parent/'asr')
            mic,spoken=session_outputs(None,'capture',root)
            self.assertEqual(mic.parent,spoken.parent)
            self.assertEqual(mic.name,'audio.wav')


if __name__=='__main__': unittest.main()
