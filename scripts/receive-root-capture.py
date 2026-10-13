#!/usr/bin/env python3
"""Offline receiver prototype. No SSH launcher, device worker or capture approval."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-backups'
ROOT_BYTES = 256 * 1024**2
MAX_LINE = 256


def prepare_output(path):
    path = Path(path).absolute()
    if path.parent != PRIVATE or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Use a new direct private backup child without symlinks.')
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    info = PRIVATE.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Private backup parent ownership/permissions differ.')
    if shutil.disk_usage(PRIVATE).free < ROOT_BYTES + 64 * 1024**2:
        raise ValueError('Insufficient host space for root capture and margin.')
    path.mkdir(mode=0o700)  # Never reuse an earlier successful or failed attempt.
    return path


def check_output(output):
    output = Path(output).absolute()
    if output.parent != PRIVATE or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Unexpected private capture destination.')
    for path in (PRIVATE, output):
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Unsafe private directory metadata.')
    for name in ('rootfs.bin.partial', 'rootfs.bin', 'CAPTURE-MANIFEST.json', 'CAPTURE-MANIFEST.json.partial'):
        if (output / name).exists() or (output / name).is_symlink():
            raise ValueError('Prior capture evidence exists; no reuse.')
    return output


def private_fd(path):
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def receive(stream, control, output, session):
    """Receive one fixed root frame and acknowledge only after durable readback.

    stream/control are binary file-like protocol channels supplied by a future
    separately reviewed controller. No process, network or device is opened here.
    Any failure preserves partial evidence without a success manifest.
    """
    if not isinstance(session, str) or not re.fullmatch('[a-f0-9]{64}', session):
        raise ValueError('Expected fresh controller-supplied 256-bit session token.')
    output = check_output(output)
    begin = ('NIMBUS-ROOT-BEGIN ' + session + ' ' + str(ROOT_BYTES) + ' 179:2 ro\n').encode()
    if stream.readline(MAX_LINE + 1) != begin:
        raise ValueError('Capture header/state/session/geometry refused.')
    partial = output / 'rootfs.bin.partial'
    checksum = hashlib.sha256()
    with os.fdopen(private_fd(partial), 'wb') as destination:
        remaining = ROOT_BYTES
        while remaining:
            data = stream.read(min(1024**2, remaining))
            if not data or len(data) > remaining:
                raise ValueError('Truncated or oversized capture frame; partial evidence retained.')
            destination.write(data)
            checksum.update(data)
            remaining -= len(data)
        destination.flush()
        os.fsync(destination.fileno())
    digest = checksum.hexdigest()
    end = ('NIMBUS-ROOT-END ' + session + ' ' + digest + '\n').encode()
    if stream.readline(MAX_LINE + 1) != end:
        raise ValueError('Source-stream digest/session/end marker refused.')
    info = partial.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != ROOT_BYTES:
        raise ValueError('Private partial metadata differs.')
    with partial.open('rb') as saved:
        if hashlib.file_digest(saved, 'sha256').hexdigest() != digest:
            raise ValueError('Host file readback differs; no acknowledgment.')
    sync_directory(output)
    ack = ('NIMBUS-HOST-VERIFIED ' + session + ' ' + digest + '\n').encode()
    written = control.write(ack)
    if written != len(ack):
        raise ValueError('Acknowledgment write failed; no completed capture.')
    control.flush()
    # Never treat matching bytes alone as completion. Premature rw, restoration
    # failure, missing trailer, disconnect and unexpected trailing bytes refuse.
    restored = ('NIMBUS-ROOT-RESULT ' + session + ' ro-until-ack rw-restored ssh-restored vendor-restored\n').encode()
    if stream.readline(MAX_LINE + 1) != restored or stream.read(1):
        raise ValueError('Lifecycle/restoration completion refused; partial evidence retained.')
    # Hardlink promotion is exclusive, unlike rename's overwrite semantics.
    final = output / 'rootfs.bin'
    os.link(partial, final, follow_symlinks=False)
    sync_directory(output)
    manifest = {
        'schema': 'nimbus-private-root-capture-receipt/v1', 'session': session,
        'bytes': ROOT_BYTES, 'sha256': digest,
        'same_stream_sha256_verified': True, 'host_file_readback_verified': True,
        'host_acknowledgment_sent': True, 'device_reported_ro_until_ack': True,
        'device_reported_rw_and_services_restored': True,
        'offline_receiver_prototype': True,
        'filesystem_consistency_verified': False, 'restore_tested': False,
        'flash_authorized': False, 'production_ready': False,
        'limitations': 'Protocol receipt only; device assertions do not establish native lifecycle, filesystem consistency or physical recovery.'}
    receipt_partial = output / 'CAPTURE-MANIFEST.json.partial'
    receipt_final = output / 'CAPTURE-MANIFEST.json'
    with os.fdopen(private_fd(receipt_partial), 'wb') as receipt:
        receipt.write((json.dumps(manifest, indent=2) + '\n').encode())
        receipt.flush()
        os.fsync(receipt.fileno())
    sync_directory(output)
    os.link(receipt_partial, receipt_final, follow_symlinks=False)
    try:
        sync_directory(output)
    except OSError:
        # Withdraw only our own publication link; retain the complete partial
        # receipt and image evidence. Never replace/delete somebody else's file.
        try:
            pending, published = receipt_partial.lstat(), receipt_final.lstat()
            if (pending.st_dev, pending.st_ino) == (published.st_dev, published.st_ino):
                receipt_final.unlink()
                sync_directory(output)
        except OSError:
            pass  # Filesystem failure/power loss cannot promise withdrawal durability.
        raise
    # Retain partial as another name for the same inode, including after success.
    # A controller must also confirm SSH/worker exit and read-only offline fsck.
    return manifest


if __name__ == '__main__':
    raise SystemExit('Receiver prototype only. No live capture launcher or device worker is supplied.')
