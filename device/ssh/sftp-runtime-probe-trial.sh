#!/bin/sh
# Exact version/own-process probes only. No server, account, jail or media action.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
umask 077
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
SHA=/usr/bin/sha256sum
fail() { printf '%s\n' "$1" >&2; exit 2; }
[ "$#" -eq 1 ] || fail 'Use --check or --run only.'
case "$1" in --check|--run) :;; *) fail 'No other runtime action accepted.';; esac
[ "$(id -u)" = 0 ] && [ "$(uname -m)" = armv7l ] || fail 'Expected authorized native ARMv7 root session.'
[ "$BASE" = /tmp/nimbus-sftp-probe-r1 ] && [ ! -L /tmp ] && [ ! -L "$BASE" ] || fail 'Use the fresh fixed private tmpfs stage.'
[ "$(stat -c '%u:%g:%a' "$BASE")" = 0:0:700 ] || fail 'Private stage metadata differs.'
[ -f "$SHA" ] && [ ! -L "$SHA" ] && [ "$(stat -c '%u:%g:%a' "$SHA")" = 0:0:755 ] || fail 'Standalone native hasher metadata differs.'
printf '%s  %s\n' c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2 "$SHA" | "$SHA" -c - >/dev/null || fail 'Native hasher pin differs.'
prerequisites() {
    [ -r /proc/modules ] && [ -r /proc/self/mountinfo ] && [ -r /proc/mounts ] || fail 'Ownership metadata unavailable.'
    awk '$1~/^g_/ || $1=="usb_f_mass_storage" {bad=1}
         NF<6 || $2!~/^[0-9]+$/ || $3!~/^[0-9]+$/ {bad=1}
         END {exit bad}' /proc/modules || fail 'USB export active/unknown; no probe executed.'
    root_identity=$(awk '$5=="/" && index($0," - ext3 "){n++;value=$3} END {if(n!=1)exit 1;print value}' /proc/self/mountinfo) || fail 'Expected root identity unavailable.'
    [ "$root_identity" = 179:2 ] && [ "$(cat /sys/class/block/mmcblk0p2/dev)" = 179:2 ] || fail 'Root block identity differs.'
    awk '$2=="/tmp" {n++;if($3!="tmpfs" || $4!~/(^|,)rw(,|$)/ || $4~/(^|,)ro(,|$)/)bad=1} END {exit n!=1 || bad}' /proc/mounts || fail 'Writable tmpfs stage unavailable.'
    [ "$(cat /sys/class/power_supply/mc13892_charger/online)" = 1 ] || fail 'External power not detected.'
    free=$(df -k /tmp | awk '$2~/^[0-9]+$/ && $4~/^[0-9]+$/ {print $4;exit}')
    case "$free" in ''|*[!0-9]*) fail 'Tmpfs budget unknown.';; esac
    [ "$free" -ge 256 ] || fail 'Retain at least 256 KiB tmpfs headroom.'
}
cd "$BASE"
for file in trial.sh MANIFEST.json SHA256SUMS sshd rlimit-compat-probe rlimit-select-compat-probe; do
    [ -f "$file" ] && [ ! -L "$file" ] && [ "$(stat -c '%u:%g:%a:%h' "$file")" = 0:0:600:1 ] || fail 'Fresh package file metadata differs.'
done
[ ! -e CLAIM ] && [ ! -L CLAIM ] || fail 'Prior probe attempt retained; never rerun or repair this stage.'
"$SHA" -c SHA256SUMS >/dev/null || fail 'Package hashes differ.'
printf '%s  %s\n' \
 bc10f02c3d1803bcb643448326b9579cc7c08bb25d62f0bb0e43d6565d005355 sshd \
 0374ac9c229b371433508dbe4b97709cdf3a6396646fe9c07b2419da1f94a520 rlimit-compat-probe \
 1274e41fa34f92f1e07d84a513ef9348663617460b8b5edf3f6bf6de325531d9 rlimit-select-compat-probe | "$SHA" -c - >/dev/null || fail 'Pinned ARM probe inputs differ.'
prerequisites
if [ "$1" = --check ]; then printf '%s\n' 'SFTP-PROBE-CHECK=PASS no-runtime-executed'; exit 0; fi
# Claim before chmod/execution; failed attempts stay private and non-reusable.
(set -C; printf 'ATTEMPTED\n' > CLAIM) || fail 'Could not claim a fresh attempt.'
chmod 700 sshd rlimit-compat-probe rlimit-select-compat-probe
prerequisites
version=$(./sshd -V 2>&1) || fail 'Candidate version probe failed; evidence retained.'
[ "$version" = 'OpenSSH_10.6p1, without OpenSSL' ] || fail 'Candidate version differs.'
printf 'VERSION %s\n' "$version"
prerequisites
# Capture via a pipe, never a regular device log: probe FSIZE=0 is intentional.
raw=$(./rlimit-compat-probe) || fail 'Raw process compatibility probe failed.'
case "$raw" in
 '{"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":true,"scope":"process_compatibility_only"}'|\
 '{"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":false,"scope":"process_compatibility_only"}') :;;
 *) fail 'Raw probe observations differ.';;
esac
printf 'RAW %s\n' "$raw"
prerequisites
fallback=$(./rlimit-select-compat-probe) || fail 'Selected fallback compatibility probe failed.'
[ "$fallback" = '{"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":true,"scope":"process_compatibility_only"}' ] || fail 'Selected fallback observations differ.'
printf 'FALLBACK %s\n' "$fallback"
prerequisites
printf '%s\n' 'SFTP-PROBE-RESULT=PASS process-compatibility-only service_qualified=no flash_authorized=no'
