#!/bin/sh
# Metadata-only beta checkpoint. No signals, mounts, updater or watchdog probes.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
[ "$(id -u)" = 0 ] || { echo 'Authorized root session required.'; exit 1; }
echo 'BETA CAPTURE CHECKPOINT — INVENTORY ONLY; NOT WRITE/FLASH APPROVAL'
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || {
    echo 'USB export active or state unavailable; stop.'; exit 1;
}
[ -r /proc/self/mountinfo ] && [ -r /sys/class/block/mmcblk0p2/dev ] || exit 1
checkpoint_root=$(awk '$5 == "/" && index($0, " - ext3 ") {print $3}' /proc/self/mountinfo)
[ "$checkpoint_root" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || {
    echo 'Expected internal root identity not established; stop.'; exit 1;
}
echo 'Expected ext3 root identity: confirmed; USB export: inactive'
echo 'Power metadata (not proof of uninterrupted external power):'
for checkpoint_field in /sys/class/power_supply/mc13892_charger/online \
    /sys/class/power_supply/mc13892_bat/status \
    /sys/class/power_supply/mc13892_bat/capacity; do
    if [ -r "$checkpoint_field" ]; then
        checkpoint_value=$(cat "$checkpoint_field")
        case "$checkpoint_value" in
            ''|*[!A-Za-z0-9\ -]*) checkpoint_value=unrecognized;;
        esac
        printf '%s/%s: %s\n' "$(basename "$(dirname "$checkpoint_field")")" "${checkpoint_field##*/}" "$checkpoint_value"
    else
        printf '%s/%s: unavailable\n' "$(basename "$(dirname "$checkpoint_field")")" "${checkpoint_field##*/}"
    fi
done
echo 'Listening entries (counts only; not ownership or authentication proof):'
for checkpoint_port in 08B0 08B1; do
    checkpoint_count=0
    for checkpoint_table in /proc/net/tcp /proc/net/tcp6; do
        [ -r "$checkpoint_table" ] || continue
        checkpoint_n=$(awk -v port="$checkpoint_port" '$4 == "0A" && $2 ~ (":" port "$") {n++} END {print n+0}' "$checkpoint_table")
        checkpoint_count=$((checkpoint_count + checkpoint_n))
    done
    case "$checkpoint_port" in 08B0) checkpoint_number=2224;; 08B1) checkpoint_number=2225;; esac
    printf 'Port %s: %s listening entries\n' "$checkpoint_number" "$checkpoint_count"
done
echo 'Temporary listener staging metadata only (no log/key contents):'
checkpoint_stage=/tmp/nimbus-capture-ssh-v1
if [ -d "$checkpoint_stage" ] && [ ! -L "$checkpoint_stage" ]; then
    stat -c 'Stage uid:gid:mode=%u:%g:%a' "$checkpoint_stage" || exit 1
    # File names come from the reviewed launcher; never enumerate private paths.
    for checkpoint_name in listener.log listener.pid; do
        checkpoint_file="$checkpoint_stage/$checkpoint_name"
        if [ -f "$checkpoint_file" ] && [ ! -L "$checkpoint_file" ]; then
            printf '%s ' "$checkpoint_name"
            stat -c 'uid:gid:mode=%u:%g:%a bytes=%s' "$checkpoint_file" || exit 1
        else
            printf '%s: unavailable or unsafe\n' "$checkpoint_name"
        fi
    done
else
    echo 'Stage unavailable or unsafe; do not recreate blindly.'
fi
echo 'No stop/restart, signal, sync, remount, block read/write, environment helper, watchdog open or reboot performed.'
echo 'Run the separate root-writer inventory next; retain both listeners.'
