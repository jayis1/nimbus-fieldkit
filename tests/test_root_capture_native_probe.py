import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'device/root-capture-native-probe.c'
spec=importlib.util.spec_from_file_location('native_probe_builder',ROOT/'scripts/build-root-capture-native-probe.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class NativeProbeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('gcc'),'Host compiler unavailable')
    def test_host_probe_and_argument_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary=Path(temporary)/'probe'
            subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-fstack-protector-strong',str(SOURCE),'-o',str(binary)],check=True,capture_output=True)
            for args in ([],['--capture'],['--probe','extra']):
                result=subprocess.run([str(binary),*args],capture_output=True,timeout=5)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(2,b'',b''))
            for _ in range(3):
                result=subprocess.run([str(binary),'--probe'],capture_output=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stderr)
                for name in ('monotonic','self_fd_enumeration','pipe_peer_loss_poll','detached_child_session','own_child_signal_and_select','own_child_reaped'):
                    self.assertIn((name+'=PASS\n').encode(),result.stdout)
                self.assertTrue(result.stdout.endswith(b'PROBE=PASS native_capture_qualified=no\n'))

    def test_source_has_no_device_write_or_service_launch_entry(self):
        text=SOURCE.read_text()
        for forbidden in ('/dev/mmc','mount(', 'reboot(', 'socket(', 'exec(', 'execl(', 'system(', 'O_CREAT'):
            self.assertNotIn(forbidden,text)
        self.assertIn('kill(child,SIGUSR1)',text)
        self.assertIn('waitpid(child',text)

    def test_wrong_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'wrong';archive.write_bytes(b'not the SDK')
            with patch.object(builder.subprocess,'run') as run:
                with self.assertRaises(ValueError): builder.build(archive,root/'output')
                self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_preserved_arm_probe_matches_source_and_emulated_results(self):
        base=ROOT/'build/nimbus-root-capture-native-probe-v1'
        if not base.exists(): self.skipTest('Inert ARM probe not built')
        spec=importlib.util.spec_from_file_location('probe_audit',ROOT/'scripts/build-root-capture-stream.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        checks=module.load_checks();manifest=json.loads((base/'BUILD-MANIFEST.json').read_text())
        self.assertEqual(checks.audit_elf(base/'native-probe.arm'),manifest['artifact'])
        self.assertEqual(checks.digest(SOURCE),manifest['source_sha256'])
        self.assertEqual(checks.digest(base/SOURCE.name),manifest['source_sha256'])
        for flag in ('hardware_validated','capture_qualified','flash_authorized'): self.assertFalse(manifest[flag])
        self.assertEqual((base/'native-probe.arm').stat().st_mode&0o777,0o600)
        if shutil.which('qemu-arm-static'):
            with tempfile.TemporaryDirectory() as temporary:
                binary=Path(temporary)/'probe';shutil.copyfile(base/'native-probe.arm',binary);binary.chmod(0o700)
                result=subprocess.run(['qemu-arm-static',str(binary),'--probe'],capture_output=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,(base/'EMULATED-PROBE.txt').read_bytes())
