import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from benchmarks import ocsc_local_bundle as bundle

ROOT=Path(__file__).resolve().parents[1]


def archive(path,name,data=b'corpus text'):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr(name,data)
        z.writestr(bundle.INVENTORY,json.dumps({'files':{
            name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}))


class LocalBundleTests(unittest.TestCase):
    def test_verified_data_import_and_conflict_preflight(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            base=Path(directory);source=base/'input.zip'
            archive(source,'recordings/6008_reading.txt')
            with patch.object(bundle,'ROOT',base):
                bundle.import_bundle(source)
                self.assertEqual((base/'recordings/6008_reading.txt').read_bytes(),b'corpus text')
                (base/'recordings/6008_reading.txt').write_text('keep existing version')
                with self.assertRaises(FileExistsError):bundle.import_bundle(source)

    def test_refuses_code_git_and_outside_paths(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            base=Path(directory)
            for name in ('../outside.txt','.git/hooks/pre-commit','run_client.py'):
                source=base/'input.zip';archive(source,name)
                with patch.object(bundle,'ROOT',base),self.assertRaises(ValueError):
                    bundle.read_verified(source)

    def test_rejects_modified_content(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            source=Path(directory)/'input.zip';archive(source,'recordings/6008_reading.txt')
            with zipfile.ZipFile(source,'a') as z:z.writestr('unexpected.txt',b'bad')
            with self.assertRaises(ValueError):bundle.read_verified(source)

    def test_metadata_paths_are_portable(self):
        self.assertEqual(bundle.portable({'manifest':'output\\ocsc\\manifests\\book.json'}),
                         {'manifest':'output/ocsc/manifests/book.json'})


if __name__=='__main__':unittest.main()
