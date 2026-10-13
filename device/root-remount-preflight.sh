#!/bin/sh
# Read-only metadata/dependency review. NEVER invokes mount or changes services.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
fail() { echo "$1"; exit 1; }
[ "$#" -eq 0 ] || fail 'No action arguments accepted; inventory only'
[ "$(id -u)" = 0 ] || fail 'Authorized root session required'
connection=${SSH_CONNECTION-}
[ "${connection##* }" = 2225 ] || fail 'Use the independently verified port-2225 connection'
echo 'ROOT REMOUNT DEPENDENCIES — INVENTORY ONLY; NO MOUNT AUTHORIZATION'
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || fail 'USB export active or unknown'
root_major_minor=$(awk '$5=="/" && index($0," - ext3 ") {n++; dev=$3} END {if(n==1) print dev; else exit 1}' /proc/self/mountinfo) || fail 'Root identity ambiguous'
[ "$root_major_minor" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || fail 'Unexpected root device'
root_source=$(awk '$2=="/" && $3=="ext3" {n++; source=$1} END {if(n==1) print source; else exit 1}' /proc/mounts) || fail 'Root mount record ambiguous'
case "$root_source" in /dev/root|/dev/mmcblk0p2) :;; *) fail 'Unreviewed root source';; esac
root_options=$(awk '$2=="/" && $3=="ext3" {print $4}' /proc/mounts)
# Only known non-secret root options may be printed. New flags require review.
case ",$root_options," in *,rw,*) :;; *) fail 'Root is not writable';; esac
options_tail=$root_options
while [ -n "$options_tail" ]; do
    option=${options_tail%%,*}
    case "$option" in rw|relatime|noatime|nodiratime|nosuid|nodev|noexec|sync|dirsync|errors=continue|errors=remount-ro|errors=panic|barrier=0|barrier=1|data=writeback|data=ordered|data=journal) :;; *) fail 'Unreviewed root option; suppressed';; esac
    case "$options_tail" in *,*) options_tail=${options_tail#*,};; *) options_tail='';; esac
done
printf 'Root device identity: matched; source=%s; options=%s\n' "$root_source" "$root_options"
awk '$2=="/tmp" && $3=="tmpfs" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts || fail 'Writable tmpfs not established'
[ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power not detected'
echo 'External power detected; USB export inactive; root/tmp writable'
for directory in /bin /etc; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'Unsafe utility directory'
done
verify_tool() {
    [ -f "$1" ] && [ -x "$1" ] && [ ! -L "$1" ] || fail 'Expected regular utility unavailable'
    [ "$(stat -c '%u:%g' "$1")" = 0:0 ] || fail 'Unexpected utility ownership'
    printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null || fail 'Utility hash differs from offline review'
    printf 'utility=%s sha256=matched\n' "${1##*/}"
}
verify_tool /bin/mount 5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be
verify_tool /bin/busybox aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c
if [ -L /etc/mtab ]; then
    target=$(readlink /etc/mtab)
    case "$target" in /proc/mounts|../proc/mounts|/proc/self/mounts) echo 'mtab=recognized proc symlink';; *) fail 'Unreviewed mtab symlink target; suppressed';; esac
elif [ -f /etc/mtab ]; then
    echo 'mtab=regular file; contents not read; future trial must suppress table updates'
elif [ ! -e /etc/mtab ]; then
    echo 'mtab=absent; future trial must suppress table creation'
else fail 'Unreviewed mtab path type'; fi
df -k /tmp
echo 'No mount command, service signal, sync, remount, watchdog access, raw partition read/write or reboot performed'
