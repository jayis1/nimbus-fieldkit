#!/usr/bin/env python3
"""Source-only integration probe bundle; no installer, listener or vendor assets."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'nimbus-companion-status.sh': 'device/nimbus-companion-status.sh',
    'GAMEHACK-COMPANION-STATUS.md': 'docs/GAMEHACK-COMPANION-STATUS.md',
}


def package(output):
    files = {name: (ROOT / source).read_bytes() for name, source in SOURCES.items()}
    manifest = {'schema': 'nimbus-companion-probe-bundle/v1',
                'status': 'source-only/native validation pending',
                'hardware_validated': False, 'installer': False,
                'files': [{'name': name, 'bytes': len(data),
                           'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w') as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o600
                info.mtime = 1767225600
                archive.addfile(info, io.BytesIO(data))
    except Exception:
        output.unlink()  # Only this newly created incomplete output.
        raise
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('Companion probe bundle SHA-256:', package(args.output))
