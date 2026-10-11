#!/bin/sh
# Run only from the new, verified startup-v1 directory.
set -eu
base=/root/nimbus-ssh-test
stage="$base/startup-v1"
target=/etc/rc.d/rc.local
backup="$stage/rc.local.before-ssh"
[ "$(id -u)" = 0 ] || { echo 'Root required.'; exit 1; }
[ "$(pwd -P)" = "$stage" ] || { echo 'Wrong staging directory.'; exit 1; }
sha256sum -c SHA256SUMS || exit 1
command -v cmp >/dev/null || { echo 'cmp unavailable; stopped.'; exit 1; }
[ -f "$target" ] && [ -x "$target" ] && [ ! -L "$target" ] || exit 1
[ ! -e "$backup" ] && [ ! -e "$stage/rc.local.new" ] || {
  echo 'Previous staging detected; do not rerun blindly.'; exit 1;
}
if grep -q 'NIMBUS-KEY-SSH-V1\|nimbus-ssh-test' "$target"; then
  echo 'Existing SSH integration; stopped.'; exit 1
fi
printf '%s  %s\n' \
  1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c \
  "$base/dropbearmulti-bound" | sha256sum -c - || exit 1
sh -n start-ssh.sh
cp -p "$target" "$backup"
cmp "$target" "$backup" || exit 1
cp -p "$target" "$stage/rc.local.new"
cat >> "$stage/rc.local.new" <<'HOOK'

# NIMBUS-KEY-SSH-V1: only start; preserve all vendor shutdown behavior.
if [ "$1" = start ]; then
    /bin/sh /root/nimbus-ssh-test/startup-v1/start-ssh.sh \
      </dev/null >>/root/nimbus-ssh-test/boot.log 2>&1 &
fi
HOOK
sh -n "$stage/rc.local.new"
chmod 700 start-ssh.sh
umask 077
touch "$base/boot.log"
chmod 600 "$base/boot.log"
# Refuse concurrent edits since backup rather than overwriting them.
cmp "$target" "$backup" || exit 1
mv "$stage/rc.local.new" "$target"
sync
echo 'SSH boot hook staged. No service started/stopped, radio change or reboot.'
echo "Original rc.local saved at $backup"
