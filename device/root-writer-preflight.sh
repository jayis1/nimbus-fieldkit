#!/bin/sh
# Metadata only: do not open fd targets, invoke services or alter mounts.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
[ "$(id -u)" = 0 ] || { echo 'Use the authorized root SSH session.'; exit 1; }
echo 'ROOT WRITE HOLDERS — READ ONLY; NO REMOUNT AUTHORIZATION'
for tool in stat awk; do
    command -v "$tool" >/dev/null 2>&1 || { echo 'Required metadata tool unavailable'; exit 1; }
done
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || {
    echo 'USB export active or state unavailable; stop review'; exit 1;
}
[ -r /proc/self/mountinfo ] && [ -r /sys/class/block/mmcblk0p2/dev ] || {
    echo 'Root identity metadata unavailable'; exit 1;
}
mount_device=$(awk '$5 == "/" && index($0, " - ext3 ") {print $3}' /proc/self/mountinfo)
[ "$mount_device" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || {
    echo 'Expected internal ext3 root identity not established'; exit 1;
}
root_device=$(stat -c '%d' /) || exit 1
case "$root_device" in ''|*[!0-9]*) echo 'Invalid root device metadata'; exit 1;; esac
major=${mount_device%:*}; minor=${mount_device#*:}
case "$major:$minor" in *[!0-9:]*|:*) echo 'Invalid mount device metadata'; exit 1;; esac
map_device=$(printf '%02x:%02x' "$major" "$minor") || exit 1
holders=0; descriptors=0; mappings=0; incomplete=0
for process in /proc/[0-9]*; do
    [ -d "$process/fd" ] || continue
    pid=${process##*/}
    writable=0; shared=0
    for fd in "$process"/fd/[0-9]*; do
        [ -L "$fd" ] && [ -f "$fd" ] || continue
        device=$(stat -L -c '%d' "$fd" 2>/dev/null) || { incomplete=$((incomplete + 1)); continue; }
        [ "$device" = "$root_device" ] || continue
        info="$process/fdinfo/${fd##*/}"
        if [ ! -r "$info" ]; then incomplete=$((incomplete + 1)); continue; fi
        flags=$(awk '$1 == "flags:" {print $2}' "$info" 2>/dev/null)
        case "$flags" in ''|*[!0-7]*) incomplete=$((incomplete + 1)); continue;; esac
        # fdinfo encodes flags in octal; prefix zero also handles unpadded values.
        access=$((0$flags & 3))
        case "$access" in 1|2) writable=$((writable + 1));; esac
    done
    if [ -r "$process/maps" ]; then
        shared=$(awk -v dev="$map_device" '$4 == dev && $2 ~ /^.w.s$/ {n++} END {print n+0}' "$process/maps" 2>/dev/null) || {
            incomplete=$((incomplete + 1)); shared=0;
        }
    else
        incomplete=$((incomplete + 1))
    fi
    if [ "$writable" -gt 0 ] || [ "$shared" -gt 0 ]; then
        # Whitelist labels only; never echo arbitrary comm, argv or fd/map paths.
        label=other
        if [ -r "$process/comm" ]; then
            comm=$(cat "$process/comm" 2>/dev/null) || comm=unknown
            case "$comm" in
                event_manager|fw_server|nimbus|dropbear|dropbearmulti-b|syslogd|klogd|crond|sh|ash|bash|pure-ftpd|minidlna|avahi-daemon)
                    label=$comm;;
            esac
        fi
        printf 'pid=%s label=%s writable_root_fds=%s shared_writable_root_mappings=%s\n' "$pid" "$label" "$writable" "$shared"
        holders=$((holders + 1)); descriptors=$((descriptors + writable)); mappings=$((mappings + shared))
    fi
done
printf 'Observed holder processes: %s; writable root fds: %s; shared writable root mappings: %s\n' "$holders" "$descriptors" "$mappings"
printf 'Incomplete/raced metadata observations: %s\n' "$incomplete"
echo 'File paths, map addresses, process arguments and arbitrary process names suppressed.'
echo 'Selected service-script hashes ONLY (scripts read as data, never sourced/executed):'
for script in /etc/rc.d/init.d/nimbus-service \
    /etc/rc.d/init.d/service/S00eventmanager \
    /etc/rc.d/init.d/service/S15fwserver \
    /etc/rc.d/init.d/service/S20nimbus; do
    if [ -f "$script" ] && [ ! -L "$script" ]; then
        sha256sum "$script"
    else
        printf 'Selected service-script unavailable: %s\n' "${script##*/}"
    fi
done
echo 'This scan is racy and not an exhaustive remount eligibility test; zero holders does not certify safety.'
echo 'No service stop, signal, sync, remount, repair, watchdog open or reboot performed.'
