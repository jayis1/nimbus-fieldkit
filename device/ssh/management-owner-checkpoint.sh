#!/bin/sh
# Read-only process/socket association. No stop targets or state changes supplied.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
fail() { echo "$1" >&2; exit 1; }
[ "$#" = 0 ] || fail 'No action arguments accepted.'
[ "$(id -u)" = 0 ] || fail 'Authorized root session required.'
for tool in awk stat readlink sha256sum; do
    command -v "$tool" >/dev/null 2>&1 || fail 'Required observation tool unavailable.'
done
[ -r /proc/modules ] && ! grep -q '^g_file_storage ' /proc/modules || fail 'USB export active or unknown.'
[ -r /proc/self/mountinfo ] && [ -r /sys/class/block/mmcblk0p2/dev ] || fail 'Root metadata unavailable.'
root_identity=$(awk '$5 == "/" && index($0, " - ext3 ") {print $3}' /proc/self/mountinfo)
[ "$root_identity" = "$(cat /sys/class/block/mmcblk0p2/dev)" ] || fail 'Expected ext3 root identity not established.'
[ -r /proc/net/tcp ] || fail 'IPv4 socket metadata unavailable.'
echo 'MANAGEMENT OWNER CHECKPOINT — READ ONLY; NOT STOP/REMOUNT APPROVAL'
observed=0
for process in /proc/[0-9]*; do
    [ -r "$process/comm" ] || continue
    label=$(cat "$process/comm" 2>/dev/null) || continue
    case "$label" in
        nimbus) expected=b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd;;
        dropbear|dropbearmulti-b|dropbearmulti) expected=1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c;;
        *) continue;;
    esac
    pid=${process##*/}
    # Greedy removal supports spaces/parentheses in comm; fields then begin at state.
    identity=$(awk '{sub(/^[0-9]+ \(.*\) /, ""); print $2 ":" $20}' "$process/stat" 2>/dev/null) || identity=
    parent=${identity%:*}; start=${identity#*:}
    case "$parent:$start" in ''|:*|*:|*[!0-9:]*)
        printf 'pid=%s identity=unavailable_or_raced\n' "$pid"; continue;;
    esac
    match=unavailable_or_unsafe
    if [ -f "$process/exe" ]; then
        bytes=$(stat -L -c '%s' "$process/exe" 2>/dev/null) || bytes=
        case "$bytes" in ''|*[!0-9]*) :;; *)
            if [ "$bytes" -le 8388608 ]; then
                actual=$(sha256sum "$process/exe" 2>/dev/null | awk '{print $1}')
                if [ "$actual" = "$expected" ]; then match=matched; else match=different_or_raced; fi
            fi;;
        esac
    fi
    port2224=0; port2225=0; incomplete=0
    [ -d "$process/fd" ] || incomplete=$((incomplete+1))
    for fd in "$process"/fd/[0-9]*; do
        [ -L "$fd" ] || continue
        target=$(readlink "$fd" 2>/dev/null) || { incomplete=$((incomplete+1)); continue; }
        case "$target" in socket:\[*\]) inode=${target#socket:[}; inode=${inode%]};; *) continue;; esac
        case "$inode" in ''|*[!0-9]*) incomplete=$((incomplete+1)); continue;; esac
        for table in /proc/net/tcp /proc/net/tcp6; do
            [ -r "$table" ] || continue
            counts=$(awk -v inode="$inode" '$4 == "0A" && $10 == inode {
                if ($2 ~ /:08B0$/) a++; if ($2 ~ /:08B1$/) b++
            } END {print a+0 ":" b+0}' "$table") || { incomplete=$((incomplete+1)); continue; }
            port2224=$((port2224 + ${counts%:*}))
            port2225=$((port2225 + ${counts#*:}))
        done
    done
    after=$(awk '{sub(/^[0-9]+ \(.*\) /, ""); print $2 ":" $20}' "$process/stat" 2>/dev/null) || after=
    if [ "$after" != "$identity" ]; then
        printf 'pid=%s identity=changed_or_raced\n' "$pid"; continue
    fi
    printf 'pid=%s label=%s parent_pid=%s start_ticks=%s reviewed_executable=%s listening_fd_refs_2224=%s listening_fd_refs_2225=%s incomplete=%s\n' \
        "$pid" "$label" "$parent" "$start" "$match" "$port2224" "$port2225" "$incomplete"
    observed=$((observed+1))
done
printf 'Whitelisted process observations: %s\n' "$observed"
echo 'Only listener associations shown; no peer addresses, arguments, executable paths or key/log contents.'
echo 'Racy metadata, not guaranteed session ancestry or exhaustive holder inventory. Never reuse PIDs as stop targets.'
echo 'No signals, service invocation, sync, remount, watchdog access, block access, reboot or firmware write performed.'
