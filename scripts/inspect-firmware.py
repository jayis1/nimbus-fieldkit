#!/usr/bin/env python3
"""Read-only Nimbus wrapper inspector. No extraction, repacking or flashing."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct
import zlib

HEADER_SIZE = 152
MAGIC = 0x57AE2D64


def vendor_crc(data, seed=255):
    # Reflected CRC table, no final XOR; vendor API seed is an unsigned byte.
    return zlib.crc32(data, seed ^ 0xFFFFFFFF) ^ 0xFFFFFFFF


def payload_crc(stream):
    value = 0xFFFFFFFF
    while True:
        block = stream.read(4096)
        value = vendor_crc(block, value & 255)
        # C feof loop also computes an empty final block for exact multiples.
        if len(block) < 4096:
            return value


def inspect(path):
    path = Path(path)
    with path.open('rb') as stream:
        import os
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Only regular offline image files are accepted')
        header = bytearray(stream.read(HEADER_SIZE))
        if len(header) != HEADER_SIZE:
            raise ValueError('Truncated Nimbus header')
        magic, head_crc, data_crc, timestamp = struct.unpack_from('>4I', header)
        # Validator loads size directly on little-endian ARM; version is swapped.
        declared_size = struct.unpack_from('<I', header, 16)[0]
        version = struct.unpack_from('>I', header, 20)[0]
        header[4:8] = bytes(4)
        calculated_header = vendor_crc(header)
        calculated_payload = payload_crc(stream)
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    checks = {'magic': magic == MAGIC,
              'size': info.st_size == HEADER_SIZE + declared_size,
              'header_crc': calculated_header == head_crc,
              'payload_crc': calculated_payload == data_crc}
    return {'schema': 'nimbus-image-inspection/v1', 'bytes': info.st_size,
            'sha256': digest, 'payload_bytes': declared_size,
            'version_raw': f'0x{version:08x}', 'timestamp_raw': timestamp,
            'image_name': bytes(header[24:]).split(b'\0', 1)[0].decode('ascii', errors='replace'),
            'checks': checks, 'wrapper_checks_pass': all(checks.values()),
            'header_crc': {'stored': f'{head_crc:08x}', 'calculated': f'{calculated_header:08x}'},
            'payload_crc': {'stored': f'{data_crc:08x}', 'calculated': f'{calculated_payload:08x}'},
            'flash_ready': False,
            'warning': 'Checks reproduce one vendor validator, not authenticity, boot compatibility or recovery safety. No image is approved for flashing.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    try:
        result = inspect(args.image)
    except (OSError, ValueError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(result, indent=2))
    return 0 if result['wrapper_checks_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
