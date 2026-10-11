#!/usr/bin/env python3
"""Offline rootfs candidate builder. Never creates a vendor update or flashes."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
STOCK_HASH = '4dd2907ec920443855b221b1f67c5086e369b84861fb0a486d74da2c7671b203'
SSH_HASH = '1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c'
STAMP = 1767225600


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_members(members):
    names = set()
    symlinks = set()
    regular = set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not path.parts or member.name in names:
            raise ValueError('Unsafe or duplicate archive path: ' + member.name)
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError('Unsupported archive node: ' + member.name)
        names.add(member.name)
        if member.issym():
            symlinks.add(member.name)
        if member.isfile():
            regular.add(member.name)
    for member in members:
        if any(str(parent) in symlinks for parent in PurePosixPath(member.name).parents):
            raise ValueError('Archive writes through a symlink: ' + member.name)
        if member.islnk() and member.linkname not in regular:
            raise ValueError('Hardlink must reference a contained regular file.')


def write(root, name, data, mode=0o644):
    path = root / name
    if any(parent.is_symlink() for parent in path.parents if parent != root.parent):
        raise ValueError('Overlay would traverse a symlink: ' + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Overlay destination is a symlink: ' + name)
    # Replace instead of mutating vendor hardlinked files.
    temporary = path.with_name(path.name + '.nimbus-new')
    with temporary.open('xb') as stream:
        stream.write(data)
    os.chmod(temporary, mode)
    os.chown(temporary, 0, 0)
    os.utime(temporary, (STAMP, STAMP))
    os.replace(temporary, path)


def build(args):
    if digest(args.stock_rootfs) != STOCK_HASH:
        raise ValueError('Vendor rootfs hash does not match reviewed 3.04 input.')
    if digest(args.ssh_binary) != SSH_HASH:
        raise ValueError('SSH binary is not the tested interface-fail-closed candidate.')
    output = args.output.resolve()
    if str(output).startswith('/dev/'):
        raise ValueError('Refusing device output.')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    root = output / 'rootfs-tree'
    root.mkdir()
    with tarfile.open(args.stock_rootfs) as archive:
        members = archive.getmembers()
        validate_members(members)
        # Pinned vendor archive; validated no write paths under symlinks.
        archive.extractall(root, members=members, filter='fully_trusted')
        stock_page = archive.extractfile('nimbus/data/index.html').read()
    removed = []
    for path in (root / 'etc/ssh').glob('ssh_host_*'):
        if path.is_file() or path.is_symlink():
            removed.append(str(path.relative_to(root)))
            path.unlink()
    for name in ('etc/shadow', 'etc/shadow-'):
        path = root / name
        if path.exists():
            lines = path.read_text().splitlines()
            for i, line in enumerate(lines):
                fields = line.split(':')
                if fields[0] == 'root':
                    fields[1] = '!'
                    lines[i] = ':'.join(fields)
            write(root, name, ('\n'.join(lines) + '\n').encode(), 0o600)
    # Build UI from the clean vendor page, not from private live-rootfs dumps.
    web = output / 'stock-web-input.tar'
    with tarfile.open(web, 'w') as archive:
        member = tarfile.TarInfo('data/index.html')
        member.size = len(stock_page)
        archive.addfile(member, io.BytesIO(stock_page))
    spec = importlib.util.spec_from_file_location('unified_candidate', ROOT / 'scripts/build-unified-dashboard.py')
    unified = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(unified)
    ui = output / 'unified-source.tar'
    unified.build(web, ui, ROOT / 'build/nimbus-unified-v05.tar')
    with tarfile.open(ui) as archive:
        for member in archive:
            if member.isfile() and (member.name == 'index.html' or member.name.startswith('fieldkit-v06/')):
                write(root, 'nimbus/data/' + member.name, archive.extractfile(member).read())
    for name, source in unified.native.SOURCES.items():
        # No standalone dashboard entry point in the image.
        if name.startswith('dashboard/') and name != 'dashboard/snapshot.awk':
            continue
        write(root, 'opt/nimbus/native/' + name, (ROOT / source).read_bytes(), 0o755 if name.endswith('.sh') else 0o644)
    for name in ('UNIFIED-DASHBOARD.md', 'GAMEHACK-OPTIONAL-ENHANCEMENTS.md', 'SECURITY-PLAN.md'):
        write(root, 'opt/nimbus/native/docs/' + name, (ROOT / 'docs' / name).read_bytes())
    for name in ('nimbus-sd-doctor.sh', 'retire-v04-homepage.sh'):
        write(root, 'opt/nimbus/' + name, (ROOT / 'device' / name).read_bytes(), 0o755)
    write(root, 'opt/nimbus/dropbearmulti', args.ssh_binary.read_bytes(), 0o700)
    write(root, 'opt/nimbus/image-start.sh', (ROOT / 'device/image-start.sh').read_bytes(), 0o700)
    keys = root / 'etc/nimbus'
    keys.mkdir(mode=0o700)
    write(root, 'etc/nimbus/PROVISIONING.txt', b'No keys included. Provision a unique Ed25519 host key and authorized_keys securely before any boot. Do not flash this candidate.\n', 0o600)
    conf = (root / 'etc/inetd.conf').read_text()
    lines = ['# NIMBUS-TELNET-OFF ' + line if line.split() and line.split()[0] == 'telnet' else line for line in conf.splitlines()]
    write(root, 'etc/inetd.conf', ('\n'.join(lines) + '\n').encode())
    rc = (root / 'etc/rc.d/rc.local').read_bytes()
    write(root, 'etc/rc.d/rc.local', rc + b'\n# NIMBUS-CUSTOM-IMAGE\nif [ "$1" = start ]; then\n    /bin/sh /opt/nimbus/image-start.sh\nfi\n', 0o755)
    # Existing per-device settings partition is not included. First-use AP mode
    # remains a provisioning gate; do not copy credentials or calibration here.
    defaults = root / 'opt/qsi/config/platform_default'
    text = defaults.read_text()
    text = '\n'.join('CFG_WIFI_AP_MODE=wpa2aes' if line.startswith('CFG_WIFI_AP_MODE=') else line for line in text.splitlines()) + '\n'
    write(root, str(defaults.relative_to(root)), text.encode())
    once = root / 'etc/rc.d/init.d/once/wifiap_passwd'
    text = once.read_text().replace('$CMD_SET_CFG_WIFI_AP_MODE "open"', '$CMD_SET_CFG_WIFI_AP_MODE "wpa2aes"')
    write(root, str(once.relative_to(root)), text.encode(), 0o755)
    # Attach new handheld features as a separate source bundle, not executable
    # ARM64/Python applications placed on the ARMv7 SanDisk.
    companion = ROOT / 'build/gamehack-nimbus-library-staged-v1.tar'
    if not companion.is_file():
        raise ValueError('Build the staged GameHack source bundle first.')
    shutil.copyfile(companion, output / companion.name)
    for script in ('opt/nimbus/image-start.sh', 'etc/rc.d/rc.local'):
        subprocess.run(['sh', '-n', str(root / script)], check=True)
    root_tar = output / 'rootfs.tar'
    with tarfile.open(root_tar, 'w', format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(root.rglob('*')):
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    image = output / 'rootfs.ext3.candidate'
    with image.open('xb') as stream:
        stream.truncate(256 * 1024 * 1024)
    env = os.environ.copy()
    env['E2FSPROGS_FAKE_TIME'] = str(STAMP)
    with (output / 'mkfs.log').open('w') as log:
        subprocess.run(['mke2fs', '-t', 'ext3', '-b', '1024', '-I', '128',
                        '-O', 'none,has_journal,filetype,sparse_super,large_file',
                        '-m', '1', '-U', 'fc051111-2222-4333-8444-555555555555',
                        '-E', 'lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0',
                        '-d', str(root), '-F', str(image)], check=True, env=env, stdout=log, stderr=subprocess.STDOUT)
    with (output / 'fsck-readonly.log').open('w') as log:
        subprocess.run(['e2fsck', '-f', '-n', str(image)], check=True, stdout=log, stderr=subprocess.STDOUT)
    manifest = {'schema': 'nimbus-custom-rootfs/v1', 'flash_ready': False,
                'boot_tested': False, 'recovery_tested': False, 'vendor_update_container': False,
                'stock_rootfs_sha256': STOCK_HASH, 'ssh_sha256': SSH_HASH,
                'image_bytes': image.stat().st_size, 'removed_vendor_host_keys': removed,
                'credentials': 'No personal keys/passwords/settings/backups imported; stock vendor accounts otherwise remain.',
                'preserved': ['vendor kernel/modules', 'bootloader/rescue external to this image', 'partition layout external to this image', 'stock web handlers'],
                'blocked': ['secure offline provisioning', 'recovery/restoration', 'native boot', 'SD write validation', 'GameHack downstream SSH access'],
                'artifacts': {p.name: digest(p) for p in (image, root_tar, output / companion.name, ui)}}
    (output / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'NOT-FLASHABLE.txt').write_text('OFFLINE CANDIDATE ONLY. Not a vendor .img updater. No boot/recovery test. No personal SSH keys or Wi-Fi credentials included. Do not use dd, vendor upgrade, rescue or USB flashing with this artifact. SD write support is unverified.\n')
    sums = {p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS'}
    (output / 'SHA256SUMS').write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(sums.items())))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-rootfs', type=Path, required=True)
    parser.add_argument('--ssh-binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('FAKEROOTKEY'):
        raise SystemExit('Run under fakeroot to preserve vendor ownership without host root privileges.')
    build(args)
