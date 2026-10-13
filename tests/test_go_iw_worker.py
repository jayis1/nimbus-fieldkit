import fcntl
import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'device/wardrive-go-iw-worker.c'
spec=importlib.util.spec_from_file_location('go_iw_builder',ROOT/'scripts/build-go-iw-worker.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def clear_fixture_capabilities():
    # Harness processes can retain capabilities even with a non-root UID.
    # Drop them only in this owned fixture subprocess; do not weaken the worker.
    class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
    class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
    header=Header(0x20080522,0);data=(Data*2)()
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.capset(ctypes.byref(header),ctypes.byref(data))!=0:raise OSError('Fixture capability drop refused')


@unittest.skipUnless(shutil.which('gcc') and os.geteuid()!=0,'Non-root host compiler fixture required')
class FixedIwWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=fixture_temp(prefix='go-iw-worker-tests-')
        cls.root=Path(cls.temporary.name)
        cls.private=tempfile.TemporaryFile();cls.private.write(b'PRIVATE_FIXTURE_NOT_FOR_WORKER');cls.private.flush()
        cls.extra=fcntl.fcntl(cls.private.fileno(),fcntl.F_DUPFD,200)
        source=cls.root/'fake-iw.c'
        source.write_text('''#define _POSIX_C_SOURCE 200809L
#include <sys/resource.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv) {
 struct rlimit limit;
 if(argc!=2 || getenv("PRIVATE_SENTINEL") || getenv("LD_PRELOAD")) return 9;
 if(fcntl('''+str(cls.extra)+''',F_GETFD)!=-1 || errno!=EBADF) return 9;
 if(!strcmp(argv[1],"dev")) {for(;;) pause();}
 if(strcmp(argv[1],"list") || getrlimit(RLIMIT_NPROC,&limit) || limit.rlim_cur || limit.rlim_max) return 9;
 if(fork()!=-1 || errno!=EAGAIN) return 9;
 return write(1,"PRIVATE_SYNTHETIC",17)==17?0:9;
}
''')
        cls.mock=cls.root/'fake-iw';cls.binary=cls.root/'worker'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',str(source),'-o',str(cls.mock)],check=True,capture_output=True,timeout=20)
        cls.mock.chmod(0o755)
        cls.digest=hashlib.sha256(cls.mock.read_bytes()).hexdigest()
        cls.defines=['-DGO_IW_FIXTURE','-DGO_WORKER_DIAGNOSTICS','-DGO_IW_PATH="'+str(cls.mock)+'"',
                     '-DGO_IW_HASH="'+cls.digest+'"','-DGO_IW_BYTES='+str(cls.mock.stat().st_size)]
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*cls.defines,str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True,timeout=20)

    @classmethod
    def tearDownClass(cls):
        os.close(cls.extra);cls.private.close();cls.temporary.cleanup()

    def run_worker(self,*args,**kwargs):
        return subprocess.run([str(self.binary),*args],capture_output=True,timeout=5,preexec_fn=clear_fixture_capabilities,**kwargs)

    def test_fixed_worker_exec_and_nonroot_fork_limit(self):
        result=self.run_worker('--query','list')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b'result=completed bytes=17 child_reaped=yes pipe_drained=yes',result.stdout)
        self.assertNotIn(b'PRIVATE',result.stdout);self.assertFalse(result.stderr)
        self.assertIn(b'descendant_containment_verified=no native_scan_verified=no',result.stdout)

    def test_environment_and_inherited_private_descriptor_are_removed(self):
        env=os.environ.copy();env['PRIVATE_SENTINEL']='PRIVATE';env['LD_PRELOAD']=''
        result=self.run_worker('--query','list',env=env,pass_fds=(self.extra,))
        self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn(b'PRIVATE',result.stdout)

    def test_inherited_capabilities_are_refused_not_assumed_safe_from_uid(self):
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc/self/status').read_text().splitlines() if ':' in line}
        privileged=any(int(fields[name],16) for name in ('CapInh','CapPrm','CapEff'))
        result=subprocess.run([str(self.binary),'--query','list'],capture_output=True,timeout=4)
        if privileged:
            self.assertEqual(result.returncode,5)
            self.assertIn(b'Fixture worker exit=19',result.stderr)
        else:self.assertEqual(result.returncode,0)

    def test_real_exec_boundary_still_has_deadline(self):
        result=self.run_worker('--query','dev')
        self.assertEqual(result.returncode,3)
        self.assertIn(b'result=timeout bytes=0 child_reaped=yes pipe_drained=yes',result.stdout)

    def test_control_close_and_stop_cancel_fixed_worker(self):
        for frame,reason in ((b'',b'control_closed'),(b'STOP\n',b'control_stop')):
            result=self.run_worker('--query-controlled','dev',input=frame)
            self.assertEqual(result.returncode,7);self.assertIn(b'result='+reason,result.stdout)
            self.assertIn(b'child_reaped=yes pipe_drained=yes',result.stdout)

    def test_scan_arbitrary_command_and_extra_arguments_are_refused(self):
        for args in ([],['--scan'],['--query','scan'],['--query','/bin/sh'],
                     ['--query','dev','wlan1'],['--probe','normal']):
            result=self.run_worker(*args)
            self.assertEqual(result.returncode,2);self.assertFalse(result.stdout);self.assertFalse(result.stderr)

    def test_unsafe_mode_and_symlink_refuse_before_exec(self):
        self.mock.chmod(0o777)
        try:self.assertEqual(self.run_worker('--query','list').returncode,2)
        finally:self.mock.chmod(0o755)
        target=self.mock.with_name('retained-mock');self.mock.rename(target);self.mock.symlink_to(target)
        try:self.assertEqual(self.run_worker('--query','list').returncode,2)
        finally:self.mock.unlink();target.rename(self.mock)

    def test_hash_mismatch_refuses_before_exec(self):
        bad=self.root/'bad-pin';defines=[value if not value.startswith('-DGO_IW_HASH') else '-DGO_IW_HASH="'+'0'*64+'"' for value in self.defines]
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*defines,str(SOURCE),'-o',str(bad)],check=True,capture_output=True,timeout=20)
        result=subprocess.run([str(bad),'--query','list'],capture_output=True,timeout=3)
        self.assertEqual(result.returncode,2);self.assertFalse(result.stdout)


class IwWorkerPolicyTests(unittest.TestCase):
    def test_production_is_fixed_nonroot_readonly_and_not_complete_sandbox(self):
        text=SOURCE.read_text()
        self.assertIn('geteuid()==0',text);self.assertIn('getgroups(0,NULL)!=0',text)
        self.assertIn('security.capability',text);self.assertIn('fexecve(executable,arguments,environment)',text)
        self.assertIn('!strcmp(mode,"list") || !strcmp(mode,"dev")',text)
        for forbidden in ('setuid(','setgid(','system(','execl(','O_WRONLY','O_CREAT','"scan"','"monitor"'):
            self.assertNotIn(forbidden,text)

    def test_wrong_sdk_refuses_before_output_or_compiler(self):
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            root=Path(temporary);archive=root/'wrong.tar';archive.write_bytes(b'wrong')
            with self.assertRaises(ValueError):builder.build(archive,root/'output')
            self.assertFalse((root/'output').exists());run.assert_not_called()
