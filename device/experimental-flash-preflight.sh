#!/bin/sh
# Read-only inventory for an experimental single-device deployment review.
# No mounts, block writes, config changes, firmware helpers or reboot commands.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
errors=0
reject() { printf 'FAIL: %s\n' "$1"; errors=$((errors + 1)); }
[ "$(id -u)" = 0 ] || { echo 'Run in your authorized root SSH session.'; exit 1; }
printf '%s\n' 'EXPERIMENTAL PREFLIGHT — READ ONLY; NOT FLASH AUTHORIZATION'
printf 'Kernel: '; uname -r
architecture=$(uname -m)
printf 'Architecture: %s\n' "$architecture"
case "$architecture" in armv7l) :;; *) reject 'Unexpected hardware architecture';; esac
if [ ! -r /proc/modules ]; then
    reject 'Cannot inspect USB export state'
elif grep -q '^g_file_storage ' /proc/modules; then
    reject 'USB storage export active; do not deploy'
else
    echo 'USB storage export: inactive'
fi

check_partition() {
    name="$1"; expected_start="$2"; expected_size="$3"
    if [ ! -b "/dev/$name" ] || [ ! -r "/sys/class/block/$name/start" ] ||
       [ ! -r "/sys/class/block/$name/size" ]; then
        reject "Missing expected partition metadata: $name"
        return
    fi
    start=$(cat "/sys/class/block/$name/start")
    size=$(cat "/sys/class/block/$name/size")
    printf '%s start=%s sectors=%s\n' "$name" "$start" "$size"
    [ "$start" = "$expected_start" ] && [ "$size" = "$expected_size" ] ||
        reject "Partition boundary differs from reviewed layout: $name"
}
check_partition mmcblk0p1 30720 8192
check_partition mmcblk0p2 38912 524288
check_partition mmcblk0p3 563200 409600
check_partition mmcblk0p4 972800 121169920
if [ -r /sys/class/block/mmcblk0/size ]; then
    total=$(cat /sys/class/block/mmcblk0/size)
    printf 'Internal disk sectors: %s\n' "$total"
    [ "$total" = 122142720 ] || reject 'Whole-disk size differs from reviewed device'
else
    reject 'Internal disk size unavailable'
fi

printf '%s\n' 'Root filesystem mount (no files read):'
if [ -r /proc/mounts ]; then
    awk '$2 == "/" && $3 != "rootfs" {print $1, $2, $3, $4}' /proc/mounts
    awk '$2 == "/" && $3 == "ext3" {found=1} END {exit !found}' /proc/mounts ||
        reject 'Expected ext3 root mount not established'
else
    reject 'Cannot inspect mounts'
fi

printf '%s\n' 'Power evidence (not a stable-power certification):'
if [ -r /sys/class/power_supply/mc13892_charger/online ]; then
    online=$(cat /sys/class/power_supply/mc13892_charger/online)
    printf 'External power online: %s\n' "$online"
    case "$online" in 0|1) :;; *) reject 'Invalid power indication';; esac
else
    reject 'Power state unavailable'
fi
for supply in /sys/class/power_supply/*; do
    [ -r "$supply/type" ] || continue
    [ "$(cat "$supply/type")" = Battery ] || continue
    for field in capacity status voltage_now; do
        [ ! -r "$supply/$field" ] || { printf 'Battery %s: ' "$field"; cat "$supply/$field"; }
    done
done
printf '%s\n' 'Firmware services (no arguments/credentials shown):'
ps -A | grep -E 'event_manager|fw_server' || :
printf 'Inventory failures: %s\n' "$errors"
printf '%s\n' 'Fresh private backups, reviewed package/write path and explicit trial review still required.' \
    'Unbricking is not guaranteed. This script never certifies production readiness.'
[ "$errors" -eq 0 ]
