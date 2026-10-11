#!/usr/bin/env python3
"""One-file, one-client, short-lived transfer server; no filesystem browsing."""
import argparse
import hashlib
import hmac
import io
import ipaddress
import json
from pathlib import Path
import secrets
import tarfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ALLOWED = {'MANIFEST.json', 'nimbus-agent.sh', 'device-inventory.sh', 'NATIVE-INSTALL.md',
           'docs/FEATURES.md', 'docs/FIRMWARE-3.04-INSPECTION.md'}
ALLOWED_V03 = ALLOWED | {'nimbus-settings.sh', 'docs/TOGGLES.md'}
ALLOWED_V04 = ALLOWED_V03 | {'nimbus-dashboard.sh', 'dashboard/index.html', 'dashboard/dashboard.css',
                           'dashboard/dashboard.js', 'dashboard/snapshot.awk', 'docs/DASHBOARD.md'}


def load_bundle(path):
    data = Path(path).read_bytes()
    if not 1 <= len(data) <= 2 * 1024 * 1024:
        raise ValueError('Only a small native script bundle may be served')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        members = archive.getmembers()
        names = {m.name for m in members}
        if names not in (ALLOWED, ALLOWED_V03, ALLOWED_V04) or len(members) != len(names) or any(not m.isfile() for m in members):
            raise ValueError('Bundle must contain only the approved native scripts/docs')
        manifest = json.load(archive.extractfile('MANIFEST.json'))
        entries = manifest.get('files', [])
        if {item['name'] for item in entries} != names - {'MANIFEST.json'}:
            raise ValueError('Invalid manifest file set')
        for item in entries:
            contents = archive.extractfile(item['name']).read()
            if len(contents) != item['bytes'] or hashlib.sha256(contents).hexdigest() != item['sha256']:
                raise ValueError('Bundle checksum mismatch')
    return data


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass  # Do not log the transfer token.

    def do_GET(self):
        if self.client_address[0] != self.server.allowed_client or not hmac.compare_digest(self.path.encode(), self.server.transfer_path.encode()):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(self.server.bundle)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(self.server.bundle)
        self.wfile.flush()
        self.server.delivered = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--bind', required=True, help='Specific IPv4 address on this computer; never 0.0.0.0')
    parser.add_argument('--client', required=True, help='Only this SanDisk IPv4 address may download')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--lifetime', type=int, default=900)
    args = parser.parse_args()
    bind, client = ipaddress.IPv4Address(args.bind), ipaddress.IPv4Address(args.client)
    if bind.is_unspecified or bind.is_multicast or client.is_unspecified or client.is_multicast:
        parser.error('Use specific unicast addresses')
    if not 1 <= args.lifetime <= 1800:
        parser.error('Lifetime must be 1–1800 seconds')
    data = load_bundle(args.bundle)
    with HTTPServer((str(bind), args.port), Handler) as server:
        server.allowed_client = str(client)
        server.bundle = data
        server.transfer_path = '/' + secrets.token_urlsafe(24) + '/nimbus-native-kit.tar'
        server.delivered = False
        server.timeout = 1
        print(f'Transfer URL: http://{bind}:{server.server_port}{server.transfer_path}', flush=True)
        print(f'SHA-256: {hashlib.sha256(data).hexdigest()}', flush=True)
        print(f'Allowed client: {client}; expires in {args.lifetime}s or after one download. Scripts/docs only; no credentials.', flush=True)
        deadline = time.monotonic() + args.lifetime
        while not server.delivered and time.monotonic() < deadline:
            server.handle_request()
        print('Transfer service stopped; device-side hash verification is still required.', flush=True)


if __name__ == '__main__':
    main()
