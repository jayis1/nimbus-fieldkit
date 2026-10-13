#!/bin/sh
# Read-only UI/publisher-path inventory. No staging, publish, service or mount action.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
[ "$#" = 1 ] && [ "$1" = --check ] || exit 2
[ "$(id -u)" = 0 ] || exit 1
printf 'ROOT MOUNT:\n'
awk '$2=="/" {print}' /proc/mounts
printf 'UI BASELINES:\n'
for name in fieldkit-v06/toolkit.html fieldkit-v06/toolkit.js fieldkit-v06/toolkit.css fieldkit-performance-r1/bridge.js; do
    path=/nimbus/data/$name
    if [ -f "$path" ] && [ ! -L "$path" ]; then
        stat -c '%u:%g:%a:%s' "$path"
        sha256sum "$path"
    else printf 'Missing/nonregular/symlink UI target: %s\n' "$name"; fi
done
printf 'KNOWN PUBLISHER LOCATIONS (metadata/hash only; no snapshot contents):\n'
for base in /mnt/storage/nimbus-unified-v05/native /mnt/storage/nimbus-unified-v06/native /mnt/storage/nimbus-fieldkit-v04 /mnt/storage/nimbus-fieldkit-v03; do
    printf 'Location: %s\n' "$base"
    if [ ! -d "$base" ] || [ -L "$base" ]; then
        printf 'Missing or symlink directory\n'
        continue
    fi
    for name in nimbus-dashboard.sh nimbus-settings.sh dashboard/snapshot.awk dashboard/state.json; do
        path=$base/$name
        if [ -f "$path" ] && [ ! -L "$path" ]; then
            stat -c '%u:%g:%a:%s' "$path"
            sha256sum "$path"
        else printf 'Missing/nonregular/symlink: %s\n' "$name"; fi
    done
done
printf 'FREE SPACE:\n'
df -k /tmp /mnt/storage
printf 'Check-only complete: no files written, publisher started, services or mounts changed.\n'
