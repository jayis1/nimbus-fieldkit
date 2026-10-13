import hashlib
import importlib.util
import io
import json
from pathlib import Path
import resource
import shutil
import struct
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sftp_runtime', ROOT / 'scripts/build-sftp-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def elf(stack_flags=6, extra_type=None):
    headers = [(1, 0, 0x8000, 0x8000, 148, 148, 5, 4),
               (0x6474e551, 0, 0, 0, 0, 0, stack_flags, 4),
               (0x6474e552, 0, 0x8000, 0x8000, 0, 0, 4, 4)]
    if extra_type is not None:
        headers.append((extra_type, 0, 0, 0, 0, 0, 4, 4))
    data = bytearray(52)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHI', data, 16, 2, 40, 1)
    struct.pack_into('<I', data, 28, 52)
    struct.pack_into('<I', data, 36, 0x05000000)
    struct.pack_into('<HHH', data, 40, 52, 32, len(headers))
    return bytes(data) + b''.join(struct.pack('<8I', *header) for header in headers)


class SFTPRuntimeTests(unittest.TestCase):
    def test_arm_static_metadata_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture'
            path.write_bytes(elf())
            report = runtime.audit_elf(path)
            self.assertTrue(report['static_exec'])
            self.assertTrue(report['non_executable_stack'])
            self.assertEqual(report['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_dynamic_exec_stack_wrong_arch_and_header_bounds_refused(self):
        bad_arch = bytearray(elf())
        struct.pack_into('<H', bad_arch, 18, 62)
        bad_bounds = bytearray(elf())
        struct.pack_into('<I', bad_bounds, 28, 10000)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture'
            for data in (elf(stack_flags=7), elf(extra_type=2), elf(extra_type=3),
                         bad_arch, bad_bounds, b'not ELF'):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    runtime.audit_elf(path)

    def test_symlink_candidate_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'fixture').write_bytes(elf())
            (root / 'alias').symlink_to(root / 'fixture')
            with self.assertRaises(ValueError):
                runtime.audit_elf(root / 'alias')

    def test_archive_hash_and_symlink_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'archive'
            path.write_bytes(b'fixture archive')
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            runtime.verify_archive(path, checksum)
            with self.assertRaises(ValueError):
                runtime.verify_archive(path, '0' * 64)
            alias = root / 'alias'
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                runtime.verify_archive(alias, checksum)

    def test_bad_inputs_fail_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runtime.subprocess, 'run') as run:
            root = Path(temporary)
            path = root / 'archive'
            path.write_bytes(b'wrong archive')
            with self.assertRaises(ValueError):
                runtime.build(path, path, path, path, root / 'output')
            self.assertFalse((root / 'output').exists())
            run.assert_not_called()

    def test_tar_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'archive.tar'
            with tarfile.open(archive, 'w') as stream:
                info = tarfile.TarInfo('../escape')
                info.size = 1
                stream.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(tarfile.TarError):
                runtime.extract(archive, root / 'extracted')
            self.assertFalse((root / 'escape').exists())

    def test_existing_and_symlink_output_refused_without_commands(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runtime, 'verify_archive'), \
                patch.object(runtime.subprocess, 'run') as run:
            root = Path(temporary)
            metadata = root / 'metadata'
            metadata.write_bytes(b'fixture')
            output = root / 'output'
            output.mkdir()
            (output / 'preserved').write_bytes(b'never overwrite')
            with self.assertRaises(FileExistsError):
                runtime.build(metadata, metadata, metadata, metadata, output)
            alias = root / 'alias'
            alias.symlink_to(output)
            with self.assertRaises(ValueError):
                runtime.build(metadata, metadata, metadata, metadata, alias)
            self.assertEqual((output / 'preserved').read_bytes(), b'never overwrite')
            run.assert_not_called()

    def test_wrong_signature_stops_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runtime, 'verify_archive'), \
                patch.object(runtime, 'extract') as extract, patch.object(runtime.subprocess, 'run') as run:
            root = Path(temporary)
            metadata = root / 'metadata'
            metadata.write_bytes(b'fixture')
            run.return_value = subprocess.CompletedProcess([], 0, '[GNUPG:] VALIDSIG wrong-signer\n', '')
            with self.assertRaises(ValueError):
                runtime.build(metadata, metadata, metadata, metadata, root / 'output')
            extract.assert_not_called()
            self.assertFalse((root / 'output/BUILD-MANIFEST.json').exists())

    def test_all_resource_limits_required_and_poll_fallback_enforced(self):
        header = '#define SANDBOX_RLIMIT 1\n#define HAVE_RLIMIT_NPROC /**/\n'
        runtime.verify_config_header(header)
        for name in ('SANDBOX_SKIP_RLIMIT_NOFILE', 'SANDBOX_SKIP_RLIMIT_FSIZE',
                     'HAVE_POLL', 'HAVE_PPOLL', 'WITH_OPENSSL'):
            with self.assertRaises(ValueError):
                runtime.verify_config_header(header + '#define ' + name + ' 1\n')
        with self.assertRaises(ValueError):
            runtime.verify_config_header('#define SANDBOX_RLIMIT 1\n')

    def test_cross_probe_patch_is_exact_and_explicitly_unqualified(self):
        fragment = '''  { printf "%s\\n" "$as_me:${as_lineno-$LINENO}: WARNING: cross compiling: assuming no" >&5
printf "%s\\n" "$as_me: WARNING: cross compiling: assuming no" >&2;}
\t select_works_with_rlimit=no'''
        updated = runtime.patch_cross_rlimit(fragment)
        self.assertIn('native probe required', updated)
        self.assertIn('select_works_with_rlimit=yes', updated)
        for text in ('changed upstream code', fragment + fragment):
            with self.assertRaises(ValueError):
                runtime.patch_cross_rlimit(text)

    @unittest.skipUnless(shutil.which('gcc'), 'Host C compiler unavailable')
    def test_probe_limits_only_its_child_and_refuses_arguments(self):
        before = {name: resource.getrlimit(name) for name in
                  (resource.RLIMIT_NOFILE, resource.RLIMIT_NPROC, resource.RLIMIT_FSIZE)}
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'probe'
            subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'device/ssh/rlimit-compat-probe.c'), '-o', str(binary)],
                           check=True, capture_output=True, timeout=10)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['select_with_nofile_zero'])
            self.assertTrue(report['pselect_with_nofile_zero'])
            self.assertEqual(report['scope'], 'process_compatibility_only')
            result = subprocess.run([str(binary), '--start'], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
        self.assertEqual(before, {name: resource.getrlimit(name) for name in before})
