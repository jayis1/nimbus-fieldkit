#!/bin/sh
# Read-only precondition for toolkit writes, never an ownership-transition tool.
set -u
PROC=${NIMBUS_PROC_DIR:-/proc}
fail() { printf '%s\n' "$1" >&2; exit 2; }
[ "$#" -eq 2 ] || fail 'Usage: check-write|check-read ABSOLUTE_PATH (no action performed)'
case "$1" in check-write|check-read) mode=$1;; *) fail 'Unknown media check; no action performed';; esac
path=$2
case "$path" in
    /*) :;; *) fail 'Use an absolute destination path';;
esac
case "$path" in
    *//*|*/./*|*/../*|*/.|*/..|*\\*) fail 'Noncanonical destination path';;
esac
case "$path" in /) :;; */) fail 'Use canonical paths without a trailing slash';; esac
parent=$path
while [ "$parent" != / ]; do
    [ ! -L "$parent" ] || fail 'Symlink destination component'
    parent=$(dirname "$parent") || fail 'Cannot inspect destination path'
done
case "$path" in
    /mnt/storage|/mnt/storage/*) media=/mnt/storage; source=/dev/mmcblk0p4;;
    /mnt/sdcard|/mnt/sdcard/*) media=/mnt/sdcard; source=/dev/mmcblk1p1;;
    /mnt|/mnt/*|/storage|/storage/*|/sdcard|/sdcard/*|/var/ftp/storage|/var/ftp/storage/*|/var/ftp/sdcard|/var/ftp/sdcard/*)
        fail 'Unmanaged or public media alias destination';;
    *)
        # A bind/alternate mount of the known media devices must not bypass
        # policy just because a caller uses a different destination prefix.
        if [ -r "$PROC/mounts" ]; then
            awk -v path="$path" '
                ($1=="/dev/mmcblk0p4" || $1=="/dev/mmcblk1p1") &&
                (path==$2 || index(path,$2 "/")==1) {bad=1}
                END {exit bad}
            ' "$PROC/mounts" || fail 'Unmanaged mount alias of a known media device'
        fi
        printf '%s\n' 'MEDIA-WRITE-GUARD=PASS non-media-path (not a writability/privacy guarantee)'; exit 0;;
esac
[ -d "$media" ] && [ ! -L "$media" ] || fail 'Media mount directory absent or unsafe; never create a substitute'
[ -r "$PROC/modules" ] && [ -f "$PROC/modules" ] && [ ! -L "$PROC/modules" ] || fail 'USB export inventory unavailable'
awk '
    $1 ~ /^g_/ || $1=="usb_f_mass_storage" {bad=1}
    NF<6 || $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ {bad=1}
    END {exit bad}
' "$PROC/modules" || fail 'USB storage export loaded or inventory malformed; refuse local media access'
# /proc/mounts is legitimately a procfs symlink on Linux; do not reject that
# kernel alias. PROC is an explicit fixture override, not an untrusted API input.
[ -r "$PROC/mounts" ] && [ -f "$PROC/mounts" ] || fail 'Mount inventory unavailable'
# One expected mount, supported filesystem, explicit rw without ro. Refuse
# nested mounts and aliases along the selected path, not merely a matching row.
awk -v media="$media" -v source="$source" -v path="$path" -v mode="$mode" '
    $2==media {
        count++
        rw=($4 ~ /(^|,)rw(,|$)/); ro=($4 ~ /(^|,)ro(,|$)/)
        if($1!=source || $3 !~ /^(texfat|vfat|exfat|ext3)$/ || rw==ro ||
           (mode=="check-write" && !rw)) bad=1
    }
    $2!=media && index($2,media "/")==1 &&
        (path==$2 || index(path,$2 "/")==1) {bad=1}
    END {exit count!=1 || bad}
' "$PROC/mounts" || fail 'Media mount missing, read-only, changed or ambiguous'
printf '%s\n' 'MEDIA-WRITE-GUARD=PASS observed-local-access (not a lifecycle lock)'
