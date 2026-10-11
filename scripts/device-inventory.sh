#!/bin/sh
# Run on the device only through existing authorized shell access.
# Read-only; stdout only. No probing, mounting, installing, or flash writes.
set -u
section() { printf '\n### %s\n' "$1"; }
show() {
    if [ -r "$1" ]; then cat "$1"; else printf 'Unavailable: %s\n' "$1"; fi
}
section 'Kernel'
uname -a
section 'CPU'
show /proc/cpuinfo
section 'Memory'
show /proc/meminfo
section 'Boot command line (review before sharing)'
show /proc/cmdline
section 'MTD layout'
show /proc/mtd
section 'Block devices'
show /proc/partitions
section 'Mounted filesystems'
show /proc/mounts
section 'Loaded modules'
show /proc/modules
section 'Network counters'
show /proc/net/dev
section 'Wireless status'
show /proc/net/wireless
section 'Interfaces and drivers'
for interface in /sys/class/net/*; do
    [ -e "$interface" ] || continue
    printf '\n%s\n' "$interface"
    if command -v readlink >/dev/null 2>&1; then readlink "$interface/device/driver" || :; fi
done
section 'Available tools'
for tool in busybox python3 python ip iw iwconfig hostapd tcpdump sha256sum dropbear; do
    command -v "$tool" || :
done
section 'Power supplies'
for supply in /sys/class/power_supply/*; do
    [ -d "$supply" ] || continue
    printf '\n%s\n' "$supply"
    for property in type status capacity voltage_now; do
        [ ! -r "$supply/$property" ] || { printf '%s: ' "$property"; cat "$supply/$property"; }
    done
done
