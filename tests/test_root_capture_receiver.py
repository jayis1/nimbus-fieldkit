import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('root_receiver', ROOT / 'scripts/receive-root-capture.py')
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)
SESSION = 'a' * 64
DATA = b'synthetic root fixture; no credentials or device data'
DIGEST = hashlib.sha256(DATA).hexdigest()


def frames(result=None, end=None, begin=None):
    return ((begin or f'NIMBUS-ROOT-BEGIN {SESSION} {len(DATA)} 179:2 ro\n').encode() + DATA +
            (end or f'NIMBUS-ROOT-END {SESSION} {DIGEST}\n').encode() +
            (result if result is not None else
             f'NIMBUS-ROOT-RESULT {SESSION} ro-until-ack rw-restored ssh-restored vendor-restored\n').encode())


class RootCaptureReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.private = Path(self.temporary.name) / 'private'
        self.patch_private = patch.object(receiver, 'PRIVATE', self.private)
        self.patch_bytes = patch.object(receiver, 'ROOT_BYTES', len(DATA))
        self.patch_private.start(); self.patch_bytes.start()
        self.addCleanup(self.patch_private.stop); self.addCleanup(self.patch_bytes.stop)
        self.output = receiver.prepare_output(self.private / 'new')

    def test_complete_receipt_is_not_consistency_or_restore_certification(self):
        control = io.BytesIO()
        manifest = receiver.receive(io.BytesIO(frames()), control, self.output, SESSION)
        self.assertEqual(control.getvalue(), f'NIMBUS-HOST-VERIFIED {SESSION} {DIGEST}\n'.encode())
        self.assertEqual((self.output / 'rootfs.bin').read_bytes(), DATA)
        self.assertEqual((self.output / 'rootfs.bin').stat().st_ino,
                         (self.output / 'rootfs.bin.partial').stat().st_ino)
        for name in ('rootfs.bin', 'rootfs.bin.partial', 'CAPTURE-MANIFEST.json'):
            self.assertEqual(stat.S_IMODE((self.output / name).stat().st_mode), 0o600)
        for flag in ('filesystem_consistency_verified', 'restore_tested', 'flash_authorized', 'production_ready'):
            self.assertIs(manifest[flag], False)

    def test_ack_requires_synced_file_readback_and_precedes_result_read(self):
        events = []
        class Stream(io.BytesIO):
            def readline(self, limit=-1):
                line = super().readline(limit)
                if line.startswith(b'NIMBUS-ROOT-RESULT'):
                    self_test.assertIn('ack', events)
                return line
        class Control(io.BytesIO):
            def write(self, data):
                self_test.assertEqual((output / 'rootfs.bin.partial').read_bytes(), DATA)
                self_test.assertIn('sync', events)
                events.append('ack')
                return super().write(data)
        self_test, output = self, self.output
        real_sync = receiver.os.fsync
        def sync(fd):
            events.append('sync')
            return real_sync(fd)
        with patch.object(receiver.os, 'fsync', side_effect=sync):
            receiver.receive(Stream(frames()), Control(), self.output, SESSION)

    def test_bad_header_geometry_root_state_and_session_refused_before_file(self):
        for begin in (f'NIMBUS-ROOT-BEGIN {SESSION} {len(DATA)} 179:2 rw\n',
                      f'NIMBUS-ROOT-BEGIN {SESSION} {len(DATA)} 179:4 ro\n',
                      f'NIMBUS-ROOT-BEGIN {SESSION} 999 179:2 ro\n',
                      f'NIMBUS-ROOT-BEGIN {"b"*64} {len(DATA)} 179:2 ro\n', 'x'*300+'\n'):
            with self.assertRaises(ValueError):
                receiver.receive(io.BytesIO(frames(begin=begin)), io.BytesIO(), self.output, SESSION)
            self.assertEqual(list(self.output.iterdir()), [])

    def test_truncation_or_wrong_digest_never_acknowledges(self):
        header = f'NIMBUS-ROOT-BEGIN {SESSION} {len(DATA)} 179:2 ro\n'.encode()
        for number, content in enumerate((header + DATA[:3], frames(end=f'NIMBUS-ROOT-END {SESSION} {"0"*64}\n'))):
            output = receiver.prepare_output(self.private / ('bad' + str(number)))
            control = io.BytesIO()
            with self.assertRaises(ValueError):
                receiver.receive(io.BytesIO(content), control, output, SESSION)
            self.assertEqual(control.getvalue(), b'')
            self.assertTrue((output / 'rootfs.bin.partial').exists())
            self.assertFalse((output / 'CAPTURE-MANIFEST.json').exists())
            self.assertFalse((output / 'rootfs.bin').exists())

    def test_premature_rw_failed_restoration_disconnect_and_trailing_data_refused(self):
        bad = ('', f'NIMBUS-ROOT-RESULT {SESSION} rw-before-ack rw-restored ssh-restored vendor-restored\n',
               f'NIMBUS-ROOT-RESULT {SESSION} ro-until-ack rw-failed ssh-restored vendor-restored\n',
               f'NIMBUS-ROOT-RESULT {SESSION} ro-until-ack rw-restored ssh-failed vendor-restored\n',
               f'NIMBUS-ROOT-RESULT {SESSION} ro-until-ack rw-restored ssh-restored vendor-failed\n')
        for number, result in enumerate(bad):
            output = receiver.prepare_output(self.private / ('failed' + str(number)))
            with self.assertRaises(ValueError):
                receiver.receive(io.BytesIO(frames(result=result)), io.BytesIO(), output, SESSION)
            self.assertFalse((output / 'rootfs.bin').exists())
            self.assertFalse((output / 'CAPTURE-MANIFEST.json').exists())
        with self.assertRaises(ValueError):
            receiver.receive(io.BytesIO(frames() + b'extra'), io.BytesIO(), self.output, SESSION)
        self.assertFalse((self.output / 'CAPTURE-MANIFEST.json').exists())

    def test_failed_ack_write_or_flush_never_promotes(self):
        class Broken(io.BytesIO):
            def write(self, data):
                return 0
        class BrokenFlush(io.BytesIO):
            def flush(self):
                raise OSError('synthetic disconnect')
        for number, control in enumerate((Broken(), BrokenFlush())):
            output = receiver.prepare_output(self.private / ('ackbad' + str(number)))
            with self.assertRaises((ValueError, OSError)):
                receiver.receive(io.BytesIO(frames()), control, output, SESSION)
            self.assertFalse((output / 'CAPTURE-MANIFEST.json').exists())
            self.assertFalse((output / 'rootfs.bin').exists())

    def test_prior_files_symlinks_and_unsafe_directory_refused(self):
        prior = self.output / 'rootfs.bin'
        prior.write_bytes(b'preserved')
        with self.assertRaises(ValueError):
            receiver.receive(io.BytesIO(frames()), io.BytesIO(), self.output, SESSION)
        self.assertEqual(prior.read_bytes(), b'preserved')
        with self.assertRaises(FileExistsError):
            receiver.prepare_output(self.output)
        alias = self.private / 'alias'
        alias.symlink_to(self.output)
        with self.assertRaises(ValueError):
            receiver.prepare_output(alias)
        self.private.chmod(0o755)
        with self.assertRaises(ValueError):
            receiver.prepare_output(self.private / 'unsafe')

    def test_invalid_token_and_short_disk_space_refuse(self):
        with self.assertRaises(ValueError):
            receiver.receive(io.BytesIO(frames()), io.BytesIO(), self.output, 'invalid')
        usage = type('Usage', (), {'free': 1})()
        with patch.object(receiver.shutil, 'disk_usage', return_value=usage):
            with self.assertRaises(ValueError):
                receiver.prepare_output(self.private / 'no-space')
        self.assertFalse((self.private / 'no-space').exists())

    def test_failed_host_fsync_never_acknowledges(self):
        control = io.BytesIO()
        with patch.object(receiver.os, 'fsync', side_effect=OSError('synthetic storage failure')):
            with self.assertRaises(OSError):
                receiver.receive(io.BytesIO(frames()), control, self.output, SESSION)
        self.assertEqual(control.getvalue(), b'')
        self.assertFalse((self.output / 'CAPTURE-MANIFEST.json').exists())

    def test_host_readback_mismatch_never_acknowledges(self):
        control = io.BytesIO()
        wrong = type('Digest', (), {'hexdigest': lambda self: '0' * 64})()
        with patch.object(receiver.hashlib, 'file_digest', return_value=wrong):
            with self.assertRaises(ValueError):
                receiver.receive(io.BytesIO(frames()), control, self.output, SESSION)
        self.assertEqual(control.getvalue(), b'')
        self.assertFalse((self.output / 'CAPTURE-MANIFEST.json').exists())

    def test_receipt_fsync_failure_never_publishes_final_manifest(self):
        real_sync = receiver.os.fsync
        def sync(fd):
            if Path(f'/proc/self/fd/{fd}').resolve().name == 'CAPTURE-MANIFEST.json.partial':
                raise OSError('synthetic receipt sync failure')
            return real_sync(fd)
        with patch.object(receiver.os, 'fsync', side_effect=sync):
            with self.assertRaises(OSError):
                receiver.receive(io.BytesIO(frames()), io.BytesIO(), self.output, SESSION)
        self.assertTrue((self.output/'CAPTURE-MANIFEST.json.partial').exists())
        self.assertFalse((self.output/'CAPTURE-MANIFEST.json').exists())
        self.assertEqual((self.output/'rootfs.bin').read_bytes(), DATA)

    def test_publication_sync_failure_withdraws_only_own_final_link(self):
        real_sync = receiver.sync_directory
        calls = 0
        def sync(path):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError('synthetic publication failure')
            return real_sync(path)
        with patch.object(receiver, 'sync_directory', side_effect=sync):
            with self.assertRaises(OSError):
                receiver.receive(io.BytesIO(frames()), io.BytesIO(), self.output, SESSION)
        self.assertTrue((self.output/'CAPTURE-MANIFEST.json.partial').exists())
        self.assertFalse((self.output/'CAPTURE-MANIFEST.json').exists())

    def test_partial_receipt_refuses_attempt_reuse(self):
        partial = self.output/'CAPTURE-MANIFEST.json.partial'
        partial.write_bytes(b'original failed receipt')
        with self.assertRaises(ValueError):
            receiver.receive(io.BytesIO(frames()), io.BytesIO(), self.output, SESSION)
        self.assertEqual(partial.read_bytes(), b'original failed receipt')
