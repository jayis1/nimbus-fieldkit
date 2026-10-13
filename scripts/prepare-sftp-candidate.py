#!/usr/bin/env python3
"""Prepare an inactive restricted SFTP profile locally; never deploy or start SSH."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path

STAGE = '/root/nimbus-sftp-candidate-v1'
PORT = 2226
ACCOUNT = 'nimbus-files'


def config(address):
    address = ipaddress.IPv4Address(address)
    if not any(address in ipaddress.IPv4Network(network)
               for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Select one explicit RFC1918 LAN IPv4 address, never wildcard/public/loopback')
    return f'''# INACTIVE CANDIDATE: requires a separately qualified modern ARM OpenSSH runtime.
# Never use the vendor sshd or replace management Dropbear with this profile.
Port {PORT}
ListenAddress {address}:{PORT}
AddressFamily inet
HostKey {STAGE}/host-ed25519
PidFile {STAGE}/sshd.pid
AuthorizedKeysFile /etc/nimbus-sftp-auth/nimbus-files/authorized_keys
AuthorizedKeysCommand none
AllowUsers {ACCOUNT}
PermitRootLogin no
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
UsePAM no
StrictModes yes
ChrootDirectory {STAGE}/jail
ForceCommand internal-sftp -R -d /internal
Subsystem sftp internal-sftp
DisableForwarding yes
AllowTcpForwarding no
AllowStreamLocalForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTunnel no
PermitTTY no
PermitUserEnvironment no
PermitUserRC no
UseDNS no
MaxAuthTries 3
MaxSessions 1
MaxStartups 2:30:4
LoginGraceTime 30
ClientAliveInterval 30
ClientAliveCountMax 2
LogLevel VERBOSE
'''


def prepare(output, address):
    payload = config(address).encode()
    output = Path(output).absolute()
    # Refuse symlink ancestors instead of silently resolving into another tree.
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise ValueError('Refusing symlink candidate path')
    if not output.parent.is_dir():
        raise ValueError('Use an existing parent directory')
    plan = {
        'schema': 'nimbus-restricted-sftp-plan/v1',
        'status': 'inactive configuration; runtime and native validation pending',
        'installable': False, 'hardware_validated': False,
        'listener': {'address': str(ipaddress.IPv4Address(address)), 'port': PORT},
        'account': ACCOUNT, 'stage': STAGE,
        'shares': [
            {'source': '/mnt/storage', 'jail_path': '/internal', 'mode': 'read_only'},
            {'source': '/mnt/sdcard', 'jail_path': '/sd', 'mode': 'read_only'},
        ],
        'remote_write': False,
        'runtime': {'implementation': 'maintained OpenSSH with internal-sftp',
                    'binary_sha256': None, 'toolchain_sha256': None,
                    'privsep_path': STAGE + '/empty'},
        'preserved': ['management TCP 2224', 'temporary management TCP 2225',
                      'vendor services', 'AP/uplink policy', 'Pi pairing/USB route',
                      'SD main/FTP mount policy', 'existing keys and backups'],
        'required_gates': [
            'Verify current maintained source, signatures, toolchain/libc fixes and ARM compatibility',
            'Qualify candidate runtime; never launch the old vendor sshd with this config',
            'Confirm actual chosen interface/address and narrowly scoped downstream access',
            'Provision distinct non-root account and dedicated client/host keys with pinned enrollment',
            'Public authorized-key path must be traversable/readable by nimbus-files, root-owned and not user-writable',
            'Review public-share content; chroot is not confidentiality for stock HTTP/FTP shares',
            'Reject active/unknown USB export and absent/unknown source mounts',
            'Require root-owned jail hierarchy with no writable jail root or symlink components',
            'Review isolated read-only bind views; verify VFS ro without changing source mount policy',
            'Review session/USB-export lifecycle; no client may retain media handles across USB handoff',
            'Review private stage/logs, fresh identities and rollback before any live start',
            'Explicit native trial approval before accounts, keys, bind mounts or listeners are created',
            'Test pinned non-root SFTP; reject root, shell, PTY, forwarding, writes and path escapes',
            'Qualify GameHack pairing and readback separately before enabling its UI',
        ],
    }
    files = {'sshd_config': payload,
             'PLAN.json': (json.dumps(plan, indent=2) + '\n').encode(),
             'NOT-INSTALLABLE.txt': b'Inactive source configuration only. No ARM runtime, keys, account, jail, installer or listener is supplied. Do not deploy or execute the vendor sshd.\n'}
    manifest = {'schema': 'nimbus-restricted-sftp-config/v1',
                'files': [{'name': name, 'bytes': len(data),
                           'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.mkdir(mode=0o700)  # Exclusive; retain incomplete evidence if a write fails.
    for name, data in files.items():
        with (output / name).open('xb') as stream:
            (output / name).chmod(0o600)
            stream.write(data)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--listen-address', required=True, help='Explicit intended private LAN address; no listener starts')
    args = parser.parse_args()
    try:
        prepare(args.output, args.listen_address)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print('Prepared inactive profile. No runtime supplied; no device changed.')
