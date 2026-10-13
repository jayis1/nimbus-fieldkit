#!/usr/bin/env python3
"""Build a guarded first-party UI-only package. Never connects to a device."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BEFORE={
    'toolkit.html':'ebaad09ee0834bd496e760e148c180d0f88117f82088b8987e439f2f06642f79',
    'toolkit.js':'a9d6678149d711656e4076045a1ceece5bf48410d997ce207bca205f2ec2813d',
    'toolkit.css':'ca6f72c45a75302ce50f2ffffb47a90733ce6aede27a89ecaec3b7e1366092b4',
    'bridge.js':'5a748e55be9b8334da16fe59ae1cadeecdad46f99a0e4f2119195c5fdc16ec52',
}
NAMES=(*BEFORE,'battery.js')
STAGE='/tmp/nimbus-dashboard-ab-r1'


def payload():
    spec=importlib.util.spec_from_file_location('dashboard_ab_assets',ROOT/'scripts/build-unified-dashboard.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    html,css,js=module.toolkit_assets()
    return {'toolkit.html':html.encode(),'toolkit.css':css.encode(),'toolkit.js':js.encode(),
            'bridge.js':(ROOT/'device/unified/bridge.js').read_bytes().replace(b'/data/fieldkit-v05/',b'/data/fieldkit-v06/'),
            'battery.js':(ROOT/'device/unified/battery.js').read_bytes()}


def installer(before,after):
    if set(before)!=set(BEFORE) or set(after)!=set(NAMES) or any(not re.fullmatch('[a-f0-9]{64}',v) for v in (*before.values(),*after.values())):
        raise ValueError('Expected fixed UI inventory/hash values.')
    def cases(values):
        return '\n'.join(f"        {name}) printf '%s' {digest};;" for name,digest in values.items())
    return r'''#!/bin/sh
# Replace four first-party UI assets/add battery only. No homepage/service/media writes.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
DATA=/nimbus/data
NAMES='toolkit.html toolkit.js toolkit.css bridge.js battery.js'
[ "$(id -u)" = 0 ] || exit 1
[ "$BASE" = /tmp/nimbus-dashboard-ab-r1 ] || exit 1
for directory in /tmp "$BASE" /nimbus "$DATA" "$DATA/fieldkit-v06" "$DATA/fieldkit-performance-r1"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || exit 1
done
[ "$(stat -c '%u:%g:%a' "$BASE")" = 0:0:700 ] || exit 1
awk '$2=="/" && $3=="ext3" {if(($1!="/dev/root" && $1!="/dev/mmcblk0p2") || $4!="rw,relatime,errors=continue,barrier=0,data=writeback") bad=1;n++} END {exit n!=1 || bad}' /proc/mounts || exit 1
cd "$BASE"
for package_file in toolkit.html toolkit.js toolkit.css bridge.js battery.js install.sh MANIFEST.json SHA256SUMS; do
    [ -f "$package_file" ] && [ ! -L "$package_file" ] || exit 1
    [ "$(stat -c '%u:%g:%a:%h' "$package_file")" = 0:0:600:1 ] || exit 1
done
/usr/bin/sha256sum -c SHA256SUMS >/dev/null || exit 1
before() {
    case "$1" in
BEFORE_CASES
        *) return 1;;
    esac
}
after() {
    case "$1" in
AFTER_CASES
        *) return 1;;
    esac
}
target() {
    case "$1" in
        bridge.js) printf '%s' "$DATA/fieldkit-performance-r1/bridge.js";;
        toolkit.html|toolkit.js|toolkit.css|battery.js) printf '%s' "$DATA/fieldkit-v06/$1";;
        *) return 1;;
    esac
}
matches() {
    [ -f "$2" ] && [ ! -L "$2" ] || return 1
    printf '%s  %s\n' "$1" "$2" | /usr/bin/sha256sum -c - >/dev/null
}
baseline() {
    for name in $NAMES; do
        path=$(target "$name") || return 1
        if [ "$name" = battery.js ]; then
            [ ! -e "$path" ] && [ ! -L "$path" ] || return 1
        else
            [ "$(stat -c '%u:%g:%a:%h' "$path")" = 0:0:644:1 ] || return 1
            matches "$(before "$name")" "$path" || return 1
        fi
        [ ! -e "$path.nimbus-ab-new" ] && [ ! -L "$path.nimbus-ab-new" ] || return 1
    done
}
replace_asset() {
    name=$1; source=$2; path=$(target "$name")
    [ ! -e "$path.nimbus-ab-new" ] && [ ! -L "$path.nimbus-ab-new" ] || return 1
    (set -C; cat "$source" > "$path.nimbus-ab-new") || return 1
    chmod 644 "$path.nimbus-ab-new" || return 1
    cmp "$source" "$path.nimbus-ab-new" || return 1
    mv "$path.nimbus-ab-new" "$path" || return 1
}
saved_backups_ok() {
    [ -d backups ] && [ ! -L backups ] && [ "$(stat -c '%u:%g:%a' backups)" = 0:0:700 ] || return 1
    for saved_name in toolkit.html toolkit.js toolkit.css bridge.js; do
        matches "$(before "$saved_name")" "backups/$saved_name" || return 1
    done
}
restore_owned_changes() {
    saved_backups_ok || return 1
    restored=yes
    for restore_name in $NAMES; do
        restore_path=$(target "$restore_name")
        if matches "$(after "$restore_name")" "$restore_path"; then
            if [ "$restore_name" = battery.js ]; then
                # Only this exact newly installed hash, never an unrelated file.
                rm "$restore_path" || restored=no
            else
                replace_asset "$restore_name" "backups/$restore_name" || restored=no
            fi
        elif [ "$restore_name" = battery.js ]; then
            [ ! -e "$restore_path" ] && [ ! -L "$restore_path" ] || restored=no
        else
            matches "$(before "$restore_name")" "$restore_path" || restored=no
        fi
    done
    [ "$restored" = yes ]
}
case "${1:-}" in
 --check)
    [ ! -e backups ] && [ ! -L backups ] && [ ! -e STATUS ] && [ ! -L STATUS ] || exit 1
    baseline || { echo 'UI changed/previous stage; refusing update'; exit 1; }
    echo 'DASHBOARD-AB-CHECK=PASS no-UI-written';;
 install)
    # An exclusive retained marker prevents simultaneous transaction attempts.
    mkdir -m 700 transaction-lock || exit 1
    [ ! -e backups ] && [ ! -L backups ] && [ ! -e STATUS ] && [ ! -L STATUS ] || exit 1
    baseline || { echo 'UI changed; refusing update'; exit 1; }
    mkdir -m 700 backups
    for name in toolkit.html toolkit.js toolkit.css bridge.js; do
        cp -p "$(target "$name")" "backups/$name"
        matches "$(before "$name")" "backups/$name"
    done
    saved_backups_ok
    (set -C; printf 'INSTALLING\n' > STATUS)
    committed=no
    finish() {
        trap - EXIT
        trap '' HUP INT TERM
        if [ "$committed" != yes ]; then
            if restore_owned_changes; then echo 'Installation failed; known UI changes restored; evidence retained.';
            else echo 'Partial/unknown rollback; preserve all files and inspect. No rerun.'; fi
            printf 'FAILED\n' > STATUS
            exit 1
        fi
    }
    trap finish EXIT
    trap 'exit 1' HUP INT TERM
    for name in $NAMES; do
        path=$(target "$name")
        if [ "$name" = battery.js ]; then [ ! -e "$path" ] && [ ! -L "$path" ] || exit 1;
        else matches "$(before "$name")" "$path" || exit 1; fi
        replace_asset "$name" "$name"
        matches "$(after "$name")" "$path"
    done
    sync
    printf 'INSTALLED\n' > STATUS
    committed=yes
    echo 'DASHBOARD-AB-INSTALL=PASS Pi A/B + homepage battery; no service, media, key or mount changes.';;
 rollback)
    [ -d transaction-lock ] && [ ! -L transaction-lock ] || exit 1
    mkdir -m 700 rollback-lock || exit 1
    [ -f STATUS ] && [ ! -L STATUS ] && [ "$(cat STATUS)" = INSTALLED ] || exit 1
    saved_backups_ok
    # Refuse all changes before restoring anything if a later edit is present.
    for name in $NAMES; do matches "$(after "$name")" "$(target "$name")" || exit 1; done
    restore_owned_changes || exit 1
    sync
    printf 'ROLLED-BACK\n' > STATUS
    echo 'DASHBOARD-AB-ROLLBACK=PASS original assets restored; private backups retained.';;
 *) echo 'Use --check, install or rollback'; exit 2;;
esac
'''.replace('BEFORE_CASES',cases(before)).replace('AFTER_CASES',cases(after))


def build(output):
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or output.exists():raise ValueError('Refusing existing/symlink output.')
    files=payload()
    if set(files)!=set(NAMES) or any(len(data)>131072 for data in files.values()):raise ValueError('Unexpected UI inventory/budget.')
    after={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    files['install.sh']=installer(BEFORE,after).encode()
    report={'schema':'nimbus-dashboard-ab/v1','status':'prepared/not installed','device_stage':STAGE,
            'before':BEFORE,'after':after,'root_files_changed':5,'main_homepage_changed':False,
            'raw_firmware_write':False,'storage_mode_change':False,'service_change':False,
            'battery_source':'read-only vendor getBatteryLevel','telemetry_missing':'USB ownership/publisher absence is reported, not replaced with fake snapshots',
            'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    files['MANIFEST.json']=(json.dumps(report,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                for name,data in sorted(files.items()):
                    member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.uid=member.gid=0;member.mtime=1767225600
                    archive.addfile(member,io.BytesIO(data))
    if output.stat().st_size>131072:raise ValueError('UI package exceeds budget; retain failed artifact.')
    return {'archive_bytes':output.stat().st_size,'archive_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),**report}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=build(args.output)
    except (OSError,ValueError):parser.error('UI build refused; no device changed.')
    print(json.dumps({'bytes':report['archive_bytes'],'sha256':report['archive_sha256'],'status':'prepared/not installed'},indent=2))
