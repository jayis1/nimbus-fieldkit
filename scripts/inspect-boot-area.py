#!/usr/bin/env python3
"""Read-only uImage inventory of a local boot-area backup, not a restore tool."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct
import zlib

MAGIC = b'\x27\x05\x19\x56'


def inspect(data):
    images = []
    start = 0
    while True:
        offset = data.find(MAGIC, start)
        if offset < 0:
            break
        start = offset + 4
        if offset + 64 > len(data):
            continue
        header = data[offset:offset + 64]
        fields = struct.unpack('>7I4B32s', header)
        size = fields[3]
        if not size or offset + 64 + size > len(data):
            continue
        payload = data[offset + 64:offset + 64 + size]
        name = fields[-1].split(b'\0', 1)[0]
        # Only header labels, never arbitrary printable bootloader/environment contents.
        label = ''.join(chr(value) if 32 <= value < 127 else '?' for value in name)
        images.append({'offset_bytes': offset, 'payload_bytes': size,
                       'total_bytes': size + 64, 'header_label': label,
                       'header_crc_ok': zlib.crc32(header[:4] + bytes(4) + header[8:]) & 0xffffffff == fields[1],
                       'payload_crc_ok': zlib.crc32(payload) & 0xffffffff == fields[6],
                       'os': fields[7], 'arch': fields[8], 'type': fields[9], 'compression': fields[10],
                       'image_sha256': hashlib.sha256(header + payload).hexdigest()})
    return {'schema': 'nimbus-boot-inventory/v1', 'backup_bytes': len(data), 'images': images,
            'recovery_tested': False, 'flash_authorized': False,
            'note': 'CRCs prove local consistency only. No extraction, restore, boot or authenticity validation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    args = parser.parse_args()
    info = args.backup.lstat()
    if not stat.S_ISREG(info.st_mode) or not 64 <= info.st_size <= 32 * 1024 * 1024:
        raise SystemExit('Expected a regular local boot-area backup, at most 32 MiB; no devices/links.')
    print(json.dumps(inspect(args.backup.read_bytes()), indent=2))
