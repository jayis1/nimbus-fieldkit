import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provision_image', ROOT / 'scripts/provision-image.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)
TOOL = Path(os.environ.get('NIMBUS_DROPBEARKEY', '/tmp/opencode/nimbus-provisioning-host-tools/dropbear-2026.94/dropbearkey'))


def key():
    raw = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + bytes(range(32))
    return 'ssh-ed25519 ' + base64.b64encode(raw).decode() + ' fixture\n'


class ProvisioningTests(unittest.TestCase):
    def test_public_key_strict_wire_format(self):
        clean, pin = provision.public_key(key())
        self.assertNotIn('fixture', clean)
        self.assertTrue(pin.startswith('SHA256:'))
        for text in ('', key() + key(), 'command="id" ' + key(), 'ssh-rsa AAAA', 'ssh-ed25519 !!!!', 'ssh-ed25519 AAAA'):
            with self.assertRaises(ValueError):
                provision.public_key(text)

    def test_private_paths_and_files(self):
        with self.assertRaises(ValueError):
            provision.private_path(ROOT / 'build' / 'public')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'key'
            path.write_bytes(b'private fixture')
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                provision.read_private(path)
            path.chmod(0o600)
            self.assertEqual(provision.read_private(path), b'private fixture')
            link = path.with_name('link'); link.symlink_to(path)
            with self.assertRaises(ValueError):
                provision.read_private(link)

    @unittest.skipUnless(TOOL.is_file(), 'Trusted native Dropbear key tool unavailable')
    def test_real_unique_keys_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            previous = provision.PRIVATE
            provision.PRIVATE = base / 'private'
            try:
                authorized = base / 'client.pub'; authorized.write_text(key())
                first, second = provision.PRIVATE / 'first', provision.PRIVATE / 'second'
                a = provision.create(first, authorized, TOOL, 'fixture-a')
                b = provision.create(second, authorized, TOOL, 'fixture-b')
                self.assertNotEqual(a['host_fingerprint'], b['host_fingerprint'])
                self.assertFalse(a['native_access_verified'])
                self.assertFalse(a['flash_authorized'])
                self.assertEqual(provision.validate(first, TOOL), a)
                with self.assertRaises(FileExistsError):
                    provision.create(first, authorized, TOOL, 'fixture-a')
                data = json.loads((first / 'PROVISIONING.json').read_text())
                data['host_fingerprint'] = 'SHA256:wrong'
                (first / 'PROVISIONING.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    provision.validate(first, TOOL)
                (second / 'authorized_keys').chmod(0o644)
                with self.assertRaises(ValueError):
                    provision.validate(second, TOOL)
            finally:
                provision.PRIVATE = previous
