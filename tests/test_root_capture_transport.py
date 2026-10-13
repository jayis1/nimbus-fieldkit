import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_transport', ROOT/'scripts/root-capture-transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
TOKEN = 'a'*64
DATA = b'fixture'*10000
DIGEST = hashlib.sha256(DATA).hexdigest()


class CaptureTransportTests(unittest.TestCase):
    def test_full_256mib_synthetic_stream_real_host_sync_readback_and_ack(self):
        # Real fixed geometry and real host filesystem IO, no SSH, raw device,
        # native service or remount. This is NOT a consistency/restore test.
        receiver=transport.load_receiver()
        self.assertEqual(receiver.ROOT_BYTES,268435456)
        chunk=bytes(range(256))*256
        checksum=hashlib.sha256()
        for _ in range(receiver.ROOT_BYTES//len(chunk)):checksum.update(chunk)
        expected=checksum.hexdigest()
        with fixture_temp(prefix='transport-fullsize-') as temporary:
            private=Path(temporary)/'private'
            with patch.object(receiver,'PRIVATE',private):
                output=receiver.prepare_output(private/'attempt')
                child=f'''
import hashlib, pathlib, sys
out=sys.stdout.buffer
chunk=bytes(range(256))*256
size=268435456
checksum=hashlib.sha256()
out.write(b'NIMBUS-ROOT-BEGIN {TOKEN} 268435456 179:2 ro\\n');out.flush()
for _ in range(size//len(chunk)):
 out.write(chunk);checksum.update(chunk)
digest=checksum.hexdigest()
out.write(('NIMBUS-ROOT-END {TOKEN} '+digest+'\\n').encode());out.flush()
ack=sys.stdin.buffer.readline()
if ack != ('NIMBUS-HOST-VERIFIED {TOKEN} '+digest+'\\n').encode():sys.exit(8)
path=pathlib.Path({str(output/'rootfs.bin.partial')!r})
if path.stat().st_size != size:sys.exit(9)
with path.open('rb') as saved:
 if hashlib.file_digest(saved,'sha256').hexdigest()!=digest:sys.exit(10)
sys.stderr.write('SYNTHETIC-ACK-AFTER-HOST-READBACK=PASS\\n');sys.stderr.flush()
out.write(b'NIMBUS-ROOT-RESULT {TOKEN} ro-until-ack rw-restored ssh-restored vendor-restored\\n');out.flush()
'''
                real_fsync=os.fsync
                events=[]
                def sync(fd):
                    # Instrument and actually execute fsync; never stub it.
                    events.append(Path(f'/proc/self/fd/{fd}').resolve().name)
                    return real_fsync(fd)
                with subprocess.Popen([sys.executable,'-c',child],stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0) as process:
                    with patch.object(receiver.os,'fsync',side_effect=sync):
                        result=transport.receive_process(process,output,TOKEN,seconds=60,receiver=receiver)
                    self.assertEqual(process.wait(timeout=5),0)
                self.assertEqual(result['bytes'],receiver.ROOT_BYTES)
                self.assertEqual(result['sha256'],expected)
                self.assertTrue(result['host_file_readback_verified'])
                self.assertTrue(result['host_acknowledgment_sent'])
                self.assertIn('rootfs.bin.partial',events);self.assertIn('attempt',events)
                self.assertIn(b'SYNTHETIC-ACK-AFTER-HOST-READBACK=PASS', (output/'TRANSPORT-STDERR.log').read_bytes())
                self.assertEqual((output/'rootfs.bin').stat().st_ino,(output/'rootfs.bin.partial').stat().st_ino)
                with (output/'rootfs.bin').open('rb') as saved:self.assertEqual(hashlib.file_digest(saved,'sha256').hexdigest(),expected)
                receipt=json.loads((output/'CAPTURE-MANIFEST.json').read_text())
                for flag in ('filesystem_consistency_verified','restore_tested','production_ready','flash_authorized'):
                    self.assertFalse(receipt[flag])

    def test_fixed_pinned_non_tty_plan_never_launches(self):
        with patch.object(subprocess, 'Popen') as launch:
            plan = transport.ssh_plan(TOKEN,host='192.0.2.10')
            launch.assert_not_called()
        for item in ('StrictHostKeyChecking=yes', 'HostKeyAlias=[192.0.2.10]:2224',
                     'BatchMode=yes', 'RequestTTY=no', 'ForwardAgent=no', 'ControlPath=none'):
            self.assertIn(item, plan)
        self.assertIn('-T', plan)
        self.assertNotIn('-n', plan)
        self.assertNotIn('sh -s', plan[-1])
        for invalid in ('', TOKEN+';reboot', 'A'*64, None):
            with self.assertRaises(ValueError):
                transport.ssh_plan(invalid,host='192.0.2.10')
        for invalid_host in ('', '127.0.0.1', '0.0.0.0', '224.0.0.1', 'device;reboot', None):
            with self.assertRaises(ValueError):transport.ssh_plan(TOKEN,host=invalid_host)

    def child(self, status=0, diagnostics=100000, extra=False, truncated=False, stall=False):
        return f'''
import sys, time
out=sys.stdout.buffer
data=b'fixture'*10000
out.write(b'NIMBUS-ROOT-BEGIN {TOKEN} {len(DATA)} 179:2 ro\\n');out.flush()
if {truncated!r}:
 out.write(data[:20]);out.flush();sys.exit(0)
out.write(data);out.flush()
sys.stderr.buffer.write(b'd'*{diagnostics});sys.stderr.buffer.flush()
out.write(b'NIMBUS-ROOT-END {TOKEN} {DIGEST}\\n');out.flush()
ack=sys.stdin.buffer.readline()
if ack != b'NIMBUS-HOST-VERIFIED {TOKEN} {DIGEST}\\n': sys.exit(8)
out.write(b'NIMBUS-ROOT-RESULT {TOKEN} ro-until-ack rw-restored ssh-restored vendor-restored\\n');out.flush()
if {extra!r}: out.write(b'extra');out.flush()
if {stall!r}: time.sleep(1)
sys.exit({status})
'''

    def run_case(self, **kwargs):
        with fixture_temp(prefix='transport-test-') as temporary:
            private = Path(temporary)/'private'
            receiver = transport.load_receiver()
            with patch.object(receiver, 'PRIVATE', private), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(private/'attempt')
                with subprocess.Popen([sys.executable, '-c', self.child(**kwargs)], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as process:
                    try:
                        result = transport.receive_process(process, output, TOKEN, seconds=5, receiver=receiver)
                        error = None
                    except (ValueError, OSError) as failure:
                        result, error = None, failure
                    process.wait(timeout=5)
                names = {path.name for path in output.iterdir()}
                log = (output/'TRANSPORT-STDERR.log').read_bytes()
                data = (output/'rootfs.bin').read_bytes() if 'rootfs.bin' in names else None
                return result, error, names, log, data

    def test_full_duplex_large_diagnostics_do_not_deadlock_or_pollute_image(self):
        result, error, names, log, data = self.run_case()
        self.assertIsNone(error)
        self.assertEqual(data, DATA)
        self.assertEqual(log, b'd'*100000)
        self.assertIn('CAPTURE-MANIFEST.json', names)
        self.assertFalse(result['filesystem_consistency_verified'])
        self.assertFalse(result['flash_authorized'])

    def test_nonzero_exit_after_valid_trailer_prevents_promotion_and_receipt(self):
        _, error, names, _, _ = self.run_case(status=7)
        self.assertIsInstance(error, ValueError)
        self.assertNotIn('rootfs.bin', names)
        self.assertNotIn('CAPTURE-MANIFEST.json', names)
        self.assertIn('rootfs.bin.partial', names)

    def test_diagnostic_overflow_is_bounded_and_irreversibly_invalid(self):
        _, error, names, log, _ = self.run_case(diagnostics=transport.MAX_DIAGNOSTICS+100000)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(len(log), transport.MAX_DIAGNOSTICS)
        self.assertNotIn('CAPTURE-MANIFEST.json', names)

    def test_truncation_and_trailing_bytes_refuse_completion(self):
        for kwargs in ({'truncated': True}, {'extra': True}):
            with self.subTest(kwargs=kwargs):
                _, error, names, _, _ = self.run_case(**kwargs)
                self.assertIsInstance(error, ValueError)
                self.assertNotIn('CAPTURE-MANIFEST.json', names)
                self.assertNotIn('rootfs.bin', names)

    def test_timeout_after_trailer_does_not_commit_or_signal_child(self):
        with fixture_temp(prefix='transport-timeout-') as temporary:
            receiver = transport.load_receiver()
            with patch.object(receiver, 'PRIVATE', Path(temporary)/'private'), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(receiver.PRIVATE/'attempt')
                with subprocess.Popen([sys.executable, '-c', self.child(stall=True)], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as process:
                    with patch.object(process, 'terminate') as terminate, patch.object(process, 'kill') as kill:
                        with self.assertRaises(TimeoutError):
                            transport.receive_process(process, output, TOKEN, seconds=0.3, receiver=receiver)
                        terminate.assert_not_called();kill.assert_not_called()
                    self.assertIsNone(process.poll())
                    process.wait(timeout=5)  # Fixture naturally exits; never leave a child behind.
                self.assertFalse((output/'CAPTURE-MANIFEST.json').exists())
                self.assertFalse((output/'rootfs.bin').exists())

    def test_prior_diagnostic_evidence_refuses_overwrite(self):
        with fixture_temp(prefix='transport-existing-') as temporary:
            receiver = transport.load_receiver()
            with patch.object(receiver, 'PRIVATE', Path(temporary)/'private'), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(receiver.PRIVATE/'attempt')
                (output/'TRANSPORT-STDERR.log').write_bytes(b'preserve')
                with subprocess.Popen([sys.executable, '-c', 'pass'], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as process:
                    with self.assertRaises(FileExistsError):
                        transport.receive_process(process, output, TOKEN, receiver=receiver)
                self.assertEqual((output/'TRANSPORT-STDERR.log').read_bytes(), b'preserve')

    def test_diagnostic_sync_failure_prevents_image_promotion(self):
        real_sync = os.fsync
        def sync(fd):
            if Path(f'/proc/self/fd/{fd}').resolve().name == 'TRANSPORT-STDERR.log':
                raise OSError('synthetic diagnostic sync failure')
            return real_sync(fd)
        with patch.object(transport.os, 'fsync', side_effect=sync):
            _, error, names, _, _ = self.run_case()
        self.assertIsInstance(error, OSError)
        self.assertNotIn('rootfs.bin', names)
        self.assertNotIn('CAPTURE-MANIFEST.json', names)

    def test_buffered_pipes_refuse_before_log_creation(self):
        with fixture_temp(prefix='transport-buffered-') as temporary:
            receiver = transport.load_receiver()
            with patch.object(receiver, 'PRIVATE', Path(temporary)/'private'), patch.object(receiver, 'ROOT_BYTES', len(DATA)):
                output = receiver.prepare_output(receiver.PRIVATE/'attempt')
                with subprocess.Popen([sys.executable, '-c', 'pass'], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                    with self.assertRaises(ValueError):
                        transport.receive_process(process, output, TOKEN, receiver=receiver)
                self.assertEqual(list(output.iterdir()), [])
