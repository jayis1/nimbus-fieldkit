import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('custom_image', ROOT / 'scripts/build-custom-image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
CANDIDATE = ROOT / 'build/nimbus-custom-rootfs-candidate-v1'


class CustomImageTests(unittest.TestCase):
    def test_archive_safety(self):
        for name in ('../outside', '/absolute'):
            member = tarfile.TarInfo(name)
            with self.assertRaises(ValueError):
                builder.validate_members([member])
        link = tarfile.TarInfo('etc')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc'
        child = tarfile.TarInfo('etc/file')
        with self.assertRaises(ValueError):
            builder.validate_members([link, child])

    def test_candidate_gates_and_image_geometry(self):
        if not CANDIDATE.exists():
            self.skipTest('Offline image candidate has not been built')
        manifest = json.loads((CANDIDATE / 'BUILD-MANIFEST.json').read_text())
        for key in ('flash_ready', 'boot_tested', 'recovery_tested', 'vendor_update_container'):
            self.assertFalse(manifest[key])
        self.assertEqual((CANDIDATE / 'rootfs.ext3.candidate').stat().st_size, 256 * 1024 ** 2)
        self.assertEqual(builder.digest(CANDIDATE / 'rootfs.ext3.candidate'), manifest['artifacts']['rootfs.ext3.candidate'])

    def test_candidate_ui_security_and_no_personal_keys(self):
        if not CANDIDATE.exists():
            self.skipTest('Offline image candidate has not been built')
        with tarfile.open(CANDIDATE / 'rootfs.tar') as archive:
            names = archive.getnames()
            self.assertFalse(any(name.startswith('etc/ssh/ssh_host_') for name in names))
            self.assertNotIn('etc/nimbus/host-ed25519', names)
            self.assertNotIn('etc/nimbus/authorized_keys', names)
            self.assertNotIn('opt/nimbus/native/dashboard/index.html', names)
            self.assertFalse(any('.private-backups' in name or 'numbus-backup' in name for name in names))
            conf = archive.extractfile('etc/inetd.conf').read().decode()
            self.assertFalse(any(line.split() and line.split()[0] == 'telnet' for line in conf.splitlines()))
            page = archive.extractfile('nimbus/data/index.html').read()
            self.assertIn(b'btnNimbusFieldKit', page)
            self.assertIn(b'/data/fieldkit-v06/', page)
            bridge = archive.extractfile('nimbus/data/fieldkit-v06/bridge.js').read()
            self.assertIn(b'nimbus-settings-sign-in', bridge)
            self.assertIn(b'AdminLoginSetting', bridge)
            self.assertEqual(archive.getmember('opt/nimbus/dropbearmulti').uid, 0)
            self.assertEqual(archive.getmember('opt/nimbus/dropbearmulti').mode, 0o700)

    def test_vendor_modules_unchanged(self):
        vendor = Path('/tmp/opencode/sandisk-fw-3-04/rootfs_nimbus_v3.04.tar')
        if not CANDIDATE.exists() or not vendor.exists():
            self.skipTest('Vendor/candidate archives unavailable')
        with tarfile.open(vendor) as stock, tarfile.open(CANDIDATE / 'rootfs.tar') as custom:
            for member in stock:
                if member.isfile() and member.name.startswith('lib/modules/'):
                    self.assertEqual(stock.extractfile(member).read(), custom.extractfile(member.name).read(), member.name)

    def test_filesystem_image_matches_security_and_ui_archive(self):
        if not CANDIDATE.exists() or not shutil.which('debugfs'):
            self.skipTest('Candidate or read-only debugfs unavailable')
        with tarfile.open(CANDIDATE / 'rootfs.tar') as archive:
            for name in ('etc/inetd.conf', 'etc/rc.d/rc.local', 'opt/nimbus/image-start.sh',
                         'nimbus/data/fieldkit-v06/bridge.js'):
                result = subprocess.run(['debugfs', '-R', 'cat /' + name,
                                         str(CANDIDATE / 'rootfs.ext3.candidate')], capture_output=True, check=True)
                self.assertEqual(result.stdout, archive.extractfile(name).read(), name)
