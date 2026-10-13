#!/bin/sh
# Read-only GameHack integration report. No Python, systemd, listener or writes.
set -u
[ "$#" -eq 0 ] || { printf '%s\n' 'No arguments accepted; no action performed.' >&2; exit 2; }
command -v awk >/dev/null 2>&1 || exit 2
awk -v mounts=/proc/mounts -v modules=/proc/modules \
    -v tcp=/proc/net/tcp -v tcp6=/proc/net/tcp6 '
function mount_state(path,    line,n,a,opts,i,ro,rw,count,result) {
    count=0; result="absent"
    while ((getline line < mounts) > 0) {
        n=split(line,a," ")
        if (n < 4 || a[2] != path) continue
        count++; ro=0; rw=0
        n=split(a[4],opts,",")
        for (i=1;i<=n;i++) { if(opts[i]=="ro") ro=1; if(opts[i]=="rw") rw=1 }
        result=(ro && !rw ? "read_only" : (rw && !ro ? "read_write" : "unknown"))
    }
    close(mounts)
    return count>1 ? "unknown" : result
}
function export_state(    line,status,rc) {
    status="inactive"
    while ((rc=(getline line < modules)) > 0)
        if (line ~ /^g_file_storage[ \t]/) status="active"
    close(modules)
    return rc<0 ? "unknown" : status
}
function listener(path,    line,a,n,rc,found) {
    found=0
    while ((rc=(getline line < path)) > 0) {
        n=split(line,a," ")
        if(n>=4 && a[2] ~ /:08B0$/ && a[4]=="0A") found=1
    }
    close(path)
    return found ? "observed" : (rc<0 ? "unknown" : "not_observed")
}
BEGIN {
    # Readability failure is distinct from a successfully read empty table.
    rc=(getline line < mounts); close(mounts)
    internal=rc<0 ? "unknown" : mount_state("/mnt/storage")
    sd=rc<0 ? "unknown" : mount_state("/mnt/sdcard")
    ftp=rc<0 ? "unknown" : mount_state("/var/ftp/sdcard")
    usb=export_state()
    v4=listener(tcp); v6=listener(tcp6)
    ssh=(v4=="observed" || v6=="observed") ? "observed" : \
        ((v4=="unknown" || v6=="unknown") ? "unknown" : "not_observed")
    printf "{\"schema\":\"nimbus-companion-status/v1\",\"scope\":\"device_observation\","
    printf "\"storage\":{\"internal\":\"%s\",\"sd\":\"%s\",\"sd_ftp\":\"%s\",\"usb_export\":\"%s\"},",internal,sd,ftp,usb
    printf "\"management\":{\"port\":2224,\"listener\":\"%s\",\"authentication\":\"not_tested\",\"host_pin\":\"not_tested\",\"downstream_access\":\"not_qualified\"},",ssh
    printf "\"integration\":{\"remote_browsing\":\"not_qualified\",\"sftp\":\"not_qualified\",\"backup_transfer\":\"not_qualified\",\"media_playback\":\"client_validation_required\",\"pi_worker\":\"independent\"},"
    printf "\"permissions\":{\"remote_write\":false,\"configure_network\":false,\"change_mounts\":false},"
    printf "\"limitations\":[\"Non-atomic observations; refresh before an action\",\"Mount rw is not permission or a successful write test\",\"Listener presence is not pinned authentication\",\"USB export absence is not exclusive ownership proof\",\"Stock media shares are not private backup storage\"]}\n"
}'
