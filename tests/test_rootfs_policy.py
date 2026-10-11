import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rootfs_policy', ROOT / 'scripts/rootfs-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class RootfsPolicyTests(unittest.TestCase):
    def fixture(self, path, private=False, telnet=False):
        files = {
            'opt/nimbus/image-start.sh': (ROOT / 'device/image-start.sh').read_bytes(),
            'opt/nimbus/dropbearmulti': b'fixture executable, never run',
            'opt/nimbus/native/nimbus-dashboard.sh': b'fixture',
            'opt/nimbus/native/dashboard/snapshot.awk': b'fixture',
            'etc/inetd.conf': b'telnet stream tcp\n' if telnet else b'# telnet disabled\n',
            'etc/shadow': b'root:!:0:0:0:0:0:0:0\n',
            'opt/qsi/config/platform_default': b'CFG_WIFI_AP_MODE=wpa2aes\n',
            'nimbus/data/index.html': b'btnNimbusFieldKit /data/fieldkit-v06/',
            'nimbus/data/fieldkit-v06/bridge.js': b'nimbus-settings-sign-in AdminLoginSetting',
            'lib/modules/fixture.ko': b'fixture module, never run',
        }
        if private:
            files.update({'etc/nimbus/host-ed25519': b'fixture-not-a-key', 'etc/nimbus/authorized_keys': b'fixture-not-a-key'})
        with tarfile.open(path, 'w') as archive:
            directory = tarfile.TarInfo('etc/nimbus'); directory.type = tarfile.DIRTYPE
            directory.mode = 0o700; archive.addfile(directory)
            for name, data in files.items():
                info = tarfile.TarInfo(name); info.size = len(data)
                info.mode = 0o700 if name == 'opt/nimbus/dropbearmulti' else 0o600 if name.startswith('etc/nimbus/') else 0o644
                archive.addfile(info, io.BytesIO(data))

    def test_generic_static_checks_do_not_certify_boot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rootfs.tar'; self.fixture(path)
            report = policy.audit(path)
            self.assertTrue(report['offline_policy_pass'])
            self.assertFalse(report['production_ready'])
            self.assertFalse(report['flash_authorized'])
            self.assertIn('lib/modules/fixture.ko', report['module_hashes'])

    def test_private_material_requires_explicit_private_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rootfs.tar'; self.fixture(path, private=True)
            self.assertFalse(policy.audit(path)['offline_policy_pass'])
            # Static presence/mode policy is not cryptographic key validation.
            self.assertTrue(policy.audit(path, private=True)['offline_policy_pass'])

    def test_active_telnet_fails_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rootfs.tar'; self.fixture(path, telnet=True)
            self.assertFalse(policy.audit(path)['checks']['telnet_disabled'])

    def test_unsafe_hardlinks_and_devices_refused(self):
        regular = tarfile.TarInfo('inside')
        for target in ('../inside', '/inside', './inside', 'missing'):
            link = tarfile.TarInfo('link'); link.type = tarfile.LNKTYPE; link.linkname = target
            with self.assertRaises(ValueError):
                policy.validate_members([regular, link])
        device = tarfile.TarInfo('device'); device.type = tarfile.CHRTYPE
        with self.assertRaises(ValueError):
            policy.validate_members([device])

    def test_archive_budgets_refused_before_body_read(self):
        member = tarfile.TarInfo('oversized'); member.size = policy.MAX_FILE_BYTES + 1
        with self.assertRaises(ValueError):
            policy.validate_members([member])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'oversized.tar'
            # Header only: validator must reject without trying to read its body.
            path.write_bytes(member.tobuf())
            with tarfile.open(path) as archive:
                with self.assertRaises(ValueError):
                    policy.collect_members(archive)
