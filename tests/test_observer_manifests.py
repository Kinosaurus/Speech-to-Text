import tempfile
import unittest
from pathlib import Path
from benchmarks.observer_manifests import observer_manifest_paths

class ObserverManifestTests(unittest.TestCase):
    def test_explicit_custom_corpus_manifest_is_not_rewritten_into_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/'output/ocsc/manifests/participant_01_story.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            result=observer_manifest_paths(root,'output/ocsc/manifests/participant_01_story.json')
            self.assertEqual(result,{'participant_01':path})
    def test_missing_explicit_manifest_fails_instead_of_using_another_book(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                observer_manifest_paths(directory,'unknown_story.json')
    def test_default_offbook_observers_preserved(self):
        self.assertEqual(set(observer_manifest_paths('.')),{'horse','fat_cat','tea','little_mermaid'})
