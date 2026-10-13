#!/bin/sh
# Preparation only until separately approved. No capture, force, freeze or reboot.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
trial_stage=/tmp/nimbus-root-restoration-trial-v1
readonly trial_stage
base=/root/nimbus-ssh-test
binary="$base/dropbearmulti-bound"
launcher="$base/startup-v1/start-ssh.sh"
service=/etc/rc.d/init.d/service/S20nimbus
ssh_hash=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c
vendor_hash=b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd
rw_options=rw,relatime,errors=continue,barrier=0,data=writeback
ro_options=ro,relatime,errors=continue,barrier=0,data=writeback
readonly rw_options ro_options
fail() { echo "$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Authorized root session required'
[ "$#" -le 1 ] || fail 'Use --check or --start'
mode=${1:---check}
case "$mode" in --check|--start|--worker) :;; *) fail 'Use --check or --start';; esac
connection=${SSH_CONNECTION-}
[ "${connection##* }" = 2225 ] || fail 'Use the independently verified port-2225 session'
[ "$(CDPATH= cd "$(dirname "$0")" && pwd -P)" = "$trial_stage" ] || fail 'Wrong private stage'
for directory in /tmp "$trial_stage" /root "$base" "$base/startup-v1" "$base/auth" /bin /etc /etc/rc.d /etc/rc.d/init.d /etc/rc.d/init.d/service /opt /opt/qsi /opt/qsi/config /nimbus; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'Unsafe dependency directory'
done
for directory in "$trial_stage" "$base" "$base/auth"; do
    [ "$(stat -c '%u:%g:%a' "$directory")" = 0:0:700 ] || fail 'Unsafe private directory metadata'
done
cd "$trial_stage"
sha256sum -c SHA256SUMS >/dev/null || fail 'Trial source checksum mismatch'
for tool in stat sha256sum awk nohup setsid; do command -v "$tool" >/dev/null || fail 'Required tool unavailable'; done
private_file() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%g:%a' "$1")" = 0:0:600 ]; }
verify_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%g' "$1")" = 0:0 ] &&
    printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null
}
ssh_inputs() {
    verify_file "$binary" "$ssh_hash" && [ -x "$binary" ] &&
    verify_file "$launcher" 173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41 &&
    [ "$(stat -c '%a' "$launcher")" = 700 ] &&
    private_file "$base/host-ed25519" && [ -s "$base/host-ed25519" ] &&
    private_file "$base/auth/authorized_keys" && [ -s "$base/auth/authorized_keys" ] &&
    private_file "$base/boot.log" && [ -d /sys/class/net/wlan1 ]
}
vendor_inputs() {
    verify_file "$service" 2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3 &&
    verify_file /nimbus/nimbus "$vendor_hash" &&
    verify_file /opt/qsi/config/nimbus.conf 6a32518bd0e5f024a766a8cfb3f722dc4752b952b4ce629ed27fcc8bca4293f5 &&
    verify_file /opt/qsi/config/develop.conf 970a00795c0464a7e97b44d6b50d5bd9dbe6f851d51c7408b55cd058e3c93664 &&
    verify_file /opt/qsi/config/platform_functions 16bcf3ec02fc8a660256bfa37674d6dfd5ef786345d7c2ff624cf1c2b030e136
}
safe_socket_path() { [ ! -L /tmp/comm.socket ] && { [ ! -e /tmp/comm.socket ] || [ -S /tmp/comm.socket ]; }; }
usb_tmp_safe() {
    [ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules &&
    awk '$2=="/tmp" && $3=="tmpfs" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n!=1}' /proc/mounts
}
root_state() {
    state=unknown
    [ "$(awk '$5=="/" && index($0," - ext3 ") {n++; dev=$3} END {if(n==1) print dev; else exit 1}' /proc/self/mountinfo)" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || return 1
    source=$(awk '$2=="/" && $3=="ext3" {n++; dev=$1} END {if(n==1) print dev; else exit 1}' /proc/mounts) || return 1
    case "$source" in /dev/root|/dev/mmcblk0p2) :;; *) return 1;; esac
    options=$(awk '$2=="/" && $3=="ext3" {print $4}' /proc/mounts) || return 1
    case "$options" in "$rw_options") state=rw;; "$ro_options") state=ro;; *) return 1;; esac
    # Require both the VFS view and superblock to agree, not just a ro bind view.
    awk -v wanted="$state" '$5=="/" {n++; if($6 != wanted ",relatime") bad=1; for(i=7;i<=NF;i++) if($i=="-") {if($(i+1)!="ext3" || $(i+3) !~ ("^" wanted "(,|$)")) bad=1}} END {exit n!=1 || bad}' /proc/self/mountinfo
}
root_rw() { root_state && [ "$state" = rw ]; }
mount_input() { verify_file /bin/mount 5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be && [ -x /bin/mount ]; }
root_rw && usb_tmp_safe || fail 'Expected writable root/options/tmp or inactive USB not established'
[ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power not detected'
ssh_inputs && vendor_inputs && mount_input && safe_socket_path || fail 'Reviewed dependency mismatch'
for name in started worker.log RESULT; do
    if [ "$mode" != --worker ]; then [ ! -e "$name" ] && [ ! -L "$name" ] || fail 'Prior trial exists; no rerun'; fi
done
if [ "$mode" = --worker ]; then private_file started && private_file worker.log && [ ! -e RESULT ] && [ ! -L RESULT ] || fail 'Worker not freshly launched'; fi
# The sourced first-party helper has generic globals; trial state is namespaced.
. "$trial_stage/identity.sh"
trial_old=$old; trial_replacement=$replacement; trial_vendor=$vendor
old_stamp=$(start_time "$trial_old"); replacement_stamp=$(start_time "$trial_replacement"); vendor_stamp=$(start_time "$trial_vendor")
process_valid() {
    [ "$(readlink "/proc/$1/exe" 2>/dev/null || :)" = "$2" ] &&
    [ "$(start_time "$1" 2>/dev/null || :)" = "$3" ] &&
    printf '%s  %s\n' "$4" "/proc/$1/exe" | sha256sum -c - >/dev/null
}
replacement_ok() { process_valid "$trial_replacement" "$binary" "$replacement_stamp" "$ssh_hash" && socket_owned "$trial_replacement" 08B1; }
old_ok() { process_valid "$trial_old" "$binary" "$old_stamp" "$ssh_hash" && socket_owned "$trial_old" 08B0; }
vendor_ok() { process_valid "$trial_vendor" /nimbus/nimbus "$vendor_stamp" "$vendor_hash" && socket_owned "$trial_vendor" 0050; }
no_children() {
    for status in /proc/[0-9]*/status; do
        [ -r "$status" ] || continue
        parent=$(awk '$1=="PPid:" {print $2}' "$status") || return 1
        [ -n "$parent" ] && [ "$parent" != "$1" ] || return 1
    done
}
port_free() {
    [ -r /proc/net/tcp ] || return 1
    for table in /proc/net/tcp /proc/net/tcp6; do
        [ -r "$table" ] || continue
        awk -v port="$1" '$2 ~ (":" port "$") && $4=="0A" {bad=1} END {exit bad}' "$table" || return 1
    done
}
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
            case "$((0$flags & 3))" in 1|2) :;; *) continue;; esac
            target=$(readlink "$fd") || return 1
            if [ "$1" = before ] && [ "${process##*/}" = "$trial_old" ] && [ "$target" = "$base/boot.log" ]; then :
            elif [ "$1" != empty ] && [ "${process##*/}" = "$trial_vendor" ] && [ "$target" = /nimbus/settings.db ]; then :
            else return 1; fi
        done
    done
}
root_rw && replacement_ok && old_ok && vendor_ok && no_children "$trial_old" && no_children "$trial_vendor" && writer_check before || fail 'Identity/children/writers changed; no action'
if [ "$mode" = --check ]; then echo 'Check-only passed; no signal, launch or mount change'; exit 0; fi
if [ "$mode" = --start ]; then
    (set -C; printf 'separately approved root restoration trial\n' > started)
    (set -C; : > worker.log)
    nohup setsid sh "$trial_stage/trial.sh" --worker </dev/null >>worker.log 2>&1 &
    echo 'Detached restoration worker launched; retain port 2225'
    tries=0
    while [ "$tries" -lt 45 ] && [ ! -f RESULT ]; do tries=$((tries+1)); sleep 1; done
    if [ -f RESULT ] && [ ! -L RESULT ]; then result=$(cat RESULT); printf 'Trial result: %s\n' "$result"; [ "$result" = PASS ] || exit 1; exit 0; fi
    echo 'No final result; retain stage and review through port 2225. No rerun/reboot.'
    exit 2
fi
old_requested=no; vendor_requested=no; ro_requested=no; rw_requested=no
ssh_start_requested=no; vendor_start_requested=no; finish_result=FAIL
observe_exit() {
    tries=0
    while [ "$(start_time "$1" 2>/dev/null || :)" = "$2" ]; do
        [ "$tries" -lt 10 ] || return 1
        tries=$((tries+1)); sleep 1
    done
}
find_vendor() {
    found_vendor=''
    for node in /proc/[0-9]*; do
        [ -r "$node/comm" ] || continue
        [ "$(cat "$node/comm" 2>/dev/null || :)" = nimbus ] || continue
        [ -z "$found_vendor" ] || return 1
        found_vendor=${node##*/}
    done
}
any_vendor_ok() {
    find_vendor && [ -n "$found_vendor" ] || return 1
    stamp=$(start_time "$found_vendor") || return 1
    case "$stamp" in ''|*[!0-9]*) return 1;; esac
    process_valid "$found_vendor" /nimbus/nimbus "$stamp" "$vendor_hash" && socket_owned "$found_vendor" 0050
}
any_old_ok() {
    private_file "$base/boot.pid" && [ "$(stat -c '%s' "$base/boot.pid")" -le 16 ] || return 1
    restored_pid=$(cat "$base/boot.pid")
    case "$restored_pid" in ''|*[!0-9]*|0|1) return 1;; esac
    stamp=$(start_time "$restored_pid") || return 1
    case "$stamp" in ''|*[!0-9]*) return 1;; esac
    process_valid "$restored_pid" "$binary" "$stamp" "$ssh_hash" && socket_owned "$restored_pid" 08B0
}
restore_rw() {
    root_state || { echo 'Root state/options unknown; no blind remount'; return 1; }
    [ "$state" != rw ] || return 0
    [ "$ro_requested" = yes ] && [ "$rw_requested" = no ] || { echo 'Writable restoration not authorized again'; return 1; }
    usb_tmp_safe && replacement_ok && mount_input || return 1
    rw_requested=yes
    echo 'Requesting one explicit writable restoration with original options'
    /bin/mount -n -i -w -t ext3 -o "remount,$rw_options" /dev/mmcblk0p2 / || return 1
    root_rw || return 1
}
restore_vendor() {
    find_vendor || return 1
    if [ -n "$found_vendor" ]; then any_vendor_ok; return $?; fi
    [ "$vendor_start_requested" = no ] && port_free 0050 && vendor_inputs && safe_socket_path || return 1
    vendor_start_requested=yes
    sh "$service" start </dev/null >/dev/null 2>&1 &
    echo 'Reviewed Nimbus start requested once'
    tries=0
    while [ "$tries" -lt 15 ]; do if any_vendor_ok; then return 0; fi; tries=$((tries+1)); sleep 1; done
    return 1
}
restore_ssh() {
    if any_old_ok; then return 0; fi
    [ "$(start_time "$trial_old" 2>/dev/null || :)" != "$old_stamp" ] || return 1
    [ "$ssh_start_requested" = no ] && port_free 08B0 && ssh_inputs || return 1
    ssh_start_requested=yes
    nohup setsid sh "$launcher" </dev/null >>"$base/boot.log" 2>&1 &
    echo 'Reviewed normal SSH start requested once'
    tries=0
    while [ "$tries" -lt 15 ]; do if any_old_ok; then return 0; fi; tries=$((tries+1)); sleep 1; done
    return 1
}
cleanup() {
    trap - EXIT HUP INT TERM
    recovered=yes
    if restore_rw && root_rw && usb_tmp_safe && replacement_ok; then
        if [ "$vendor_requested" = yes ]; then restore_vendor || recovered=no; else vendor_ok || recovered=no; fi
        # Attempt SSH restoration independently even if vendor restart failed.
        if [ "$old_requested" = yes ]; then restore_ssh || recovered=no; else old_ok || recovered=no; fi
    else recovered=no; echo 'Root rw/management not verified; stopped services not launched'; fi
    if [ "$recovered" = yes ]; then echo 'Restoration observed: root rw, normal SSH/Nimbus present, original port 2225 retained';
    else finish_result=FAIL; echo 'Partial/failed recovery; retain port 2225 and all evidence. No force/reboot.'; fi
    (set -C; printf '%s\n' "$finish_result" > "$trial_stage/RESULT") || :
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
root_rw && usb_tmp_safe && replacement_ok && old_ok && vendor_ok && no_children "$trial_old" && writer_check before || fail 'State changed before old-listener TERM'
old_requested=yes
echo 'Requesting one TERM for freshly verified normal SSH listener'
kill -TERM "$trial_old"
observe_exit "$trial_old" "$old_stamp" && port_free 08B0 || fail 'Old listener exit/port release failed; no force'
root_rw && usb_tmp_safe && replacement_ok && vendor_ok && no_children "$trial_vendor" && writer_check vendor_only || fail 'State changed before Nimbus TERM'
vendor_requested=yes
echo 'Requesting one TERM for freshly verified Nimbus only'
kill -TERM "$trial_vendor"
observe_exit "$trial_vendor" "$vendor_stamp" && find_vendor && [ -z "$found_vendor" ] && port_free 0050 || fail 'Nimbus exit/quiescence not established; no force'
root_rw && usb_tmp_safe && replacement_ok && writer_check empty && mount_input || fail 'State changed before remount; no mount attempted'
[ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power lost; no mount attempted'
ro_requested=yes
echo 'Requesting one non-forced read-only remount; no capture'
/bin/mount -n -i -r -t ext3 -o "remount,$ro_options" /dev/mmcblk0p2 / || fail 'Read-only remount refused/failed'
root_state && [ "$state" = ro ] && replacement_ok || fail 'Expected read-only state not verified'
echo 'Expected root read-only configuration observed; restoring immediately'
restore_rw || fail 'Writable restoration refused/failed; no retry'
restore_vendor || fail 'Nimbus restoration not verified'
restore_ssh || fail 'Normal SSH restoration not verified'
root_rw && usb_tmp_safe && replacement_ok && any_vendor_ok && any_old_ok || fail 'Final restoration state incomplete'
finish_result=PASS
echo 'Root restoration process/state trial completed; fresh pinned login/browser checks still required'
