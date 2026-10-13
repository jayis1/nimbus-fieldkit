import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

import test_root_capture_worker as coordinator

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'device/root-capture-guardian.c'
TOKEN = 'a'*64


@unittest.skipUnless(shutil.which('gcc'), 'Host compiler unavailable')
class GuardianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = fixture_temp(prefix='guardian-build-')
        cls.binary = Path(cls.build.name)/'guardian-fixture'
        cls.disabled = Path(cls.build.name)/'guardian-disabled'
        flags = ['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-fstack-protector-strong']
        subprocess.run([*flags, '-DNIMBUS_GUARDIAN_FIXTURE', str(SOURCE), '-o', str(cls.binary)], check=True, capture_output=True)
        subprocess.run([*flags, str(SOURCE), '-o', str(cls.disabled)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nimbus-guardian-fixture-', dir=Path.home()/'.cache')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def fixture(self):
        stage, proc, database = coordinator.CaptureWorkerTests().fixture(self.base)
        return stage, proc, database

    def command(self, stage):
        return [str(self.binary), '--fixture', TOKEN, str(stage)]

    def environment(self):
        return dict(os.environ, SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')

    def read_frame(self, process):
        self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN'))
        self.assertEqual(process.stdout.read(len(coordinator.DATA)), coordinator.DATA)
        self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-END'))

    def test_default_build_cannot_run_fixture_or_native_mode(self):
        for args in ([], ['--fixture', TOKEN, str(self.base)], ['--supervise', TOKEN]):
            result = subprocess.run([str(self.disabled), *args], capture_output=True, timeout=5)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b'', b''))
        self.assertEqual(list(self.base.iterdir()), [])

    def test_guardian_receiver_transport_round_trip(self):
        stage, _, database = self.fixture()
        original = database.read_bytes()
        spec = importlib.util.spec_from_file_location('guardian_transport', ROOT/'scripts/root-capture-transport.py')
        transport = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(transport)
        receiver = transport.load_receiver()
        with patch.object(receiver, 'PRIVATE', self.base/'private'), patch.object(receiver, 'ROOT_BYTES', len(coordinator.DATA)):
            output = receiver.prepare_output(receiver.PRIVATE/'attempt')
            with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=self.environment(), bufsize=0) as process:
                receipt = transport.receive_process(process, output, TOKEN, seconds=15, receiver=receiver)
                self.assertEqual(process.returncode, 0)
            self.assertEqual((output/'rootfs.bin').read_bytes(), coordinator.DATA)
            self.assertFalse(receipt['filesystem_consistency_verified'])
        self.assertEqual(database.read_bytes(), original)
        self.assertIn('invalidated=no', (stage/'GUARDIAN-RESULT').read_text())
        self.assertIn('restoration_certified=no', (stage/'GUARDIAN-RESULT').read_text())
        self.assertIn('Restoration observed', (stage/'GUARDIAN-STDERR.log').read_text())
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')

    def test_output_disconnect_while_ack_input_stays_open_recovers(self):
        stage, proc, _ = self.fixture()
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            process.stdout.close()  # No further writes are pending: poll must detect this.
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertIn('invalidated=yes', (stage/'GUARDIAN-RESULT').read_text())
        self.assertEqual((stage/'GUARDIAN-INVALID').read_text(), TOKEN)
        self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
        self.assertIn(' rw,', (proc/'mounts').read_text())

    def test_control_disconnect_never_succeeds(self):
        stage, _, _ = self.fixture()
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            process.stdin.close()
            self.assertNotEqual(process.wait(timeout=10), 0)
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', process.stdout.read())
        self.assertIn('invalidated=yes', (stage/'GUARDIAN-RESULT').read_text())
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')

    def test_waiter_death_does_not_kill_detached_owner(self):
        stage, proc, _ = self.fixture()
        # A separate fixture process is a subreaper so that killing the waiter
        # cannot leave an orphan/zombie in the test harness or require PID1 cleanup.
        runner = r'''
import ctypes, os, pathlib, signal, subprocess, sys, time
assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0
binary, stage, token, size = sys.argv[1:]
with subprocess.Popen([binary, '--fixture', token, stage], stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE) as waiter:
 assert waiter.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN')
 assert len(waiter.stdout.read(int(size))) == int(size)
 assert waiter.stdout.readline().startswith(b'NIMBUS-ROOT-END')
 owners=pathlib.Path(f'/proc/{waiter.pid}/task/{waiter.pid}/children').read_text().split()
 assert len(owners)==1
 owner=int(owners[0])
 assert os.getsid(owner)==owner
 waiter.kill();waiter.wait(timeout=5)
 assert pathlib.Path(f'/proc/{owner}/exe').resolve()==pathlib.Path(binary)
 waiter.stdout.close();waiter.stdin.close()
 deadline=time.monotonic()+10
 while True:
  ended,status=os.waitpid(owner, os.WNOHANG)
  if ended:
   assert os.WIFEXITED(status) and os.WEXITSTATUS(status)!=0
   break
  assert time.monotonic()<deadline, 'owner did not complete'
  time.sleep(0.02)
assert 'invalidated=yes' in pathlib.Path(stage,'GUARDIAN-RESULT').read_text()
'''
        result = subprocess.run([sys.executable, '-c', runner, str(self.binary), str(stage), TOKEN, str(len(coordinator.DATA))],
                                env=self.environment(), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
        self.assertEqual((stage/'mounts').read_text().count('-n -i -w'), 1)
        self.assertIn(' rw,', (proc/'mounts').read_text())

    def test_persistent_claim_prevents_second_worker_even_after_failure(self):
        stage, _, _ = self.fixture()
        first = subprocess.run(self.command(stage), input=b'', capture_output=True, env=self.environment(), timeout=10)
        self.assertNotEqual(first.returncode, 0)
        before = {p.name: p.read_bytes() for p in stage.iterdir() if p.is_file()}
        second = subprocess.run(self.command(stage), input=b'', capture_output=True, env=self.environment(), timeout=5)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in stage.iterdir() if p.is_file()})

    def test_extra_inherited_descriptor_refuses_before_claim_or_worker(self):
        stage, _, database = self.fixture()
        with database.open('rb') as inherited:
            result = subprocess.run(self.command(stage), input=b'', capture_output=True, env=self.environment(),
                                    pass_fds=(inherited.fileno(),), timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((stage/'GUARDIAN-CLAIM').exists())
        self.assertFalse((stage/'signals').exists())
        self.assertFalse((stage/'mounts').exists())

    def test_excess_ack_invalidates_and_restores(self):
        stage, _, _ = self.fixture()
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            stdout, _ = process.communicate(input=b'x'*300+b'\n', timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', stdout)
        self.assertIn('invalidated=yes', (stage/'GUARDIAN-RESULT').read_text())

    def test_owner_term_recovers_without_killing_process_group(self):
        stage, _, _ = self.fixture()
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
            self.assertEqual(len(children), 1)
            owner = int(children[0])
            self.assertEqual(Path(f'/proc/{owner}/exe').resolve(), self.binary)
            os.kill(owner, signal.SIGTERM)
            self.assertNotEqual(process.wait(timeout=10), 0)
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', process.stdout.read())
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')

    def test_log_overflow_is_bounded_and_invalidates(self):
        stage, _, _ = self.fixture()
        worker = stage/'worker.sh'
        # Synthetic wrapper emits diagnostics BEFORE any coordinator action.
        worker.write_text('#!/bin/sh\n'+str(sys.executable)+" -c 'import sys;sys.stderr.write(\"d\"*200000)'\nexit 7\n")
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertEqual((stage/'GUARDIAN-STDERR.log').stat().st_size, 131072)
        self.assertIn('invalidated=yes', (stage/'GUARDIAN-RESULT').read_text())
        self.assertFalse((stage/'mounts').exists())

    def test_disconnect_during_raw_fixture_read_drains_before_rw(self):
        stage, proc, _ = self.fixture()
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN'))
            process.stdout.close()
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
        self.assertEqual((stage/'mounts').read_text().count('-n -i -w'), 1)
        self.assertIn(' rw,', (proc/'mounts').read_text())
        self.assertIn('invalidated=yes', (stage/'GUARDIAN-RESULT').read_text())

    def test_owner_deadline_cancels_cooperatively_and_drains(self):
        stage, _, _ = self.fixture()
        fast = self.base/'guardian-short-deadline'
        subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DNIMBUS_GUARDIAN_FIXTURE', '-DNIMBUS_GUARDIAN_DEADLINE_SECONDS=1',
                        str(SOURCE), '-o', str(fast)], check=True, capture_output=True)
        with subprocess.Popen([str(fast), '--fixture', TOKEN, str(stage)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            # Leave both channels open, withholding ACK until the owner expires.
            self.assertNotEqual(process.wait(timeout=10), 0)
            self.assertNotIn(b'NIMBUS-ROOT-RESULT', process.stdout.read())
        self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')

    def test_cancellation_while_cleanup_runs_does_not_interrupt_restoration(self):
        stage, proc, _ = self.fixture()
        # Pause cleanup immediately before its safe rw check, after signal traps
        # are protected. Only test source is changed, and its fixture sum repinned.
        worker = stage/'worker.sh'
        text = worker.read_text().replace('    recovered=yes\n',
                                        '    : > cleanup-entered\n    sleep 1\n    recovered=yes\n')
        worker.write_text(text)
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n'
                                              for name in ('worker.sh', 'identity.sh', 'streamer')))
        with subprocess.Popen(self.command(stage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment()) as process:
            self.read_frame(process)
            process.stdin.write(b'invalid ack\n'); process.stdin.flush()
            deadline = time.monotonic()+5
            while not (stage/'cleanup-entered').exists():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            process.stdout.close()  # Owner now sends its one TERM during cleanup.
            self.assertNotEqual(process.wait(timeout=10), 0)
        self.assertEqual((stage/'RESULT').read_text(), TOKEN+' FAIL\n')
        self.assertEqual((stage/'starts').read_text(), 'vendor\nssh\n')
        self.assertIn(' rw,', (proc/'mounts').read_text())
import hashlib
