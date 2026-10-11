import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'device/ssh/capture-listener.sh'


class CaptureListenerTests(unittest.TestCase):
    def fixture(self, base, occupied=False, unsafe=False):
        root = base / 'root'; auth = root / 'nimbus-ssh-test/auth'; auth.mkdir(parents=True, mode=0o700)
        auth.parent.chmod(0o700)
        private = auth / 'authorized_keys'; private.write_bytes(b'fixture public key'); private.chmod(0o644 if unsafe else 0o600)
        host = auth.parent / 'host-ed25519'; host.write_bytes(b'fixture host identity'); host.chmod(0o600)
        binary = auth.parent / 'dropbearmulti-bound'
        binary.write_text('#!/bin/sh\necho FIXTURE-BINARY-EXECUTED\nexit 99\n'); binary.chmod(0o700)
        proc = base / 'proc'; (proc / 'net').mkdir(parents=True)
        (proc / 'modules').write_text('')
        (proc / 'mounts').write_text('none /tmp tmpfs rw,size=4096k 0 0\n')
        (proc / 'net/tcp').write_text('0: 00000000:08B1 00000000:0000 0A\n' if occupied else '')
        (base / 'sys/class/net/wlan1').mkdir(parents=True)
        tmp = base / 'tmp'; tmp.mkdir()
        script = SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]', ':')
        script = script.replace('/root', str(root)).replace('/tmp/nimbus-capture', str(tmp / 'nimbus-capture'))
        script = script.replace('for dir in /tmp ', 'for dir in ' + str(tmp) + ' ')
        script = script.replace('/proc/', str(proc) + '/').replace('/sys/', str(base / 'sys') + '/')
        script = script.replace('1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c',
                                hashlib.sha256(binary.read_bytes()).hexdigest())
        # Production insists on root ownership; fixture uses the test user's uid.
        script = script.replace("stat -c '%u:%g:%a'", "stat -c '0:0:%a'")
        path = base / 'listener.sh'; path.write_text(script)
        return path, tmp

    def test_default_check_only_does_not_execute_or_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); path, tmp = self.fixture(base)
            before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result = subprocess.run(['sh', str(path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('Check-only', result.stdout)
            self.assertNotIn('FIXTURE-BINARY-EXECUTED', result.stdout)
            self.assertFalse(list(tmp.iterdir()))
            after = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_occupied_port_unsafe_keys_and_existing_stage_refused(self):
        for scenario in ('occupied', 'unsafe', 'existing'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                path, tmp = self.fixture(Path(folder), occupied=scenario == 'occupied', unsafe=scenario == 'unsafe')
                if scenario == 'existing': (tmp / 'nimbus-capture-ssh-v1').mkdir()
                result = subprocess.run(['sh', str(path), '--start'], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Starting OPTIONAL', result.stdout)

    def test_source_scope_and_syntax(self):
        subprocess.run(['sh', '-n', str(SCRIPT)], check=True)
        text = SCRIPT.read_text()
        for prohibited in ('killall', 'kill -TERM', 'fw_setenv', 'mount -o', 'fsfreeze', '\ncp ', '2224 \\'):
            self.assertNotIn(prohibited, text)
        self.assertIn('-F -l wlan1 -p 0.0.0.0:2225', text)
        self.assertNotIn('dropbear -F -E', text)
        self.assertIn('nohup setsid', text)

    def test_hash_mismatch_never_starts_listener(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); path, tmp = self.fixture(base)
            (base / 'root/nimbus-ssh-test/dropbearmulti-bound').write_text('changed binary fixture')
            result = subprocess.run(['sh', str(path), '--start'], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('hash mismatch', result.stdout)
            self.assertFalse(list(tmp.iterdir()))

    def test_failed_fixture_launch_retains_private_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            path, tmp = self.fixture(Path(folder))
            result = subprocess.run(['sh', str(path), '--start'], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Do not stop port 2224', result.stdout)
            stage = tmp / 'nimbus-capture-ssh-v1'
            self.assertEqual(stage.stat().st_mode & 0o777, 0o700)
            self.assertEqual((stage / 'listener.log').stat().st_mode & 0o777, 0o600)
            self.assertIn('FIXTURE-BINARY-EXECUTED', (stage / 'listener.log').read_text())

    def test_specific_retry_preserves_original_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path, tmp = self.fixture(Path(folder))
            stage = tmp / 'nimbus-capture-ssh-v1'; stage.mkdir(mode=0o700)
            log = stage / 'listener.log'; log.write_text('Invalid option -E\nfixture help\n'); log.chmod(0o600)
            result = subprocess.run(['sh', str(path), '--retry-invalid-E'], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)  # Harmless fixture executable exits 99.
            self.assertIn('Specific failed stage preserved', result.stdout)
            self.assertEqual((tmp / 'nimbus-capture-ssh-v1.invalid-E/listener.log').read_text(), 'Invalid option -E\nfixture help\n')

    def test_retry_rejects_unrelated_failure_pid_or_occupied_port(self):
        for scenario in ('unrelated', 'pid', 'occupied'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                path, tmp = self.fixture(Path(folder), occupied=scenario == 'occupied')
                stage = tmp / 'nimbus-capture-ssh-v1'; stage.mkdir(mode=0o700)
                log = stage / 'listener.log'
                log.write_text('other failure\n' if scenario == 'unrelated' else 'Invalid option -E\n'); log.chmod(0o600)
                if scenario == 'pid': (stage / 'listener.pid').write_text('123\n')
                result = subprocess.run(['sh', str(path), '--retry-invalid-E'], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Starting OPTIONAL', result.stdout)
                self.assertTrue(log.exists())
                self.assertFalse((tmp / 'nimbus-capture-ssh-v1.invalid-E').exists())
