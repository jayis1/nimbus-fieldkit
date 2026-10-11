#!/bin/sh
# Inventory only. Never opens a watchdog device or invokes freeze/thaw tools.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
[ "$(id -u)" = 0 ] || { echo 'Use the authorized root SSH session.'; exit 1; }
echo 'CAPTURE CAPABILITIES — READ ONLY; NO FREEZE OR RECOVERY AUTHORIZATION'
printf 'Kernel: '; uname -r
echo 'Memory (kB; inventory, not a reservation):'
if [ -r /proc/meminfo ]; then
    grep -E '^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|Shmem|Mlocked):' /proc/meminfo
else
    echo 'Memory metadata unavailable'
fi
echo 'Selected mounts (no mount changes):'
if [ -r /proc/mounts ]; then
    awk '$2 == "/" || $2 == "/tmp" || $2 == "/run" || $2 == "/dev/shm" {print $1, $2, $3, $4}' /proc/mounts
fi
echo 'Swap backing mounts (swap filenames suppressed; no swap changes):'
if [ -r /proc/swaps ] && [ -r /proc/mounts ]; then
    awk 'FNR == NR {mounts[$2]=$1; next}
        FNR > 1 {
            backing="unknown"; longest=0
            for (m in mounts) {
                if ((m == "/" || $1 == m || index($1, m "/") == 1) && length(m) > longest) {
                    backing=mounts[m]; longest=length(m)
                }
            }
            if ($2 == "partition") backing=$1
            if (backing !~ /^\/dev\/(mmcblk[0-9]+(p[0-9]+)?|root)$/ && backing != "tmpfs" && backing != "shm") backing="other-or-unknown"
            printf "swap%d type=%s size_kB=%s used_kB=%s priority=%s backing=%s\n", ++n, $2, $3, $4, $5, backing
        }
        END {if (!n) print "No active swap entries reported"}' /proc/mounts /proc/swaps
else
    echo 'Swap metadata unavailable'
fi
echo 'Vendor tool presence/hash (not executed):'
for tool in /sbin/fsfreeze /usr/sbin/fsfreeze /bin/busybox; do
    if [ -f "$tool" ] && [ ! -L "$tool" ]; then
        sha256sum "$tool"
    fi
done
echo 'Selected kernel config (if available):'
if [ -r /proc/config.gz ] && command -v zcat >/dev/null 2>&1; then
    zcat /proc/config.gz | grep -E '^(CONFIG_(IKCONFIG|IKCONFIG_PROC|EXT3_FS|JBD|WATCHDOG|WATCHDOG_NOWAYOUT|MXC_WATCHDOG)=|# CONFIG_WATCHDOG_NOWAYOUT is not set)' || :
else
    echo 'Kernel config unavailable through proc'
fi
echo 'Freeze/thaw kernel symbol names (addresses suppressed; not proof of safety):'
if [ -r /proc/kallsyms ]; then
    awk '$3 ~ /^(freeze_super|thaw_super|ext3_freeze|ext3_unfreeze|ioctl_fsfreeze|ioctl_fsthaw)$/ {print $3}' /proc/kallsyms
fi
echo 'Watchdog device-node presence ONLY (never opened):'
for node in /dev/watchdog /dev/watchdog0; do
    [ ! -c "$node" ] || printf '%s present\n' "$node"
done
echo 'Watchdog kernel metadata (may be absent on this legacy kernel):'
for dir in /sys/class/watchdog/watchdog*; do
    [ -d "$dir" ] || continue
    for field in identity state timeout timeleft nowayout; do
        if [ -r "$dir/$field" ]; then
            printf '%s %s: ' "${dir##*/}" "$field"
            cat "$dir/$field"
        fi
    done
done
echo 'Processes with fd links to standard watchdog paths (links read, devices NOT opened):'
watchdog_links=0
if command -v readlink >/dev/null 2>&1; then
    for fd in /proc/[0-9]*/fd/[0-9]*; do
        [ -L "$fd" ] || continue
        target=$(readlink "$fd" 2>/dev/null) || continue
        case "$target" in
            /dev/watchdog|/dev/watchdog0)
                pid=${fd#/proc/}; pid=${pid%%/*}
                printf 'pid=%s fd=%s standard-watchdog-link\n' "$pid" "${fd##*/}"
                watchdog_links=$((watchdog_links + 1))
                ;;
        esac
    done
    printf 'Observed standard watchdog fd links: %s\n' "$watchdog_links"
else
    echo 'readlink unavailable'
fi
echo 'FD scan is racy and excludes aliases/closed handles; zero links does NOT prove watchdog inactive.'
echo 'Selected process names ONLY (not arguments or open-device state):'
ps -A | grep -E 'watchdog|event_manager|fw_server|dropbear' || :
echo 'USB-export module evidence:'
if [ -r /proc/modules ]; then
    if grep -q '^g_file_storage ' /proc/modules; then
        echo 'ACTIVE — capture/deployment review must stop'
        exit 1
    fi
else
    echo 'Unavailable — capture/deployment review must stop'
    exit 1
fi
echo 'No active USB-export module found'
echo 'No freeze, thaw, watchdog open, mount change, firmware helper or reboot performed.'
echo 'Missing watchdog metadata does not prove it inactive. No consistent capture is certified.'
