#!/usr/bin/env python3
"""Package reviewed native scripts/docs only; never install or flash a device."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
# Reproducible modern timestamp avoids legacy tar's warnings about epoch-zero files.
ARCHIVE_MTIME = 1767225600  # 2026-01-01 UTC
SOURCES = {
    'nimbus-agent.sh': 'device/nimbus-agent.sh',
    'nimbus-companion-status.sh': 'device/nimbus-companion-status.sh',
    'nimbus-settings.sh': 'device/nimbus-settings.sh',
    'nimbus-dashboard.sh': 'device/nimbus-dashboard.sh',
    'nimbus-media-guard.sh': 'device/nimbus-media-guard.sh',
    'dashboard/index.html': 'fieldkit/index.html',
    'dashboard/dashboard.css': 'fieldkit/dashboard.css',
    'dashboard/dashboard.js': 'fieldkit/dashboard.js',
    'dashboard/battery.js': 'device/unified/battery.js',
    'dashboard/snapshot.awk': 'device/dashboard/snapshot.awk',
    'device-inventory.sh': 'scripts/device-inventory.sh',
    'NATIVE-INSTALL.md': 'device/NATIVE-INSTALL.md',
    'docs/FEATURES.md': 'docs/FEATURES.md',
    'docs/GAMEHACK-COMPANION-STATUS.md': 'docs/GAMEHACK-COMPANION-STATUS.md',
    'docs/TOGGLES.md': 'docs/TOGGLES.md',
    'docs/DASHBOARD.md': 'docs/DASHBOARD.md',
    'docs/MEDIA-OWNERSHIP-GUARD.md': 'docs/MEDIA-OWNERSHIP-GUARD.md',
    'docs/FIRMWARE-3.04-INSPECTION.md': 'docs/FIRMWARE-3.04-INSPECTION.md',
}


def package(output):
    files = {name: (ROOT / source).read_bytes() for name, source in SOURCES.items()}
    manifest = {'schema': 'nimbus-native-kit/v1', 'version': '0.4', 'status': 'candidate/not installed',
                'files': [{'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation; do not overwrite earlier bundles or follow an output symlink.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w') as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755 if name.endswith('.sh') else 0o644
                info.mtime = ARCHIVE_MTIME
                archive.addfile(info, io.BytesIO(data))
    except Exception:
        output.unlink()  # Only the newly created incomplete output.
        raise
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('Native candidate bundle SHA-256:', package(args.output))
