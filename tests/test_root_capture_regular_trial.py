import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('regular_builder',ROOT/'scripts/build-root-capture-regular-trial.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
TOKEN='c'*64


@unittest.skipUnless(shutil.which('gcc') and Path('/usr/bin/sha256sum').is_file(),'Host compiler/hasher unavailable')
class RegularPipelineTests(unittest.TestCase):
    def fixture(self,base,hasher_hash=None,hasher_metadata=None):
        stage=base/'stage';stage.mkdir(mode=0o700)
        files=builder.fixture_files()
        # Host-only pin substitution; ARM uses the owner's vendor executable.
        native_hash=hashlib.sha256(Path('/usr/bin/sha256sum').read_bytes()).hexdigest()
        st=Path('/usr/bin/sha256sum').stat()
        metadata=f'{st.st_uid}:{st.st_gid}:{st.st_mode&0o777:o}:{st.st_size}'
        files['worker.sh']=files['worker.sh'].replace(builder.HASHER_SHA.encode(),(hasher_hash or native_hash).encode()).replace(
            builder.HASHER_METADATA.encode(),(hasher_metadata or metadata).encode())
        files['fixture-hasher']=b'#!/bin/sh\nexec /usr/bin/sha256sum\n'
        for name,data in files.items():
            path=stage/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            path.write_bytes(data);path.chmod(0o700 if name=='fixture-hasher' else 0o600)
        streamer=stage/'streamer'
        subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNIMBUS_CAPTURE_FIXTURE',
                        '-DNIMBUS_FIXTURE_HASHER="'+str(stage/'fixture-hasher')+'"',str(ROOT/'device/root-capture-stream.c'),'-o',str(streamer)],check=True,capture_output=True)
        streamer.chmod(0o700);files['streamer']=streamer.read_bytes()
        sums=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items()))
        (stage/'SHA256SUMS').write_text(sums);(stage/'SHA256SUMS').chmod(0o600)
        files['SHA256SUMS']=sums.encode()
        guard=builder.load('regular_host_pins',ROOT/'scripts/build-root-capture-guardian.py')
        (base/'guardian-pins.h').write_text(guard.pins_header({name:hashlib.sha256(files[name]).hexdigest() for name in ('worker.sh','identity.sh','streamer','SHA256SUMS')}))
        binary=base/'guardian'
        subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNIMBUS_GUARDIAN_FIXTURE','-DNIMBUS_GUARDIAN_PINNED',
                        '-I',str(base),str(ROOT/'device/root-capture-guardian.c'),'-o',str(binary)],check=True,capture_output=True)
        for name,data in (('started',(TOKEN+'\n').encode()),('worker.log',b'')):
            (stage/name).write_bytes(data);(stage/name).chmod(0o600)
        return stage,binary

    def test_positive_native_code_pipeline_hashes_fake_bytes_and_drains(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,binary=self.fixture(Path(temporary))
            with subprocess.Popen([str(binary),'--fixture',TOKEN,str(stage)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
                stdout=process.stdout.read()
                self.assertEqual(process.wait(timeout=10),0,process.stderr.read())
            self.assertIn(b'REGULAR-TRIAL=PASS reader-closed hasher-drained synthetic-only native_capture_qualified=no',stdout)
            wire=(stage/'SYNTHETIC-WIRE').read_bytes();digest=hashlib.sha256(builder.DATA).hexdigest()
            self.assertEqual(wire,f'NIMBUS-ROOT-BEGIN {TOKEN} 262144 179:2 ro\n'.encode()+builder.DATA+
                             f'NIMBUS-ROOT-END {TOKEN} {digest}\n'.encode())
            self.assertEqual((stage/'CHILD-DRAIN').read_text(),f'NIMBUS-CHILD-DRAIN {TOKEN} reader-closed hasher-drained\n')
            self.assertIn('helper_status=0 synthetic-only host_readback_verified=no',(stage/'REGULAR-RESULT').read_text())
            self.assertIn('invalidated=no worker_exited=yes',(stage/'GUARDIAN-RESULT').read_text())

    def test_changed_or_symlink_fixture_refuses_before_reader(self):
        for symlink in (False,True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                stage,binary=self.fixture(Path(temporary))
                target=stage/'fixture/dev/mmcblk0p2'
                if symlink:
                    target.unlink();target.symlink_to('/dev/null')
                else:target.write_bytes(b'changed fake data')
                with subprocess.Popen([str(binary),'--fixture',TOKEN,str(stage)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
                    stdout=process.stdout.read()
                    self.assertNotEqual(process.wait(timeout=5),0)
                self.assertNotIn(b'REGULAR-TRIAL=PASS',stdout)
                self.assertFalse((stage/'CHILD-DRAIN').exists());self.assertFalse((stage/'SYNTHETIC-WIRE').exists())

    def test_wrong_standalone_hasher_pin_or_metadata_refuses_before_reader(self):
        for params in ({'hasher_hash':'0'*64},{'hasher_metadata':'0:0:755:1'}):
            with self.subTest(params=params), tempfile.TemporaryDirectory() as temporary:
                stage,binary=self.fixture(Path(temporary),**params)
                with subprocess.Popen([str(binary),'--fixture',TOKEN,str(stage)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
                    stdout=process.stdout.read()
                    self.assertNotEqual(process.wait(timeout=5),0)
                self.assertNotIn(b'REGULAR-TRIAL=PASS',stdout)
                self.assertFalse((stage/'CHILD-DRAIN').exists());self.assertFalse((stage/'SYNTHETIC-WIRE').exists())


class RegularBundleTests(unittest.TestCase):
    def test_bad_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'wrong';archive.write_bytes(b'untrusted')
            with patch.object(builder.subprocess,'run') as run:
                with self.assertRaises(ValueError):builder.build(archive,root/'output')
                self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_worker_has_no_mount_service_or_device_reader_entry(self):
        text='\n'.join(line for line in builder.fixture_files()['worker.sh'].decode().splitlines() if not line.lstrip().startswith('#'))
        for forbidden in (' /dev/mmc','/etc/rc','/root/','mount ','reboot','kill ','--supervise'):
            self.assertNotIn(forbidden,text)
        self.assertIn('--stream-evidence',text)
        self.assertIn('host_readback_verified=no',text)

    def test_preserved_bundle_contains_regular_fixture_only_and_pinned_artifacts(self):
        base=ROOT/'build/nimbus-reader-regular-trial-v2'
        if not base.exists():self.skipTest('Regular trial not built')
        manifest=json.loads((base/'BUILD-MANIFEST.json').read_text())
        checks=builder.load('regular_audit',ROOT/'scripts/build-root-capture-stream.py').load_checks()
        self.assertEqual(checks.digest(base/'regular-trial.tar.gz'),manifest['bundle_sha256'])
        self.assertEqual(checks.audit_elf(base/'fixture-streamer.arm'),manifest['streamer'])
        self.assertEqual(checks.audit_elf(base/'regular-guardian.arm'),manifest['guardian'])
        self.assertIn('-DNIMBUS_CAPTURE_FIXTURE',manifest['stream_compile_arguments'])
        self.assertIn('-DNIMBUS_GUARDIAN_FIXTURE',manifest['guard_compile_arguments'])
        with tarfile.open(base/'regular-trial.tar.gz') as archive:
            files={member.name for member in archive if member.isfile()}
            self.assertEqual(files,set(manifest['files']))
            for member in archive:
                self.assertTrue(member.isfile() or member.isdir());self.assertFalse(member.name.startswith('/'))
                self.assertNotIn('..',Path(member.name).parts)
                if member.isfile():self.assertEqual(hashlib.sha256(archive.extractfile(member).read()).hexdigest(),manifest['files'][member.name])
            self.assertEqual(archive.extractfile('fixture/dev/mmcblk0p2').read(),builder.DATA)
            for name,data in builder.fixture_files().items():self.assertEqual(archive.extractfile(name).read(),data)
        for flag in ('hardware_validated','capture_qualified','flash_authorized','real_capture_worker_included'):self.assertFalse(manifest[flag])
