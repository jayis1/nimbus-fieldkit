import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package_native', Path(__file__).parents[1] / 'scripts/package-native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativePackageTests(unittest.TestCase):
    def test_manifest_hashes_and_safe_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'kit.tar'
            checksum = native.package(output)
            self.assertEqual(checksum, hashlib.sha256(output.read_bytes()).hexdigest())
            with tarfile.open(output) as archive:
                self.assertEqual(set(archive.getnames()), set(native.SOURCES) | {'MANIFEST.json'})
                manifest = json.load(archive.extractfile('MANIFEST.json'))
                for entry in manifest['files']:
                    data = archive.extractfile(entry['name']).read()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                for item in archive.getmembers():
                    self.assertTrue(item.isfile())
                    self.assertFalse(item.name.startswith('/'))
                    self.assertNotIn('..', Path(item.name).parts)
                    self.assertFalse(item.name.endswith('.img'))
            with self.assertRaises(FileExistsError): native.package(output)

    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(native.package(root / 'a.tar'), native.package(root / 'b.tar'))
