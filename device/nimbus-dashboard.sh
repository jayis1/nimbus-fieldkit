#!/bin/sh
# Publish static, read-only JSON for the browser; NEVER execute browser requests.
set -u
umask 077
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd) || exit 2
STATE="${NIMBUS_STATE_DIR:-$BASE/.settings}"
PROC="${NIMBUS_PROC_DIR:-/proc}"
POWER="${NIMBUS_POWER_DIR:-/sys/class/power_supply}"
FEATURES='network_health watchdog speed_tests backup_vault offline_toolbox storage_alerts file_sync pi_jobs local_git encrypted_archives'
fail() { printf '%s\n' "$1" >&2; exit 2; }
enabled() { [ ! -L "$STATE" ] && [ -f "$STATE/$1" ] && [ ! -L "$STATE/$1" ] && [ "$(cat "$STATE/$1")" = on ]; }
snapshot() {
    [ -d "$BASE/dashboard" ] && [ ! -L "$BASE/dashboard" ] || fail 'Missing or symlink dashboard directory'
    work="$BASE/dashboard/.publish-lock"
    mkdir "$work" 2>/dev/null || fail 'Publisher busy or stale .publish-lock; review before retrying'
    trap 'rm -f "$work/features.tsv" "$work/vault.tsv" "$work/state.json"; rmdir "$work" 2>/dev/null' 0
    trap 'exit 1' 1 2 15
    : > "$work/features.tsv"
    for feature in $FEATURES; do
        on=off; enabled "$feature" && on=on
        available=yes
        reason=$(NIMBUS_STATE_DIR="$STATE" sh "$BASE/nimbus-settings.sh" availability "$feature") || available=no
        printf '%s\t%s\t%s\t%s\n' "$feature" "$on" "$available" "$reason" >> "$work/features.tsv"
    done
    : > "$work/vault.tsv"
    count=0
    if [ ! -L "$BASE/vault" ]; then
        for file in "$BASE"/vault/*; do
            [ -f "$file" ] && [ ! -L "$file" ] || continue
            name=$(basename "$file")
            case "$name" in *[!a-zA-Z0-9._-]*) continue;; esac
            size=$(LC_ALL=C ls -ln "$file" | awk '{print $5}')
            case "$size" in ''|*[!0-9]*) continue;; esac
            printf '%s\t%s\n' "$name" "$size" >> "$work/vault.tsv"
            count=$((count + 1)); [ "$count" -lt 64 ] || break
        done
    fi
    disk=$(df -k "$BASE" | awk '$2~/^[0-9]+$/&&$3~/^[0-9]+$/&&$4~/^[0-9]+$/ {print $2 " " $3 " " $4; exit}')
    set -- $disk
    [ "$#" -eq 3 ] || fail 'Cannot read storage metrics'
    battery_capacity=''; battery_status=Unknown
    for supply in "$POWER"/*; do
        [ -r "$supply/type" ] || continue
        [ "$(cat "$supply/type")" = Battery ] || continue
        if [ -r "$supply/capacity" ]; then battery_capacity=$(cat "$supply/capacity"); fi
        if [ -r "$supply/status" ]; then battery_status=$(cat "$supply/status"); fi
        break
    done
    for file in uptime meminfo net/route net/dev net/tcp; do [ -r "$PROC/$file" ] || fail "Missing readable $PROC/$file"; done
    # Arguments are data, not shell expressions. The awk encoder escapes JSON strings.
    awk -f "$BASE/dashboard/snapshot.awk" \
        -v generated_at="$(date +%s)" -v publisher="${NIMBUS_PUBLISHER_MODE:-manual}" \
        -v install_path="$BASE" -v hostname="$(hostname)" \
        -v disk_total="$1" -v disk_used="$2" -v disk_free="$3" \
        -v battery_capacity="$battery_capacity" -v battery_status="$battery_status" \
        -v uptime_file="$PROC/uptime" -v memory_file="$PROC/meminfo" \
        -v routes_file="$PROC/net/route" -v interfaces_file="$PROC/net/dev" \
        -v features_file="$work/features.tsv" -v vault_file="$work/vault.tsv" -v tcp_file="$PROC/net/tcp" \
        "$PROC/uptime" "$PROC/meminfo" "$PROC/net/route" "$PROC/net/dev" \
        "$work/features.tsv" "$work/vault.tsv" "$PROC/net/tcp" > "$work/state.json" || fail 'Snapshot encoder failed'
    [ ! -L "$BASE/dashboard/state.json" ] || fail 'Refusing a symlink snapshot'
    if [ -e "$BASE/dashboard/state.json" ] && [ ! -f "$BASE/dashboard/state.json" ]; then fail 'Snapshot destination is not a regular file'; fi
    mv -f "$work/state.json" "$BASE/dashboard/state.json" || fail 'Could not publish snapshot'
    rm -f "$work/features.tsv" "$work/vault.tsv"
    rmdir "$work" || fail 'Could not release publisher lock'
    trap - 0 1 2 15
}

case "${1:-help}" in
    help|--help)
        printf '%s\n' 'Nimbus dark dashboard: static assets plus local snapshot publisher' \
            'snapshot                    Publish one read-only telemetry snapshot' \
            'watch [COUNT INTERVAL]       Bounded publisher, requires watchdog + health ON' \
            'import-settings OLD_DIR      Copy only validated ON/OFF flags into empty settings' \
            'No browser command execution, radio changes, listeners, or vendor-dashboard replacement.';;
    snapshot) snapshot; printf 'Published dashboard/state.json\n';;
    import-settings)
        [ "$#" -eq 2 ] || fail 'Select the old installation directory'
        old="$2/.settings"
        [ -d "$old" ] && [ ! -L "$old" ] || fail 'Old settings unavailable or symlinked'
        [ ! -e "$STATE" ] && [ ! -L "$STATE" ] || fail 'New settings already exist; refusing overwrite'
        for feature in $FEATURES; do
            if [ -e "$old/$feature" ]; then
                [ -f "$old/$feature" ] && [ ! -L "$old/$feature" ] || fail 'Invalid old setting'
                value=$(cat "$old/$feature")
                case "$value" in on|off) :;; *) fail 'Invalid old setting value';; esac
            fi
        done
        mkdir "$STATE" || fail 'Cannot create new settings directory'
        for feature in $FEATURES; do
            if [ -f "$old/$feature" ]; then cat "$old/$feature" > "$STATE/$feature" || fail 'Could not copy setting'; fi
        done
        printf 'Imported ON/OFF flags only; no jobs or services started.\n';;
    watch)
        count="${2:-120}"; interval="${3:-15}"
        [ "$#" -le 3 ] || fail 'Usage: watch COUNT INTERVAL'
        case "$count:$interval" in *[!0-9:]*|:*|*:) fail 'Use integer bounds';; esac
        [ "${#count}" -le 3 ] && [ "${#interval}" -le 3 ] || fail 'Invalid publisher bounds'
        [ "$count" -ge 1 ] && [ "$count" -le 240 ] && [ "$interval" -ge 5 ] && [ "$interval" -le 300 ] || fail 'Count 1–240; interval 5–300 seconds'
        enabled watchdog && enabled network_health || fail 'Enable watchdog and network_health first'
        export NIMBUS_PUBLISHER_MODE=watching
        index=0
        while [ "$index" -lt "$count" ] && enabled watchdog && enabled network_health; do
            snapshot; index=$((index + 1)); printf 'Snapshot %s/%s\n' "$index" "$count"
            [ "$index" -lt "$count" ] || break
            elapsed=0
            while [ "$elapsed" -lt "$interval" ] && enabled watchdog && enabled network_health; do sleep 1; elapsed=$((elapsed + 1)); done
        done
        NIMBUS_PUBLISHER_MODE=stopped; export NIMBUS_PUBLISHER_MODE
        snapshot
        printf 'Publisher stopped; Wi-Fi and routing unchanged.\n';;
    *) fail 'Unknown dashboard action';;
esac
