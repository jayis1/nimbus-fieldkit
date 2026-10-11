#!/bin/sh
# Persistent, fail-closed user-level settings. Never source/evaluate saved settings.
# No rootfs, startup, service, firewall, or radio-mode changes.
set -u
umask 077
SELF="$0"
BASE=$(CDPATH= cd "$(dirname "$SELF")" && pwd) || exit 2
STATE="${NIMBUS_STATE_DIR:-$BASE/.settings}"
FEATURES='network_health watchdog speed_tests backup_vault offline_toolbox storage_alerts file_sync pi_jobs local_git encrypted_archives'
fail() { printf '%s\n' "$1" >&2; exit 2; }
valid_feature() {
    case "$1" in network_health|watchdog|speed_tests|backup_vault|offline_toolbox|storage_alerts|file_sync|pi_jobs|local_git|encrypted_archives) return 0;; *) return 1;; esac
}
enabled() {
    [ ! -L "$STATE" ] && [ ! -L "$STATE/$1" ] && [ -f "$STATE/$1" ] || return 1
    [ "$(cat "$STATE/$1" 2>/dev/null)" = on ]
}
need() { command -v "$1" >/dev/null 2>&1; }
capability() {
    case "$1" in
        network_health) printf 'Read-only routes and interface counters\n';;
        watchdog)
            enabled network_health || { printf 'Enable network_health first\n'; return 1; }
            need sleep || { printf 'sleep unavailable\n'; return 1; }
            printf 'Manual, bounded checks; no reconnect or Wi-Fi changes\n';;
        speed_tests)
            if need iperf3 || need iperf; then printf 'Explicit authorized target only; 10-second client test\n'
            else printf 'iperf/iperf3 not installed\n'; return 1; fi;;
        backup_vault|file_sync|encrypted_archives)
            need sha256sum && need wc && need date && need basename || { printf 'Required checksum/file utilities unavailable\n'; return 1; }
            if [ "$1" = encrypted_archives ]; then printf 'Stores pre-encrypted files only; encryption happens on GameHack\n'
            else printf 'Explicit single-file copy; checksum verification; no overwrites\n'; fi;;
        offline_toolbox)
            [ -d "$BASE/docs" ] || { printf 'Bundled documentation directory unavailable\n'; return 1; }
            printf 'Local documents; no Internet needed\n';;
        storage_alerts)
            need df && need awk || { printf 'df/awk unavailable\n'; return 1; }
            printf 'Read-only free-space report; warning below 64 MiB\n';;
        pi_jobs) printf 'Use GameHack pinned Pi client; SanDisk has no verified secure pairing\n'; return 1;;
        local_git)
            need git || { printf 'git not installed\n'; return 1; }
            printf 'Explicit creation of a new local bare repository\n';;
    esac
}
write_setting() {
    [ ! -L "$STATE" ] || fail 'Refusing a symlink settings directory'
    mkdir -p "$STATE" || fail 'Settings directory is not writable'
    [ -d "$STATE" ] || fail 'Invalid settings directory'
    [ ! -L "$STATE/$1" ] || fail 'Refusing a symlink setting'
    if [ -e "$STATE/$1" ] && [ ! -f "$STATE/$1" ]; then fail 'Setting path is not a regular file'; fi
    mkdir "$STATE/.write-lock" 2>/dev/null || fail 'Settings busy or stale .write-lock; review before retrying'
    temporary="$STATE/.toggle.$$"
    if (set -C; printf '%s\n' "$2" > "$temporary"); then
        if mv -f "$temporary" "$STATE/$1"; then
            rmdir "$STATE/.write-lock"
        else
            rm -f "$temporary"
            rmdir "$STATE/.write-lock"
            fail 'Could not commit setting'
        fi
    else
        rmdir "$STATE/.write-lock"
        fail 'Could not create private temporary setting'
    fi
}
require_enabled() {
    valid_feature "$1" || fail 'Unknown feature'
    enabled "$1" || fail "$1 is OFF; enable it explicitly first"
    capability "$1" >/dev/null || fail "$1 dependencies are unavailable"
}
health() {
    printf '\n### Local network health (not an Internet-success claim)\n'
    for file in /proc/net/route /proc/net/dev; do
        if [ -r "$file" ]; then printf '\n%s\n' "$file"; cat "$file"; fi
    done
}
storage() {
    printf '\n### Storage containing toolkit\n'
    df -k "$BASE" || return 1
    free_kb=$(df -k "$BASE" | awk '$4 ~ /^[0-9]+$/ && NF >= 6 {print $4; exit}')
    case "$free_kb" in ''|*[!0-9]*) printf 'Free-space warning threshold unavailable\n';;
        *) if [ "$free_kb" -lt 65536 ]; then printf 'WARNING: less than 64 MiB available\n'; fi;; esac
}
valid_ipv4() {
    printf '%s\n' "$1" | awk -F. 'NF!=4 {exit 1} {for(i=1;i<=4;i++) if($i !~ /^[0-9]+$/ || length($i)>3 || $i>255) exit 1; if($1==0 || $1>=224) exit 1}'
}
copy_verified() {
    source="$1"; destination="$2"
    [ -f "$source" ] && [ ! -L "$source" ] || fail 'Choose one regular, non-symlink source file'
    [ -d "$destination" ] && [ ! -L "$destination" ] || fail 'Destination must be an existing non-symlink directory'
    size=$(wc -c < "$source")
    [ "$size" -le 67108864 ] || fail 'File exceeds 64 MiB limit'
    filename=$(basename "$source")
    case "$filename" in ''|.|..|*[!a-zA-Z0-9._-]*) fail 'Use a simple filename containing letters, digits, dot, underscore or hyphen';; esac
    target="$destination/$filename"
    checksum=$(sha256sum < "$source") || fail 'Source checksum failed'
    if (set -C; cat "$source" > "$target"); then
        copied=$(sha256sum < "$target") || fail 'Readback checksum failed; keep output for inspection'
        [ "$copied" = "$checksum" ] || fail 'Checksum mismatch; output may be partial, do not use it'
        printf 'Verified copy: %s\nSHA-256: %s\n' "$target" "$copied"
    else
        fail 'Copy refused or failed; existing files are never overwritten. A new output may be partial.'
    fi
}
show() {
    printf 'Nimbus features — all default OFF; monitor mode excluded\n'
    for feature in $FEATURES; do
        value=OFF; enabled "$feature" && value=ON
        availability=available
        reason=$(capability "$feature") || availability=unavailable
        printf '%-19s %-3s %-11s %s\n' "$feature" "$value" "$availability" "$reason"
    done
}

case "${1:-show}" in
    help|--help)
        printf '%s\n' 'Nimbus user-level feature switches (no monitor mode)' \
            'show                         Show ON/OFF and availability' \
            'availability FEATURE         Explain native feature prerequisites' \
            'set FEATURE on|off           Persist a setting; unsupported ON is refused' \
            'menu                         Interactive ON/OFF menu' \
            'run network_health           Read routes/interface counters' \
            'run watchdog [COUNT INTERVAL] Foreground, bounded loop; OFF stops within ~1 second' \
            'run storage_alerts           Read free space and warn below 64 MiB' \
            'run offline_toolbox [DOC]    List/read a bundled document' \
            'run backup_vault FILE        Copy one reviewed file into our local vault' \
            'run file_sync FILE DIRECTORY Copy one reviewed file to mounted/local storage' \
            'run encrypted_archives FILE  Store pre-encrypted .age/.gpg data (not encryption)' \
            'run speed_tests IP authorized Run a 10-second iperf client against your server' \
            'run local_git NAME           Create a NEW local bare repository' \
            'Settings do not start daemons, add dependencies, alter services, or enable radio modes.';;
    show) show;;
    availability)
        [ "$#" -eq 2 ] && valid_feature "$2" || fail 'Select a known feature'
        capability "$2";;
    set)
        [ "$#" -eq 3 ] || fail 'Usage: set FEATURE on|off'
        valid_feature "$2" || fail 'Unknown feature (monitor mode is not configurable)'
        case "$3" in on|off) :;; *) fail 'Value must be on or off';; esac
        if [ "$3" = on ]; then
            reason=$(capability "$2") || fail "$2 cannot be enabled: $reason"
        fi
        write_setting "$2" "$3"
        if [ "$2" = network_health ] && [ "$3" = off ]; then write_setting watchdog off; fi
        printf '%s is %s\n' "$2" "$3";;
    menu)
        while :; do
            printf '\n'; show; printf '\n'
            index=1
            for feature in $FEATURES; do printf '%s) toggle %s\n' "$index" "$feature"; index=$((index + 1)); done
            printf 'q) quit\nSelect: '
            read -r selection || exit 0
            selection=$(printf '%s' "$selection" | tr -d '\015')
            case "$selection" in q|Q) exit 0;; 1|2|3|4|5|6|7|8|9|10) :;; *) printf 'Select 1–10 or q\n'; continue;; esac
            index=1
            for feature in $FEATURES; do
                if [ "$selection" = "$index" ]; then
                    value=on; enabled "$feature" && value=off
                    NIMBUS_STATE_DIR="$STATE" sh "$SELF" set "$feature" "$value" || :
                    break
                fi
                index=$((index + 1))
            done
        done;;
    run)
        [ "$#" -ge 2 ] || fail 'Usage: run FEATURE [arguments]'
        feature="$2"; require_enabled "$feature"; shift 2
        case "$feature" in
            network_health) [ "$#" -eq 0 ] || fail 'No target required'; health;;
            storage_alerts) [ "$#" -eq 0 ] || fail 'No target required'; storage;;
            watchdog)
                count="${1:-12}"; interval="${2:-10}"
                [ "$#" -le 2 ] || fail 'Usage: run watchdog [COUNT INTERVAL]'
                case "$count:$interval" in *[!0-9:]*|:*|*:) fail 'Count and interval must be integers';; esac
                [ "${#count}" -le 3 ] && [ "${#interval}" -le 3 ] || fail 'Invalid watchdog bounds'
                [ "$count" -ge 1 ] && [ "$count" -le 120 ] && [ "$interval" -ge 5 ] && [ "$interval" -le 300 ] || fail 'Count 1–120; interval 5–300 seconds'
                index=0
                while [ "$index" -lt "$count" ] && enabled watchdog && enabled network_health; do
                    health
                    if enabled storage_alerts; then storage; fi
                    index=$((index + 1))
                    [ "$index" -lt "$count" ] || break
                    wait_seconds=0
                    while [ "$wait_seconds" -lt "$interval" ] && enabled watchdog && enabled network_health; do
                        sleep 1; wait_seconds=$((wait_seconds + 1))
                    done
                done
                printf 'Watchdog stopped. Wi-Fi and routing unchanged.\n';;
            offline_toolbox)
                if [ "$#" -eq 0 ]; then ls "$BASE/docs"
                elif [ "$#" -eq 1 ]; then
                    case "$1" in FEATURES.md|FIRMWARE-3.04-INSPECTION.md|TOGGLES.md) cat "$BASE/docs/$1";; *) fail 'Unknown bundled document';; esac
                else fail 'Usage: run offline_toolbox [DOC]'; fi;;
            backup_vault|encrypted_archives)
                [ "$#" -eq 1 ] || fail 'Select one reviewed file'
                if [ "$feature" = encrypted_archives ]; then
                    case "$1" in *.age|*.gpg) :;; *) fail 'Use a pre-encrypted .age or .gpg file; encrypt on GameHack first';; esac
                    printf 'Opaque archive storage only; encryption/authenticity is not validated here.\n'
                fi
                [ ! -L "$BASE/vault" ] || fail 'Refusing symlink vault'
                mkdir -p "$BASE/vault" || fail 'Cannot create local vault'
                copy_verified "$1" "$BASE/vault";;
            file_sync) [ "$#" -eq 2 ] || fail 'Usage: run file_sync FILE DIRECTORY'; copy_verified "$1" "$2";;
            speed_tests)
                [ "$#" -eq 2 ] && [ "$2" = authorized ] || fail 'Usage: run speed_tests IP authorized (permission required)'
                valid_ipv4 "$1" || fail 'Use a numeric IPv4 unicast target'
                if need iperf3; then iperf3 -c "$1" -t 10; else iperf -c "$1" -t 10; fi;;
            local_git)
                [ "$#" -eq 1 ] || fail 'Select a new repository name'
                case "$1" in ''|.|..|*[!a-zA-Z0-9._-]*) fail 'Invalid repository name';; esac
                [ ! -L "$BASE/repos" ] || fail 'Refusing symlink repository root'
                mkdir -p "$BASE/repos" || fail 'Cannot create repository root'
                mkdir "$BASE/repos/$1.git" || fail 'Repository already exists or destination is not writable'
                git init --bare "$BASE/repos/$1.git";;
            *) fail 'Feature unavailable in this native profile';;
        esac;;
    *) fail 'Unknown action; use help';;
esac
