#!/usr/bin/env python3
"""Read-only image integrity/blocker report. Never certifies or flashes firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

GATES = {
    'secure_provisioning_verified': 'Secure per-device key/Wi-Fi provisioning has not been verified.',
    'boot_tested': 'Custom image native boot has not been verified.',
    'recovery_tested': 'Matching disaster recovery/restoration has not been verified.',
    'vendor_update_container': 'No reviewed vendor update/deployment container is available.',
    'sd_write_verified': 'Candidate SD startup, persistent readback and USB ownership handoff remain unverified.',
    'downstream_pairing_verified': 'GameHack downstream management/transfer pairing is unverified.',
    'redistribution_reviewed': 'Vendor-component redistribution rights have not been established.',
    'legacy_services_reviewed': 'Legacy HTTP/FTP/accounts/reset behavior remains unaudited.'}


def artifact(base, name):
    if not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..'):
        raise ValueError('Unsafe artifact name.')
    path = base / name
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Artifact must be a regular file, not a link/device.')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit(base):
    base = Path(base).resolve()
    path = artifact(base, 'BUILD-MANIFEST.json')
    if path.stat().st_size > 65536:
        raise ValueError('Manifest too large.')
    manifest = json.loads(path.read_text())
    if not isinstance(manifest, dict) or manifest.get('schema') != 'nimbus-custom-rootfs/v1':
        raise ValueError('Unsupported image manifest.')
    sums = artifact(base, 'SHA256SUMS')
    if sums.stat().st_size > 65536:
        raise ValueError('Checksum file too large.')
    listed = {}
    for line in sums.read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (.+)', line)
        if not match or match[2] in listed:
            raise ValueError('Invalid/duplicate checksum entry.')
        listed[match[2]] = match[1]
    required = ('BUILD-MANIFEST.json', 'rootfs.ext3.candidate', 'rootfs.tar', 'NOT-FLASHABLE.txt')
    if any(name not in listed for name in required):
        raise ValueError('Required artifact missing from checksum list.')
    failures = []
    for name, expected in listed.items():
        if digest(artifact(base, name)) != expected:
            failures.append(name)
    references = manifest.get('artifacts')
    if not isinstance(references, dict) or any(listed.get(name) != expected for name, expected in references.items()):
        raise ValueError('Manifest/artifact checksum disagreement.')
    image = artifact(base, 'rootfs.ext3.candidate')
    if image.stat().st_size != 256 * 1024 ** 2 or manifest.get('image_bytes') != image.stat().st_size:
        failures.append('rootfs image geometry')
    blockers = [message for key, message in GATES.items() if manifest.get(key) is not True]
    # Boolean claims in a mutable local manifest cannot prove hardware evidence.
    return {'schema': 'nimbus-readiness-report/v1', 'integrity_verified': not failures,
            'integrity_failures': failures, 'production_ready': False,
            'flash_authorized': False, 'release_blockers': blockers,
            'evidence_note': 'Manifest flags/checksums are not independently verified hardware or licensing evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.directory)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({'integrity_verified': False, 'production_ready': False, 'error': str(error)}))
        raise SystemExit(1)
    print(json.dumps(report, indent=2))
    raise SystemExit(2 if report['integrity_verified'] else 1)
