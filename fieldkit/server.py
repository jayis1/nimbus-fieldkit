#!/usr/bin/env python3
"""Local-only FieldKit prototype; no third-party dependencies or firmware writes."""
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import socket
import stat
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

try:
    from .nimbus_fieldkit import report as ecosystem_report
    from . import tools
except ImportError:
    from nimbus_fieldkit import report as ecosystem_report
    import tools

WEB = Path(__file__).with_name('index.html')
MAX_FILE = 64 * 1024 * 1024


def read_optional(path):
    try:
        return Path(path).read_text()[:32768]
    except OSError:
        return 'Unavailable'


def status(vault):
    disk = shutil.disk_usage(vault)
    return {
        'mode': 'HOST PROTOTYPE — not device firmware',
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'architecture': platform.machine(),
        'uptime': read_optional('/proc/uptime').split()[0],
        'memory': read_optional('/proc/meminfo'),
        'interfaces': [name for _, name in socket.if_nameindex()],
        'routes': read_optional('/proc/net/route'),
        'wireless': read_optional('/proc/net/wireless'),
        'storage': {'total': disk.total, 'free': disk.free, 'used': disk.used},
        'device_battery': 'Unknown — requires device integration',
    }


def open_vault_file(vault, name):
    # Single-component names and O_NOFOLLOW prevent traversal and symlink escapes.
    if not name or name in ('.', '..') or '/' in name or '\\' in name or '\x00' in name:
        raise ValueError('Use a single filename inside the vault')
    fd = os.open(vault / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
            raise ValueError('Only regular files up to 64 MiB are supported')
        return os.fdopen(fd, 'rb')
    except Exception:
        os.close(fd)
        raise


def vault_files(vault):
    files = []
    for path in sorted(vault.iterdir()):
        info = path.lstat()
        if stat.S_ISREG(info.st_mode):
            files.append({'name': path.name, 'bytes': info.st_size,
                          'supported': info.st_size <= MAX_FILE})
        if len(files) >= 500:
            break
    return files


def check_ports(target, ports, networks):
    address = ipaddress.ip_address(target)
    if not any(address in network for network in networks):
        raise ValueError('Target is outside the explicitly authorized network scope')
    if address.is_multicast or address.is_unspecified:
        raise ValueError('A unicast target is required')
    if not isinstance(ports, list) or not 1 <= len(ports) <= 16:
        raise ValueError('Supply between 1 and 16 TCP ports')
    if any(type(port) is not int or not 1 <= port <= 65535 for port in ports):
        raise ValueError('Ports must be integers from 1 to 65535')
    results = []
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    for port in dict.fromkeys(ports):
        start = time.monotonic()
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.5)
            try:
                connection.connect((str(address), port))
                state = 'open'
            except OSError:
                state = 'closed / filtered / unreachable'
        results.append({'port': port, 'state': state,
                        'ms': round((time.monotonic() - start) * 1000)})
    return {'target': str(address), 'results': results}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Avoid logging query strings containing private filenames.
        pass

    def reply(self, code, data, content_type='application/json'):
        payload = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        expected_host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected_host:
            self.reply(403, {'error': 'Use the printed localhost URL'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{expected_host}':
            self.reply(403, {'error': 'Cross-origin requests are not allowed'})
            return False
        value = self.headers.get('Authorization', '')
        if not hmac.compare_digest(value, 'Bearer ' + self.server.token):
            self.reply(401, {'error': 'Paste the session token from the terminal'})
            return False
        return True

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/':
            self.reply(200, WEB.read_bytes(), 'text/html; charset=utf-8')
            return
        assets = {'/dashboard.css': ('dashboard.css', 'text/css; charset=utf-8'),
                  '/dashboard.js': ('dashboard.js', 'application/javascript; charset=utf-8')}
        if url.path in assets:
            name, content_type = assets[url.path]
            self.reply(200, WEB.with_name(name).read_bytes(), content_type)
            return
        if not self.authorized():
            return
        if getattr(self.server, 'privacy', False) and url.path in ('/api/files', '/api/hash', '/api/download', '/api/node', '/api/native-state'):
            self.reply(403, {'error': 'Local privacy mode blocks file sharing and device probes'})
            return
        try:
            if url.path == '/api/status':
                self.reply(200, status(self.server.vault))
            elif url.path == '/api/ecosystem':
                self.reply(200, ecosystem_report())
            elif url.path == '/api/privacy':
                self.reply(200, {'enabled': getattr(self.server, 'privacy', False),
                                 'scope': 'this local prototype only; not SanDisk services'})
            elif url.path == '/api/node':
                target = getattr(self.server, 'device', None)
                self.reply(200, tools.node_status(target) if target else {'status': 'Start with --device NUMERIC_IP to enable explicit device probing'})
            elif url.path == '/api/native-state':
                target = getattr(self.server, 'device', None)
                path = getattr(self.server, 'native_path', '/storage/nimbus-fieldkit-v04/dashboard/state.json')
                self.reply(200, tools.native_snapshot(target, path) if target else {'status': 'No device configured; this is host data only'})
            elif url.path == '/api/docs':
                name = parse_qs(url.query).get('name', [''])[0]
                if not name:
                    self.reply(200, {'documents': list(tools.DOCUMENTS)})
                elif name in tools.DOCUMENTS:
                    self.reply(200, (tools.DOCS / name).read_bytes(), 'text/plain; charset=utf-8')
                else:
                    raise ValueError('Unknown offline document')
            elif url.path == '/api/files':
                self.reply(200, {'files': vault_files(self.server.vault)})
            elif url.path in ('/api/hash', '/api/download'):
                name = parse_qs(url.query).get('name', [''])[0]
                with open_vault_file(self.server.vault, name) as source:
                    # Bounded read also handles a file growing after fstat.
                    data = source.read(MAX_FILE + 1)
                if len(data) > MAX_FILE:
                    raise ValueError('File exceeds 64 MiB')
                if url.path == '/api/hash':
                    self.reply(200, {'name': name, 'sha256': hashlib.sha256(data).hexdigest()})
                else:
                    self.reply(200, data, 'application/octet-stream')
            else:
                self.reply(404, {'error': 'Not found'})
        except (OSError, ValueError) as error:
            self.reply(400, {'error': str(error)})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path not in ('/api/check', '/api/privacy', '/api/diagnostic'):
            self.reply(404, {'error': 'Not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 2048:
                raise ValueError('Request must be 1–2048 bytes')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Supply a JSON object')
            if self.path == '/api/privacy':
                if type(body.get('enabled')) is not bool:
                    raise ValueError('Supply a boolean enabled value')
                self.server.privacy = body['enabled']
                self.reply(200, {'enabled': self.server.privacy, 'scope': 'local prototype only'})
                return
            if getattr(self.server, 'privacy', False):
                self.reply(403, {'error': 'Local privacy mode blocks active diagnostics'})
                return
            if self.path == '/api/diagnostic' and body.get('action') == 'routes':
                self.reply(200, tools.routes())
                return
            if not isinstance(body.get('target'), str):
                raise ValueError('Supply a numeric target IP')
            if body.get('authorized') is not True:
                raise ValueError('Confirm permission for this target')
            if self.path == '/api/check':
                self.reply(200, check_ports(body['target'], body.get('ports'), self.server.networks))
            else:
                address = ipaddress.ip_address(body['target'])
                if not any(address in network for network in self.server.networks):
                    raise ValueError('Target is outside the authorized network scope')
                action = body.get('action')
                if action == 'ping':
                    self.reply(200, tools.ping(str(address)))
                elif action == 'dns':
                    self.reply(200, tools.dns_query(str(address), body.get('name', 'example.com')))
                else:
                    raise ValueError('Unknown diagnostic action')
        except (ValueError, OSError, TypeError, tools.subprocess.SubprocessError) as error:
            self.reply(400, {'error': str(error)})

    def setup(self):
        super().setup()
        self.connection.settimeout(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=Path('vault'))
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--allow-network', action='append', default=[], metavar='CIDR')
    parser.add_argument('--device', help='Explicit SanDisk numeric IP for bounded, read-only service probes')
    parser.add_argument('--native-path', default='/storage/nimbus-fieldkit-v04/dashboard/state.json', help='Read-only native snapshot path on the configured device')
    args = parser.parse_args()
    args.vault.mkdir(parents=True, exist_ok=True)
    networks = [ipaddress.ip_network(value, strict=True) for value in args.allow_network]
    with HTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.vault = args.vault.resolve()
        server.networks = networks
        server.device = tools.target_ip(args.device) if args.device else None
        server.native_path = tools.native_snapshot_path(args.native_path)
        server.privacy = False
        server.token = secrets.token_urlsafe(32)
        print(f'HOST PROTOTYPE: http://127.0.0.1:{server.server_port}', flush=True)
        print(f'Session token: {server.token}', flush=True)
        print(f'Authorized scopes: {networks or "none (checks disabled)"}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
