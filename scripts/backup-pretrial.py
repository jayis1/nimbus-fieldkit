#!/usr/bin/env python3
"""Stream private rollback material over pinned SSH; no explicit device writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-backups'
FILES = [('boot-area.bin', 15 * 1048576), ('settings.bin', 4 * 1048576),
         ('rootfs.bin', 256 * 1048576), ('fwpool.bin', 200 * 1048576),
         ('wl1271-nvs.bin', 912), ('stock-web.tar', None), ('partitions.txt', None)]

# Remote stdout is a strictly framed private binary stream. Each hash is computed
# from the same bytes mirrored to SSH stdout, not a second live-partition read.
REMOTE = r'''set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
[ "$(id -u)" = 0 ] || exit 1
[ -r /proc/modules ] || exit 1
if grep -q '^g_file_storage ' /proc/modules; then exit 1; fi
[ "$(cat /sys/class/block/mmcblk0/size)" = 122142720 ] || exit 1
for spec in 'mmcblk0p1 30720 8192' 'mmcblk0p2 38912 524288' 'mmcblk0p3 563200 409600' 'mmcblk0p4 972800 121169920'; do
    set -- $spec
    [ -b "/dev/$1" ] || exit 1
    [ "$(cat "/sys/class/block/$1/start")" = "$2" ] || exit 1
    [ "$(cat "/sys/class/block/$1/size")" = "$3" ] || exit 1
done
emit_block() {
    printf 'NIMBUS-BEGIN %s %s\n' "$1" "$2"
    (exec 3>&1; dd if="$3" bs=1048576 count="$4" | tee /proc/self/fd/3 | sha256sum)
    printf 'NIMBUS-END %s\n' "$1"
}
emit_block boot-area.bin 15728640 /dev/mmcblk0 15
emit_block settings.bin 4194304 /dev/mmcblk0p1 4
emit_block rootfs.bin 268435456 /dev/mmcblk0p2 256
emit_block fwpool.bin 209715200 /dev/mmcblk0p3 200
[ "$(wc -c < /lib/firmware/ti-connectivity/wl1271-nvs.bin)" -eq 912 ] || exit 1
printf 'NIMBUS-BEGIN wl1271-nvs.bin 912\n'
(exec 3>&1; cat /lib/firmware/ti-connectivity/wl1271-nvs.bin | tee /proc/self/fd/3 | sha256sum)
printf 'NIMBUS-END wl1271-nvs.bin\n'
web_bytes=$(tar -cf - -C /nimbus data | wc -c)
[ "$web_bytes" -gt 0 ] && [ "$web_bytes" -le 67108864 ] || exit 1
printf 'NIMBUS-BEGIN stock-web.tar %s\n' "$web_bytes"
(exec 3>&1; tar -cf - -C /nimbus data | tee /proc/self/fd/3 | sha256sum)
printf 'NIMBUS-END stock-web.tar\n'
inventory=$(for name in mmcblk0p1 mmcblk0p2 mmcblk0p3 mmcblk0p4; do
    printf '%s %s %s\n' "$name" "$(cat /sys/class/block/$name/start)" "$(cat /sys/class/block/$name/size)"
done)
inventory_bytes=$(printf '%s\n' "$inventory" | wc -c)
printf 'NIMBUS-BEGIN partitions.txt %s\n' "$inventory_bytes"
(exec 3>&1; printf '%s\n' "$inventory" | tee /proc/self/fd/3 | sha256sum)
printf 'NIMBUS-END partitions.txt\n'
'''


def receive(stream, output, files=FILES):
    records = []
    for name, expected in files:
        line = stream.readline(257)
        match = re.fullmatch(rb'NIMBUS-BEGIN ([a-zA-Z0-9.-]+) ([0-9]{1,12})\n', line)
        if not match or match[1].decode() != name:
            raise ValueError('Unexpected/malformed backup frame.')
        size = int(match[2])
        limit = 65536 if name == 'partitions.txt' else 64 * 1048576
        if (expected is not None and size != expected) or (expected is None and not 0 < size <= limit):
            raise ValueError('Unexpected backup size.')
        path = output / (name + '.partial')
        checksum = hashlib.sha256()
        with path.open('xb') as destination:
            path.chmod(0o600)
            remaining = size
            while remaining:
                data = stream.read(min(1048576, remaining))
                if not data:
                    raise ValueError('Truncated private backup; partial file retained.')
                destination.write(data); checksum.update(data); remaining -= len(data)
            destination.flush(); os.fsync(destination.fileno())
        trailer = stream.readline(257)
        match = re.fullmatch(rb'([a-f0-9]{64})  -\n', trailer)
        digest = checksum.hexdigest()
        if not match or match[1].decode() != digest:
            raise ValueError('Device-stream and host checksum disagreement.')
        if stream.readline(257) != ('NIMBUS-END ' + name + '\n').encode():
            raise ValueError('Invalid backup end marker.')
        # Re-read the actual private host file, not merely the receiving buffer.
        with path.open('rb') as saved:
            if hashlib.file_digest(saved, 'sha256').hexdigest() != digest:
                raise ValueError('Host file readback checksum disagreement.')
        final = output / name
        if final.exists() or final.is_symlink():
            raise ValueError('Refusing an existing private backup destination.')
        path.rename(final)
        records.append({'name': name, 'bytes': size, 'sha256': digest})
        print('Verified private backup:', name, flush=True)
    if stream.read(1):
        raise ValueError('Unexpected trailing backup data.')
    return records


def prepare_output(path):
    path = Path(os.path.abspath(path))
    if path.parent != PRIVATE or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Use a new direct child of .private-backups/, without symlinks.')
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    info = PRIVATE.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Private backup parent must be owned with mode 0700.')
    if shutil.disk_usage(PRIVATE).free < 1024 ** 3:
        raise ValueError('At least 1 GiB free host space required.')
    path.mkdir(mode=0o700)
    return path


def backup(args):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}', args.host):
        raise ValueError('Use an explicit hostname or IPv4 address.')
    for path in (args.identity, args.known_hosts):
        if not path.is_file():
            raise ValueError('Existing private identity and dedicated known-hosts file required.')
    output = prepare_output(args.output)
    command = ['ssh', '-T', '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null',
               '-o', 'UserKnownHostsFile=' + str(args.known_hosts), '-o', 'IdentitiesOnly=yes',
               '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no',
               '-o', 'KbdInteractiveAuthentication=no', '-o', 'ConnectTimeout=10',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
               '-i', str(args.identity), '-p', '2224', 'root@' + args.host, 'sh -s']
    # SSH key prompts use the local terminal. Diagnostics remain in private staging.
    with (output / 'ssh-transfer.log').open('xb') as log:
        log_path = output / 'ssh-transfer.log'; log_path.chmod(0o600)
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        timer = threading.Timer(1800, process.kill); timer.daemon = True; timer.start()
        try:
            process.stdin.write(REMOTE.encode()); process.stdin.close()
            records = receive(process.stdout, output)
            if process.wait(timeout=30) != 0:
                raise ValueError('SSH backup command failed; private staging retained.')
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill(); process.wait()
            process.stdout.close()
    manifest = {'schema': 'nimbus-private-pretrial-backup/v1', 'captured_utc': datetime.now(timezone.utc).isoformat(),
                'device_host': args.host, 'ssh_port': 2224, 'files': records,
                'same_stream_sha256_verified': True, 'host_file_readback_verified': True,
                'live_raw_snapshot': True, 'filesystem_consistency_verified': False,
                'restore_tested': False, 'flash_authorized': False,
                'warning': 'Private credentials-bearing rollback material, not a certified recovery image or full media-disk backup.'}
    with (output / 'BACKUP-MANIFEST.json').open('x') as stream:
        stream.write(json.dumps(manifest, indent=2) + '\n')
    (output / 'BACKUP-MANIFEST.json').chmod(0o600)
    with (output / 'SHA256SUMS').open('x') as stream:
        stream.write(''.join(r['sha256'] + '  ' + r['name'] + '\n' for r in records))
    (output / 'SHA256SUMS').chmod(0o600)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--identity', type=Path, default=Path.home() / '.ssh/nimbus-admin-ed25519')
    parser.add_argument('--known-hosts', type=Path, default=Path.home() / '.ssh/nimbus-test-known-hosts')
    parser.add_argument('--output', type=Path, default=PRIVATE / ('nimbus-pretrial-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')))
    args = parser.parse_args(); os.umask(0o077)
    try:
        output = backup(args)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit('Backup failed. Private staging retained; inspect locally, never upload its contents. No flash performed.')
    print('Complete private backup set:', output)
    print('Live-read consistency and restore are untested. No firmware writes or device-side backup staging performed.')
