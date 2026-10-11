#!/bin/sh
# Optional temporary management listener. Never stops the existing listener.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
mode=${1:---check}
case "$mode" in --check|--start) :;; *) echo 'Use --check or --start'; exit 1;; esac
[ "$#" -le 1 ] || exit 1
fail() { echo "$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Authorized root SSH session required'
base=/root/nimbus-ssh-test
stage=/tmp/nimbus-capture-ssh-v1
binary="$base/dropbearmulti-bound"
hash=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c
for tool in stat sha256sum awk nohup setsid; do
    command -v "$tool" >/dev/null 2>&1 || fail 'Required tool unavailable'
done
for dir in /tmp /root "$base" "$base/auth"; do
    [ -d "$dir" ] && [ ! -L "$dir" ] || fail 'Required directory missing or symlinked'
done
for dir in "$base" "$base/auth"; do
    [ "$(stat -c '%u:%g:%a' "$dir")" = '0:0:700' ] || fail 'Private SSH directory permissions not established'
done
private_file() {
    [ -f "$1" ] && [ -s "$1" ] && [ ! -L "$1" ] &&
    [ "$(stat -c '%u:%g:%a' "$1")" = '0:0:600' ]
}
private_file "$base/host-ed25519" && private_file "$base/auth/authorized_keys" || fail 'Existing private SSH keys have unsafe metadata'
[ -f "$binary" ] && [ -x "$binary" ] && [ ! -L "$binary" ] || fail 'Trusted SSH binary unavailable'
printf '%s  %s\n' "$hash" "$binary" | sha256sum -c - >/dev/null || fail 'SSH binary hash mismatch'
[ -d /sys/class/net/wlan1 ] || fail 'Management interface unavailable'
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || fail 'USB export active or state unavailable'
awk '$2 == "/tmp" && $3 == "tmpfs" && $4 ~ /(^|,)rw(,|$)/ {n++} END {exit n != 1}' /proc/mounts || fail 'Expected writable tmpfs /tmp not established'
[ ! -e "$stage" ] && [ ! -L "$stage" ] || fail 'Prior temporary stage exists; inspect it rather than rerun'
[ -r /proc/net/tcp ] || fail 'Listener metadata unavailable'
for table in /proc/net/tcp /proc/net/tcp6; do
    [ -r "$table" ] || continue
    if awk '$2 ~ /:08B1$/ && $4 == "0A" {found=1} END {exit !found}' "$table"; then
        fail 'Port 2225 already occupied; existing services left untouched'
    fi
done
echo 'Temporary listener checks passed: existing keys, pinned binary, wlan1 and RAM-backed logging'
if [ "$mode" = --check ]; then
    echo 'Check-only: no staging, listener, signal, mount change or reboot performed'
    exit 0
fi
mkdir -m 700 "$stage"
echo 'Starting OPTIONAL temporary key-only listener on wlan1 TCP 2225'
# nohup protects against the starting SSH session closing; setsid detaches it.
# Same existing identity/authorized-key files, with no key copies or boot edits.
nohup setsid "$binary" dropbear -F -E -l wlan1 -p 0.0.0.0:2225 \
    -r "$base/host-ed25519" -D "$base/auth" -P "$stage/listener.pid" -T 3 -I 600 \
    </dev/null >"$stage/listener.log" 2>&1 &
tries=0
while [ "$tries" -lt 5 ]; do
    if [ -f "$stage/listener.pid" ] && [ ! -L "$stage/listener.pid" ]; then
        pid=$(cat "$stage/listener.pid")
        case "$pid" in ''|*[!0-9]*|0|1) fail 'Invalid temporary PID; inspect private stage';; esac
        if kill -0 "$pid" 2>/dev/null &&
           awk '$2 == "00000000:08B1" && $4 == "0A" {found=1} END {exit !found}' /proc/net/tcp; then
            echo 'Temporary listener process/listening entry observed; authenticated login is STILL REQUIRED'
            echo 'Port 2224, startup hooks, keys, vendor services and mounts left unchanged'
            echo 'Private tmpfs stage retained; no permanent install or automatic root remount'
            exit 0
        fi
    fi
    tries=$((tries + 1)); sleep 1
done
fail 'Temporary listener not verified; private stage retained. Do not stop port 2224 or blindly retry'
