#!/usr/bin/env python3
"""LOCAL-ONLY exact vendor startup-warning patch; no device access."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '7ba6554dd579ffb9d86ea20ed011ae083dbb50442820ff132751a219b1498d67'


def patch_controller(data):
    if hashlib.sha256(data).hexdigest() != BASELINE:
        raise ValueError('Unknown vendor controller; refusing patch')
    start = data.index(b'\t\t\tvar isiPadOriPhone = navigator.userAgent.match(/iPad/i) || navigator.userAgent.match(/iPhone/i);')
    end = data.index(b'\t\t\tthis.bind();', start)
    block = data[start:end]
    if len(block) != 391 or block.count(b'FlashDetect.versionAtLeast(10)') != 1 or block.count(b't4u.showMessage') != 1:
        raise ValueError('Unexpected startup check structure')
    return data[:start] + b'\t\t\t// Music uses HTML5; no obsolete plugin-install startup warning.\r\n' + data[end:]


def installer(after):
    return '''#!/bin/sh
# Only the exact vendor controller startup warning. No service/mount/firmware actions.
set -eu
umask 077
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd)
TARGET=/nimbus/data/js/t4u.controller.js
[ "$(id -u)" = 0 ] && [ "$BASE" = /root/nimbus-flash-warning-r1 ] || exit 1
[ "$(stat -c '%u:%g:%a' "$BASE")" = '0:0:700' ] || exit 1
for path in /nimbus /nimbus/data /nimbus/data/js "$TARGET"; do [ ! -L "$path" ] || exit 1; done
cd "$BASE"
baseline() { printf '%s  %s\\n' BEFORE "$1" | sha256sum -c -; }
replace() {
    [ ! -e "$TARGET.nimbus-warning-new" ] && [ ! -L "$TARGET.nimbus-warning-new" ] || return 1
    (set -C; cat "$1" > "$TARGET.nimbus-warning-new")
    chmod 644 "$TARGET.nimbus-warning-new"
    cmp "$1" "$TARGET.nimbus-warning-new"
    mv "$TARGET.nimbus-warning-new" "$TARGET"
}
case "${1:-}" in
 install)
    sha256sum -c SHA256SUMS
    baseline "$TARGET"
    [ ! -e backups ] && [ ! -L backups ] || { echo 'Prior attempt exists; no blind retry'; exit 1; }
    mkdir -m 700 backups
    cp -p "$TARGET" backups/t4u.controller.js
    baseline backups/t4u.controller.js
    baseline "$TARGET"
    replace t4u.controller.js
    printf '%s  %s\\n' AFTER "$TARGET" | sha256sum -c -
    sync
    echo 'Obsolete Flash startup warning removed. HTML5 player and all other controls unchanged.'
    echo 'Hard-refresh the original dashboard to discard the cached controller.'
    ;;
 rollback)
    baseline backups/t4u.controller.js
    printf '%s  %s\\n' AFTER "$TARGET" | sha256sum -c - || { echo 'Later controller edits; refusing rollback'; exit 1; }
    replace backups/t4u.controller.js
    baseline "$TARGET"
    sync
    echo 'Exact original controller restored; private backup retained.'
    ;;
 *) echo 'Use install or rollback'; exit 1;;
esac
'''.replace('BEFORE', BASELINE).replace('AFTER', after)


def build(stock_web, output):
    output = Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('Existing artifact; no overwrite')
    with tarfile.open(stock_web) as archive:
        member = archive.getmember('data/js/t4u.controller.js')
        if not member.isfile() or member.size > 1048576: raise ValueError('Invalid controller member')
        patched = patch_controller(archive.extractfile(member).read())
    after = hashlib.sha256(patched).hexdigest()
    files = {'t4u.controller.js': patched, 'install.sh': installer(after).encode()}
    report = {'schema': 'nimbus-flash-warning/v1', 'before_sha256': BASELINE, 'after_sha256': after,
              'public_redistribution': False, 'status': 'local candidate/not installed'}
    files['MANIFEST.json'] = (json.dumps(report, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                member = tarfile.TarInfo(name); member.size = len(data); member.mode = 0o600; member.mtime = 1767225600
                archive.addfile(member, io.BytesIO(data))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-web', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.stock_web, args.output), indent=2))
