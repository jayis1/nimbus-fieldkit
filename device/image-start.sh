#!/bin/sh
# Custom rootfs candidate only. Requires separately provisioned unique SSH keys.
set -u
umask 077
keys=/etc/nimbus
if [ -f "$keys/host-ed25519" ] && [ ! -L "$keys/host-ed25519" ] &&
   [ -s "$keys/authorized_keys" ] && [ ! -L "$keys/authorized_keys" ]; then
    chmod 700 "$keys"
    chmod 600 "$keys/host-ed25519" "$keys/authorized_keys"
    (
        tries=0
        while [ ! -d /sys/class/net/wlan1 ]; do
            tries=$((tries + 1))
            [ "$tries" -lt 60 ] || exit 1
            sleep 2
        done
        exec /opt/nimbus/dropbearmulti dropbear -F -l wlan1 -p 0.0.0.0:2224 \
          -r "$keys/host-ed25519" -D "$keys" -P /var/run/nimbus-ssh.pid -T 3 -I 600
    ) </dev/null >>/var/log/nimbus-ssh.log 2>&1 &
else
    echo 'Nimbus SSH not started: unique host key and authorized_keys must be provisioned offline.' >&2
fi
# Never populate unmounted media or overwrite an existing toolkit installation.
if awk '$2 == "/mnt/storage" && $4 !~ /(^|,)ro(,|$)/ {found=1} END {exit !found}' /proc/mounts; then
    base=/mnt/storage/nimbus-unified-v05
    if [ ! -e "$base" ] && [ ! -L "$base" ]; then
        mkdir "$base" && cp -R /opt/nimbus/native "$base/native"
    fi
    if [ -d "$base/native" ] && [ ! -L "$base" ] && [ ! -L "$base/native" ]; then
        sh "$base/native/nimbus-dashboard.sh" snapshot
    fi
fi
# Deliberately no SD repair/remount, gateway/radio edits or Pi service changes.
