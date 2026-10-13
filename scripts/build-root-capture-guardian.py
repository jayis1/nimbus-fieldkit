#!/usr/bin/env python3
"""Build an inactive ARM guardian pinned to reviewed coordinator inputs. No deployment."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reviewed_inputs(directory):
    generator = load('guardian_worker_generator', ROOT/'scripts/prepare-root-capture-worker.py')
    directory = Path(directory).absolute()
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError('Symlink coordinator directory refused.')
    expected_worker = generator.generate((ROOT/'device/root-restoration-trial.sh').read_text()).encode()
    files = {}
    for name in ('worker.sh', 'identity.sh', 'streamer', 'SHA256SUMS'):
        path = directory/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
            raise ValueError('Expected bounded regular coordinator inputs.')
        files[name] = path.read_bytes()
    if files['worker.sh'] != expected_worker:
        raise ValueError('Worker differs from current reviewed generator.')
    if hashlib.sha256(files['identity.sh']).hexdigest() != generator.IDENTITY_HASH:
        raise ValueError('Identity input mismatch.')
    if hashlib.sha256(files['streamer']).hexdigest() != generator.STREAM_HASH:
        raise ValueError('Streamer input mismatch.')
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    expected_sums = ''.join(hashes[name]+'  '+name+'\n' for name in sorted(files) if name != 'SHA256SUMS').encode()
    if files['SHA256SUMS'] != expected_sums:
        raise ValueError('Checksum inventory mismatch.')
    return hashes


def pins_header(hashes):
    names = {'worker.sh': 'WORKER', 'identity.sh': 'IDENTITY', 'streamer': 'STREAM', 'SHA256SUMS': 'SUMS'}
    return ''.join('#define NIMBUS_'+names[name]+'_SHA "'+hashes[name]+'"\n' for name in names)


def build(archive, coordinator, output):
    checks = load('guardian_build_checks', ROOT/'scripts/build-root-capture-stream.py').load_checks()
    checks.verify_archive(archive, checks.TOOLCHAIN_SHA256)
    hashes = reviewed_inputs(coordinator)
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)) or any(p in (Path('/dev'), Path('/proc'), Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe output path.')
    sources = {}
    for name in ('root-capture-guardian.c', 'root-capture-sha256.h'):
        path = ROOT/'device'/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError('Expected bounded first-party source.')
        sources[name] = path.read_bytes()
    output.mkdir(mode=0o700)
    checks.extract(archive, output/'sdk')
    sdk = output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env = {'PATH': str(sdk/'bin')+':/usr/bin:/bin', 'HOME': str(output), 'LC_ALL': 'C'}
    checks.run(['sh', str(sdk/'relocate-sdk.sh')], sdk, output/'sdk-relocation.log', env=env)
    for name, data in sources.items():
        with (output/name).open('xb') as stream:
            stream.write(data)
        (output/name).chmod(0o600)
    (output/'guardian-pins.h').write_text(pins_header(hashes))
    binary = output/'root-capture-guardian.arm'
    args = [str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'), '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
            '-DNIMBUS_GUARDIAN_PINNED', '-fstack-protector-strong', '-static', '-no-pie',
            '-ffile-prefix-map='+str(output)+'=/nimbus-guardian-build',
            '-Wl,-z,noexecstack,-z,relro,-z,now', str(output/'root-capture-guardian.c'), '-o', str(binary)]
    checks.run(args, output, output/'compile.log', env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'), '--strip-unneeded', str(binary)], output, output/'strip.log', env=env)
    artifact = checks.audit_elf(binary)
    result = subprocess.run(['qemu-arm-static', str(binary)], capture_output=True, timeout=10)
    if (result.returncode, result.stdout, result.stderr) != (2, b'', b''):
        raise ValueError('ARM no-argument refusal differs.')
    binary.chmod(0o600)
    manifest = {'schema': 'nimbus-root-capture-guardian-build/v1', 'artifact': artifact, 'input_sha256': hashes,
                'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()},
                'sdk_archive_sha256': checks.TOOLCHAIN_SHA256, 'compile_arguments': args[1:],
                'fixed_native_entry_compiled': True, 'emulated_no_argument_refusal': True,
                'hardware_validated': False, 'installable': False, 'flash_authorized': False,
                'limitations': ['No live launcher or deployment approval; requires separately reviewed exclusive staging.',
                                'Native old-kernel sessions, signals, descriptors, resource budget and descendants unqualified.',
                                'Static non-PIE; no SIGKILL, power-loss or kernel-stall recovery guarantee.']}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output/'NOT-RUN-ON-DEVICE.txt').write_text('Inactive pinned guardian only. No live approval, staging kit or launch command. Do not run on the drive.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive', type=Path, required=True)
    parser.add_argument('--coordinator-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        build(args.toolchain_archive, args.coordinator_directory, args.output)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.error('Offline guardian build failed; retain evidence. No device changed.')
    print('Inactive pinned ARM guardian built; native staging/qualification remains pending.')
