#!/usr/bin/env python3
"""Offline rootfs archive policy checks; never extracts, mounts or flashes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile

MAX_NODES = 10000
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def collect_members(archive):
    members = []
    total = 0
    for member in archive:
        if len(members) >= MAX_NODES or not 0 <= member.size <= MAX_FILE_BYTES:
            raise ValueError('Rootfs archive exceeds bounded geometry/node policy.')
        total += member.size
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Rootfs declared content exceeds 256 MiB budget.')
        members.append(member)
    return members


def canonical(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts or name.rstrip('/') != str(path):
        raise ValueError('Unsafe/noncanonical archive path.')
    return str(path)


def validate_members(members):
    if len(members) > MAX_NODES or sum(m.size for m in members) > MAX_TOTAL_BYTES:
        raise ValueError('Rootfs archive exceeds bounded geometry/node policy.')
    nodes = {}
    for member in members:
        name = canonical(member.name)
        if name in nodes or not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError('Duplicate/unsupported archive node.')
        if not 0 <= member.size <= MAX_FILE_BYTES:
            raise ValueError('Invalid/oversized archive node.')
        nodes[name] = member
    for name, member in nodes.items():
        for parent in PurePosixPath(name).parents:
            node = nodes.get(str(parent))
            if node is not None and not node.isdir():
                raise ValueError('Archive child traverses a non-directory node.')
        if member.islnk():
            target = nodes.get(canonical(member.linkname))
            if target is None or not target.isfile():
                raise ValueError('Hardlink must reference a contained regular file.')


def audit(path, private=False):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 512 * 1024 * 1024:
        raise ValueError('Only regular offline rootfs archives are accepted.')
    with tarfile.open(path) as archive:
        members = collect_members(archive)
        validate_members(members)
        nodes = {canonical(m.name): m for m in members}
        def read(name, limit=1024 * 1024):
            node = nodes.get(name)
            if node is None or not node.isfile() or not 0 <= node.size <= limit:
                raise ValueError('Required bounded regular file missing: ' + name)
            return archive.extractfile(node).read()
        def permissions(name, mode, directory=False):
            node = nodes.get(name)
            return bool(node and (node.isdir() if directory else node.isfile()) and
                        node.uid == 0 and node.gid == 0 and node.mode == mode)
        start = read('opt/nimbus/image-start.sh').decode()
        conf = read('etc/inetd.conf').decode()
        shadow = read('etc/shadow').decode()
        defaults = read('opt/qsi/config/platform_default').decode()
        page = read('nimbus/data/index.html')
        bridge = read('nimbus/data/fieldkit-v06/bridge.js')
        read('opt/nimbus/native/nimbus-dashboard.sh')
        read('opt/nimbus/native/dashboard/snapshot.awk')
        checks = {
            'telnet_disabled': not any(l.split() and not l.lstrip().startswith('#') and l.split()[0] == 'telnet' for l in conf.splitlines()),
            'root_password_locked': any(l.startswith('root:') and l.split(':')[1].startswith(('!', '*')) for l in shadow.splitlines()),
            'vendor_host_keys_removed': not any(n.startswith('etc/ssh/ssh_host_') for n in nodes),
            'ssh_binary_private_root_owned': permissions('opt/nimbus/dropbearmulti', 0o700),
            'ssh_directory_private_root_owned': permissions('etc/nimbus', 0o700, directory=True),
            'immutable_boot_publisher': 'sh /opt/nimbus/native/nimbus-dashboard.sh snapshot' in start and 'sh "$base/native/nimbus-dashboard.sh"' not in start,
            'ssh_runtime_permission_gate': "'0:0:600'" in start and "'0:0:700'" in start and 'dropbearkey -y' in start,
            'wlan1_only_management': 'dropbear -F -l wlan1 -p 0.0.0.0:2224' in start,
            'wpa2_default': [l for l in defaults.splitlines() if l.startswith('CFG_WIFI_AP_MODE=')] == ['CFG_WIFI_AP_MODE=wpa2aes'],
            'unified_homepage': b'btnNimbusFieldKit' in page and b'/data/fieldkit-v06/' in page,
            'settings_signin_fix': b'nimbus-settings-sign-in' in bridge and b'AdminLoginSetting' in bridge,
            'no_standalone_dashboard': 'opt/nimbus/native/dashboard/index.html' not in nodes,
        }
        keys = ('etc/nimbus/host-ed25519', 'etc/nimbus/authorized_keys')
        checks['key_distribution_policy'] = (all(permissions(n, 0o600) and nodes[n].size > 0 for n in keys)
                                             if private else all(n not in nodes for n in keys))
        return {'schema': 'nimbus-rootfs-policy/v1', 'checks': checks,
                'offline_policy_pass': all(checks.values()), 'private_per_device': private,
                'module_hashes': {m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                                  for m in members if m.isfile() and m.name.startswith('lib/modules/')},
                'production_ready': False, 'flash_authorized': False,
                'limitations': 'Static selected-file checks, not complete security, boot, Wi-Fi provisioning, recovery or vendor-service validation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--private', action='store_true', help='Expect private per-device SSH material; never redistribute')
    args = parser.parse_args()
    try:
        report = audit(args.archive, args.private)
    except (OSError, ValueError, tarfile.TarError):
        raise SystemExit('Rootfs policy audit failed: invalid/unsupported offline archive. No private contents printed.')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['offline_policy_pass'] else 1)
