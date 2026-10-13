#!/usr/bin/env python3
"""Build inactive ARM stream component from a pinned local SDK. Never deploys."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def load_checks():
    spec = importlib.util.spec_from_file_location('capture_runtime_checks', ROOT / 'scripts/build-sftp-runtime.py')
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    return checks


def build(archive, output):
    checks = load_checks()
    checks.verify_archive(archive, checks.TOOLCHAIN_SHA256)
    source = ROOT / 'device/root-capture-stream.c'
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 65536:
        raise ValueError('Expected bounded first-party C source.')
    output = Path(output).absolute()
    if any(parent.is_symlink() for parent in (output, *output.parents)):
        raise ValueError('Symlink output path refused.')
    if any(parent in (Path('/dev'), Path('/proc'), Path('/sys')) for parent in output.parents):
        raise ValueError('Device/pseudo-filesystem output refused.')
    output.mkdir(mode=0o700)
    checks.extract(archive, output / 'sdk')
    sdk = output / 'sdk/armv5-eabi--musl--stable-2026.08-1'
    env = {'PATH': str(sdk / 'bin') + ':/usr/bin:/bin', 'HOME': str(output), 'LC_ALL': 'C'}
    checks.run(['sh', str(sdk / 'relocate-sdk.sh')], sdk, output / 'sdk-relocation.log', env=env)
    copied = output / 'root-capture-stream.c'
    shutil.copyfile(source, copied)
    copied.chmod(0o600)
    binary = output / 'root-capture-stream.arm'
    args = [str(sdk / 'bin/arm-buildroot-linux-musleabi-gcc'), '-std=c99', '-Os',
            '-Wall', '-Wextra', '-Werror', '-fstack-protector-strong', '-static', '-no-pie',
            '-ffile-prefix-map=' + str(output) + '=/nimbus-capture-build',
            '-Wl,-z,noexecstack,-z,relro,-z,now', str(copied), '-o', str(binary)]
    checks.run(args, output, output / 'compile.log', env=env)
    checks.run([str(sdk / 'bin/arm-buildroot-linux-musleabi-strip'), '--strip-unneeded', str(binary)],
               output, output / 'strip.log', env=env)
    artifact = checks.audit_elf(binary)
    # No-argument refusal exercises ARM startup only, not any partition or mount.
    result = subprocess.run(['qemu-arm-static', str(binary)], capture_output=True, timeout=10)
    if result.returncode != 2 or result.stdout or result.stderr:
        raise ValueError('ARM emulated no-argument refusal differs.')
    binary.chmod(0o600)
    manifest = {'schema': 'nimbus-root-capture-stream-build/v1',
                'source_sha256': checks.digest(copied), 'sdk_archive_sha256': checks.TOOLCHAIN_SHA256,
                'compile_arguments': args[1:], 'artifact': artifact,
                'fixture_build': False, 'emulated_no_argument_refusal': True,
                'hardware_validated': False, 'installable': False, 'flash_authorized': False,
                'limitations': ['Stream component only; native coordinator/transport unimplemented.',
                                'Static EXEC is not PIE/ASLR; vendor BusyBox hashing still required.',
                                'SDK trust is pinned archive consistency, not independent build reproduction.',
                                'Native stream/syscall/cancellation/old-kernel behavior untested.']}
    (output / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'NOT-RUN-ON-DEVICE.txt').write_text('Inactive component only. No live coordinator, deployment approval or firmware installation. Do not run a standalone raw capture.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        build(args.toolchain_archive, args.output)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.error('Offline build failed; retain evidence for review. No device changed.')
    print('Inactive ARM stream component built. Native lifecycle/transport qualification pending.')
