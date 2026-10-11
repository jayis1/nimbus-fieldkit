#!/usr/bin/env python3
"""Offline rootfs candidate builder. Never creates a vendor update or flashes."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
STOCK_HASH = '4dd2907ec920443855b221b1f67c5086e369b84861fb0a486d74da2c7671b203'
SSH_HASH = '1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c'
STAMP = 1767225600
spec = importlib.util.spec_from_file_location('rootfs_policy', ROOT / 'scripts/rootfs-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
validate_members = policy.validate_members


def digest(path):
    if not stat.S_ISREG(Path(path).lstat().st_mode):
        raise ValueError('Expected a regular local input, not a device/link.')
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(root, name, data, mode=0o644):
    policy.canonical(name)
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
    provisioning = None
    provision_dir = getattr(args, 'provisioning_dir', None)
    if provision_dir:
        if not getattr(args, 'dropbearkey', None):
            raise ValueError('Private provisioning requires a trusted host dropbearkey validator.')
        spec = importlib.util.spec_from_file_location('provision_image', ROOT / 'scripts/provision-image.py')
        provision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provision)
        provisioning = provision.validate(provision_dir, args.dropbearkey.resolve())
        # A provisioned rootfs contains a private identity. Never put it in public build artifacts.
        provision.private_path(args.output)
    if digest(args.stock_rootfs) != STOCK_HASH:
        raise ValueError('Vendor rootfs hash does not match reviewed 3.04 input.')
    if digest(args.ssh_binary) != SSH_HASH:
        raise ValueError('SSH binary is not the tested interface-fail-closed candidate.')
    companion = ROOT / 'build/gamehack-nimbus-library-staged-v1.tar'
    if not companion.is_file() or companion.is_symlink():
        raise ValueError('Build the staged GameHack source bundle first.')
    output = args.output.resolve()
    if any(output == Path(p) or Path(p) in output.parents for p in ('/dev', '/proc', '/sys')):
        raise ValueError('Refusing device output.')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    root = output / 'rootfs-tree'
    root.mkdir()
    with tarfile.open(args.stock_rootfs) as archive:
        members = policy.collect_members(archive)
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
    warning_spec = importlib.util.spec_from_file_location('flash_warning_fix', ROOT / 'scripts/package-flash-warning-fix.py')
    warning_fix = importlib.util.module_from_spec(warning_spec)
    warning_spec.loader.exec_module(warning_fix)
    controller = root / 'nimbus/data/js/t4u.controller.js'
    write(root, 'nimbus/data/js/t4u.controller.js', warning_fix.patch_controller(controller.read_bytes()))
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
    if provisioning:
        for name in ('host-ed25519', 'authorized_keys'):
            data = provision.read_private(provision_dir / name)
            if hashlib.sha256(data).hexdigest() != provisioning['files'][name]:
                raise ValueError('Provisioning changed during build.')
            write(root, 'etc/nimbus/' + name, data, 0o600)
        write(root, 'etc/nimbus/PROVISIONING.txt', b'PRIVATE PER-DEVICE CANDIDATE. Unique SSH material included. Do not redistribute or flash before boot/recovery gates pass. Wi-Fi settings remain external.\n', 0o600)
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
    shutil.copyfile(companion, output / companion.name)
    for script in ('opt/nimbus/image-start.sh', 'etc/rc.d/rc.local'):
        subprocess.run(['sh', '-n', str(root / script)], check=True)
    root_tar = output / 'rootfs.tar'
    with tarfile.open(root_tar, 'w', format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(root.rglob('*')):
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    report = policy.audit(root_tar, private=bool(provisioning))
    if not report['offline_policy_pass']:
        raise ValueError('Offline rootfs policy checks failed; preserve staging for review.')
    with tarfile.open(args.stock_rootfs) as stock:
        vendor_modules = {m.name: hashlib.sha256(stock.extractfile(m).read()).hexdigest()
                          for m in stock if m.isfile() and m.name.startswith('lib/modules/')}
    if report['module_hashes'] != vendor_modules:
        raise ValueError('Vendor module inventory/content changed; refusing candidate.')
    report['vendor_module_hashes_match'] = True
    (output / 'ROOTFS-POLICY.json').write_text(json.dumps(report, indent=2) + '\n')
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
                 'offline_policy_pass': True,
                 'sd_access_policy': 'Preserve vendor read-only default; no automatic writable remount or lock override.',
                'image_bytes': image.stat().st_size, 'removed_vendor_host_keys': removed,
                'credentials': 'No personal keys/passwords/settings/backups imported; stock vendor accounts otherwise remain.',
                'preserved': ['vendor kernel/modules', 'bootloader/rescue external to this image', 'partition layout external to this image', 'stock web handlers'],
                 'blocked': ['native SSH/Wi-Fi provisioning validation', 'recovery/restoration', 'native boot', 'candidate SD policy validation', 'GameHack downstream SSH access', 'legacy-service and redistribution review'],
                 'artifacts': {p.name: digest(p) for p in (image, root_tar, output / companion.name, ui)}}
    sources = set(unified.native.SOURCES.values()) | {
        'scripts/build-custom-image.py', 'scripts/rootfs-policy.py',
        'scripts/build-unified-dashboard.py', 'scripts/package-native.py', 'scripts/package-flash-warning-fix.py',
        'scripts/provision-image.py', 'device/image-start.sh',
        'device/nimbus-sd-doctor.sh', 'device/retire-v04-homepage.sh',
        'device/unified/bridge.js', 'device/unified/stock-dark.css', 'device/unified/audio-html5.js',
        'fieldkit/index.html', 'fieldkit/dashboard.css', 'fieldkit/dashboard.js',
        'docs/UNIFIED-DASHBOARD.md', 'docs/GAMEHACK-OPTIONAL-ENHANCEMENTS.md', 'docs/SECURITY-PLAN.md'}
    manifest['overlay_source_sha256'] = {name: digest(ROOT / name) for name in sorted(sources)}
    manifest['previous_ui_bundle_sha256'] = digest(ROOT / 'build/nimbus-unified-v05.tar')
    manifest['artifacts']['ROOTFS-POLICY.json'] = digest(output / 'ROOTFS-POLICY.json')
    if provisioning:
        manifest['credentials'] = 'PRIVATE per-device SSH identity; existing Wi-Fi settings remain external. Never redistribute.'
        manifest['private_per_device'] = True
        manifest['ssh_material_validated_offline'] = True
        manifest['host_fingerprint'] = provisioning['host_fingerprint']
        manifest['client_fingerprint'] = provisioning['client_fingerprint']
        manifest['secure_provisioning_verified'] = False
    (output / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    warning = 'OFFLINE CANDIDATE ONLY. Not a vendor .img updater. No boot/recovery test. Do not use dd, vendor upgrade, rescue or USB flashing with this artifact. SD write support is unverified.\n'
    warning += 'PRIVATE SSH KEYS INCLUDED. NEVER REDISTRIBUTE.\n' if provisioning else 'No personal SSH keys or Wi-Fi credentials included.\n'
    (output / 'NOT-FLASHABLE.txt').write_text(warning)
    sums = {p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS'}
    (output / 'SHA256SUMS').write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(sums.items())))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-rootfs', type=Path, required=True)
    parser.add_argument('--ssh-binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--provisioning-dir', type=Path, help='Optional PRIVATE per-device SSH bundle')
    parser.add_argument('--dropbearkey', type=Path, help='Trusted host validator required with provisioning')
    args = parser.parse_args()
    if not os.environ.get('FAKEROOTKEY'):
        raise SystemExit('Run under fakeroot to preserve vendor ownership without host root privileges.')
    build(args)
