import hashlib
import importlib.util
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'device/root-capture-stream.c'
TOKEN = 'a' * 64
SIZE = 262144


@unittest.skipUnless(shutil.which('gcc') and Path('/usr/bin/sha256sum').is_file(), 'Host C compiler/hasher unavailable')
class NativeCaptureStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.build.name) / 'capture-fixture'
        cls.production = Path(cls.build.name) / 'capture-production'
        flags = ['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-fstack-protector-strong']
        subprocess.run([*flags, '-DNIMBUS_CAPTURE_FIXTURE', str(SOURCE), '-o', str(cls.binary)], check=True, capture_output=True)
        subprocess.run([*flags, str(SOURCE), '-o', str(cls.production)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        (self.base / 'proc/self').mkdir(parents=True)
        (self.base / 'sys/class/block/mmcblk0p2').mkdir(parents=True)
        (self.base / 'dev').mkdir()
        self.data = bytes(range(256)) * (SIZE // 256)
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.partition = self.base / 'dev/mmcblk0p2'
        self.partition.write_bytes(self.data)
        self.modules = self.base / 'proc/modules'
        self.modules.write_text('')
        self.mounts = self.base / 'proc/mounts'
        self.mounts.write_text('/dev/root / ext3 ro,relatime,errors=continue,barrier=0,data=writeback 0 0\n')
        self.mountinfo = self.base / 'proc/self/mountinfo'
        self.mountinfo.write_text('20 1 179:2 / / ro,relatime - ext3 /dev/root ro,errors=continue,barrier=0,data=writeback\n')
        for name, data in (('dev', '179:2\n'), ('start', '38912\n'), ('size', '512\n')):
            (self.base / 'sys/class/block/mmcblk0p2' / name).write_text(data)

    def ack(self, token=TOKEN, digest=None):
        return f'NIMBUS-HOST-VERIFIED {token} {digest or self.digest}\n'.encode()

    def command(self):
        return [str(self.binary), '--stream', TOKEN, str(self.base)]

    def run_capture(self, ack=None):
        before = {p: p.read_bytes() for p in self.base.rglob('*') if p.is_file() and not p.is_symlink()}
        result = subprocess.run(self.command(), input=self.ack() if ack is None else ack, capture_output=True, timeout=10)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        return result

    def test_stream_hashes_exact_delivered_bytes_and_never_emits_restoration_marker(self):
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        header = f'NIMBUS-ROOT-BEGIN {TOKEN} {SIZE} 179:2 ro\n'.encode()
        footer = f'NIMBUS-ROOT-END {TOKEN} {self.digest}\n'.encode()
        self.assertEqual(result.stdout, header + self.data + footer)
        self.assertNotIn(b'NIMBUS-ROOT-RESULT', result.stdout)

    def test_production_hash_child_uses_standalone_not_busybox_applet(self):
        text=SOURCE.read_text()
        self.assertIn('execl("/usr/bin/sha256sum", "sha256sum", (char *)NULL)',text)
        self.assertNotIn('execl("/bin/busybox"',text)

    def evidence_command(self, evidence):
        args = self.command()
        args[1] = '--stream-evidence'
        return ['sh', '-c', 'umask 077; exec 4>"$1"; shift; exec "$@"', 'fixture', str(evidence), *args]

    def test_child_drain_evidence_requires_closed_reader_and_reaped_hasher(self):
        evidence = self.base/'CHILD-DRAIN'
        result = subprocess.run(self.evidence_command(evidence), input=self.ack(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(evidence.read_text(), f'NIMBUS-CHILD-DRAIN {TOKEN} reader-closed hasher-drained\n')
        self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b'NIMBUS-CHILD-DRAIN', result.stdout)

    def test_cancellation_still_records_child_drain_but_not_capture_success(self):
        evidence = self.base/'CHILD-DRAIN'
        with subprocess.Popen(self.evidence_command(evidence), stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            process.stdout.readline(); process.stdout.read(SIZE); process.stdout.readline()
            process.send_signal(signal.SIGTERM)
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertEqual(evidence.read_text(), f'NIMBUS-CHILD-DRAIN {TOKEN} reader-closed hasher-drained\n')

    def test_missing_or_unsafe_evidence_descriptor_refuses_before_read(self):
        args = self.command();args[1] = '--stream-evidence'
        result = subprocess.run(args, input=self.ack(), capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout), (2, b''))
        command = ['sh', '-c', 'exec 4>/dev/null; exec "$@"', 'fixture', *args]
        result = subprocess.run(command, input=self.ack(), capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout), (2, b''))

    def test_output_loss_records_drain_after_terminating_hasher(self):
        evidence = self.base/'CHILD-DRAIN'
        with subprocess.Popen(self.evidence_command(evidence), stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            process.stdout.close()
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertEqual(evidence.read_text(), f'NIMBUS-CHILD-DRAIN {TOKEN} reader-closed hasher-drained\n')

    def test_rw_unknown_geometry_export_and_superblock_disagreement_refuse(self):
        cases = ((self.mounts, self.mounts.read_text().replace(' ro,', ' rw,')),
                 (self.mountinfo, self.mountinfo.read_text().replace(' - ext3 /dev/root ro,', ' - ext3 /dev/root rw,')),
                 (self.modules, 'g_file_storage 1\n'),
                 (self.base / 'sys/class/block/mmcblk0p2/dev', '179:4\n'),
                 (self.base / 'sys/class/block/mmcblk0p2/size', '1024\n'))
        for path, bad in cases:
            with self.subTest(path=path.name):
                original = path.read_text()
                path.write_text(bad)
                result = self.run_capture()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
                path.write_text(original)

    def test_symlink_or_short_fixture_partition_refuses(self):
        self.partition.write_bytes(b'short')
        self.assertEqual(self.run_capture().stdout, b'')
        self.partition.unlink()
        target = self.base / 'other'
        target.write_bytes(self.data)
        self.partition.symlink_to(target)
        self.assertEqual(self.run_capture().stdout, b'')

    def test_wrong_missing_or_overlong_ack_refuses_after_stream(self):
        for ack in (b'', self.ack(token='c'*64), self.ack(digest='c'*64), b'x'*300+b'\n'):
            with self.subTest(ack_bytes=len(ack)):
                result = self.run_capture(ack)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'NIMBUS-ROOT-RESULT', result.stdout)

    def test_state_change_during_ack_wait_invalidates(self):
        with subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN'))
            self.assertEqual(process.stdout.read(SIZE), self.data)
            self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-END'))
            self.mounts.write_text(self.mounts.read_text().replace(' ro,', ' rw,'))
            stdout, _ = process.communicate(input=self.ack(), timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(stdout, b'')

    def test_disconnect_during_output_and_cancellation_during_ack_clean_up(self):
        with subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            process.stdout.close()
            process.stdin.close()
            self.assertNotEqual(process.wait(timeout=10), 0)
        with subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            process.stdout.readline(); process.stdout.read(SIZE); process.stdout.readline()
            process.send_signal(signal.SIGTERM)
            _, _ = process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)

    def test_production_build_refuses_fixture_override_and_no_arguments(self):
        for command in ([str(self.production)], [str(self.production), '--stream', TOKEN, str(self.base)]):
            result = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')

    def test_hasher_failure_and_malformed_digest_never_emit_end(self):
        for number, body in enumerate((
                '/usr/bin/sha256sum\nexit 7\n',
                'cat >/dev/null\nprintf "invalid digest\\n"\n', 'exit 7\n')):
            fake = self.base / ('hasher' + str(number))
            fake.write_text('#!/bin/sh\n' + body)
            fake.chmod(0o700)
            binary = self.base / ('variant' + str(number))
            subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-DNIMBUS_CAPTURE_FIXTURE', '-DNIMBUS_FIXTURE_HASHER="' + str(fake) + '"',
                            str(SOURCE), '-o', str(binary)], check=True, capture_output=True)
            result = subprocess.run([str(binary), '--stream', TOKEN, str(self.base)],
                                    input=self.ack(), capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b'NIMBUS-ROOT-END', result.stdout)

    def test_oversized_or_symlink_metadata_refuses(self):
        self.modules.write_bytes(b'x'*20000)
        self.assertEqual(self.run_capture().stdout, b'')
        self.modules.unlink()
        target = self.base / 'module-data'
        target.write_bytes(b'')
        self.modules.symlink_to(target)
        self.assertEqual(self.run_capture().stdout, b'')

    def test_real_native_stream_integrates_with_host_receiver_ack(self):
        spec = importlib.util.spec_from_file_location('native_stream_receiver', ROOT / 'scripts/receive-root-capture.py')
        receiver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(receiver)
        private = self.base / 'private-backups'
        with patch.object(receiver, 'PRIVATE', private), patch.object(receiver, 'ROOT_BYTES', SIZE):
            output = receiver.prepare_output(private / 'synthetic')
            with subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                state = {'end': False, 'result': False}
                test = self
                class CoordinatorFixture:
                    # Only the restoration result is mocked. The compiled native
                    # reader/hasher/ACK wait and host fsync/readback are real.
                    def readline(self, limit):
                        if state['end']:
                            test.assertEqual(process.wait(timeout=10), 0)
                            test.assertIn(' ro,', test.mounts.read_text())
                            state['result'] = True
                            return f'NIMBUS-ROOT-RESULT {TOKEN} ro-until-ack rw-restored ssh-restored vendor-restored\n'.encode()
                        line = process.stdout.readline(limit)
                        if line.startswith(b'NIMBUS-ROOT-END'):
                            state['end'] = True
                        return line
                    def read(self, size):
                        return process.stdout.read(size)
                manifest = receiver.receive(CoordinatorFixture(), process.stdin, output, TOKEN)
                self.assertTrue(state['result'])
                self.assertEqual((output / 'rootfs.bin').read_bytes(), self.data)
                self.assertFalse(manifest['filesystem_consistency_verified'])
