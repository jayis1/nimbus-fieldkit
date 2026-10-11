#!/bin/sh
# Custom rootfs candidate only. Requires separately provisioned unique SSH keys.
set -u
umask 077
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
keys=/etc/nimbus
private_file() {
    [ -f "$1" ] && [ -s "$1" ] && [ ! -L "$1" ] &&
        [ "$(stat -c '%u:%g:%a' "$1" 2>/dev/null)" = '0:0:600' ]
}
if [ -d "$keys" ] && [ ! -L "$keys" ] &&
   [ "$(stat -c '%u:%g:%a' "$keys" 2>/dev/null)" = '0:0:700' ] &&
   private_file "$keys/host-ed25519" && private_file "$keys/authorized_keys" &&
   /opt/nimbus/dropbearmulti dropbearkey -y -f "$keys/host-ed25519" >/dev/null 2>&1; then
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
    echo 'Nimbus SSH not started: valid offline keys with root ownership and private permissions required.' >&2
fi
# Never populate unmounted media or overwrite an existing toolkit installation.
if [ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules &&
   awk '$1 == "/dev/mmcblk0p4" && $2 == "/mnt/storage" && $4 ~ /(^|,)rw(,|$)/ {found=1} END {exit !found}' /proc/mounts; then
    base=/mnt/storage/nimbus-unified-v05
    if [ ! -e "$base" ] && [ ! -L "$base" ]; then
        mkdir "$base" && cp -R /opt/nimbus/native "$base/native"
    fi
    if [ -d "$base/native" ] && [ ! -L "$base" ] && [ ! -L "$base/native" ]; then
        # Exported media is DATA, never a root boot-time code source.
        NIMBUS_DATA_DIR="$base/native" sh /opt/nimbus/native/nimbus-dashboard.sh snapshot
    fi
fi
# Deliberately no SD repair/remount, gateway/radio edits or Pi service changes.
