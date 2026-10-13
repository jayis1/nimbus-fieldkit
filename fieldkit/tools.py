#!/usr/bin/env python3
"""Bounded field utilities; explicit targets/transfers, no privileged changes."""
import argparse
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

MAX_FILE = 64 * 1024 * 1024
DOCS = Path(__file__).with_name('nimbus-docs')
if not DOCS.is_dir():
    DOCS = Path(__file__).resolve().parents[1] / 'docs'
DOCUMENTS = ('FEATURES.md', 'GAMEHACK.md', 'FIRMWARE.md',
              'FIRMWARE-3.04-INSPECTION.md', 'LIVE-TEST-2026-10-11.md', 'TOGGLES.md', 'DASHBOARD.md')


def companion_report(raw):
    """Validate a bounded native observation, never grant authority from JSON."""
    if not isinstance(raw, bytes) or len(raw) > 16384:
        raise ValueError('Companion report must be at most 16 KiB of JSON bytes')

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate companion report field')
            result[key] = value
        return result

    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or data.get('schema') != 'nimbus-companion-status/v1'
            or data.get('scope') != 'device_observation'):
        raise ValueError('Invalid companion report schema/scope')
    storage, management = data.get('storage'), data.get('management')
    integration, permissions = data.get('integration'), data.get('permissions')
    if not all(isinstance(value, dict) for value in (storage, management, integration, permissions)):
        raise ValueError('Missing companion report sections')
    mounts = ('internal', 'sd', 'sd_ftp')
    if any(storage.get(name) not in ('absent', 'read_only', 'read_write', 'unknown') for name in mounts):
        raise ValueError('Invalid storage observation')
    if storage.get('usb_export') not in ('active', 'inactive', 'unknown'):
        raise ValueError('Invalid USB export observation')
    if (type(management.get('port')) is not int or management['port'] != 2224
            or management.get('listener') not in ('observed', 'not_observed', 'unknown')
            or any(management.get(name) != 'not_tested' for name in ('authentication', 'host_pin'))
            or management.get('downstream_access') != 'not_qualified'):
        raise ValueError('Invalid management observation; report cannot authenticate itself')
    if (any(integration.get(name) != 'not_qualified'
            for name in ('remote_browsing', 'sftp', 'backup_transfer'))
            or integration.get('media_playback') != 'client_validation_required'
            or integration.get('pi_worker') != 'independent'
            or set(permissions) != {'remote_write', 'configure_network', 'change_mounts'}
            or any(value is not False for value in permissions.values())):
        raise ValueError('Unqualified companion capabilities or permissions')
    if storage['usb_export'] == 'active':
        state = 'blocked_usb_export'
    elif (storage['usb_export'] == 'unknown'
          or any(storage[name] in ('absent', 'unknown') for name in mounts)):
        state = 'blocked_storage_unconfirmed'
    else:
        state = 'local_mounts_observed'
    return {'schema': 'gamehack-companion-review/v1', 'state': state,
            'storage': {name: storage[name] for name in (*mounts, 'usb_export')},
            'management_listener': management['listener'],
            'transport_provenance': 'not_verified_by_reader',
            'remote_browsing_enabled': False, 'remote_transfer_enabled': False,
            'note': 'Observation only, not current pairing, private storage or write authorization. Pi remains independent.'}


def native_snapshot_path(path):
    if not re.fullmatch(r'/(storage|sdcard)/[A-Za-z0-9_./-]+/dashboard/state\.json', path) or '..' in Path(path).parts:
        raise ValueError('Use a static snapshot path under storage/sdcard; no traversal or query strings')
    return path


def native_snapshot(target, path):
    target, path = target_ip(target), native_snapshot_path(path)
    connection = http.client.HTTPConnection(target, timeout=3)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        if response.status != 200:
            return {'status': 'Native dashboard snapshot unavailable; publish it on the drive first'}
        raw = response.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise ValueError('Native snapshot exceeds size limit')
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('schema') != 'nimbus-dashboard/v1' or data.get('scope') != 'device':
            raise ValueError('Invalid native dashboard snapshot schema')
        return data
    except (OSError, http.client.HTTPException):
        return {'status': 'Configured device snapshot could not be reached; no native telemetry assumed'}
    finally:
        connection.close()


def target_ip(value):
    address = ipaddress.ip_address(value)
    if address.is_multicast or address.is_unspecified:
        raise ValueError('Specify a numeric unicast IP')
    return str(address)


def node_status(target):
    target = target_ip(target)
    family = socket.AF_INET6 if ':' in target else socket.AF_INET
    ports = {}
    for port in (21, 22, 23, 80, 443, 2224):
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.6)
            ports[str(port)] = connection.connect_ex((target, port)) == 0
    identity = {'verified_sandisk_web_page': False}
    if ports['80']:
        connection = http.client.HTTPConnection(target, timeout=2)
        try:
            connection.request('GET', '/')
            response = connection.getresponse()
            preview = response.read(8192)
            identity = {'http_status': response.status,
                        'verified_sandisk_web_page': b'SanDisk Wireless Media Drive' in preview}
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
    return {'target': target, 'checked_at': time.time(), 'reachable_services': ports,
            'web_identity': identity, 'battery': 'Unknown: no authenticated telemetry',
            'clients': 'Unknown: no authenticated telemetry',
            'remote_storage': 'Unknown: no authenticated telemetry',
            'internet_transit': 'Not tested by this probe; requires a downstream Wi-Fi-bound test',
            'warnings': ([name for port, name in [('21', 'FTP exposed'), ('23', 'Telnet exposed')]
                          if ports[port]] + ([] if ports['443'] else ['HTTPS unavailable']))}


def dns_query(server, name, source=None):
    server = target_ip(server)
    if ':' in server:
        raise ValueError('DNS diagnostic currently supports IPv4 servers only')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', name):
        raise ValueError('Invalid DNS name')
    labels = name.rstrip('.').split('.')
    if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in labels):
        raise ValueError('Invalid DNS label')
    identifier = secrets.randbelow(65536)
    question = b''.join(bytes([len(label)]) + label.encode() for label in labels)
    packet = struct.pack('!HHHHHH', identifier, 0x100, 1, 0, 0, 0) + question + b'\0' + struct.pack('!HH', 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        if source:
            connection.bind((target_ip(source), 0))
        connection.settimeout(3)
        connection.connect((server, 53))
        connection.send(packet)
        response = connection.recv(4096)
    if len(response) < 12:
        raise ValueError('Truncated DNS response')
    received, flags, _, answers, _, _ = struct.unpack('!HHHHHH', response[:12])
    if received != identifier or not flags & 0x8000:
        raise ValueError('DNS response mismatch')
    return {'server': server, 'name': name, 'rcode': flags & 15, 'answer_count': answers,
            'truncated': bool(flags & 0x200)}


def ping(target):
    result = subprocess.run(['ping', '-n', '-c', '3', '-W', '1', target_ip(target)],
                            capture_output=True, text=True, timeout=6)
    return {'exit_code': result.returncode, 'output': (result.stdout + result.stderr)[:4096]}


def routes():
    result = subprocess.run(['ip', '-4', 'route', 'show'], capture_output=True, text=True, timeout=3)
    return {'exit_code': result.returncode, 'output': (result.stdout + result.stderr)[:8192]}


def regular_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
            raise ValueError('Only regular files up to 64 MiB are supported')
        return os.fdopen(fd, 'rb')
    except Exception:
        os.close(fd)
        raise


def digest(path):
    with regular_file(path) as source:
        data = source.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError('File exceeds 64 MiB')
    return hashlib.sha256(data).hexdigest()


def sync_file(source, destination):
    """Explicit, single-file transfer to an existing local/mounted directory."""
    source, destination = Path(source), Path(destination)
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError('Destination must be an existing, non-symlink directory')
    output = destination / source.name
    # Exclusive creation never overwrites an existing file or follows a symlink.
    with regular_file(source) as stream:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            checksum = hashlib.sha256()
            total = 0
            with os.fdopen(fd, 'wb') as target:
                while True:
                    block = stream.read(65536)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_FILE:
                        raise ValueError('File exceeds 64 MiB')
                    target.write(block)
                    checksum.update(block)
                target.flush()
                os.fsync(target.fileno())
            if digest(output) != checksum.hexdigest():
                raise ValueError('Transfer verification failed')
            return {'file': str(output), 'bytes': total, 'sha256': checksum.hexdigest(), 'verified': True}
        except Exception:
            output.unlink()  # Only our newly created transfer, never pre-existing files.
            raise


def vault_manifest(vault):
    vault = Path(vault)
    entries = []
    for path in sorted(vault.iterdir()):
        if len(entries) >= 500:
            break
        info = path.lstat()
        if stat.S_ISREG(info.st_mode) and info.st_size <= MAX_FILE:
            entries.append({'name': path.name, 'bytes': info.st_size, 'sha256': digest(path)})
    return {'schema': 'nimbus-vault/v1', 'created': time.time(), 'files': entries}


def save_manifest(vault):
    vault = Path(vault)
    data = vault_manifest(vault)
    fd, filename = tempfile.mkstemp(prefix='manifest-', suffix='.json', dir=vault)
    with os.fdopen(fd, 'w') as output:
        json.dump(data, output, indent=2)
        output.write('\n')
    return filename


def queue_command(action, value=None):
    if action not in ('jobs', 'submit', 'result', 'cancel'):
        raise ValueError('Unknown queue action')
    command = ['gamehack-companion', action]
    if action == 'submit':
        if not value or not isinstance(value, str) or len(value) > 1800 or '\x00' in value:
            raise ValueError('Task must contain 1–1800 characters')
        command.append(value)
    elif action in ('result', 'cancel'):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
            raise ValueError('Enter the 32-character lowercase hex job ID')
        command.append(value)
    return shlex.join(command)


def privacy_plan():
    return {'status': 'device changes blocked until secure administration is verified',
            'steps': ['Secure AP with WPA2-AES; do not use open/WEP/TKIP',
                      'Back up working device configuration and calibration using verified access',
                      'Verify key-only SSH with pinned host identity in a second session',
                      'Only then disable Telnet/FTP and unnecessary discovery/forwarding',
                      'Restrict management to the trusted control LAN; validate reboot/recovery'],
            'capture': 'SanDisk capture blocked pending live driver capabilities; Pi capture remains capability-checked'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for action in ('status', 'ping', 'watch'):
        command = commands.add_parser(action)
        command.add_argument('target')
        if action == 'watch':
            command.add_argument('--count', type=int, default=6)
            command.add_argument('--interval', type=int, default=10)
    command = commands.add_parser('dns')
    command.add_argument('server'); command.add_argument('name'); command.add_argument('--source')
    command = commands.add_parser('sync')
    command.add_argument('source', type=Path); command.add_argument('destination', type=Path)
    command = commands.add_parser('manifest'); command.add_argument('vault', type=Path)
    commands.add_parser('routes'); commands.add_parser('privacy-plan')
    commands.add_parser('companion-report', help='Review native status JSON from stdin; no network or writes')
    args = parser.parse_args()
    try:
        if args.action == 'watch':
            if not 1 <= args.count <= 120 or not 5 <= args.interval <= 300:
                raise ValueError('Watch count 1–120, interval 5–300 seconds')
            for index in range(args.count):
                print(json.dumps(node_status(args.target)), flush=True)
                if index + 1 < args.count:
                    time.sleep(args.interval)
            return
        if args.action == 'status': result = node_status(args.target)
        elif args.action == 'ping': result = ping(args.target)
        elif args.action == 'dns': result = dns_query(args.server, args.name, args.source)
        elif args.action == 'routes': result = routes()
        elif args.action == 'sync': result = sync_file(args.source, args.destination)
        elif args.action == 'manifest': result = {'manifest': save_manifest(args.vault)}
        elif args.action == 'companion-report': result = companion_report(sys.stdin.buffer.read(16385))
        else: result = privacy_plan()
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
