import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'device/ssh/management-owner-checkpoint.sh'


class ManagementOwnerTests(unittest.TestCase):
    def fixture(self, exported=False, wrong_binary=False, args=()):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            proc = base / 'proc'
            (proc / 'self').mkdir(parents=True)
            (proc / 'net').mkdir()
            (proc / 'modules').write_text('g_file_storage 1\n' if exported else '')
            (proc / 'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
            block = base / 'sys/class/block/mmcblk0p2'
            block.mkdir(parents=True)
            (block / 'dev').write_text('179:2\n')
            binary = base / 'private-executable-name'
            binary.write_bytes(b'fixture executable; never execute')
            for pid, label, parent, start, socket in (
                    ('100', 'dropbearmulti-b', '1', '123', '111'),
                    ('200', 'dropbear', '100', '456', '222'),
                    ('300', 'private customer name', '1', '789', '333')):
                process = proc / pid
                (process / 'fd').mkdir(parents=True)
                (process / 'comm').write_text(label + '\n')
                (process / 'stat').write_text(pid + ' (strange ) comm) ' +
                                             ' '.join(['S', parent] + ['0'] * 17 + [start]) + '\n')
                (process / 'exe').symlink_to(binary)
                (process / 'fd/3').symlink_to('socket:[' + socket + ']')
                (process / 'fd/4').symlink_to(base / 'PRIVATE KEY OR LOG DO NOT READ')
            (proc / 'net/tcp').write_text('0: 00000000:08B0 00000000:0000 0A 0:0 00:0 0 0 0 111\n'
                                         '1: 00000000:08B0 01020304:ABCD 01 0:0 00:0 0 0 0 222\n')
            (proc / 'net/tcp6').write_text('')
            text = SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]', ':')
            text = text.replace('1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c',
                                '0' * 64 if wrong_binary else hashlib.sha256(binary.read_bytes()).hexdigest())
            # Quoted one-pass replacement; no recursive /tmp substitution.
            text = text.replace('/proc/', str(proc) + '/').replace('/sys/', str(base / 'sys') + '/')
            script = base / 'checkpoint.sh'
            script.write_text(text)
            before = {p: p.read_bytes() for p in base.rglob('*') if p.is_file() and not p.is_symlink()}
            result = subprocess.run(['sh', str(script), *args], capture_output=True, text=True, timeout=10)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            return result

    def test_listener_parent_and_session_distinguished(self):
        result = self.fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pid=100 label=dropbearmulti-b parent_pid=1 start_ticks=123 reviewed_executable=matched listening_fd_refs_2224=1', result.stdout)
        self.assertIn('pid=200 label=dropbear parent_pid=100 start_ticks=456 reviewed_executable=matched listening_fd_refs_2224=0', result.stdout)
        for private in ('01020304', 'private customer name', 'private-executable-name', 'PRIVATE KEY'):
            self.assertNotIn(private, result.stdout + result.stderr)

    def test_mismatch_not_promoted_to_matched(self):
        result = self.fixture(wrong_binary=True)
        self.assertIn('reviewed_executable=different_or_raced', result.stdout)
        self.assertNotIn('reviewed_executable=matched', result.stdout)

    def test_export_and_action_arguments_refuse(self):
        for kwargs in ({'exported': True}, {'args': ('--stop',)}):
            result = self.fixture(**kwargs)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('pid=100', result.stdout)

    def test_shell_syntax(self):
        result = subprocess.run(['sh', '-n', str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
