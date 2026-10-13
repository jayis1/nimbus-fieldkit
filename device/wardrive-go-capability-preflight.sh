#!/bin/sh
# Read-only metadata only: no scan/ioctl, mode/channel/route change or service call.
# No SSID/BSSID/MAC, saved Wi-Fi config, credentials, process args or GPS output.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
[ "$#" -eq 0 ] || exit 2
command -v awk >/dev/null 2>&1 || exit 2
printf 'GO-INVENTORY=v1\n'
for name in wlan0 wlan1; do
    if [ -d "/sys/class/net/$name" ]; then
        state=$(cat "/sys/class/net/$name/operstate" 2>/dev/null) || state=unknown
        case "$state" in up|down|dormant|unknown|lowerlayerdown|notpresent|testing) :;; *) state=unknown;; esac
        if [ -d "/sys/class/net/$name/wireless" ]; then wireless=observed; else wireless=not_observed; fi
        printf 'INTERFACE %s present operstate=%s wireless_sysfs=%s\n' "$name" "$state" "$wireless"
    else
        printf 'INTERFACE %s not_observed\n' "$name"
    fi
done
if [ -r /proc/net/wireless ]; then
    awk '$1=="wlan0:" || $1=="wlan1:" {name=$1; sub(/:$/, "",name); print "WIRELESS_PROC " name " observed"}' /proc/net/wireless
else
    printf 'WIRELESS_PROC unavailable\n'
fi
if [ -r /proc/modules ]; then
    awk '$1 ~ /^(wl12xx|wl12xx_sdio|wl1271|wl1271_sdio|cfg80211|mac80211|g_file_storage)$/ {print "MODULE " $1 " observed"}' /proc/modules
else
    printf 'MODULES unavailable\n'
fi
for tool in iw iwconfig iwlist; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf 'TOOL %s present_not_executed\n' "$tool"
    else
        printf 'TOOL %s not_observed\n' "$tool"
    fi
done
if [ -r /proc/config.gz ] && command -v zcat >/dev/null 2>&1; then
    zcat /proc/config.gz | awk '/^CONFIG_(WIRELESS_EXT|WEXT_CORE|CFG80211|MAC80211|WL12XX|WL1271|WL12XX_SDIO)=(y|m)$/ {print "KCONFIG " $0}'
else
    printf 'KCONFIG unavailable\n'
fi
printf 'QUALIFICATION scan=unqualified coexistence=unqualified monitor=unqualified native_go=unqualified\n'
printf 'GO-INVENTORY-END radio_actions=none credential_reads=none\n'
