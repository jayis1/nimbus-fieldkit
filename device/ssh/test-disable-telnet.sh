#!/bin/sh
# Temporary five-minute trial. Always restores the original config afterward.
set -eu
[ "$(id -u)" = 0 ] || exit 1
command -v nohup >/dev/null || { echo 'nohup missing; stopped.'; exit 1; }
command -v cmp >/dev/null || exit 1
base=/root/nimbus-ssh-test/telnet-trial-v1
conf=/etc/inetd.conf
[ -f "$conf" ] && [ ! -L "$conf" ] || exit 1
# Require one unambiguous, currently running stock inetd master.
pid=$(ps -ef | awk '$8 == "/usr/sbin/inetd" {print $2}')
case "$pid" in ''|*[!0-9]*) echo 'Cannot identify one inetd master; stopped.'; exit 1;; esac
[ "$(cat /proc/"$pid"/comm)" = inetd ] || exit 1
count=$(awk '$1 == "telnet" {n++} END {print n+0}' "$conf")
[ "$count" = 1 ] || { echo 'Expected exactly one active Telnet entry.'; exit 1; }
grep -q '^telnet stream tcp nowait root /bin/busybox telnetd -i$' "$conf" || exit 1
umask 077
mkdir "$base" || { echo 'Trial directory exists; do not rerun blindly.'; exit 1; }
chmod 700 "$base"
cp -p "$conf" "$base/inetd.conf.before"
cp -p "$conf" "$base/inetd.conf.disabled"
awk '{if ($1 == "telnet") print "# NIMBUS-TELNET-TRIAL " $0; else print}' \
  "$base/inetd.conf.before" > "$base/content"
cat "$base/content" > "$base/inetd.conf.disabled"
cp -p "$base/inetd.conf.disabled" "$base/inetd.conf.install"
cat > "$base/restore.sh" <<'RESTORE'
#!/bin/sh
set -eu
base=/root/nimbus-ssh-test/telnet-trial-v1
case "${1:-}" in now) ;; *) sleep 300;; esac
if ! cmp -s /etc/inetd.conf "$base/inetd.conf.disabled"; then
  echo 'Not restoring: config already restored or changed; inspect manually.'
  exit 1
fi
cp -p "$base/inetd.conf.before" "$base/inetd.conf.restore"
mv "$base/inetd.conf.restore" /etc/inetd.conf
sync
pid=$(ps -ef | awk '$8 == "/usr/sbin/inetd" {print $2}')
case "$pid" in
  '') /usr/sbin/inetd;;
  *[!0-9]*) echo 'Config restored; ambiguous inetd processes, no signal sent.'; exit 1;;
  *) [ "$(cat /proc/"$pid"/comm)" = inetd ] || exit 1; kill -HUP "$pid";;
esac
echo 'Original inetd configuration restored; verify new Telnet connections.'
RESTORE
sh -n "$base/restore.sh"
chmod 700 "$base/restore.sh"
nohup sh "$base/restore.sh" </dev/null > "$base/rollback.log" 2>&1 &
timer=$!
printf '%s\n' "$timer" > "$base/timer.pid"
sleep 1
kill -0 "$timer" || { echo 'Rollback timer unavailable; stopped.'; exit 1; }
cmp "$conf" "$base/inetd.conf.before" || exit 1
mv "$base/inetd.conf.install" "$conf"
sync
kill -HUP "$pid"
echo 'Telnet entry disabled for five-minute trial; SSH unchanged.'
echo "Rollback timer PID: $timer"
echo "Early restore: sh $base/restore.sh now"
echo 'Do not reboot, cancel the timer, or edit inetd.conf during this trial.'
