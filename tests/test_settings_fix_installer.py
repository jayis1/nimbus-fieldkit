import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SettingsFixTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(ROOT / 'device/unified/install-settings-fix.sh')], check=True)

    def test_patch_and_guarded_rollback_on_fixture_only(self):
        shipped = ROOT / 'build/nimbus-unified-v06.tar'
        if not shipped.exists():
            self.skipTest('Shipped v0.6 baseline unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target, stage = base / 'web', base / 'stage'
            target.mkdir(); stage.mkdir()
            with tarfile.open(shipped) as archive:
                for name in ('bridge.js', 'stock-dark.css'):
                    (target / name).write_bytes(archive.extractfile('fieldkit-v06/' + name).read())
                    (stage / name).write_bytes((ROOT / 'device/unified' / name).read_bytes())
            sums = ''.join(hashlib.sha256((stage / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in ('bridge.js', 'stock-dark.css'))
            (stage / 'SHA256SUMS').write_text(sums)
            script = (ROOT / 'device/unified/install-settings-fix.sh').read_text()
            script = script.replace('[ "$(id -u)" = 0 ]', ':')
            script = script.replace('/nimbus/data/fieldkit-v06', str(target)).replace('/nimbus/data', str(base))
            script = script.replace('\n  sync\n', '\n  : # Fixture: do not sync unrelated host disks.\n')
            installer = stage / 'install.sh'; installer.write_text(script)
            subprocess.run(['sh', str(installer), 'install'], check=True, capture_output=True)
            self.assertEqual((target / 'bridge.js').read_bytes(), (stage / 'bridge.js').read_bytes())
            # User edits are never blindly discarded by rollback.
            patched = (target / 'bridge.js').read_bytes()
            (target / 'bridge.js').write_bytes(b'user-change')
            self.assertNotEqual(subprocess.run(['sh', str(installer), 'rollback'], capture_output=True).returncode, 0)
            self.assertEqual((target / 'bridge.js').read_bytes(), b'user-change')
            (target / 'bridge.js').write_bytes(patched)
            subprocess.run(['sh', str(installer), 'rollback'], check=True, capture_output=True)
            self.assertEqual((target / 'bridge.js').read_bytes(), (stage / 'backups/bridge.js').read_bytes())
