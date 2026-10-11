#!/bin/sh
# Boot-only launcher; no passwords, forwarding, or radio changes.
set -eu
base=/root/nimbus-ssh-test
hash=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c
printf '%s  %s\n' "$hash" "$base/dropbearmulti-bound" | sha256sum -c - || exit 1
[ -r "$base/host-ed25519" ] && [ -r "$base/auth/authorized_keys" ] || exit 1
tries=0
while [ ! -d /sys/class/net/wlan1 ]; do
  tries=$((tries + 1))
  [ "$tries" -lt 60 ] || { echo 'SSH not started: wlan1 unavailable.'; exit 1; }
  sleep 2
done
# Patched binary closes the socket if SO_BINDTODEVICE fails.
exec "$base/dropbearmulti-bound" dropbear \
  -F -l wlan1 -p 0.0.0.0:2224 \
  -r "$base/host-ed25519" -D "$base/auth" \
  -P "$base/boot.pid" -T 3 -I 600
