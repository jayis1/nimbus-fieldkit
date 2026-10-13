#!/bin/sh
# Positive synthetic regular-file trial only. Never runs the real coordinator.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
[ "$#" = 2 ] && [ "$1" = --worker ] || exit 2
session=$2
case "$session" in ''|*[!0-9a-f]*) exit 2;; esac
[ "${#session}" = 64 ] || exit 2
stage=$(pwd -P)
for name in worker.sh identity.sh streamer fixture-hasher fixture/dev/mmcblk0p2 fixture/proc/modules fixture/proc/mounts fixture/proc/self/mountinfo fixture/sys/class/block/mmcblk0p2/dev fixture/sys/class/block/mmcblk0p2/start fixture/sys/class/block/mmcblk0p2/size; do
    [ -f "$name" ] && [ ! -L "$name" ] || exit 1
done
sha256sum -c SHA256SUMS >/dev/null
# Verify the existing vendor executable as an ordinary regular input, not a
# block read. The wrapper execs the standalone executable, not a BusyBox applet.
[ -f /usr/bin/sha256sum ] && [ ! -L /usr/bin/sha256sum ] || exit 1
[ "$(stat -c '%u:%g:%a:%s' /usr/bin/sha256sum)" = '@HASHER_METADATA@' ] || exit 1
printf '%s  %s\n' @HASHER_SHA256@ /usr/bin/sha256sum | sha256sum -c - >/dev/null
set -C
exec 4> CHILD-DRAIN
set +C
status=0
# Precomputed synthetic ACK tests the native reader/hasher, NOT a host durable
# readback protocol. The complete fake wire is confined to this private tmpfs.
printf 'NIMBUS-HOST-VERIFIED %s %s\n' "$session" @DATA_SHA256@ |
    "$stage/streamer" --stream-evidence "$session" "$stage/fixture" 4>&4 > SYNTHETIC-WIRE || status=$?
exec 4>&-
set -C
printf '%s helper_status=%s synthetic-only host_readback_verified=no\n' "$session" "$status" > REGULAR-RESULT
[ "$status" = 0 ] || exit 1
[ "$(cat CHILD-DRAIN)" = "NIMBUS-CHILD-DRAIN $session reader-closed hasher-drained" ] || exit 1
[ "$(stat -c %s CHILD-DRAIN)" = "$(printf 'NIMBUS-CHILD-DRAIN %s reader-closed hasher-drained\n' "$session" | wc -c | tr -d ' ')" ] || exit 1
printf 'REGULAR-TRIAL=PASS reader-closed hasher-drained synthetic-only native_capture_qualified=no\n'
