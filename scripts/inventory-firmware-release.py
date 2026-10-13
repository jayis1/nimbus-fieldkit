#!/usr/bin/env python3
"""Offline source/archive release inventory. Never installs, mounts or flashes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {
    'management-startup': ('device/image-start.sh', 'opt/nimbus/image-start.sh'),
    'native-agent': ('device/nimbus-agent.sh', 'opt/nimbus/native/nimbus-agent.sh'),
    'companion-status': ('device/nimbus-companion-status.sh', 'opt/nimbus/native/nimbus-companion-status.sh'),
    'settings': ('device/nimbus-settings.sh', 'opt/nimbus/native/nimbus-settings.sh'),
    'snapshots': ('device/nimbus-dashboard.sh', 'opt/nimbus/native/nimbus-dashboard.sh'),
    'media-ownership-guard': ('device/nimbus-media-guard.sh', 'opt/nimbus/native/nimbus-media-guard.sh'),
    'snapshot-format': ('device/dashboard/snapshot.awk', 'opt/nimbus/native/dashboard/snapshot.awk'),
    'sd-diagnostics': ('device/nimbus-sd-doctor.sh', 'opt/nimbus/nimbus-sd-doctor.sh'),
    'web-settings-bridge': ('device/unified/bridge.js', 'nimbus/data/fieldkit-v06/bridge.js'),
    'homepage-battery': ('device/unified/battery.js', 'nimbus/data/fieldkit-v06/battery.js'),
    'web-theme-layout': ('device/unified/stock-dark.css', 'nimbus/data/fieldkit-v06/stock-dark.css'),
    'html5-music': ('device/unified/audio-html5.js', 'nimbus/data/fieldkit-v06/audio-html5.js'),
    'upload-progress': ('device/unified/upload-progress.js', 'nimbus/data/fieldkit-v06/upload-progress.js'),
    'nib-buddy': ('device/unified/mascot.js', 'nimbus/data/fieldkit-v06/mascot.js'),
}
BUILD_SOURCES = ('scripts/build-custom-image.py', 'scripts/build-unified-dashboard.py',
                 'scripts/package-native.py', 'scripts/rootfs-policy.py')
BLOCKERS = (
    'Native image boot and recovery/restoration remain unqualified.',
    'No approved installation container or safe updater path exists.',
    'Fresh-owner enrollment, entropy, Wi-Fi and reset behavior remain unqualified.',
    'Restricted SFTP authentication/confinement and USB lifecycle remain unqualified.',
    'Persistent SD policy, legacy services and GameHack integration need native tests.',
    'Vendor-component redistribution permissions remain unresolved.',
)


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def regular(path, limit):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Symlink input paths are refused.')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('Expected bounded regular offline file.')
    return path


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_record(root, name, recorded):
    # Only allowlisted first-party paths are opened, never paths from a manifest.
    try:
        path = regular(root / name, 4 * 1024**2)
    except FileNotFoundError:
        return {'path': name, 'current_sha256': None, 'manifest_comparison': 'source_missing'}
    current = checksum(path)
    expected = recorded.get(name)
    return {'path': name, 'current_sha256': current,
            'manifest_comparison': ('not_recorded' if expected is None else
                                    'unchanged' if expected == current else 'changed')}


def expected_payload(root, source):
    data = regular(root / source, 4 * 1024**2).read_bytes()
    if source == 'device/unified/bridge.js':
        # Exact build-unified-dashboard.py v06 transformation, not loose matching.
        data = data.decode().replace('/data/fieldkit-v05/', '/data/fieldkit-v06/').encode()
    return data


def inventory(candidate, source_root=ROOT):
    candidate = Path(candidate).absolute()
    manifest_path = regular(candidate / 'BUILD-MANIFEST.json', 65536)
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or manifest.get('schema') != 'nimbus-custom-rootfs/v1':
        raise ValueError('Unsupported candidate manifest.')
    if manifest.get('private_per_device') is not None and manifest.get('private_per_device') is not False:
        raise ValueError('Private provisioning candidates cannot be release inputs.')
    recorded = manifest.get('overlay_source_sha256')
    references = manifest.get('artifacts')
    if not isinstance(recorded, dict) or not isinstance(references, dict):
        raise ValueError('Missing source/artifact provenance.')
    # Validate hashes without reading or reporting arbitrary manifest paths.
    if any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value)
           for value in recorded.values()):
        raise ValueError('Invalid source hash.')
    archive_path = regular(candidate / 'rootfs.tar', 512 * 1024**2)
    archive_digest = checksum(archive_path)
    if references.get('rootfs.tar') != archive_digest:
        raise ValueError('Candidate archive hash does not match manifest.')
    policy = module('rootfs-policy')
    features = []
    with tarfile.open(archive_path) as archive:
        members = policy.collect_members(archive)
        policy.validate_members(members)
        nodes = {policy.canonical(member.name): member for member in members}
        # Fail closed for known management/enrollment identities; not a complete secret audit.
        if any(name.startswith('etc/ssh/ssh_host_') or
               name in ('etc/nimbus/host-ed25519', 'etc/nimbus/authorized_keys') or
               name.startswith('etc/nimbus-sftp-auth/') and not member.isdir()
               for name, member in nodes.items()):
            raise ValueError('Archive contains known per-device identity/enrollment material.')
        for feature, (source, destination) in FEATURES.items():
            row = {'feature': feature, 'archive_path': destination,
                   **source_record(Path(source_root), source, recorded)}
            expected = (hashlib.sha256(expected_payload(Path(source_root), source)).hexdigest()
                        if row['current_sha256'] is not None else None)
            node = nodes.get(destination)
            if node is None:
                archived = None
                status = 'absent'
            elif not node.isfile() or node.size > 4 * 1024**2:
                raise ValueError('Required feature is not a bounded regular archive file.')
            else:
                archived = hashlib.sha256(archive.extractfile(node).read()).hexdigest()
                status = ('source_missing' if row['current_sha256'] is None else
                          'current' if archived == expected else 'different')
            row.update(expected_payload_sha256=expected, archive_sha256=archived,
                       archive_comparison=status)
            features.append(row)
    build_sources = [source_record(Path(source_root), name, recorded) for name in BUILD_SOURCES]
    rebuild = any(row['archive_comparison'] != 'current' or row['manifest_comparison'] != 'unchanged'
                  for row in features) or any(row['manifest_comparison'] != 'unchanged' for row in build_sources)
    return {'schema': 'nimbus-firmware-release-inventory/v1',
            'candidate_manifest_sha256': checksum(manifest_path), 'rootfs_archive_sha256': archive_digest,
            'archive_hash_matches_manifest': True, 'features': features, 'build_sources': build_sources,
            'source_rebuild_required': rebuild, 'production_ready': False, 'flash_authorized': False,
            'release_blockers': list(BLOCKERS),
            'limitations': ['Selected exact-source archive checks, not full image or secret audit.',
                            'Manifest consistency is not independently authenticated provenance.',
                            'Only the pinned v06 bridge path substitution is modeled; builder changes require review.',
                            'No device state, native tests, SFTP runtime or license permission inferred.']}


def save_report(path, report):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Symlink output parent refused.')
    if any(parent == Path('/dev') or parent == Path('/proc') or parent == Path('/sys') for parent in path.parents):
        raise ValueError('Device/pseudo-filesystem output refused.')
    # Parent must already exist. No overwrite; never creates a firmware artifact.
    data = (json.dumps(report, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Optional new private JSON report; never overwrites')
    args = parser.parse_args()
    try:
        report = inventory(args.candidate)
        if args.output:
            save_report(args.output, report)
    except (OSError, ValueError, tarfile.TarError):
        # Do not echo input metadata, private archive names or file contents on failure.
        print(json.dumps({'schema': 'nimbus-firmware-release-inventory/v1',
                          'inventory_valid': False, 'production_ready': False, 'flash_authorized': False,
                          'error': 'Invalid, private, unsafe or mismatched input; or unavailable report output.'}))
        return 1
    print(json.dumps(report, indent=2))
    return 2  # Valid inventory, still blocked for installation/distribution.


if __name__ == '__main__':
    raise SystemExit(main())
