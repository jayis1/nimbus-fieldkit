#!/bin/sh
# Management-only trial. Requires separate approval; never remounts or stops Nimbus.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
trial_stage=/tmp/nimbus-ssh-handover-trial-v2
readonly trial_stage
base=/root/nimbus-ssh-test
launcher="$base/startup-v1/start-ssh.sh"
binary="$base/dropbearmulti-bound"
ssh_hash=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c
launcher_hash=173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41
vendor_hash=b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd
fail() { echo "$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Authorized root session required'
[ "$#" -le 1 ] || fail 'Use --check or --start'
mode=${1:---check}
case "$mode" in --check|--start|--worker) :;; *) fail 'Use --check or --start';; esac
# A 2224 session would itself inherit the root log and be a stop dependency.
connection=${SSH_CONNECTION-}
[ "${connection##* }" = 2225 ] || fail 'Run only through the independently verified port-2225 session'
[ "$(CDPATH= cd "$(dirname "$0")" && pwd -P)" = "$trial_stage" ] || fail 'Wrong private stage'
for directory in /tmp "$trial_stage" /root "$base" "$base/startup-v1" "$base/auth"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'Unsafe required directory'
done
for directory in "$trial_stage" "$base" "$base/auth"; do
    [ "$(stat -c '%u:%g:%a' "$directory")" = 0:0:700 ] || fail 'Unsafe private directory metadata'
done
cd "$trial_stage"
sha256sum -c SHA256SUMS >/dev/null || fail 'Trial source checksum mismatch'
for tool in nohup setsid stat sha256sum awk; do
    command -v "$tool" >/dev/null || fail 'Required tool unavailable'
done
root_rw() {
    [ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules &&
    [ "$(awk '$5=="/" && index($0," - ext3 ") {print $3}' /proc/self/mountinfo)" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] &&
    awk '$2=="/" && $3=="ext3" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts &&
    awk '$2=="/tmp" && $3=="tmpfs" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts
}
private_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%g:%a' "$1")" = 0:0:600 ]
}
restart_inputs() {
    [ -f "$launcher" ] && [ ! -L "$launcher" ] && [ "$(stat -c '%u:%g:%a' "$launcher")" = 0:0:700 ] &&
    [ -f "$binary" ] && [ -x "$binary" ] && [ ! -L "$binary" ] &&
    printf '%s  %s\n' "$launcher_hash" "$launcher" | sha256sum -c - >/dev/null || return 1
    printf '%s  %s\n' "$ssh_hash" "$binary" | sha256sum -c - >/dev/null || return 1
    private_file "$base/host-ed25519" && [ -s "$base/host-ed25519" ] &&
    private_file "$base/auth/authorized_keys" && [ -s "$base/auth/authorized_keys" ] &&
    private_file "$base/boot.log" && [ -d /sys/class/net/wlan1 ]
}
root_rw || fail 'Expected writable root/tmpfs or inactive USB export not established'
[ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power not detected'
restart_inputs || fail 'Management restart dependency mismatch'
for name in started worker.log RESULT; do
    if [ "$mode" != --worker ]; then
        [ ! -e "$name" ] && [ ! -L "$name" ] || fail 'Prior trial evidence exists; do not rerun'
    fi
done
if [ "$mode" = --worker ]; then
    private_file started && private_file worker.log && [ ! -e RESULT ] && [ ! -L RESULT ] || fail 'Worker not launched from fresh stage'
fi
# Read-only first-party inventory; no vendor startup script is sourced.
. "$trial_stage/identity.sh"
trial_old=$old
trial_replacement=$replacement
trial_vendor=$vendor
old_stamp=$(start_time "$trial_old")
replacement_stamp=$(start_time "$trial_replacement")
vendor_stamp=$(start_time "$trial_vendor")
process_valid() {
    [ "$(readlink "/proc/$1/exe" 2>/dev/null || :)" = "$2" ] &&
    [ "$(start_time "$1" 2>/dev/null || :)" = "$3" ] &&
    printf '%s  %s\n' "$4" "/proc/$1/exe" | sha256sum -c - >/dev/null
}
replacement_unchanged() {
    process_valid "$trial_replacement" "$binary" "$replacement_stamp" "$ssh_hash" && socket_owned "$trial_replacement" 08B1
}
vendor_unchanged() {
    process_valid "$trial_vendor" /nimbus/nimbus "$vendor_stamp" "$vendor_hash" && socket_owned "$trial_vendor" 0050
}
old_unchanged() {
    process_valid "$trial_old" "$binary" "$old_stamp" "$ssh_hash" && socket_owned "$trial_old" 08B0
}
no_old_children() {
    for status in /proc/[0-9]*/status; do
        [ -r "$status" ] || continue
        parent=$(awk '$1=="PPid:" {print $2}' "$status" 2>/dev/null) || return 1
        [ -n "$parent" ] && [ "$parent" != "$trial_old" ] || return 1
    done
}
# Fail closed on unknown writable root files/mappings; never print private paths.
writer_check() {
    root_dev=$(stat -c '%d' /) || return 1
    map_dev=$(cat /sys/class/block/mmcblk0p2/dev) || return 1
    map_hex=$(printf '%02x:%02x' "${map_dev%:*}" "${map_dev#*:}") || return 1
    for process in /proc/[0-9]*; do
        [ -d "$process/fd" ] || continue
        [ -r "$process/maps" ] || return 1
        awk -v dev="$map_hex" '$4==dev && $2 ~ /^.w.s$/ {bad=1} END {exit bad}' "$process/maps" || return 1
        for fd in "$process"/fd/[0-9]*; do
            [ -L "$fd" ] && [ -f "$fd" ] || continue
            device=$(stat -L -c '%d' "$fd") || return 1
            [ "$device" = "$root_dev" ] || continue
            flags=$(awk '$1=="flags:" {print $2}' "$process/fdinfo/${fd##*/}") || return 1
            case "$flags" in ''|*[!0-7]*) return 1;; esac
            access=$((0$flags & 3))
            case "$access" in 1|2) :;; *) continue;; esac
            target=$(readlink "$fd") || return 1
            if [ "${process##*/}" = "$trial_vendor" ] && [ "$target" = /nimbus/settings.db ]; then :
            elif [ "$1" = before ] && [ "${process##*/}" = "$trial_old" ] && [ "$target" = "$base/boot.log" ]; then :
            else return 1; fi
        done
    done
}
root_rw && replacement_unchanged && vendor_unchanged && old_unchanged && no_old_children && writer_check before || fail 'Identity, children or writable-root inventory changed; no action'
if [ "$mode" = --check ]; then
    echo 'Check-only passed; no signal, launch or mount change performed'
    exit 0
fi
if [ "$mode" = --start ]; then
    (set -C; printf 'separately approved management-only trial\n' > started)
    (set -C; : > worker.log)
    nohup setsid sh "$trial_stage/trial.sh" --worker </dev/null >>worker.log 2>&1 &
    echo 'Detached management-only worker launched; port 2225 and Nimbus are retained'
    tries=0
    while [ "$tries" -lt 30 ] && [ ! -f RESULT ]; do tries=$((tries+1)); sleep 1; done
    if [ -f RESULT ] && [ ! -L RESULT ]; then
        result=$(cat RESULT); printf 'Trial result: %s\n' "$result"
        [ "$result" = PASS ] || exit 1
        exit 0
    fi
    echo 'No final result; retain stage and review through port 2225. Do not rerun.'
    exit 2
fi
port_free() {
    [ -r /proc/net/tcp ] || return 1
    for table in /proc/net/tcp /proc/net/tcp6; do
        [ -r "$table" ] || continue
        awk '$2 ~ /:08B0$/ && $4=="0A" {bad=1} END {exit bad}' "$table" || return 1
    done
}
restored_listener() {
    private_file "$base/boot.pid" && [ "$(stat -c '%s' "$base/boot.pid")" -le 16 ] || return 1
    restored_pid=$(cat "$base/boot.pid")
    case "$restored_pid" in ''|*[!0-9]*|0|1) return 1;; esac
    restored_stamp=$(start_time "$restored_pid" 2>/dev/null) || return 1
    case "$restored_stamp" in ''|*[!0-9]*) return 1;; esac
    process_valid "$restored_pid" "$binary" "$restored_stamp" "$ssh_hash" && socket_owned "$restored_pid" 08B0
}
termination_requested=no
restart_requested=no
finish_result=FAIL
restore_old() {
    if old_unchanged; then
        echo 'Original listener still present; no duplicate start requested'
        return 0
    fi
    # A surviving old parent without its socket is not proof of completed exit.
    if [ "$(start_time "$trial_old" 2>/dev/null || :)" = "$old_stamp" ]; then
        echo 'Original process has not exited; no force or duplicate start'
        return 1
    fi
    if [ "$restart_requested" = yes ]; then
        restored_listener && return 0
        echo 'Start already requested; no repeated launch'
        return 1
    fi
    port_free || { echo 'Old port occupied; no duplicate start'; return 1; }
    root_rw && replacement_unchanged && restart_inputs || { echo 'Unsafe management restart state; retain port 2225'; return 1; }
    restart_requested=yes
    # Targeted reviewed launcher only, never rc.local or a blanket service reload.
    nohup setsid sh "$launcher" </dev/null >>"$base/boot.log" 2>&1 &
    echo 'Reviewed normal listener start requested once'
    tries=0
    while [ "$tries" -lt 15 ]; do
        if restored_listener; then echo 'Matching normal listener PID/executable/socket observed'; return 0; fi
        tries=$((tries+1)); sleep 1
    done
    echo 'Normal listener recovery not verified; retain port 2225 and inspect'
    return 1
}
cleanup() {
    trap - EXIT HUP INT TERM
    if [ "$termination_requested" = yes ]; then
        if restore_old && root_rw && replacement_unchanged && vendor_unchanged; then
            echo 'Normal listener present; root rw; original replacement and Nimbus retained'
        else finish_result=FAIL; echo 'Recovery requires review through port 2225; no force/reboot attempted'; fi
    fi
    (set -C; printf '%s\n' "$finish_result" > "$trial_stage/RESULT") || :
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
root_rw && replacement_unchanged && vendor_unchanged && old_unchanged && no_old_children && writer_check before || fail 'State changed before signal'
termination_requested=yes
echo 'Requesting one TERM for freshly verified old listener only'
kill -TERM "$trial_old"
tries=0
while [ "$(start_time "$trial_old" 2>/dev/null || :)" = "$old_stamp" ]; do
    [ "$tries" -lt 10 ] || fail 'Old listener did not exit; no forced signal'
    tries=$((tries+1)); sleep 1
done
port_free || fail 'Old port still occupied or autonomously restored; no duplicate start'
root_rw && replacement_unchanged && vendor_unchanged && writer_check after || fail 'Post-exit state changed or root writer remains'
echo 'Old listener exited and root-log holders absent; no remount performed'
restore_old || fail 'Normal listener restart observation failed'
finish_result=PASS
echo 'Management-only trial completed; fresh pinned port-2224 authentication is still required'
