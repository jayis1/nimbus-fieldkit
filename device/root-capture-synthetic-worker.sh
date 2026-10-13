#!/bin/sh
# Synthetic guardian trial only. Built-ins only; no capture/service/mount commands.
set -eu
umask 077
[ "$#" = 2 ] && [ "$1" = --worker ] || exit 2
session=$2
case "$session" in ''|*[!0-9a-f]*) exit 2;; esac
[ "${#session}" = 64 ] || exit 2
completed=no
cleanup() {
    trap - EXIT
    trap '' HUP INT TERM
    set -C
    printf '%s synthetic-only completed=%s real_reader_started=no\n' "$session" "$completed" > SYNTHETIC-RESULT
}
trap cleanup EXIT
trap 'completed=no; exit 1' HUP INT TERM
printf '%s\n' "$session" > WORKER-READY
printf 'SYNTHETIC-READY %s no-real-reader\n' "$session"
# EOF/TERM is the expected native disconnect scenario. A matching synthetic ACK
# is supported only for local positive-control tests; no ROOT protocol is emitted.
ack=''
read -r ack || exit 1
[ "$ack" = "SYNTHETIC-ACK $session" ] || exit 1
completed=yes
printf 'SYNTHETIC-DONE %s no-capture\n' "$session"
