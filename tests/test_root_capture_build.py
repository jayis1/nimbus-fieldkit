import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_build', ROOT / 'scripts/build-root-capture-stream.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class CaptureBuildTests(unittest.TestCase):
    def test_wrong_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'wrong-sdk'
            archive.write_bytes(b'not the pinned SDK')
            with patch.object(builder.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    builder.build(archive, root / 'output')
                self.assertFalse((root / 'output').exists())
                run.assert_not_called()

    def test_existing_or_symlink_output_refused_before_extraction(self):
        checks = builder.load_checks()
        with tempfile.TemporaryDirectory() as temporary, patch.object(checks, 'verify_archive'), \
                patch.object(checks, 'extract') as extract, patch.object(builder, 'load_checks', return_value=checks):
            root = Path(temporary)
            output = root / 'output'
            output.mkdir()
            (output / 'preserved').write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                builder.build(root / 'unused', output)
            alias = root / 'alias'
            alias.symlink_to(output)
            with self.assertRaises(ValueError):
                builder.build(root / 'unused', alias)
            extract.assert_not_called()
            self.assertEqual((output / 'preserved').read_bytes(), b'preserve')

    def test_device_output_refused_before_creation(self):
        checks = builder.load_checks()
        with patch.object(checks, 'verify_archive'), patch.object(builder, 'load_checks', return_value=checks):
            with self.assertRaises(ValueError):
                builder.build(Path('unused'), Path('/dev/no-nimbus-component'))

    def test_local_arm_component_matches_recorded_source_and_false_gates(self):
        base = ROOT / 'build/nimbus-root-capture-stream-v3'
        if not base.exists():
            self.skipTest('Inactive local ARM component not built')
        checks = builder.load_checks()
        manifest = json.loads((base / 'BUILD-MANIFEST.json').read_text())
        self.assertEqual(checks.audit_elf(base / 'root-capture-stream.arm'), manifest['artifact'])
        self.assertEqual(checks.digest(base / 'root-capture-stream.c'), manifest['source_sha256'])
        self.assertEqual(checks.digest(ROOT / 'device/root-capture-stream.c'), manifest['source_sha256'])
        for flag in ('fixture_build', 'hardware_validated', 'installable', 'flash_authorized'):
            self.assertIs(manifest[flag], False)
        self.assertFalse(any('NIMBUS_CAPTURE_FIXTURE' in arg for arg in manifest['compile_arguments']))
        self.assertEqual((base / 'root-capture-stream.arm').stat().st_mode & 0o777, 0o600)
        if shutil.which('qemu-arm-static'):
            # QEMU requires execute permission; do not mutate the inactive export.
            with tempfile.TemporaryDirectory() as temporary:
                executable = Path(temporary) / 'component'
                shutil.copyfile(base / 'root-capture-stream.arm', executable)
                executable.chmod(0o700)
                self.assertEqual(checks.digest(executable), manifest['artifact']['sha256'])
                result = subprocess.run(['qemu-arm-static', str(executable)],
                                        capture_output=True, timeout=10)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b'', b''))
