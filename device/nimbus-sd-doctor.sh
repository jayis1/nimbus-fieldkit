#!/bin/sh
# Read-only SD inventory. Never mounts, repairs, formats, or writes the card.
set -u
if [ "$#" -ne 0 ]; then
    printf '%s\n' 'Diagnostic takes no arguments; no action was performed.' >&2
    exit 2
fi
printf '%s\n' '=== SD mount ==='
awk '$2 == "/mnt/sdcard" || $2 == "/var/ftp/sdcard" {print "source=" $1, "mount=" $2, "filesystem=" $3, "options=" $4}' /proc/mounts
source=$(awk '$2 == "/mnt/sdcard" {print $1; exit}' /proc/mounts)
printf '%s\n' '=== USB export ==='
if [ ! -r /proc/modules ]; then
    printf '%s\n' 'USB export state unknown; do not change mounts.'
elif grep -q '^g_file_storage ' /proc/modules; then
    printf '%s\n' 'USB export active; do not mount or write local media.'
else
    printf '%s\n' 'g_file_storage absent in this observation; this alone does not authorize writes.'
fi
printf '%s\n' '=== Block devices (KiB) ==='
cat /proc/partitions
printf '%s\n' '=== SD capacity and read-only flags ==='
if [ -n "$source" ]; then
    name=${source##*/}
    case "$name" in
        mmcblk[0-9]*|sd[a-z][0-9]*)
            for field in size ro; do
                file="/sys/class/block/$name/$field"
                if [ -r "$file" ]; then
                    printf '%s=' "$field"; cat "$file"
                else
                    printf '%s=unknown\n' "$field"
                fi
             done;;
    esac
    df -k /mnt/sdcard
else
    printf '%s\n' 'SD mount absent. Do not assume the internal media device is the SD card.'
fi
printf '%s\n' '=== Recent SD/storage kernel messages ==='
dmesg | grep -iE 'mmc|sdhci|texfat|exfat|fat-fs|write.protect|I/O error' | tail -n 60
printf '%s\n' 'Diagnostic only. 128GB decimal is about 119GiB; that capacity is normal.' \
    'Block ro=0 does not mean the filesystem is writable. Main and FTP mounts can differ.' \
    'A runtime rw mount does not establish writable boot/USB-return policy.' \
    'No forced rw remount, fsck, formatter, partition changes or firmware updates were run.'
