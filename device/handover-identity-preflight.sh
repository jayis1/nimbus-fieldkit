#!/bin/sh
# Read-only identity/socket/descriptor evidence. NEVER signals any process.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
fail() { echo "$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Authorized root SSH session required'
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || fail 'USB export active or unknown'
[ -r /proc/self/mountinfo ] && [ -r /sys/class/block/mmcblk0p2/dev ] || fail 'Root identity unavailable'
[ "$(awk '$5 == "/" && index($0," - ext3 ") {print $3}' /proc/self/mountinfo)" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || fail 'Unexpected root identity'
base=/root/nimbus-ssh-test
stage=/tmp/nimbus-capture-ssh-v1
binary="$base/dropbearmulti-bound"
for directory in /root "$base" /tmp "$stage"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'Unsafe management directory'
done
[ "$(stat -c '%u:%g:%a' "$base")" = 0:0:700 ] &&
[ "$(stat -c '%u:%g:%a' "$stage")" = 0:0:700 ] || fail 'Private stage permissions changed'
pid_from_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%g' "$1")" = 0:0 ] || fail 'Unsafe PID metadata'
    [ "$(stat -c '%s' "$1")" -le 16 ] || fail 'Oversized PID record'
    value=$(cat "$1")
    case "$value" in ''|*[!0-9]*|0|1) fail 'Invalid PID record';; esac
    printf '%s\n' "$value"
}
old=$(pid_from_file "$base/boot.pid")
replacement=$(pid_from_file "$stage/listener.pid")
[ "$old" != "$replacement" ] || fail 'Listener identities coincide'
start_time() {
    # Remove pid and parenthesized comm, which may itself contain spaces/parentheses.
    sed 's/.*) //' "/proc/$1/stat" | awk '{print $20}'
}
socket_owned() {
    owner="$1"; port="$2"
    inode=$(awk -v port="$port" '$2 == "00000000:" port && $4 == "0A" {n++; inode=$10} END {if(n==1) print inode; else exit 1}' /proc/net/tcp) || return 1
    case "$inode" in ''|*[!0-9]*) return 1;; esac
    for fd in "/proc/$owner"/fd/[0-9]*; do
        [ -L "$fd" ] || continue
        [ "$(readlink "$fd" 2>/dev/null || :)" = "socket:[$inode]" ] && return 0
    done
    return 1
}
identity() {
    role="$1"; pid="$2"; expected="$3"; hash="$4"
    [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$expected" ] || fail 'Unexpected process executable'
    printf '%s  %s\n' "$hash" "/proc/$pid/exe" | sha256sum -c - >/dev/null || fail 'Running executable hash differs'
    stamp=$(start_time "$pid")
    case "$stamp" in ''|*[!0-9]*) fail 'Process start identity unavailable';; esac
    children=0
    for status in /proc/[0-9]*/status; do
        [ -r "$status" ] || continue
        parent=$(awk '$1=="PPid:" {print $2}' "$status" 2>/dev/null || :)
        [ "$parent" != "$pid" ] || children=$((children + 1))
    done
    printf 'role=%s pid=%s start_ticks=%s direct_children=%s executable_hash=matched\n' "$role" "$pid" "$stamp" "$children"
    [ "$(start_time "$pid")" = "$stamp" ] || fail 'Process changed during observation'
}
echo 'HANDOVER IDENTITY INVENTORY — NO STOP OR REMOUNT AUTHORIZATION'
ssh_hash=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c
identity old_listener "$old" "$binary" "$ssh_hash"
socket_owned "$old" 08B0 || fail 'Old PID does not own the expected single IPv4 listening socket'
echo 'Old listener owns expected port-2224 socket'
identity replacement_listener "$replacement" "$binary" "$ssh_hash"
socket_owned "$replacement" 08B1 || fail 'Replacement PID does not own the expected single IPv4 listening socket'
echo 'Replacement listener owns expected port-2225 socket'
vendor=''
for process in /proc/[0-9]*; do
    [ -r "$process/comm" ] || continue
    [ "$(cat "$process/comm" 2>/dev/null || :)" = nimbus ] || continue
    [ -z "$vendor" ] || fail 'Multiple vendor writer candidates; stop review'
    vendor=${process##*/}
done
[ -n "$vendor" ] || fail 'Vendor writer unavailable'
identity vendor_writer "$vendor" /nimbus/nimbus b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd
root_device=$(stat -c '%d' /)
for owner in "$old" "$replacement" "$vendor"; do
    known_log=0; other=0; incomplete=0
    for fd in "/proc/$owner"/fd/[0-9]*; do
        [ -L "$fd" ] && [ -f "$fd" ] || continue
        device=$(stat -L -c '%d' "$fd" 2>/dev/null) || { incomplete=$((incomplete+1)); continue; }
        [ "$device" = "$root_device" ] || continue
        flags=$(awk '$1=="flags:" {print $2}' "/proc/$owner/fdinfo/${fd##*/}" 2>/dev/null || :)
        case "$flags" in ''|*[!0-7]*) incomplete=$((incomplete+1)); continue;; esac
        access=$((0$flags & 3))
        case "$access" in 1|2) :;; *) continue;; esac
        target=$(readlink "$fd" 2>/dev/null || :)
        if [ "$target" = "$base/boot.log" ]; then known_log=$((known_log+1)); else other=$((other+1)); fi
    done
    printf 'pid=%s writable_known_boot_log_fds=%s other_writable_root_fds=%s incomplete=%s\n' "$owner" "$known_log" "$other" "$incomplete"
done
echo 'Arguments, private file names, key/log contents and socket peers suppressed.'
echo 'Observations are racy, not pidfd-protected or exhaustive. Do not reuse these PIDs as stop targets.'
echo 'No signals, service execution, sync, mount change, watchdog open, raw block access or reboot performed.'
