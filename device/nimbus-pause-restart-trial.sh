#!/bin/sh
# Explicitly approved vendor-only pause/restart. No root remount or SSH handover.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
trial_stage=/tmp/nimbus-pause-restart-v1
service=/etc/rc.d/init.d/service/S20nimbus
vendor_hash=b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd
fail() { echo "$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Authorized root session required'
[ "$(CDPATH= cd "$(dirname "$0")" && pwd -P)" = "$trial_stage" ] || fail 'Wrong private staging directory'
for dir in /tmp "$trial_stage" /etc /etc/rc.d /etc/rc.d/init.d /etc/rc.d/init.d/service /opt /opt/qsi /opt/qsi/config /nimbus; do
    [ -d "$dir" ] && [ ! -L "$dir" ] || fail 'Unsafe required directory'
done
[ "$(stat -c '%u:%g:%a' "$trial_stage")" = 0:0:700 ] || fail 'Unsafe staging permissions'
cd "$trial_stage"
sha256sum -c SHA256SUMS >/dev/null || fail 'Trial source checksum mismatch'
mode=${1:---check}
case "$mode" in --check|--start|--worker) :;; *) fail 'Use --check or --start';; esac
root_rw() {
    [ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules &&
    [ "$(awk '$5=="/" && index($0," - ext3 ") {print $3}' /proc/self/mountinfo)" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] &&
    awk '$2=="/" && $3=="ext3" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts &&
    awk '$2=="/tmp" && $3=="tmpfs" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts
}
root_rw || fail 'Expected writable root/tmpfs or inactive USB export not established'
[ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power not detected'
verify_input() {
    [ -f "$1" ] && [ ! -L "$1" ] || fail 'Restart input unavailable or unsafe'
    printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null || fail 'Restart input hash mismatch'
}
restart_inputs() {
    verify_input "$service" 2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3
    verify_input /opt/qsi/config/nimbus.conf 6a32518bd0e5f024a766a8cfb3f722dc4752b952b4ce629ed27fcc8bca4293f5
    verify_input /opt/qsi/config/develop.conf 970a00795c0464a7e97b44d6b50d5bd9dbe6f851d51c7408b55cd058e3c93664
    verify_input /opt/qsi/config/platform_functions 16bcf3ec02fc8a660256bfa37674d6dfd5ef786345d7c2ff624cf1c2b030e136
    verify_input /nimbus/nimbus "$vendor_hash"
}
restart_inputs
if [ "$mode" = --start ]; then
    [ ! -e started ] && [ ! -L started ] && [ ! -e worker.log ] && [ ! -L worker.log ] || fail 'Prior trial exists; do not rerun'
    # Detached worker performs fresh identity checks immediately before its signal.
    (set -C; printf 'approved vendor-only trial\n' > started)
    (set -C; : > worker.log)
    nohup setsid sh "$trial_stage/trial.sh" --worker </dev/null >>worker.log 2>&1 &
    echo 'Detached vendor-only trial launched; both SSH listeners remain running.'
    tries=0
    while [ "$tries" -lt 30 ] && [ ! -f RESULT ]; do tries=$((tries+1)); sleep 1; done
    if [ -f RESULT ] && [ ! -L RESULT ]; then
        result=$(cat RESULT); printf 'Trial result: %s\n' "$result"
        [ "$result" = PASS ] || exit 1
        exit 0
    fi
    echo 'No final result yet; inspect retained stage. Do not rerun or launch another restart.'
    exit 2
fi
if [ "$mode" = --worker ]; then
    [ -f started ] && [ ! -L started ] && [ ! -e RESULT ] && [ ! -L RESULT ] || fail 'Worker not launched from fresh approved stage'
fi
# Source only the checksum-verified FIRST-PARTY read-only inventory, not vendor code.
. "$trial_stage/identity.sh"
trial_vendor=$vendor
trial_old=$old
trial_replacement=$replacement
trial_stamp=$(start_time "$trial_vendor")
trial_old_stamp=$(start_time "$trial_old")
trial_replacement_stamp=$(start_time "$trial_replacement")
find_vendor() {
    found_vendor=''
    for process in /proc/[0-9]*; do
        [ -r "$process/comm" ] || continue
        [ "$(cat "$process/comm" 2>/dev/null || :)" = nimbus ] || continue
        [ -z "$found_vendor" ] || return 1
        found_vendor=${process##*/}
    done
}
vendor_valid() {
    [ "$(readlink "/proc/$1/exe" 2>/dev/null || :)" = /nimbus/nimbus ] &&
    printf '%s  %s\n' "$vendor_hash" "/proc/$1/exe" | sha256sum -c - >/dev/null
}
listeners_unchanged() {
    [ "$(start_time "$trial_old" 2>/dev/null || :)" = "$trial_old_stamp" ] &&
    [ "$(start_time "$trial_replacement" 2>/dev/null || :)" = "$trial_replacement_stamp" ] &&
    socket_owned "$trial_old" 08B0 && socket_owned "$trial_replacement" 08B1
}
# Reject a vendor with children, unknown writable root files or writable mappings.
for status in /proc/[0-9]*/status; do
    [ -r "$status" ] || continue
    [ "$(awk '$1=="PPid:" {print $2}' "$status" 2>/dev/null || :)" != "$trial_vendor" ] || fail 'Vendor has children; stop review'
done
root_dev=$(stat -c '%d' /)
settings_fds=0
for fd in "/proc/$trial_vendor"/fd/[0-9]*; do
    [ -L "$fd" ] && [ -f "$fd" ] || continue
    [ "$(stat -L -c '%d' "$fd")" = "$root_dev" ] || continue
    flags=$(awk '$1=="flags:" {print $2}' "/proc/$trial_vendor/fdinfo/${fd##*/}")
    case "$flags" in ''|*[!0-7]*) fail 'Descriptor metadata incomplete';; esac
    access=$((0$flags & 3))
    case "$access" in 1|2)
        [ "$(readlink "$fd")" = /nimbus/settings.db ] || fail 'Unexpected writable root file'
        settings_fds=$((settings_fds+1));;
    esac
done
[ "$settings_fds" -eq 1 ] || fail 'Expected single settings database writer not established'
map_dev=$(cat /sys/class/block/mmcblk0p2/dev)
map_hex=$(printf '%02x:%02x' "${map_dev%:*}" "${map_dev#*:}")
awk -v dev="$map_hex" '$4==dev && $2 ~ /^.w.s$/ {bad=1} END {exit bad}' "/proc/$trial_vendor/maps" || fail 'Vendor shared writable root mapping observed'
[ ! -L /tmp/comm.socket ] && { [ ! -e /tmp/comm.socket ] || [ -S /tmp/comm.socket ]; } || fail 'Unexpected communication socket path type'
socket_owned "$trial_vendor" 0050 || fail 'Vendor does not own expected HTTP listener; stop review'
if [ "$mode" = --check ]; then echo 'Check-only passed; no process signalled or service executed.'; exit 0; fi
paused=no
restart_requested=no
finish_result=FAIL
restore_vendor() {
    find_vendor || { echo 'Ambiguous vendor processes; no duplicate restart'; return 1; }
    if [ -n "$found_vendor" ]; then
        vendor_valid "$found_vendor" || return 1
        socket_owned "$found_vendor" 0050 || return 1
        echo 'Vendor process present; no duplicate restart requested'
        return 0
    fi
    [ "$restart_requested" = no ] || { echo 'Restart already requested; not retried'; return 1; }
    root_rw || { echo 'Root/USB state changed; no blind restart'; return 1; }
    restart_inputs
    [ ! -L /tmp/comm.socket ] && { [ ! -e /tmp/comm.socket ] || [ -S /tmp/comm.socket ]; } || return 1
    restart_requested=yes
    # Only reviewed start action. Never the stock unbounded stop/reload loop.
    sh "$service" start </dev/null >/dev/null 2>&1 &
    echo 'Reviewed vendor start requested once'
    tries=0
    while [ "$tries" -lt 15 ]; do
        if find_vendor && [ -n "$found_vendor" ] && vendor_valid "$found_vendor" && socket_owned "$found_vendor" 0050; then
            echo 'Expected vendor executable and HTTP listener observed'
            return 0
        fi
        tries=$((tries+1)); sleep 1
    done
    echo 'Vendor HTTP recovery not verified; do not blindly rerun'
    return 1
}
cleanup() {
    trap - EXIT HUP INT TERM
    if [ "$paused" = yes ]; then
        if restore_vendor && root_rw && listeners_unchanged; then
            echo 'Vendor present; root still writable; both original listener identities retained'
        else finish_result=FAIL; echo 'Recovery requires review through retained SSH; no force/reboot attempted'; fi
    fi
    (set -C; printf '%s\n' "$finish_result" > "$trial_stage/RESULT") || :
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
root_rw && listeners_unchanged || fail 'State changed before signal'
find_vendor && [ "$found_vendor" = "$trial_vendor" ] && vendor_valid "$trial_vendor" &&
[ "$(start_time "$trial_vendor")" = "$trial_stamp" ] || fail 'Vendor identity changed before signal'
paused=yes
echo 'Requesting TERM for freshly verified vendor process only'
kill -TERM "$trial_vendor"
tries=0
while [ -r "/proc/$trial_vendor/stat" ] && [ "$(start_time "$trial_vendor" 2>/dev/null || :)" = "$trial_stamp" ]; do
    [ "$tries" -lt 10 ] || fail 'Vendor did not exit within observation window; no forced signal'
    tries=$((tries+1)); sleep 1
done
find_vendor || fail 'Ambiguous vendor state after TERM'
[ -z "$found_vendor" ] || fail 'Autonomous vendor restart observed; quiescence not established'
echo 'Original vendor process exited; no vendor process currently observed'
sleep 2
root_rw && listeners_unchanged || fail 'State changed during vendor pause'
restore_vendor || fail 'Restart observation failed'
finish_result=PASS
echo 'Pause/restart process and HTTP-listener trial completed; browser/API/database correctness still requires user validation'
