from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'device/root-writer-preflight.sh'


class RootWriterPreflightTests(unittest.TestCase):
    def fixture(self, base, exported=False, wrong_root=False, missing_info=False):
        proc = base / 'proc'; (proc / 'self').mkdir(parents=True)
        (proc / 'modules').write_text('g_file_storage 1 0 - Live 0\n' if exported else '')
        (proc / 'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
        sys = base / 'sys/class/block/mmcblk0p2'; sys.mkdir(parents=True)
        (sys / 'dev').write_text('179:3\n' if wrong_root else '179:2\n')
        private = base / 'private-credential-filename'; private.write_bytes(b'fixture only')
        service = base / 'etc/rc.d/init.d/nimbus-service'; service.parent.mkdir(parents=True)
        service.write_text('#!/bin/sh\necho UNSAFE-SERVICE-EXECUTED\n'); service.chmod(0o700)
        for pid, label, flags in [('42', 'dropbear', '0100001'), ('43', 'secret-arbitrary-name', '0100000'),
                                  ('44', 'fw_server', '2')]:
            process = proc / pid; (process / 'fd').mkdir(parents=True); (process / 'fdinfo').mkdir()
            (process / 'comm').write_text(label + '\n')
            (process / 'fd/3').symlink_to(private)
            if not (missing_info and pid == '42'):
                (process / 'fdinfo/3').write_text('pos:\t0\nflags:\t' + flags + '\n')
            (process / 'maps').write_text('1000-2000 rw-s 00000000 b3:02 100 /private/secret-map-path\n'
                                          if pid == '43' else '')
        script = SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]', ':')
        script = script.replace("stat -c '%d' /)", "stat -c '%d' '" + str(base) + "')")
        script = script.replace('/proc/', str(proc) + '/').replace('/sys/', str(base / 'sys') + '/')
        script = script.replace('/etc/rc.d/', str(base / 'etc/rc.d') + '/')
        path = base / 'inventory.sh'; path.write_text(script)
        return path

    def run_fixture(self, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); path = self.fixture(base, **kwargs)
            before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result = subprocess.run(['sh', str(path)], capture_output=True, text=True, timeout=10)
            after = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            return result

    def test_write_flags_and_shared_maps_without_private_details(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pid=42 label=dropbear writable_root_fds=1', result.stdout)
        self.assertIn('pid=44 label=fw_server writable_root_fds=1', result.stdout)
        self.assertIn('pid=43 label=other writable_root_fds=0 shared_writable_root_mappings=1', result.stdout)
        for private in ('private-credential-filename', 'secret-arbitrary-name', 'secret-map-path', '1000-2000'):
            self.assertNotIn(private, result.stdout)
        self.assertIn('not an exhaustive', result.stdout)
        self.assertNotIn('UNSAFE-SERVICE-EXECUTED', result.stdout)

    def test_export_or_wrong_root_refused(self):
        for kwargs in ({'exported': True}, {'wrong_root': True}):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(self.run_fixture(**kwargs).returncode, 0)

    def test_missing_fdinfo_reported_not_claimed_clean(self):
        result = self.run_fixture(missing_info=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Incomplete/raced metadata observations: 1', result.stdout)

    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(SCRIPT)], check=True)
