import json
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'device/nimbus-companion-status.sh'


class CompanionStatusTests(unittest.TestCase):
    def report(self, mounts='', modules='', tcp='', tcp6='', missing=(), args=()):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {}
            for name, data in {'mounts': mounts, 'modules': modules, 'tcp': tcp, 'tcp6': tcp6}.items():
                paths[name] = root / name
                if name not in missing:
                    paths[name].write_text(data)
            script = SCRIPT.read_text()
            for name, original in {'mounts': '/proc/mounts', 'modules': '/proc/modules',
                                   'tcp6': '/proc/net/tcp6', 'tcp': '/proc/net/tcp'}.items():
                script = script.replace(original, str(paths[name]))
            path = root / 'status.sh'
            path.write_text(script)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = subprocess.run(['sh', str(path), *args], capture_output=True, text=True, timeout=5)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            if args:
                return result
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(len(result.stdout), 4096)
            return json.loads(result.stdout)

    def test_separate_mounts_and_no_authority_from_rw(self):
        data = self.report(mounts='/dev/p1 /mnt/storage ext3 rw 0 0\n'
                           '/dev/p2 /mnt/sdcard texfat rw 0 0\n'
                           '/dev/p2 /var/ftp/sdcard texfat ro 0 0\n')
        self.assertEqual(data['storage']['internal'], 'read_write')
        self.assertEqual(data['storage']['sd'], 'read_write')
        self.assertEqual(data['storage']['sd_ftp'], 'read_only')
        self.assertFalse(data['permissions']['remote_write'])
        self.assertEqual(data['integration']['backup_transfer'], 'not_qualified')

    def test_usb_export_does_not_grant_access(self):
        data = self.report(modules='g_file_storage 1 0 - Live 0\n')
        self.assertEqual(data['storage']['usb_export'], 'active')
        self.assertEqual(data['storage']['sd'], 'absent')
        self.assertFalse(data['permissions']['change_mounts'])

    def test_missing_tables_unknown(self):
        data = self.report(missing=('mounts', 'modules', 'tcp', 'tcp6'))
        self.assertEqual(set(data['storage'].values()), {'unknown'})
        self.assertEqual(data['management']['listener'], 'unknown')

    def test_empty_tables_not_unknown(self):
        data = self.report()
        self.assertEqual(data['management']['listener'], 'not_observed')
        self.assertEqual(data['storage']['usb_export'], 'inactive')

    def test_ipv4_and_ipv6_listeners_not_authentication(self):
        for name in ('tcp', 'tcp6'):
            data = self.report(**{name: '0: 00000000:08B0 00000000:0000 0A 0:0\n'})
            self.assertEqual(data['management']['listener'], 'observed')
            self.assertEqual(data['management']['host_pin'], 'not_tested')
            self.assertEqual(data['management']['authentication'], 'not_tested')

    def test_established_connection_is_not_listener(self):
        data = self.report(tcp='0: 00000000:08B0 00000000:0000 01 0:0\n')
        self.assertEqual(data['management']['listener'], 'not_observed')

    def test_duplicate_or_ambiguous_mount_unknown(self):
        for mounts in ('x /mnt/sdcard texfat ro,rw 0 0\n',
                       'x /mnt/sdcard texfat ro 0 0\nx /mnt/sdcard texfat rw 0 0\n'):
            self.assertEqual(self.report(mounts=mounts)['storage']['sd'], 'unknown')

    def test_untrusted_metadata_not_echoed(self):
        data = self.report(mounts='secret /mnt/sdcard texfat ro,private_metadata 0 0\n')
        self.assertNotIn('private_metadata', json.dumps(data))
        self.assertNotIn('secret', json.dumps(data))

    def test_arguments_refused(self):
        result = self.report(args=('--install',))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_shell_syntax(self):
        for path in (SCRIPT, ROOT / 'device/nimbus-agent.sh'):
            subprocess.run(['sh', '-n', str(path)], check=True)

    def test_agent_dispatch_and_argument_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'nimbus-agent.sh').write_bytes((ROOT / 'device/nimbus-agent.sh').read_bytes())
            (root / 'nimbus-companion-status.sh').write_text("printf '%s\\n' fixture-dispatched\n")
            result = subprocess.run(['sh', str(root / 'nimbus-agent.sh'), 'companion-status'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, 'fixture-dispatched\n')
            result = subprocess.run(['sh', str(root / 'nimbus-agent.sh'), 'companion-status', '--install'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')

    def test_minimal_reproducible_bundle_and_no_overwrite(self):
        spec = importlib.util.spec_from_file_location('companion_package', ROOT / 'scripts/package-companion-status.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / 'a.tar', root / 'b.tar'
            checksum = builder.package(first)
            self.assertEqual(checksum, builder.package(second))
            self.assertEqual(checksum, hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)
            with tarfile.open(first) as archive:
                self.assertEqual(set(archive.getnames()), set(builder.SOURCES) | {'MANIFEST.json'})
                manifest = json.load(archive.extractfile('MANIFEST.json'))
                self.assertFalse(manifest['hardware_validated'])
                self.assertFalse(manifest['installer'])
                for entry in manifest['files']:
                    data = archive.extractfile(entry['name']).read()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                self.assertTrue(all(item.isfile() and item.mode == 0o600 for item in archive.getmembers()))
            with self.assertRaises(FileExistsError):
                builder.package(first)
            link = root / 'link.tar'
            link.symlink_to(first)
            with self.assertRaises(FileExistsError):
                builder.package(link)
            self.assertEqual(checksum, hashlib.sha256(first.read_bytes()).hexdigest())
