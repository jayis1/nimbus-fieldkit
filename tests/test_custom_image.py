import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import tarfile
import tempfile
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

    def test_archive_aliases_and_non_directory_parents_refused(self):
        for name in ('etc//file', './etc/file', 'etc/./file', 'etc/../file'):
            with self.assertRaises(ValueError):
                builder.validate_members([tarfile.TarInfo(name)])
        directory = tarfile.TarInfo('etc'); directory.type = tarfile.DIRTYPE
        alias = tarfile.TarInfo('etc/'); alias.type = tarfile.DIRTYPE
        with self.assertRaises(ValueError):
            builder.validate_members([directory, alias])
        regular = tarfile.TarInfo('etc')
        child = tarfile.TarInfo('etc/file')
        with self.assertRaises(ValueError):
            builder.validate_members([regular, child])

    def test_overlay_paths_and_digest_links_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('../escape', '/absolute', 'etc//file', './alias'):
                with self.assertRaises(ValueError):
                    builder.write(root, name, b'fixture')
            (root / 'input').write_bytes(b'fixture')
            (root / 'link').symlink_to(root / 'input')
            with self.assertRaises(ValueError):
                builder.digest(root / 'link')
            with self.assertRaises(ValueError):
                builder.digest(root)

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

    def test_hardened_generic_and_private_archives_match_images(self):
        candidates = [(ROOT / 'build/nimbus-custom-rootfs-candidate-v4', False),
                      (ROOT / '.private-provisioning/drive-a-rootfs-candidate-v4', True),
                      (ROOT / 'build/nimbus-custom-rootfs-beta1', False),
                      (ROOT / '.private-provisioning/drive-a-rootfs-beta1', True)]
        available = [(base, private) for base, private in candidates if base.exists()]
        if not available or not shutil.which('debugfs'):
            self.skipTest('Hardened local candidate/debugfs unavailable')
        for base, private in available:
            with self.subTest(private=private):
                report = builder.policy.audit(base / 'rootfs.tar', private=private)
                self.assertTrue(report['offline_policy_pass'])
                manifest = json.loads((base / 'BUILD-MANIFEST.json').read_text())
                self.assertFalse(manifest['flash_ready'])
                self.assertFalse(manifest['boot_tested'])
                self.assertFalse(manifest['recovery_tested'])
                self.assertTrue(manifest['offline_policy_pass'])
                stored = json.loads((base / 'ROOTFS-POLICY.json').read_text())
                self.assertTrue(stored['vendor_module_hashes_match'])
                with tarfile.open(base / 'rootfs.tar') as archive:
                    names = ['opt/nimbus/image-start.sh', 'opt/nimbus/native/nimbus-dashboard.sh',
                             'opt/nimbus/native/dashboard/snapshot.awk', 'etc/inetd.conf']
                    if private:
                        names += ['etc/nimbus/host-ed25519', 'etc/nimbus/authorized_keys']
                    for name in names:
                        result = subprocess.run(['debugfs', '-R', 'cat /' + name,
                                                 str(base / 'rootfs.ext3.candidate')], capture_output=True, check=True)
                        # Never print private bytes in assertion failure diagnostics.
                        self.assertTrue(result.stdout == archive.extractfile(name).read(), 'Image/archive mismatch: ' + name)

    def test_beta1_latest_ui_provenance_and_fail_closed_gates(self):
        candidates = [(ROOT / 'build/nimbus-custom-rootfs-beta1', False),
                      (ROOT / '.private-provisioning/drive-a-rootfs-beta1', True)]
        available = [(base, private) for base, private in candidates if base.exists()]
        if not available or not shutil.which('debugfs'):
            self.skipTest('Local beta1 candidates/debugfs unavailable')
        for base, private in available:
            with self.subTest(private=private):
                manifest = json.loads((base / 'BUILD-MANIFEST.json').read_text())
                for flag in ('flash_ready', 'boot_tested', 'recovery_tested', 'vendor_update_container'):
                    self.assertFalse(manifest[flag])
                with tarfile.open(base / 'rootfs.tar') as archive:
                    for filename in ('audio-html5.js', 'upload-progress.js', 'stock-dark.css'):
                        source = 'device/unified/' + filename
                        name = 'nimbus/data/fieldkit-v06/' + filename
                        self.assertEqual(manifest['overlay_source_sha256'][source], builder.digest(ROOT / source))
                        data = archive.extractfile(name).read()
                        self.assertEqual(data, (ROOT / source).read_bytes())
                        result = subprocess.run(['debugfs', '-R', 'cat /' + name,
                                                 str(base / 'rootfs.ext3.candidate')], capture_output=True, check=True)
                        self.assertEqual(result.stdout, data)
                    page = archive.extractfile('nimbus/data/index.html').read()
                    self.assertIn(b'/data/fieldkit-v06/upload-progress.js', page)
                    controller = archive.extractfile('nimbus/data/js/t4u.controller.js').read()
                    self.assertNotIn(b'FlashDetect.versionAtLeast(10)', controller)
                    keys = {'etc/nimbus/host-ed25519', 'etc/nimbus/authorized_keys'}
                    self.assertEqual(keys.intersection(archive.getnames()), keys if private else set())
                    for name in ('opt/nimbus/image-start.sh', 'opt/nimbus/dropbearmulti', 'etc/nimbus'):
                        member = archive.getmember(name)
                        self.assertEqual((member.uid, member.gid, member.mode), (0, 0, 0o700))
                    if private:
                        for name in keys:
                            member = archive.getmember(name)
                            self.assertEqual((member.uid, member.gid, member.mode), (0, 0, 0o600))
