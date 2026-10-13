import ctypes
import importlib.util
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from fixture_support import fixture_temp

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'device/wardrive-go-framing-probe.c'
spec=importlib.util.spec_from_file_location('go_framing_control',ROOT/'scripts/wardrive-go-control.py')
control=importlib.util.module_from_spec(spec);sys.modules[spec.name]=control;spec.loader.exec_module(control)


def frame(data):return struct.pack('>I',len(data))+data


@unittest.skipUnless(shutil.which('gcc'),'Host compiler unavailable')
class NativeFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=fixture_temp(prefix='go-framing-tests-')
        root=Path(cls.temporary.name);cls.binary=root/'probe'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True,timeout=20)
        wrapper=root/'wrapper.c'
        wrapper.write_text('#include "wardrive-go-framing.h"\nstatic go_frames state;\nvoid reset(void){go_frames_init(&state);}\nint feed(const unsigned char *p,size_t n){go_frame_batch b;if(go_frames_feed(&state,p,n,&b))return -1;return (int)b.count;}\nint finish(void){return go_frames_finish(&state);}\n')
        library=root/'wrapper.so'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(ROOT/'device'),str(wrapper),'-o',str(library)],check=True,capture_output=True,timeout=20)
        cls.lib=ctypes.CDLL(str(library));cls.lib.feed.argtypes=[ctypes.c_char_p,ctypes.c_size_t];cls.lib.feed.restype=ctypes.c_int

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def run_probe(self,data):return subprocess.run([str(self.binary),'--probe-frames'],input=data,capture_output=True,timeout=4)

    def test_valid_opaque_frames_are_counted_without_payload_or_auth_claim(self):
        result=self.run_probe(frame(b'PRIVATE_FIX')+frame(b'\0opaque'))
        self.assertEqual(result.returncode,0);self.assertFalse(result.stderr)
        self.assertIn(b'frames=2 payload_bytes=18',result.stdout)
        self.assertNotIn(b'PRIVATE',result.stdout)
        self.assertIn(b'auth_verified=no native_go_verified=no',result.stdout)

    def test_bad_lengths_and_truncation_refuse(self):
        for data in (struct.pack('>I',0),struct.pack('>I',2049),b'\xff'*4,b'\0',frame(b'x')[:-1]):
            with self.subTest(length=len(data)):
                result=self.run_probe(data);self.assertEqual(result.returncode,5)
                self.assertNotIn(b'result=framed',result.stdout)

    def test_maximum_frame_and_total_frame_budget(self):
        self.assertEqual(self.run_probe(frame(b'x'*2048)).returncode,0)
        self.lib.reset()
        for _ in range(4096):self.assertEqual(self.lib.feed(frame(b'x'),5),1)
        self.assertEqual(self.lib.feed(frame(b'x'),5),-1)
        self.assertEqual(self.lib.finish(),-1)

    def test_chunk_and_batch_budgets_latch_failure(self):
        for data in (b'x'*2053,frame(b'x')*9):
            self.lib.reset();self.assertEqual(self.lib.feed(data,len(data)),-1)
            self.assertEqual(self.lib.feed(frame(b'x'),5),-1)

    def test_fragmentation_and_batch_counts_match_host_model(self):
        data=frame(b'PRIVATE')+frame(b'\0opaque')+frame(b'x'*2048)
        for chunk_size in (1,2,3,4,7,64,512,2048):
            self.lib.reset();host=control.Frames()
            for offset in range(0,len(data),chunk_size):
                chunk=data[offset:offset+chunk_size]
                self.assertEqual(self.lib.feed(chunk,len(chunk)),len(host.feed(chunk)))
            self.assertEqual(self.lib.finish(),0);host.finish()

    def test_eof_deadline_and_signal_cancel_remain_failed(self):
        for signum in (None,signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
            process=subprocess.Popen([str(self.binary),'--probe-frames'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                if signum is not None:time.sleep(0.05);process.send_signal(signum)
                # Keep stdin open while waiting: communicate() would create EOF.
                process.wait(timeout=3)
                out,err=process.communicate()
                self.assertFalse(err);self.assertEqual(process.returncode,3 if signum is None else 7)
                self.assertIn(b'result=timeout' if signum is None else b'result=cancelled',out)
            finally:
                if process.poll() is None:process.kill();process.communicate(timeout=3)

    def test_regular_file_and_unknown_actions_refused(self):
        with tempfile.TemporaryFile() as file:
            result=subprocess.run([str(self.binary),'--probe-frames'],stdin=file,capture_output=True,timeout=3)
        self.assertEqual(result.returncode,2);self.assertFalse(result.stdout)
        for args in ([],['--scan'],['--probe-frames','extra']):
            result=subprocess.run([str(self.binary),*args],capture_output=True,timeout=3)
            self.assertEqual(result.returncode,2);self.assertFalse(result.stdout)

    def test_no_network_executor_authentication_or_payload_writer(self):
        text=SOURCE.read_text()
        for forbidden in ('socket(','bind(','execv(','system(','fork(','open(','fopen(','O_CREAT'):
            self.assertNotIn(forbidden,text)
