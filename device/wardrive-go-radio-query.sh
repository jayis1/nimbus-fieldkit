#!/bin/sh
# Fixed read-only nl80211 GET queries. Never trigger/dump scans, set modes,
# channels, routes, interfaces, or run service/reset helpers. Output redacted.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
[ "$#" -eq 0 ] || exit 2
[ -f /usr/sbin/iw ] && [ ! -L /usr/sbin/iw ] || exit 2
[ -f /usr/bin/sha256sum ] && [ ! -L /usr/bin/sha256sum ] || exit 2
printf '%s  %s\n' c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2 /usr/bin/sha256sum | /usr/bin/sha256sum -c - >/dev/null || exit 2
printf '%s  %s\n' 468f4271f5af9eaa5380f30b9717a58462baec4596e87461ff23859dfe44321e /usr/sbin/iw | /usr/bin/sha256sum -c - >/dev/null || exit 2
printf 'GO-RADIO-QUERY=v1\n'
if report=$(LC_ALL=C /usr/sbin/iw list 2>/dev/null); then
    printf '%s\n' "$report" | awk '
        /^Wiphy / {print "WIPHY observed"; modes=0; next}
        /Supported interface modes:/ {modes=1; next}
        /valid interface combinations:/ {print "INTERFACE_COMBINATIONS reported_not_qualified"; modes=0; next}
        modes && $1=="*" {
            if ($2=="managed" || $2=="AP" || $2=="AP/VLAN" || $2=="monitor" || $2=="IBSS" || $2=="mesh")
                print "ADVERTISED_MODE " $2
            else print "ADVERTISED_MODE other"
            next
        }
        modes && NF {modes=0}
    '
    printf 'QUERY list exit=0\n'
else
    printf 'QUERY list failed\n'
    exit 3
fi
if report=$(LC_ALL=C /usr/sbin/iw dev 2>/dev/null); then
    printf '%s\n' "$report" | awk '
        /^phy#[0-9]+$/ {phy=$0; sub(/^phy#/, "",phy); name=""; next}
        $1=="Interface" {
            name=($2=="wlan0" || $2=="wlan1") ? $2 : ""
            if (name && phy ~ /^[0-9]+$/) print "RADIO " name " phy_index=" phy
            next
        }
        name && $1=="type" {
            type=($2=="managed" || $2=="AP" || $2=="monitor" || $2=="IBSS" || $2=="AP/VLAN" || $2=="mesh") ? $2 : "unknown"
            print "INTERFACE_TYPE " name " " type
        }
        name && $1=="channel" && $2 ~ /^[0-9]+$/ && $3 ~ /^\([0-9]+$/ {
            frequency=$3; sub(/^\(/, "",frequency)
            if ($2<=196 && frequency>=2000 && frequency<=7125)
                print "CHANNEL " name " number=" $2 " frequency_mhz=" frequency
        }
    '
    printf 'QUERY dev exit=0\n'
else
    printf 'QUERY dev failed\n'
    exit 3
fi
unset report
printf 'GO-RADIO-QUERY-END scan=not_requested coexistence=unqualified native_go=unqualified\n'
