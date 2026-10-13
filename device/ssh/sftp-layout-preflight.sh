#!/bin/sh
# Fixed-path, read-only layout evidence. No private-key contents or runtime exec.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
LC_ALL=C
export PATH LC_ALL
ROOT=''
PROC=/proc
SYS=/sys
SHA=/usr/bin/sha256sum
STAGE=/root/nimbus-sftp-candidate-v1
fail() { printf '%s\n' "$1" >&2; exit 2; }
[ "$#" -eq 1 ] && [ "$1" = --check ] || fail 'Use --check only; no action performed.'
[ "$(id -u)" = 0 ] || fail 'Authorized root metadata session required.'
for tool in awk stat dirname wc grep cat; do command -v "$tool" >/dev/null 2>&1 || fail 'Required metadata tool unavailable.'; done
[ -f "$SHA" ] && [ -x "$SHA" ] && [ ! -L "$SHA" ] || fail 'Standalone checksum tool unavailable.'
safe_components() {
    component=$1
    while [ "$component" != / ]; do
        [ ! -L "$component" ] || return 1
        component=$(dirname "$component") || return 1
    done
}
bounded_hash() {
    file=$1; limit=$2
    # /proc/self is a kernel-provided symlink, not an unsafe jail component.
    if [ "$file" = "$PROC/self/mountinfo" ]; then
        [ ! -L "$file" ] || return 1
    else safe_components "$file" || return 1; fi
    [ -f "$file" ] && [ -r "$file" ] || return 1
    size=$(wc -c < "$file") || return 1
    case "$size" in ''|*[!0-9]*) return 1;; esac
    [ "$size" -le "$limit" ] || return 1
    sum=$("$SHA" "$file") || return 1
    digest=${sum%% *}
    [ "${#digest}" = 64 ] || return 1
    case "$digest" in *[!0-9a-f]*) return 1;; esac
    printf '%s' "$digest"
}
node() {
    tag=$1; path="$ROOT$2"
    if ! safe_components "$path"; then printf 'NODE %s unsafe\n' "$tag"; return; fi
    if [ ! -e "$path" ]; then printf 'NODE %s absent\n' "$tag"; return; fi
    if [ -d "$path" ]; then kind=directory
    elif [ -f "$path" ]; then kind=file
    else printf 'NODE %s special\n' "$tag"; return; fi
    identity=$(stat -c '%u %g %a %h %s %d %i' "$path" 2>/dev/null) || { printf 'NODE %s unknown\n' "$tag"; return; }
    case "$identity" in *[!0-9\ ]*) printf 'NODE %s unknown\n' "$tag";;
        *) printf 'NODE %s %s %s\n' "$tag" "$kind" "$identity";; esac
}
module_state() {
    if [ ! -r "$PROC/modules" ]; then printf unknown; return; fi
    awk '
        BEGIN {status="inactive"}
        $1 ~ /^g_/ || $1=="usb_f_mass_storage" {status="active"}
        NF<6 || $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ {bad=1}
        END {print bad ? "unknown" : status}
    ' "$PROC/modules" 2>/dev/null || printf unknown
}
metadata() {
    node root /
    node root_home /root
    node stage "$STAGE"
    node jail "$STAGE/jail"
    node privsep "$STAGE/empty"
    node etc /etc
    node auth_root /etc/nimbus-sftp-auth
    node auth_account /etc/nimbus-sftp-auth/nimbus-files
    node authorized /etc/nimbus-sftp-auth/nimbus-files/authorized_keys
    node hostkey "$STAGE/host-ed25519"
    # Do not touch jail media views while USB ownership is active/unknown.
    usb_for_nodes=$(module_state)
    if [ "$usb_for_nodes" = inactive ]; then
        node internal_view "$STAGE/jail/internal"
        node sd_view "$STAGE/jail/sd"
    else printf '%s\n' 'NODE internal_view unknown' 'NODE sd_view unknown'; fi
}
empty_directory() {
    path="$ROOT$1"
    if [ "$overmount" != none ] || ! safe_components "$path" || [ ! -d "$path" ]; then printf unknown; return; fi
    for entry in "$path"/* "$path"/.[!.]* "$path"/..?*; do
        if [ -e "$entry" ] || [ -L "$entry" ]; then printf no; return; fi
    done
    printf yes
}
modules_before=$(bounded_hash "$PROC/modules" 65536) || fail 'Module metadata unavailable or oversized.'
mounts_before=$(bounded_hash "$PROC/self/mountinfo" 262144) || fail 'Mount metadata unavailable or oversized.'
usb=$(module_state)
mount_records=$(awk -v stage="$ROOT$STAGE" -v storage="$ROOT/mnt/storage" -v sd="$ROOT/mnt/sdcard" '
function mode(text,    a,n,i,ro,rw) {
    n=split(text,a,","); for(i=1;i<=n;i++){if(a[i]=="ro")ro=1;if(a[i]=="rw")rw=1}
    return ro && rw ? "ro,rw" : ro ? "ro" : rw ? "rw" : "unknown"
}
{
    sep=0;for(i=7;i<=NF;i++)if($i=="-"){sep=i;break}
    if(!sep || NF!=sep+3 || $1!~/^[0-9]+$/ || $2!~/^[0-9]+$/ || $3!~/^[0-9]+:[0-9]+$/){bad=1;next}
    tag=""
    if($5==storage)tag="internal_source"
    if($5==sd)tag="sd_source"
    if($5==stage "/jail/internal")tag="internal_view"
    if($5==stage "/jail/sd")tag="sd_view"
    if($5==stage || $5==stage "/jail" || $5==stage "/empty" ||
       (index($5,stage "/jail/")==1 && tag=="") ||
       index($5,storage "/")==1 || index($5,sd "/")==1)over=1
    if(tag!="") {
        if(++count>16){bad=1;next}
        fs=$(sep+1);if(fs!~/^(texfat|vfat|exfat|ext3)$/)fs="unreviewed"
        source=$(sep+2);if(source!="/dev/mmcblk0p4" && source!="/dev/mmcblk1p1")source="unreviewed"
        root=($4=="/" ? "/" : "/__unreviewed_root__")
        printf "MOUNT %s %s %s %s %s %s %s %s %s\n",tag,$1,$2,$3,root,mode($6),fs,source,mode($(sep+3))
    }
}
END {if(bad)exit 1;print "OVERMOUNT " (over ? "present" : "none")}
' "$PROC/self/mountinfo") || fail 'Malformed/oversized selected mount metadata.'
overmount=${mount_records##*OVERMOUNT }
metadata_before=$(metadata)
printf '%s\n' 'NIMBUS-SFTP-LAYOUT-BEGIN 2' "USB $usb" 'BEFORE' "$metadata_before" 'MOUNTS' "$mount_records"
privsep_empty=$(empty_directory "$STAGE/empty")
sd_empty=unknown
if [ "$(module_state)" = inactive ] && ! printf '%s\n' "$mount_records" | grep -q '^MOUNT sd_'; then
    sd_empty=$(empty_directory "$STAGE/jail/sd")
fi
printf 'EMPTY privsep %s\nEMPTY sd %s\n' "$privsep_empty" "$sd_empty"
authorized_path="$ROOT/etc/nimbus-sftp-auth/nimbus-files/authorized_keys"
auth_hash=unknown
if safe_components "$authorized_path" && [ -f "$authorized_path" ] && [ ! -L "$authorized_path" ]; then
    auth_info=$(stat -c '%u:%g:%a:%h' "$authorized_path") || auth_info=unknown
    if [ "$auth_info" = 0:0:644:1 ]; then auth_hash=$(bounded_hash "$authorized_path" 16384) || auth_hash=unknown; fi
fi
printf 'AUTHORIZED_SHA256 %s\n' "$auth_hash"
passwd_hash=$(bounded_hash "$ROOT/etc/passwd" 65536) || passwd_hash=unknown
group_hash=$(bounded_hash "$ROOT/etc/group" 65536) || group_hash=unknown
if [ "$passwd_hash" = unknown ] || [ "$group_hash" = unknown ]; then
    printf '%s\n' 'ACCOUNT nimbus-files unknown' 'ACCOUNT nimbus-sshd unknown'
else
    shell_executable=no
    [ -f "$ROOT/bin/false" ] && [ -x "$ROOT/bin/false" ] && shell_executable=yes
    awk -F: -v passwd="$ROOT/etc/passwd" -v group="$ROOT/etc/group" -v executable="$shell_executable" -v privsep_home="$STAGE/empty" '
    FILENAME==passwd {
        if(NF!=7 || $3!~/^[0-9]+$/ || $4!~/^[0-9]+$/){bad=1;next}
        uidcount[$3]++;gidcount[$4]++
        if($1=="nimbus-files" || $1=="nimbus-sshd") {
            occurrences[$1]++;uid[$1]=$3;gid[$1]=$4;shell[$1]=($7=="/bin/false" ? "non_shell" : "other")
            expected_home=($1=="nimbus-files" ? "/internal" : privsep_home)
            home[$1]=($6==expected_home ? "expected" : "other")
        }
        next
    }
    FILENAME==group {
        if(NF!=4 || $3!~/^[0-9]+$/){bad=1;next}
        groups[$3]++;n=split($4,members,",")
        for(i=1;i<=n;i++)if(members[i]!="") {
            for(j=1;j<=2;j++) {
                name=(j==1 ? "nimbus-files" : "nimbus-sshd")
                if(members[i]==name)supp[name SUBSEP $3]=1
                if(gid[name]==$3 && members[i]!=name)foreign[name]=1
            }
        }
    }
    END {
        for(j=1;j<=2;j++) {
            name=(j==1 ? "nimbus-files" : "nimbus-sshd")
            if(bad){print "ACCOUNT " name " unknown";continue}
            if(!occurrences[name]){print "ACCOUNT " name " absent";continue}
            if(occurrences[name]!=1){print "ACCOUNT " name " ambiguous";continue}
            list=gid[name];count=1
            for(key in supp){split(key,pair,SUBSEP);if(pair[1]==name && pair[2]!=gid[name]){list=list "," pair[2];count++}}
            if(count>32){print "ACCOUNT " name " unknown";continue}
            exclusive=(groups[gid[name]]==1 && !foreign[name] ? "yes" : "no")
            printf "ACCOUNT %s present %s %s %s %s %s %s %s %s %s\n",name,uid[name],gid[name],shell[name],executable,uidcount[uid[name]],gidcount[gid[name]],exclusive,list,home[name]
        }
    }' "$ROOT/etc/passwd" "$ROOT/etc/group" || fail 'Account metadata observation failed.'
fi
block=unknown
if [ -r "$SYS/class/block/mmcblk1p1/dev" ]; then
    block=$(cat "$SYS/class/block/mmcblk1p1/dev") || block=unknown
    case "$block" in *[!0-9:]*|'') block=unknown;; esac
fi
printf 'BLOCK sd %s\n' "$block"
metadata_after=$(metadata)
modules_after=$(bounded_hash "$PROC/modules" 65536) || modules_after=unknown
mounts_after=$(bounded_hash "$PROC/self/mountinfo" 262144) || mounts_after=unknown
passwd_after=$(bounded_hash "$ROOT/etc/passwd" 65536) || passwd_after=unknown
group_after=$(bounded_hash "$ROOT/etc/group" 65536) || group_after=unknown
auth_after=unknown
if [ "$auth_hash" != unknown ]; then auth_after=$(bounded_hash "$authorized_path" 16384) || auth_after=unknown; fi
coherence=changed
if [ "$passwd_hash" = unknown ] || [ "$group_hash" = unknown ]; then coherence=unknown; fi
if [ "$metadata_before" = "$metadata_after" ] && [ "$modules_before" = "$modules_after" ] &&
   [ "$mounts_before" = "$mounts_after" ] && [ "$passwd_hash" = "$passwd_after" ] &&
   [ "$group_hash" = "$group_after" ] && [ "$auth_hash" = "$auth_after" ] &&
   [ "$passwd_hash" != unknown ] && [ "$group_hash" != unknown ]; then coherence=stable; fi
printf '%s\n' 'AFTER' "$metadata_after" "COHERENCE $coherence" 'NIMBUS-SFTP-LAYOUT-END 2'
