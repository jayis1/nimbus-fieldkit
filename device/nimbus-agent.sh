#!/bin/sh
# Device-native agent candidate. No dependencies on Python/systemd.
# Run manually only through verified authorized access. No install/flash actions.
set -u
umask 077
section() { printf '\n### %s\n' "$1"; }
read_file() {
    if [ -r "$1" ]; then cat "$1"; else printf 'Unavailable: %s\n' "$1"; fi
}
fail() { printf '%s\n' "$1" >&2; exit 2; }

case "${1:-help}" in
    help|--help)
        printf '%s\n' 'Nimbus native agent (candidate; not installed)' \
            'status                 Read local kernel/network/storage/power inventory' \
             'capabilities           Inspect available binaries and reported Wi-Fi modes' \
             'companion-status       Read-only GameHack integration readiness JSON' \
            'hash FILE              SHA-256 of one explicitly selected regular file' \
            'settings [arguments]   Persistent ON/OFF feature menu and settings' \
            'capture IFACE FILE authorized' \
            '                       Optional bounded ordinary-interface capture' \
            'No passwords, radio reconfiguration, service shutdown, or firmware writes.'
        ;;
    companion-status)
        [ "$#" -eq 1 ] || fail 'companion-status takes no arguments'
        directory=$(CDPATH= cd "$(dirname "$0")" && pwd) || fail 'Cannot locate companion module'
        exec sh "$directory/nimbus-companion-status.sh"
        ;;
    settings)
        shift
        directory=$(CDPATH= cd "$(dirname "$0")" && pwd) || fail 'Cannot locate settings module'
        exec sh "$directory/nimbus-settings.sh" "$@"
        ;;
    status)
        section 'Kernel'; uname -a
        section 'Memory'; read_file /proc/meminfo
        section 'Uptime'; read_file /proc/uptime
        section 'Interface counters'; read_file /proc/net/dev
        section 'Routes (kernel table)'; read_file /proc/net/route
        section 'Wireless counters'; read_file /proc/net/wireless
        section 'Storage'
        if command -v df >/dev/null 2>&1; then df -k; else printf 'df unavailable\n'; fi
        section 'Power supplies'
        for supply in /sys/class/power_supply/*; do
            [ -d "$supply" ] || continue
            printf '%s\n' "$supply"
            for property in type status capacity voltage_now; do
                if [ -r "$supply/$property" ]; then printf '%s: ' "$property"; cat "$supply/$property"; fi
            done
        done
        section 'Clients'
        printf 'Associated client count requires verified driver/hostapd telemetry; not inferred from ARP.\n'
        ;;
    capabilities)
        section 'Runtime tools'
        for tool in busybox iw hostapd_cli tcpdump timeout sha256sum dropbear sshd iperf iperf3 curl wget nc nmap; do
            command -v "$tool" || :
        done
        section 'Reported Wi-Fi capabilities (read-only)'
        if command -v iw >/dev/null 2>&1; then iw list; else printf 'iw unavailable\n'; fi
        section 'Module names'; read_file /proc/modules
        printf '\nReported support is not a successful radio/capture test.\n'
        ;;
    hash)
        [ "$#" -eq 2 ] || fail 'Usage: hash FILE'
        [ -f "$2" ] && [ ! -L "$2" ] || fail 'Select a regular non-symlink file'
        command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum is not installed'
        # Input redirection avoids interpreting a filename as an option.
        sha256sum < "$2"
        ;;
    capture)
        [ "$#" -eq 4 ] && [ "$4" = authorized ] || fail 'Usage: capture IFACE FILE authorized (permission required)'
        interface="$2"
        case "$interface" in ''|*[!a-zA-Z0-9_-]*) fail 'Invalid interface';; esac
        [ "${#interface}" -le 15 ] && [ -d "/sys/class/net/$interface" ] || fail 'Interface does not exist'
        [ -n "$3" ] && [ ! -e "$3" ] && [ ! -L "$3" ] || fail 'Output must be a new explicitly selected file'
        command -v tcpdump >/dev/null 2>&1 || fail 'tcpdump is not installed; no automatic installation'
        command -v timeout >/dev/null 2>&1 || fail 'A supported timeout utility is required'
        timeout 1 sh -c 'exit 0' >/dev/null 2>&1 || fail 'This timeout version/syntax is unsupported'
        # No promiscuous mode (-p), no monitor-mode flag, no interface/channel changes.
        # Exclusive shell redirection creates only a new output file. Contents may be private.
        set -C
        printf 'Capturing permitted traffic: max 15 seconds/250 packets/128 bytes per packet.\n' >&2
        timeout 15 tcpdump -p -n -i "$interface" -c 250 -s 128 -U -w - > "$3"
        result=$?
        case "$result" in
            0|124) printf 'Capture ended. Review output before sharing; verify its pcap integrity.\n' >&2;;
            *) printf 'Capture exited with status %s; output may be partial.\n' "$result" >&2; exit "$result";;
        esac
        ;;
    *) fail 'Unknown action; use help';;
esac
