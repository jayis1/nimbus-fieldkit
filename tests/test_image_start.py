import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.keys = self.root / 'keys'; self.keys.mkdir(mode=0o700)
        self.proc = self.root / 'proc'; self.proc.mkdir()
        self.storage = self.root / 'storage'; self.storage.mkdir()
        self.native = self.storage / 'nimbus-unified-v05/native'; self.native.mkdir(parents=True)
        self.trusted = self.root / 'trusted'; (self.trusted / 'native').mkdir(parents=True)
        self.marker = self.root / 'unsafe-execution'
        (self.native / 'nimbus-dashboard.sh').write_text(f'echo unsafe > "{self.marker}"\n')
        (self.trusted / 'native/nimbus-dashboard.sh').write_text('printf "trusted publisher: %s\\n" "$NIMBUS_DATA_DIR"\n')
        (self.proc / 'modules').write_text('')
        (self.proc / 'mounts').write_text(f'/dev/mmcblk0p4 {self.storage} texfat rw 0 0\n')
        (self.root / 'net').mkdir()
        (self.root / 'log').mkdir()
        tool = self.trusted / 'dropbearmulti'
        tool.write_text('#!/bin/sh\ncase "$1" in dropbearkey) [ "$(cat "$4")" = valid-fixture ];; dropbear) exit 0;; *) exit 1;; esac\n')
        tool.chmod(0o700)
        script = (ROOT / 'device/image-start.sh').read_text()
        for old, new in [('/etc/nimbus', str(self.keys)), ('/opt/nimbus', str(self.trusted)),
                         ('/mnt/storage', str(self.storage)), ('/proc/mounts', str(self.proc / 'mounts')),
                         ('/proc/modules', str(self.proc / 'modules')), ('/sys/class/net/wlan1', str(self.root / 'net')),
                         ('/var/log', str(self.root / 'log')), ('/var/run', str(self.root / 'log'))]:
            script = script.replace(old, new)
        # Fixtures are user-owned, not a native root-ownership validation.
        script = script.replace('0:0:', f'{os.getuid()}:{os.getgid()}:')
        self.script = self.root / 'start.sh'; self.script.write_text(script)

    def tearDown(self):
        self.temp.cleanup()

    def run_start(self):
        return subprocess.run(['sh', str(self.script)], capture_output=True, text=True, timeout=10)

    def keys_ready(self):
        for name in ('host-ed25519', 'authorized_keys'):
            (self.keys / name).write_text('valid-fixture'); (self.keys / name).chmod(0o600)

    def test_boot_never_executes_media_script(self):
        result = self.run_start()
        self.assertIn('trusted publisher:', result.stdout)
        self.assertIn('SSH not started', result.stderr)
        self.assertFalse(self.marker.exists())

    def test_exported_or_readonly_media_skips_publisher(self):
        (self.proc / 'modules').write_text('g_file_storage 1 0 - Live 0\n')
        self.assertNotIn('trusted publisher:', self.run_start().stdout)
        (self.proc / 'modules').write_text('')
        (self.proc / 'mounts').write_text(f'/dev/mmcblk0p4 {self.storage} texfat ro 0 0\n')
        self.assertNotIn('trusted publisher:', self.run_start().stdout)

    def test_unsafe_key_permissions_are_not_repaired(self):
        self.keys_ready(); (self.keys / 'host-ed25519').chmod(0o644)
        self.assertIn('SSH not started', self.run_start().stderr)
        self.assertEqual((self.keys / 'host-ed25519').stat().st_mode & 0o777, 0o644)

    def test_valid_fixture_keys_pass_validation(self):
        self.keys_ready()
        result = self.run_start()
        self.assertNotIn('SSH not started', result.stderr)
        self.assertIn('trusted publisher:', result.stdout)
        self.assertFalse(self.marker.exists())

    def test_invalid_host_key_and_symlink_directory_rejected(self):
        self.keys_ready(); (self.keys / 'host-ed25519').write_text('invalid-fixture')
        self.assertIn('SSH not started', self.run_start().stderr)
        self.keys.rename(self.root / 'real-keys'); self.keys.symlink_to(self.root / 'real-keys')
        self.assertIn('SSH not started', self.run_start().stderr)

    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(ROOT / 'device/image-start.sh')], check=True)
