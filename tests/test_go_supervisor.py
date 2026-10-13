from pathlib import Path
import importlib.util
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'device/wardrive-go-supervisor.c'
spec=importlib.util.spec_from_file_location('go_supervisor_builder',ROOT/'scripts/build-go-supervisor.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


@unittest.skipUnless(shutil.which('gcc'),'Host compiler unavailable')
class GoSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=fixture_temp(prefix='go-supervisor-tests-')
        cls.binary=Path(cls.temporary.name)/'supervisor'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True,timeout=20)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def run_probe(self,mode):
        start=time.monotonic()
        result=subprocess.run([str(self.binary),'--probe',mode],capture_output=True,timeout=5)
        self.assertLess(time.monotonic()-start,3)
        self.assertFalse(result.stderr)
        self.assertIn(b'child_reaped=yes pipe_drained=yes',result.stdout)
        self.assertIn(b'descendant_containment_verified=no native_scan_verified=no',result.stdout)
        self.assertNotIn(b'SSSSS',result.stdout)
        return result

    def test_normal_child_reaped_and_output_drained_not_republished(self):
        result=self.run_probe('normal');self.assertEqual(result.returncode,0)
        self.assertIn(b'result=completed bytes=128',result.stdout)

    def test_worker_error_is_not_success(self):
        result=self.run_probe('nonzero');self.assertEqual(result.returncode,5)
        self.assertIn(b'result=worker_failed',result.stdout)

    def test_output_budget_stops_flood(self):
        result=self.run_probe('flood');self.assertEqual(result.returncode,6)
        self.assertIn(b'result=output_limit',result.stdout)
        amount=int(result.stdout.split(b'bytes=')[1].split()[0]);self.assertLessEqual(amount,65536)

    def test_deadline_term_and_kill_escalation(self):
        for mode in ('hang','ignore-term','late-output'):
            with self.subTest(mode=mode):
                result=self.run_probe(mode);self.assertEqual(result.returncode,3)
                self.assertIn(b'result=timeout',result.stdout)

    def test_signal_cancellation_reaps_child_without_success(self):
        for signum in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
            with self.subTest(signum=signum):
                process=subprocess.Popen([str(self.binary),'--probe','ignore-term'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                try:
                    time.sleep(0.1);process.send_signal(signum)
                    out,err=process.communicate(timeout=4)
                    self.assertEqual(process.returncode,7);self.assertFalse(err)
                    self.assertIn(b'result=cancelled',out);self.assertIn(b'child_reaped=yes pipe_drained=yes',out)
                finally:
                    if process.poll() is None:process.kill();process.communicate(timeout=3)

    def test_arbitrary_command_and_scan_arguments_refuse(self):
        for args in ([],['--scan'],['--probe','/usr/sbin/iw'],['--probe','normal','extra']):
            result=subprocess.run([str(self.binary),*args],capture_output=True,timeout=3)
            self.assertEqual(result.returncode,2);self.assertFalse(result.stdout);self.assertFalse(result.stderr)

    def test_control_eof_stop_and_malformed_frames_cancel_and_reap(self):
        for frame,code,reason in ((b'',7,b'control_closed'),(b'STOP\n',7,b'control_stop'),
                                  (b'STOP',8,b'control_refused'),(b'PRIVATE',8,b'control_refused')):
            with self.subTest(frame_length=len(frame)):
                result=subprocess.run([str(self.binary),'--probe-controlled','ignore-term'],input=frame,capture_output=True,timeout=4)
                self.assertEqual(result.returncode,code);self.assertFalse(result.stderr)
                self.assertIn(b'result='+reason,result.stdout)
                self.assertIn(b'child_reaped=yes pipe_drained=yes',result.stdout)
                self.assertNotIn(b'PRIVATE',result.stdout)

    def test_control_regular_file_is_refused_before_worker(self):
        with tempfile.TemporaryFile() as file:
            file.write(b'STOP\n');file.seek(0)
            result=subprocess.run([str(self.binary),'--probe-controlled','hang'],stdin=file,capture_output=True,timeout=3)
        self.assertEqual(result.returncode,2);self.assertFalse(result.stdout);self.assertFalse(result.stderr)

    def test_fragmented_stop_frame(self):
        process=subprocess.Popen([str(self.binary),'--probe-controlled','ignore-term'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for fragment in (b'S',b'TO',b'P\n'):
                process.stdin.write(fragment);process.stdin.flush();time.sleep(0.02)
            out,err=process.communicate(timeout=3)
            self.assertEqual(process.returncode,7);self.assertFalse(err)
            self.assertIn(b'result=control_stop',out)
            self.assertIn(b'child_reaped=yes pipe_drained=yes',out)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=3)

    def test_killed_supervisor_does_not_leave_synthetic_child_running(self):
        process=subprocess.Popen([str(self.binary),'--probe','ignore-term'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        child=None
        try:
            children=Path(f'/proc/{process.pid}/task/{process.pid}/children')
            deadline=time.monotonic()+0.5
            while time.monotonic()<deadline:
                rows=children.read_text().split()
                if rows:child=int(rows[0]);break
                time.sleep(0.01)
            self.assertIsNotNone(child)
            process.kill();process.communicate(timeout=3)
            state=Path(f'/proc/{child}/stat')
            deadline=time.monotonic()+1
            while state.exists() and time.monotonic()<deadline:
                # Zombie means terminated, NOT a claim that its new parent reaped it.
                if state.read_text().rsplit(')',1)[1].split()[0]=='Z':break
                time.sleep(0.01)
            self.assertTrue(not state.exists() or state.read_text().rsplit(')',1)[1].split()[0]=='Z')
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=3)

    def test_source_has_no_radio_executor_or_private_storage_writer(self):
        source=SOURCE.read_text()
        for forbidden in ('execl(','execv(','system(','/usr/sbin/iw','fopen(','O_CREAT','mount(','setuid(','setgid('):
            self.assertNotIn(forbidden,source)


class GoSupervisorBuildTests(unittest.TestCase):
    def test_wrong_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            root=Path(temporary);archive=root/'wrong.tar';archive.write_bytes(b'wrong')
            with self.assertRaises(ValueError):builder.build(archive,root/'output')
            self.assertFalse((root/'output').exists());run.assert_not_called()
