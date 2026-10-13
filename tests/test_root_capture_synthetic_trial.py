import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('synthetic_builder',ROOT/'scripts/build-root-capture-synthetic-trial.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
TOKEN='b'*64


@unittest.skipUnless(shutil.which('gcc'),'Host compiler unavailable')
class SyntheticGuardianTests(unittest.TestCase):
    def fixture(self,base):
        stage=base/'stage';stage.mkdir(mode=0o700)
        files=builder.synthetic_inputs()
        for name,data in files.items():
            path=stage/name;path.write_bytes(data);path.chmod(0o700 if name=='streamer' else 0o600)
        (stage/'started').write_text(TOKEN+'\n');(stage/'started').chmod(0o600)
        (stage/'worker.log').write_bytes(b'');(stage/'worker.log').chmod(0o600)
        guard=builder.load('synthetic_pins',ROOT/'scripts/build-root-capture-guardian.py')
        (base/'guardian-pins.h').write_text(guard.pins_header({name:hashlib.sha256(data).hexdigest() for name,data in files.items()}))
        binary=base/'guardian'
        subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNIMBUS_GUARDIAN_PINNED','-DNIMBUS_GUARDIAN_FIXTURE',
                        '-I',str(base),str(ROOT/'device/root-capture-guardian.c'),'-o',str(binary)],check=True,capture_output=True)
        return stage,binary

    def test_positive_control_is_synthetic_not_root_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,binary=self.fixture(Path(temporary))
            with subprocess.Popen([str(binary),'--fixture',TOKEN,str(stage)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
                self.assertEqual(process.stdout.readline(),f'SYNTHETIC-READY {TOKEN} no-real-reader\n'.encode())
                process.stdin.write(f'SYNTHETIC-ACK {TOKEN}\n'.encode());process.stdin.flush()
                data=process.stdout.read()
                self.assertEqual(process.wait(timeout=5),0,process.stderr.read())
                self.assertEqual(data,f'SYNTHETIC-DONE {TOKEN} no-capture\n'.encode())
            self.assertIn('completed=yes real_reader_started=no',(stage/'SYNTHETIC-RESULT').read_text())
            self.assertIn('invalidated=no',(stage/'GUARDIAN-RESULT').read_text())
            self.assertFalse((stage/'GUARDIAN-INVALID').exists())

    def test_output_loss_cancels_only_fake_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,binary=self.fixture(Path(temporary))
            with subprocess.Popen([str(binary),'--fixture',TOKEN,str(stage)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
                self.assertTrue(process.stdout.readline().startswith(b'SYNTHETIC-READY'))
                process.stdout.close()
                self.assertNotEqual(process.wait(timeout=5),0)
            self.assertEqual((stage/'GUARDIAN-INVALID').read_text(),TOKEN)
            self.assertIn('completed=no real_reader_started=no',(stage/'SYNTHETIC-RESULT').read_text())
            self.assertIn('invalidated=yes',(stage/'GUARDIAN-RESULT').read_text())

    def test_waiter_loss_preserves_owner_until_synthetic_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,binary=self.fixture(Path(temporary))
            runner=r'''
import ctypes,os,pathlib,subprocess,sys,time
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
binary,stage,token=sys.argv[1:]
with subprocess.Popen([binary,'--fixture',token,stage],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
 assert process.stdout.readline().startswith(b'SYNTHETIC-READY')
 children=pathlib.Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
 assert len(children)==1
 owner=int(children[0]);assert os.getsid(owner)==owner
 process.kill();process.wait(timeout=5)
 assert pathlib.Path(f'/proc/{owner}/exe').resolve()==pathlib.Path(binary)
 process.stdout.close();process.stdin.close()
 deadline=time.monotonic()+5
 while True:
  ended,status=os.waitpid(owner,os.WNOHANG)
  if ended:
   assert os.WIFEXITED(status) and os.WEXITSTATUS(status)!=0
   break
  assert time.monotonic()<deadline
  time.sleep(0.01)
assert 'completed=no real_reader_started=no' in pathlib.Path(stage,'SYNTHETIC-RESULT').read_text()
assert 'invalidated=yes' in pathlib.Path(stage,'GUARDIAN-RESULT').read_text()
'''
            result=subprocess.run([sys.executable,'-c',runner,str(binary),str(stage),TOKEN],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)


class SyntheticBoundaryTests(unittest.TestCase):
    def test_worker_has_no_external_command_or_device_access(self):
        text='\n'.join(line for line in builder.synthetic_inputs()['worker.sh'].decode().splitlines() if not line.lstrip().startswith('#'))
        for forbidden in ('/dev/','/proc/','/root/','/nimbus/','mount ','dd ','kill ','exec ','sh -','$('):
            self.assertNotIn(forbidden,text)
        self.assertNotIn('NIMBUS-ROOT-',text)
        self.assertIn('real_reader_started=no',text)

    def test_bad_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'wrong';archive.write_bytes(b'not a SDK')
            with patch.object(builder.subprocess,'run') as run:
                with self.assertRaises(ValueError):builder.build(archive,root/'output')
                self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_preserved_bundle_exactly_contains_inert_pinned_inputs(self):
        base=ROOT/'build/nimbus-guardian-synthetic-trial-v1'
        if not base.exists():self.skipTest('Synthetic bundle not built')
        manifest=json.loads((base/'BUILD-MANIFEST.json').read_text())
        checks=builder.load('synthetic_checks',ROOT/'scripts/build-root-capture-stream.py').load_checks()
        self.assertEqual(checks.audit_elf(base/'synthetic-guardian.arm'),manifest['artifact'])
        self.assertEqual(checks.digest(base/'synthetic-trial.tar.gz'),manifest['bundle_sha256'])
        with tarfile.open(base/'synthetic-trial.tar.gz') as archive:
            self.assertEqual(set(archive.getnames()),{'guardian','worker.sh','identity.sh','streamer','SHA256SUMS','started','worker.log'})
            for member in archive:
                self.assertTrue(member.isfile());self.assertEqual(member.uid,0);self.assertEqual(member.gid,0)
                self.assertEqual(member.mode,0o700 if member.name in ('guardian','streamer') else 0o600)
                self.assertEqual(hashlib.sha256(archive.extractfile(member).read()).hexdigest(),manifest['files'][member.name])
            for name,data in builder.synthetic_inputs().items():self.assertEqual(archive.extractfile(name).read(),data)
        for flag in ('hardware_validated','real_capture_worker_included','capture_qualified','flash_authorized'):self.assertFalse(manifest[flag])
        for name,digest in manifest['source_sha256'].items():
            self.assertEqual(checks.digest(ROOT/'device'/name),digest)
        self.assertEqual((base/'synthetic-guardian.arm').stat().st_mode&0o777,0o600)
