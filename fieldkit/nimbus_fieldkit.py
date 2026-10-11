#!/usr/bin/env python3
"""Controller-first GameHack integration; no browser, root, or network changes."""
import hashlib
import json
import os
from pathlib import Path
import socket
import shlex
import stat
import tempfile
import time

try:
    from . import tools
except ImportError:
    try:
        import nimbus_tools as tools
    except ImportError:
        import tools

STATE = Path('/data/gamehack-zero')
VAULT = STATE / 'nimbus-vault'
LIMIT = 16384
HELP = '''GameHack Zero = controller (R2 select, L2 back).
SanDisk Nimbus = planned MAIN Wi-Fi unit and file vault.
Pi Zero W = existing USB worker; not the main Wi-Fi unit.

Stock SanDisk control LAN: 192.168.11.1/24.
Existing Pi USB link: 192.168.77.1/24 (unchanged).
Internet goal: phone hotspot -> SanDisk -> GameHack.
AP/client Internet transit passed the pre-reset live test.
Recheck after reset; no custom firmware is installed.
Local vault: /data/gamehack-zero/nimbus-vault.

Use existing Wi-Fi setup to join the SanDisk after its
secured AP has been tested. Do not replace the Pi USB
profile, enable PC gadget mode, or assume Internet access.
Pi Internet forwarding via GameHack is a separate future step.
No NFC/Sub-GHz/IR hardware is added by the SanDisk.
Snapshots stay on the handheld until explicitly transferred.
'''


def report(state=STATE):
    interfaces = [name for _, name in socket.if_nameindex()]
    pairing = Path('/home/hacker/.ssh/gamehack-pi')
    return {'schema': 'gamehack-nimbus/v1', 'created': time.time(),
            'roles': {'controller': 'GameHack Zero R36XX',
                      'main_wifi': 'SanDisk Nimbus — stock AP/uplink tested before reset; custom deployment pending',
                      'worker': 'Pi Zero W — existing pinned USB SSH'},
            'host': socket.gethostname(), 'interfaces': interfaces,
            'sandisk_control_ip': '192.168.11.1', 'pi_usb_ip': '192.168.77.1',
            'internet_plan': 'Phone hotspot -> SanDisk gateway -> GameHack; retest after reset',
            'pi_pairing_files_present': all((pairing / name).is_file() for name in ('id_ed25519', 'known_hosts')),
            'local_vault': str(state / 'nimbus-vault'),
            'sandisk_radio_capabilities': 'Unverified; no monitor/injection claim'}


def filtered_pi_metadata(state):
    # Read only one known diagnostic, never pairing keys/tasks/captures/provider data.
    path = state / 'pi-last-connection.json'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
                return {'available': False}
            raw = source.read(LIMIT + 1)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {'available': False}
        return {key: data[key] for key in ('timestamp', 'action', 'exit_code', 'reason', 'paired_usb_interfaces') if key in data}
    except (OSError, ValueError):
        return {'available': False}


def snapshot(state=STATE):
    vault = state / 'nimbus-vault'
    vault.mkdir(mode=0o700, parents=True, exist_ok=True)
    if vault.is_symlink():
        raise ValueError('Refusing a symlink vault')
    data = report(state)
    data['pi_link_metadata'] = filtered_pi_metadata(state)
    payload = (json.dumps(data, indent=2) + '\n').encode()
    fd, filename = tempfile.mkstemp(prefix='gamehack-snapshot-', suffix='.json', dir=vault)
    with os.fdopen(fd, 'wb') as output:
        output.write(payload)
    return Path(filename), hashlib.sha256(payload).hexdigest()


def menu(ui, run):
    """Uses the launcher's existing controller-friendly UI and pinned Pi client."""
    actions = ['Roles / Wi-Fi plan', 'Local field-node status', 'Save reviewed diagnostic snapshot',
               'Browse local vault', 'Pi USB link diagnostics', 'Pi worker status',
               'SanDisk service check', 'Local routing table', 'DNS check', 'Ping authorized host',
               'Save vault checksum manifest', 'Transfer one file to mounted storage',
               'Offline toolbox documents', 'Privacy / secure administration plan',
               'Pi queue: list jobs', 'Pi queue: submit task', 'Pi queue: read result', 'Pi queue: cancel job',
               'Pi passive capture (capability checked)']
    while True:
        choice = ui.select('NIMBUS / MAIN WI-FI UNIT', actions)
        if choice is None:
            return
        try:
            if choice == actions[0]:
                ui.text_view('NIMBUS TOPOLOGY', HELP)
            elif choice == actions[1]:
                ui.text_view('LOCAL STATUS / NOT SANDISK TELEMETRY', json.dumps(report(), indent=2))
            elif choice == actions[2]:
                preview = json.dumps({'host': report(), 'pi_link_metadata': filtered_pi_metadata(STATE)}, indent=2)
                ui.text_view('REVIEW SNAPSHOT CONTENT', preview)
                if ui.confirm('SAVE LOCAL SNAPSHOT?', 'Save inventory and Pi connection metadata?\nNo keys, tasks, logs or captures are included.'):
                    path, digest = snapshot()
                    ui.text_view('SAVED LOCALLY / NOT SYNCED', str(path) + '\n\nSHA-256: ' + digest)
            elif choice == actions[3]:
                ui.browse(str(VAULT))
            elif choice in actions[4:6]:
                action = 'link' if choice == actions[4] else 'status'
                ui.busy('PI USB WORKER', 'Using the existing key-pinned client...')
                ui.text_view('PI RESULT', run(['/usr/bin/python3', '/opt/hackeros/pi_worker.py', action], 40))
            elif choice == actions[6]:
                target = ui.keyboard('SanDisk numeric IP (stock: 192.168.11.1)')
                if target:
                    ui.busy('SANDISK', 'Checking one device; no login attempts...')
                    ui.text_view('SANDISK SERVICES', json.dumps(tools.node_status(target), indent=2))
            elif choice == actions[7]:
                ui.text_view('LOCAL ROUTES', json.dumps(tools.routes(), indent=2))
            elif choice in actions[8:10]:
                target = ui.keyboard('Authorized DNS server IP' if choice == actions[8] else 'Authorized target IP')
                if target and ui.confirm('AUTHORIZED DIAGNOSTIC', 'Query this target?\n' + target):
                    name = ui.keyboard('DNS name') if choice == actions[8] else None
                    if choice == actions[8] and not name:
                        continue
                    result = tools.dns_query(target, name) if name else tools.ping(target)
                    ui.text_view('DIAGNOSTIC', json.dumps(result, indent=2))
            elif choice == actions[10]:
                if ui.confirm('VAULT MANIFEST', 'Read vault files and save their checksums?'):
                    ui.text_view('MANIFEST', tools.save_manifest(VAULT))
            elif choice == actions[11]:
                source = ui.keyboard('Full path to ONE reviewed file')
                destination = ui.keyboard('Existing mounted destination directory') if source else None
                if destination and ui.confirm('TRANSFER ONE FILE?', source + '\n-> ' + destination + '\nNever overwrites existing files.'):
                    ui.text_view('VERIFIED TRANSFER', json.dumps(tools.sync_file(source, destination), indent=2))
            elif choice == actions[12]:
                document = ui.select('OFFLINE TOOLBOX', list(tools.DOCUMENTS))
                if document:
                    ui.text_view(document, (tools.DOCS / document).read_text())
            elif choice == actions[13]:
                ui.text_view('DEVICE PRIVACY / NO CHANGES APPLIED', json.dumps(tools.privacy_plan(), indent=2))
            elif choice in actions[14:18]:
                action = ('jobs', 'submit', 'result', 'cancel')[actions.index(choice) - 14]
                value = ui.keyboard('Pi task command' if action == 'submit' else '32-character job ID') if action != 'jobs' else None
                if action != 'jobs' and not value:
                    continue
                if action in ('submit', 'cancel') and not ui.confirm('PI WORKER', choice + '?\n' + value):
                    continue
                command = tools.queue_command(action, value)
                ui.busy('PI QUEUE', 'Using the existing pinned USB SSH client...')
                ui.text_view('PI QUEUE RESULT', run(['/usr/bin/python3', '/opt/hackeros/pi_worker.py', 'task', command], 40))
            elif choice == actions[18]:
                interface = ui.keyboard('Pi radio interface')
                frequency = ui.keyboard('Permitted AP frequency in MHz') if interface else None
                bssid = ui.keyboard('Permitted AP BSSID') if frequency else None
                if not bssid:
                    continue
                import re
                if not re.fullmatch('[A-Za-z0-9_-]{1,15}', interface) or not frequency.isdigit() or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', bssid):
                    raise ValueError('Invalid interface, frequency or BSSID')
                if ui.confirm('AUTHORIZED PASSIVE CAPTURE', 'Pi only, 15 seconds. Must own/have permission for AP.\nUnsupported or connected radios are refused.'):
                    task = shlex.join(['gamehack-companion', 'radio', 'wifi-capture', interface, frequency, bssid, '15'])
                    command = tools.queue_command('submit', task)
                    ui.text_view('PI CAPTURE QUEUED / NOT SANDISK CAPTURE', run(['/usr/bin/python3', '/opt/hackeros/pi_worker.py', 'task', command], 40))
        except (OSError, ValueError, tools.subprocess.SubprocessError) as error:
            ui.text_view('NIMBUS ERROR', str(error))
