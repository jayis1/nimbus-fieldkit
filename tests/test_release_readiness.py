import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load('audit-image-readiness')
hygiene = load('check-release-hygiene')


class ReadinessTests(unittest.TestCase):
    def test_source_hygiene_and_secret_markers(self):
        self.assertEqual(hygiene.violations('device/start.sh', b'echo healthy'), [])
        self.assertTrue(hygiene.violations('numbus-backup/settings.bin', b'private'))
        self.assertTrue(hygiene.violations('public.pem', b'certificate'))
        self.assertTrue(hygiene.violations('file.txt', b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----'))
        self.assertTrue(hygiene.violations('link.py', b'code', symlink=True))

    def test_artifact_paths_reject_traversal_and_links(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for name in ('../outside', '/etc/passwd', 'nested/image', '..'):
                with self.assertRaises(ValueError):
                    audit.artifact(base, name)
            (base / 'file').write_bytes(b'ok')
            (base / 'link').symlink_to(base / 'file')
            with self.assertRaises(ValueError):
                audit.artifact(base, 'link')

    def test_local_candidate_reports_not_production_ready(self):
        candidate = ROOT / 'build/nimbus-custom-rootfs-candidate-v1'
        if not candidate.exists():
            self.skipTest('Local image candidate absent')
        result = audit.audit(candidate)
        self.assertTrue(result['integrity_verified'])
        self.assertFalse(result['production_ready'])
        self.assertFalse(result['flash_authorized'])
        self.assertEqual(len(result['release_blockers']), 8)

    def test_missing_and_oversized_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'BUILD-MANIFEST.json').write_text(json.dumps({'schema': 'wrong'}))
            with self.assertRaises(ValueError):
                audit.audit(base)
            (base / 'BUILD-MANIFEST.json').write_bytes(b'x' * 65537)
            with self.assertRaises(ValueError):
                audit.audit(base)
