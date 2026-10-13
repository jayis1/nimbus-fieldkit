#!/usr/bin/env python3
"""Build an offline ARM SFTP runtime candidate; no downloads, install or listener."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import re
import struct
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'a9dc9565dffe8640f64d863cd29a32bc4a3dbdec0566a7fc44c5d6ee767d5f39'
TOOLCHAIN_SHA256 = 'a7db571eaa0f1ba2eea9a3932e8ad64bfaf33bfb7e7b96dd09702fe3ecedcf1a'
SIGNER = '7168B983815A5EEF59A4ADFD2A3F414E736060BA'
STAGE = '/root/nimbus-sftp-candidate-v1'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_archive(path, expected):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or digest(path) != expected:
        raise ValueError('Archive is not a regular hash-matched file')


def extract(path, destination):
    destination.mkdir(mode=0o700)
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) > 200000 or sum(item.size for item in members) > 2 * 1024**3:
            raise ValueError('Archive limits exceeded')
        archive.extractall(destination, filter='data')


def patch_cross_rlimit(text):
    old = '''  { printf "%s\\n" "$as_me:${as_lineno-$LINENO}: WARNING: cross compiling: assuming no" >&5
printf "%s\\n" "$as_me: WARNING: cross compiling: assuming no" >&2;}
\t select_works_with_rlimit=no'''
    new = '''  { printf "%s\\n" "$as_me:${as_lineno-$LINENO}: WARNING: using emulated select evidence; native probe required" >&5
printf "%s\\n" "$as_me: WARNING: using emulated select evidence; native probe required" >&2;}
\t select_works_with_rlimit=yes'''
    if text.count(old) != 1:
        raise ValueError('Pinned configure cross-probe layout differs')
    return text.replace(old, new)


def audit_elf(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024**2:
        raise ValueError('Select a regular candidate up to 8 MiB')
    data = path.read_bytes()
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('Expected ELF32 little-endian version 1')
    kind, machine = struct.unpack_from('<HH', data, 16)
    phoff = struct.unpack_from('<I', data, 28)[0]
    flags = struct.unpack_from('<I', data, 36)[0]
    phsize, phcount = struct.unpack_from('<HH', data, 42)
    if kind != 2 or machine != 40 or flags >> 24 != 5:
        raise ValueError('Expected ARM EABI5 EXEC')
    if phsize != 32 or not 1 <= phcount <= 128 or phoff + phsize * phcount > len(data):
        raise ValueError('Invalid program-header bounds')
    headers = [struct.unpack_from('<8I', data, phoff + i * phsize) for i in range(phcount)]
    if any(header[0] in (2, 3) for header in headers):
        raise ValueError('Dynamic/interpreter-dependent runtime refused')
    stack = [header for header in headers if header[0] == 0x6474e551]
    if len(stack) != 1 or stack[0][6] & 1:
        raise ValueError('Missing or executable GNU_STACK')
    if not any(header[0] == 0x6474e552 for header in headers):
        raise ValueError('Missing GNU_RELRO')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'architecture': 'ARM EABI5', 'static_exec': True,
            'non_executable_stack': True, 'gnu_relro': True, 'pie': False}


def verify_config_header(header):
    def defined(name):
        return re.search(r'^#define\s+' + re.escape(name) + r'(?:\s|$)', header, re.MULTILINE) is not None
    if (not defined('SANDBOX_RLIMIT') or not defined('HAVE_RLIMIT_NPROC')
            or any(defined(name) for name in ('SANDBOX_SKIP_RLIMIT_NOFILE',
                                              'SANDBOX_SKIP_RLIMIT_FSIZE',
                                              'HAVE_POLL', 'HAVE_PPOLL', 'WITH_OPENSSL'))):
        raise ValueError('Configured sandbox/portability/library policy differs')


def check_effective_config(runtime, output):
    spec = importlib.util.spec_from_file_location(
        'sftp_profile', ROOT / 'scripts/prepare-sftp-candidate.py')
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    with tempfile.TemporaryDirectory(prefix='policy-fixture-', dir=output) as temporary:
        temporary = Path(temporary)
        key, config = temporary / 'key', temporary / 'sshd_config'
        subprocess.run(['qemu-arm-static', str(runtime / 'ssh-keygen'), '-q', '-t', 'ed25519',
                        '-N', '', '-f', str(key)], check=True, capture_output=True, timeout=20)
        config.write_text(profile.config('192.168.11.1').replace(STAGE + '/host-ed25519', str(key)))
        result = subprocess.run(['qemu-arm-static', str(runtime / 'sshd'), '-T', '-f', str(config)],
                                check=True, capture_output=True, text=True, timeout=20)
        (output / 'config-emulated.log').write_text(result.stdout + result.stderr)
        effective = {name.lower(): value for name, value in
                     (line.split(' ', 1) for line in result.stdout.splitlines())}
        expected = {'permitrootlogin': 'no', 'passwordauthentication': 'no',
                    'kbdinteractiveauthentication': 'no', 'disableforwarding': 'yes',
                    'permittty': 'no', 'permituserrc': 'no', 'allowusers': 'nimbus-files',
                    'authorizedkeysfile': '/etc/nimbus-sftp-auth/nimbus-files/authorized_keys',
                    'forcecommand': 'internal-sftp -R -d /internal',
                    'chrootdirectory': STAGE + '/jail', 'listenaddress': '192.168.11.1:2226'}
        if any(effective.get(name) != value for name, value in expected.items()):
            raise ValueError('ARM emulated effective policy differs')
        return expected


def run(args, cwd, log, env=None, timeout=300):
    with log.open('ab') as stream:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise ValueError('Build/check command failed; inspect ' + str(log))


def build(source_archive, signature, release_key, toolchain_archive, output, jobs=4):
    if not 1 <= jobs <= 8:
        raise ValueError('Jobs must be 1–8')
    verify_archive(source_archive, SOURCE_SHA256)
    verify_archive(toolchain_archive, TOOLCHAIN_SHA256)
    for path in (signature, release_key):
        if Path(path).is_symlink() or not Path(path).is_file() or Path(path).stat().st_size > 1024**2:
            raise ValueError('Select regular bounded signature/key files')
    output = Path(output).absolute()
    if any(parent.is_symlink() for parent in (output, *output.parents)):
        raise ValueError('Refusing symlink output path')
    output.mkdir(mode=0o700)  # Exclusive; failed build evidence is retained.
    gpg = output / 'gpg'
    gpg.mkdir(mode=0o700)
    run(['gpg', '--homedir', str(gpg), '--batch', '--import', str(Path(release_key).absolute())],
        output, output / 'signature.log')
    result = subprocess.run(['gpg', '--homedir', str(gpg), '--batch', '--status-fd=1', '--verify',
                             str(Path(signature).absolute()), str(Path(source_archive).absolute())],
                            capture_output=True, text=True, timeout=30)
    (output / 'signature-status.log').write_text(result.stdout + result.stderr)
    valid = [line.split() for line in result.stdout.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
    if result.returncode or not any(SIGNER in line for line in valid):
        raise ValueError('Release signature does not match the published signer')
    extract(source_archive, output / 'source')
    extract(toolchain_archive, output / 'sdk')
    source = output / 'source/openssh-10.6p1'
    sdk = output / 'sdk/armv5-eabi--musl--stable-2026.08-1'
    run(['sh', str(sdk / 'relocate-sdk.sh')], sdk, output / 'sdk-relocation.log')
    cc = sdk / 'bin/arm-buildroot-linux-musleabi-gcc'
    strip = sdk / 'bin/arm-buildroot-linux-musleabi-strip'
    env = {'PATH': str(sdk / 'bin') + ':/usr/bin:/bin', 'HOME': str(output),
           'LC_ALL': 'C', 'LANG': 'C', 'CC': str(cc),
           'CFLAGS': '-Os -fstack-protector-strong -ffile-prefix-map=' + str(output) + '=/nimbus-build',
           'LDFLAGS': '-static -no-pie -Wl,-z,noexecstack,-z,relro,-z,now',
           'ac_cv_func_poll': 'no', 'ac_cv_func_ppoll': 'no'}
    runtime = output / 'runtime'
    runtime.mkdir(mode=0o700)
    probe = runtime / 'rlimit-compat-probe'
    run([str(cc), '-Os', '-Wall', '-Wextra', '-Werror', '-fstack-protector-strong',
         '-static', '-no-pie', '-Wl,-z,noexecstack,-z,relro,-z,now',
         str(ROOT / 'device/ssh/rlimit-compat-probe.c'), '-o', str(probe)],
        output, output / 'probe-build.log')
    result = subprocess.run(['qemu-arm-static', str(probe)], capture_output=True, text=True, timeout=10)
    (output / 'probe-emulated.log').write_text(result.stdout + result.stderr)
    observation = json.loads(result.stdout)
    if (result.returncode or observation.get('select_with_nofile_zero') is not True
            or observation.get('pselect_with_nofile_zero') is not True):
        raise ValueError('Emulated select/pselect compatibility check failed')
    configure = source / 'configure'
    original = configure.read_text()
    configure.write_text(patch_cross_rlimit(original))
    (output / 'configure-cross-review.json').write_text(json.dumps({
        'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'patched_sha256': digest(configure),
        'change': 'Cross-only select result based on emulation; native evidence required',
        'native_validated': False}, indent=2) + '\n')
    args = ['sh', str(configure), '--build=x86_64-pc-linux-gnu', '--host=arm-buildroot-linux-musleabi',
            '--prefix=' + STAGE + '/runtime', '--libexecdir=' + STAGE + '/runtime',
            '--sysconfdir=' + STAGE, '--with-privsep-path=' + STAGE + '/empty',
            '--with-privsep-user=nimbus-sshd', '--with-sandbox=rlimit', '--without-pie',
            '--without-openssl', '--without-zlib', '--without-pam', '--without-libedit',
            '--without-kerberos5', '--without-selinux', '--without-security-key-builtin',
            '--disable-lastlog', '--disable-utmp', '--disable-utmpx', '--disable-wtmp', '--disable-wtmpx']
    run(args, source, output / 'configure.log', env=env)
    header = (source / 'config.h').read_text()
    verify_config_header(header)
    if 'unrecognized options' in (output / 'configure.log').read_text():
        raise ValueError('Unrecognized configure options; review before building')
    # Exercise the actual upstream fallback, not merely libc select/pselect.
    fallback_probe = runtime / 'rlimit-select-compat-probe'
    run([str(cc), '-Os', '-fstack-protector-strong', '-static', '-no-pie',
         '-Wl,-z,noexecstack,-z,relro,-z,now', '-I' + str(source), '-I' + str(source / 'openbsd-compat'),
         str(ROOT / 'device/ssh/rlimit-compat-probe.c'), str(source / 'openbsd-compat/bsd-poll.c'),
         '-o', str(fallback_probe)], output, output / 'fallback-probe-build.log')
    result = subprocess.run(['qemu-arm-static', str(fallback_probe)], capture_output=True, text=True, timeout=10)
    (output / 'fallback-probe-emulated.log').write_text(result.stdout + result.stderr)
    fallback = json.loads(result.stdout)
    if result.returncode or any(fallback.get(name) is not True for name in
                                ('select_with_nofile_zero', 'pselect_with_nofile_zero', 'poll_with_nofile_zero')):
        raise ValueError('Emulated upstream select fallback failed')
    binaries = ('sshd', 'sshd-session', 'sshd-auth', 'ssh-keygen')
    run(['make', '-j' + str(jobs), *binaries], source, output / 'make.log', env=env)
    for name in binaries:
        shutil.copyfile(source / name, runtime / name)
        run([str(strip), '--strip-unneeded', str(runtime / name)], output, output / 'strip.log')
        (runtime / name).chmod(0o700)
    probe.chmod(0o700)
    fallback_probe.chmod(0o700)
    artifacts = {name: audit_elf(runtime / name) for name in
                 (*binaries, 'rlimit-compat-probe', 'rlimit-select-compat-probe')}
    result = subprocess.run(['qemu-arm-static', str(runtime / 'sshd'), '-V'],
                            capture_output=True, text=True, timeout=10)
    version = result.stdout + result.stderr
    (output / 'version-emulated.log').write_text(version)
    if result.returncode or 'OpenSSH_10.6' not in version:
        raise ValueError('Emulated sshd version check failed')
    effective = check_effective_config(runtime, output)
    manifest = {'schema': 'nimbus-sftp-runtime-build/v1', 'version': 'OpenSSH 10.6p1',
                'source_sha256': SOURCE_SHA256, 'toolchain_sha256': TOOLCHAIN_SHA256,
                'release_signer': SIGNER, 'signature_verified': True,
                'signer_trust': 'Upstream HTTPS-published fingerprint, not independent out-of-band verification',
                'sandbox': 'rlimit with all three resource limits; weaker than seccomp',
                'io_backend': 'Upstream select/pselect portability implementation',
                'cross_select_evidence': 'ARM emulation only; native probe required',
                'configure_arguments': args[2:], 'artifacts': artifacts,
                'emulated_effective_policy': effective,
                'upstream_io_fallback_emulated': fallback,
                'probe_source_sha256': digest(ROOT / 'device/ssh/rlimit-compat-probe.c'),
                'builder_source_sha256': digest(Path(__file__)),
                'hardware_validated': False, 'installable': False,
                'limitations': ['Static EXEC is not PIE/ASLR', 'No OpenSSL: restricted algorithms',
                                'Old-kernel/native auth, privilege separation, jail and USB lifecycle untested',
                                'No device keys/accounts/configuration/service or mount changes performed']}
    (output / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (runtime / 'NOT-INSTALLABLE.txt').write_text('Offline ARM candidate only. Native runtime, account/jail, pairing and USB lifecycle gates remain blocked. No installer or listener supplied.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-archive', 'signature', 'release-key', 'toolchain-archive', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    try:
        build(args.source_archive, args.signature, args.release_key, args.toolchain_archive, args.output, args.jobs)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print('Offline ARM runtime built. Native validation pending; no device changed.')
