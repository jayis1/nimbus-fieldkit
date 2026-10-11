#!/usr/bin/env python3
"""Build a LOCAL-ONLY UI patch from a verified private v0.6 homepage bundle."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def installer(before, after):
    return '''#!/bin/sh
# UI only. Never run firmware helpers or alter SSH, services, mounts or settings.
set -eu
umask 077
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd)
DATA=/nimbus/data
ASSETS="$DATA/fieldkit-audio-r1"
[ "$(id -u)" = 0 ] && [ "$BASE" = /root/nimbus-audio-html5-r1 ] || exit 1
[ "$(stat -c '%u:%g:%a' "$BASE")" = '0:0:700' ] || exit 1
[ -d "$DATA" ] && [ ! -L /nimbus ] && [ ! -L "$DATA" ] && [ ! -L "$DATA/index.html" ] || exit 1
cd "$BASE"
baseline() { printf '%s  %s\\n' BEFORE_HASH "$1" | sha256sum -c -; }
replace_index() {
    [ ! -e "$DATA/.nimbus-audio-new" ] && [ ! -L "$DATA/.nimbus-audio-new" ] || return 1
    (set -C; cat "$1" > "$DATA/.nimbus-audio-new")
    chmod 644 "$DATA/.nimbus-audio-new"
    cmp "$1" "$DATA/.nimbus-audio-new"
    mv "$DATA/.nimbus-audio-new" "$DATA/index.html"
}
case "${1:-}" in
 install)
    sha256sum -c SHA256SUMS
    baseline "$DATA/index.html" || { echo 'Homepage differs; refusing patch'; exit 1; }
    [ ! -e backups ] && [ ! -L backups ] && [ ! -e "$ASSETS" ] && [ ! -L "$ASSETS" ] || {
        echo 'Prior staging/integration exists; do not rerun blindly'; exit 1;
    }
    mkdir -m 700 backups
    cp -p "$DATA/index.html" backups/index.html
    cmp "$DATA/index.html" backups/index.html
    baseline backups/index.html
    mkdir -m 755 "$ASSETS"
    cp audio-html5.js "$ASSETS/audio-html5.js"
    chmod 644 "$ASSETS/audio-html5.js"
    cmp audio-html5.js "$ASSETS/audio-html5.js"
    baseline "$DATA/index.html"
    replace_index index.html
    printf '%s  %s\\n' AFTER_HASH "$DATA/index.html" | sha256sum -c -
    sha256sum "$DATA/index.html" "$ASSETS/audio-html5.js" > installed.sha256
    sync
    echo 'HTML5-only Music UI installed. Settings assets, services, SSH and firmware unchanged.'
    echo 'Hard-refresh the original homepage. Browser codecs and user-gesture policy still apply.'
    ;;
 rollback)
    baseline backups/index.html
    [ -f installed.sha256 ] && [ ! -L installed.sha256 ] || exit 1
    sha256sum -c installed.sha256 || { echo 'Later UI edits detected; refusing rollback'; exit 1; }
    replace_index backups/index.html
    baseline "$DATA/index.html"
    sync
    echo 'Previous homepage restored. Unreferenced additive audio asset and private backups retained.'
    ;;
 *) echo 'Use install or rollback'; exit 1;;
esac
'''.replace('BEFORE_HASH', before).replace('AFTER_HASH', after)


def build(baseline_bundle, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Refusing to overwrite an existing artifact')
    with tarfile.open(baseline_bundle) as archive:
        def read(name, limit):
            member = archive.getmember(name)
            if not member.isfile() or member.size > limit:
                raise ValueError('Invalid bounded baseline member')
            return archive.extractfile(member).read()
        manifest = json.loads(read('MANIFEST.json', 1048576))
        page = read('index.html', 1048576)
    before = hashlib.sha256(page).hexdigest()
    listed = next((f for f in manifest.get('files', []) if f.get('name') == 'index.html'), {})
    if manifest.get('schema') != 'nimbus-unified/v1' or manifest.get('version') != '0.6' or listed.get('sha256') != before:
        raise ValueError('Verified original delivered v0.6 baseline required')
    marker = b'<script src="/data/fieldkit-v06/bridge.js"></script>'
    if page.count(marker) != 1 or b'audio-html5.js' in page:
        raise ValueError('Unknown/already patched homepage; no blind replacement')
    patched = page.replace(marker, b'<script src="/data/fieldkit-audio-r1/audio-html5.js"></script>\n' + marker)
    after = hashlib.sha256(patched).hexdigest()
    files = {'index.html': patched, 'audio-html5.js': (ROOT/'device/unified/audio-html5.js').read_bytes(),
             'install.sh': installer(before, after).encode()}
    report = {'schema': 'nimbus-audio-ui/v1', 'status': 'offline candidate/not installed',
              'expected_current_index_sha256': before, 'patched_index_sha256': after,
              'contains_vendor_homepage': True, 'public_redistribution': False, 'firmware_write': False,
              'files': [{'name': name, 'sha256': hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())]}
    files['MANIFEST.json'] = (json.dumps(report, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                member = tarfile.TarInfo(name); member.size = len(data); member.mode = 0o600
                member.mtime = 1767225600; archive.addfile(member, io.BytesIO(data))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); os.umask(0o077)
    report = build(args.baseline_bundle, args.output)
    print('Local-only audio UI package built; not installed, not flashable, never upload the vendor-based archive.')
