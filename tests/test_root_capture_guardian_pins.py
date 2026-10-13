import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

import test_root_capture_worker as coordinator

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guardian_builder', ROOT/'scripts/build-root-capture-guardian.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@unittest.skipUnless(shutil.which('gcc'), 'Host compiler unavailable')
class GuardianPinTests(unittest.TestCase):
    def test_first_party_file_hash_matches_padding_boundaries_and_vectors(self):
        with fixture_temp() as temporary:
            base = Path(temporary)
            source = base/'hash-test.c'
            source.write_text('#include <stdio.h>\n#include <string.h>\n#include <errno.h>\n#include <fcntl.h>\n#include <unistd.h>\n'
                              '#include "root-capture-sha256.h"\nint main(int argc,char **argv) { char hash[65]; int fd; if(argc!=2)return 2;'
                              'fd=open(argv[1],O_RDONLY);if(fd<0||sha_file(fd,hash))return 1;puts(hash);close(fd);return 0;}\n')
            binary = base/'hash-test'
            subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT/'device'),
                            str(source), '-o', str(binary)], check=True, capture_output=True)
            datafile = base/'input'
            for data in (b'', b'abc', *(bytes(range(256))*(size//256)+bytes(range(size%256)) for size in (55,56,63,64,65,127,128,10000,1048576))):
                datafile.write_bytes(data)
                result = subprocess.run([str(binary), str(datafile)], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.decode().strip(), hashlib.sha256(data).hexdigest())
            datafile.write_bytes(b'x'*1048577)
            result = subprocess.run([str(binary), str(datafile)], capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)

    def fixture(self, base):
        stage, proc, database = coordinator.CaptureWorkerTests().fixture(base)
        (stage/'worker.log').write_bytes(b'')
        (stage/'SHA256SUMS').chmod(0o600)
        hashes = {name: hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in ('worker.sh','identity.sh','streamer','SHA256SUMS')}
        (base/'guardian-pins.h').write_text(builder.pins_header(hashes))
        binary = base/'guardian-pinned-fixture'
        subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-fstack-protector-strong',
                        '-DNIMBUS_GUARDIAN_FIXTURE', '-DNIMBUS_GUARDIAN_PINNED', '-I', str(base),
                        str(ROOT/'device/root-capture-guardian.c'), '-o', str(binary)], check=True, capture_output=True)
        return stage, proc, database, binary

    def test_pinned_fixture_runs_checked_worker_and_restores(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-pinned-guardian-',dir=Path.home()/'.cache') as temporary:
            stage, _, _, binary = self.fixture(Path(temporary))
            with subprocess.Popen([str(binary),'--fixture',coordinator.TOKEN,str(stage)],stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=dict(coordinator.os.environ,SSH_CONNECTION='127.0.0.1 1234 127.0.0.1 2225')) as process:
                self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-BEGIN'))
                self.assertEqual(process.stdout.read(len(coordinator.DATA)),coordinator.DATA)
                self.assertTrue(process.stdout.readline().startswith(b'NIMBUS-ROOT-END'))
                process.stdin.write(f'NIMBUS-HOST-VERIFIED {coordinator.TOKEN} {coordinator.DIGEST}\n'.encode());process.stdin.flush()
                self.assertIn(b'NIMBUS-ROOT-RESULT',process.stdout.read())
                self.assertEqual(process.wait(timeout=10),0,process.stderr.read())
            self.assertEqual((stage/'starts').read_text(),'vendor\nssh\n')

    def test_changed_inputs_and_marker_refuse_before_claim_or_action(self):
        for name in ('worker.sh','identity.sh','streamer','SHA256SUMS','started'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='nimbus-pinned-refusal-',dir=Path.home()/'.cache') as temporary:
                stage, _, _, binary = self.fixture(Path(temporary))
                path=stage/name
                path.write_bytes(path.read_bytes()+b'changed')
                result=subprocess.run([str(binary),'--fixture',coordinator.TOKEN,str(stage)],input=b'',capture_output=True,timeout=5)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse((stage/'GUARDIAN-CLAIM').exists())
                self.assertFalse((stage/'signals').exists())
                self.assertFalse((stage/'mounts').exists())

    def test_pinned_check_is_read_only_and_refuses_used_stage(self):
        with tempfile.TemporaryDirectory(prefix='nimbus-pinned-check-',dir=Path.home()/'.cache') as temporary:
            stage, _, _, binary=self.fixture(Path(temporary))
            before={p.name:p.read_bytes() for p in stage.iterdir() if p.is_file()}
            result=subprocess.run([str(binary),'--fixture-check',coordinator.TOKEN,str(stage)],input=b'',capture_output=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(before,{p.name:p.read_bytes() for p in stage.iterdir() if p.is_file()})
            (stage/'GUARDIAN-CLAIM').write_bytes(b'prior attempt')
            result=subprocess.run([str(binary),'--fixture-check',coordinator.TOKEN,str(stage)],input=b'',capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)


class GuardianBuildTests(unittest.TestCase):
    def test_preserved_arm_guardian_matches_source_pins_and_false_gates(self):
        base=ROOT/'build/nimbus-root-capture-guardian-v3'
        if not base.exists(): self.skipTest('Inactive ARM guardian not built')
        checks=builder.load('guardian_audit_checks',ROOT/'scripts/build-root-capture-stream.py').load_checks()
        manifest=json.loads((base/'BUILD-MANIFEST.json').read_text())
        self.assertEqual(checks.audit_elf(base/'root-capture-guardian.arm'),manifest['artifact'])
        self.assertEqual(builder.reviewed_inputs(ROOT/'build/nimbus-root-capture-coordinator-v5'),manifest['input_sha256'])
        for name,digest in manifest['source_sha256'].items():
            self.assertEqual(checks.digest(base/name),digest)
            self.assertEqual(checks.digest(ROOT/'device'/name),digest)
        self.assertFalse(any('NIMBUS_GUARDIAN_FIXTURE' in arg for arg in manifest['compile_arguments']))
        for flag in ('hardware_validated','installable','flash_authorized'):
            self.assertFalse(manifest[flag])
        self.assertEqual((base/'root-capture-guardian.arm').stat().st_mode&0o777,0o600)
        if shutil.which('qemu-arm-static'):
            with tempfile.TemporaryDirectory() as temporary:
                executable=Path(temporary)/'guardian'
                shutil.copyfile(base/'root-capture-guardian.arm',executable);executable.chmod(0o700)
                for args in ([],['--supervise',coordinator.TOKEN,'/fixture-override']):
                    result=subprocess.run(['qemu-arm-static',str(executable),*args],capture_output=True,timeout=5)
                    self.assertEqual((result.returncode,result.stdout,result.stderr),(2,b'',b''))

    def test_current_coordinator_inputs_are_reviewed_not_just_manifest_assertions(self):
        base=ROOT/'build/nimbus-root-capture-coordinator-v5'
        if not base.exists(): self.skipTest('Inactive coordinator not prepared')
        hashes=builder.reviewed_inputs(base)
        self.assertEqual(set(hashes),{'worker.sh','identity.sh','streamer','SHA256SUMS'})
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'copy'
            shutil.copytree(base,output)
            (output/'worker.sh').write_bytes(b'unreviewed worker')
            with self.assertRaises(ValueError): builder.reviewed_inputs(output)

    def test_bad_sdk_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            archive=root/'wrong-sdk';archive.write_bytes(b'untrusted')
            with patch.object(builder.subprocess,'run') as run:
                with self.assertRaises(ValueError): builder.build(archive,root/'missing',root/'output')
                self.assertFalse((root/'output').exists())
                run.assert_not_called()
