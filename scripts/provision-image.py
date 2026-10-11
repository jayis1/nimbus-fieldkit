#!/usr/bin/env python3
"""Create private offline per-device SSH material. Never mounts or flashes."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-provisioning'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def public_key(text):
    # Deliberately one plain Ed25519 key: no key options or command directives.
    lines = text.strip().splitlines()
    if len(lines) != 1 or len(text) > 4096:
        raise ValueError('Expected exactly one Ed25519 public key.')
    parts = lines[0].split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('Only a plain ssh-ed25519 public key is accepted.')
    raw = base64.b64decode(parts[1], validate=True)
    prefix = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'
    if len(raw) != len(prefix) + 32 or not raw.startswith(prefix):
        raise ValueError('Invalid Ed25519 SSH wire key.')
    pin = 'SHA256:' + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
    return parts[0] + ' ' + parts[1] + '\n', pin


def private_path(path):
    path = Path(os.path.abspath(path))
    if path == PRIVATE or PRIVATE not in path.parents:
        raise ValueError('Provisioning must stay under .private-provisioning/.')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Provisioning paths must not traverse symlinks.')
    return path


def read_private(path, limit=65536):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('Provisioning files must be owned regular files with mode 0600.')
    if info.st_size < 1 or info.st_size > limit:
        raise ValueError('Unexpected provisioning file size.')
    return path.read_bytes()


def inspect_host(tool, path):
    result = subprocess.run([str(tool), '-y', '-f', str(path)], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('Dropbear could not validate the private host key.')
    lines = [line for line in result.stdout.decode().splitlines() if line.startswith('ssh-ed25519 ')]
    if len(lines) != 1:
        raise ValueError('Expected an Ed25519 host identity.')
    return public_key(lines[0])


def validate(directory, tool):
    directory = private_path(directory)
    info = directory.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Provisioning directory must be owned with mode 0700.')
    manifest = json.loads(read_private(directory / 'PROVISIONING.json'))
    if manifest.get('schema') != 'nimbus-private-provisioning/v1':
        raise ValueError('Unsupported provisioning manifest.')
    host = read_private(directory / 'host-ed25519')
    authorized = read_private(directory / 'authorized_keys')
    _, client_pin = public_key(authorized.decode())
    _, host_pin = inspect_host(tool, directory / 'host-ed25519')
    if manifest.get('files') != {'host-ed25519': digest(host), 'authorized_keys': digest(authorized)}:
        raise ValueError('Provisioning checksum mismatch.')
    if manifest.get('host_fingerprint') != host_pin or manifest.get('client_fingerprint') != client_pin:
        raise ValueError('Provisioning identity mismatch.')
    return manifest


def create(output, authorized_key, tool, device_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', device_id):
        raise ValueError('Use a short non-secret device label.')
    output = private_path(output)
    authorized_key = Path(authorized_key)
    key_info = authorized_key.lstat()
    if not stat.S_ISREG(key_info.st_mode) or not 1 <= key_info.st_size <= 4096:
        raise ValueError('Client public key must be a small regular file, not a device/link.')
    authorized, client_pin = public_key(authorized_key.read_text())
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(PRIVATE.stat().st_mode) != 0o700 or PRIVATE.stat().st_uid != os.getuid():
        raise ValueError('Private provisioning parent must have mode 0700.')
    # No overwrites, even of an incomplete prior attempt. Review failures privately.
    output.mkdir(mode=0o700)
    with (output / 'authorized_keys').open('x') as stream:
        stream.write(authorized)
    os.chmod(output / 'authorized_keys', 0o600)
    result = subprocess.run([str(tool), '-t', 'ed25519', '-f', str(output / 'host-ed25519')],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('Host key generation failed; preserve and inspect the private staging directory.')
    os.chmod(output / 'host-ed25519', 0o600)
    host_public, host_pin = inspect_host(tool, output / 'host-ed25519')
    manifest = {'schema': 'nimbus-private-provisioning/v1', 'device_id': device_id,
                'host_fingerprint': host_pin, 'client_fingerprint': client_pin,
                'files': {name: digest(read_private(output / name)) for name in ('host-ed25519', 'authorized_keys')},
                'flash_authorized': False, 'native_access_verified': False,
                'wifi_policy': 'Existing settings partition preserved; Wi-Fi credentials/reset behavior not provisioned here.'}
    for name, data in [('PROVISIONING.json', json.dumps(manifest, indent=2) + '\n'),
                       ('host-public.pub', host_public)]:
        with (output / name).open('x') as stream:
            stream.write(data)
        os.chmod(output / name, 0o600)
    validate(output, tool)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--authorized-key', required=True, type=Path, help='Public .pub file only')
    parser.add_argument('--dropbearkey', required=True, type=Path, help='Trusted native host Dropbear key tool')
    parser.add_argument('--device-id', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = create(args.output, args.authorized_key, args.dropbearkey.resolve(), args.device_id)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit('Provisioning failed. Inspect private staging locally; do not upload its contents.')
    print(json.dumps({key: result[key] for key in ('device_id', 'host_fingerprint', 'client_fingerprint', 'flash_authorized')}, indent=2))
