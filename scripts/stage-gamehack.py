#!/usr/bin/env python3
"""Add the optional Nimbus menu to a GameHack staging tree, not an installed card."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

MENU = '        ("Raspberry Pi worker", "pi-worker"),\n'
BRANCH = '        elif action == "pi-worker":\n            self.pi_worker()\n'
ADDITION = '''        elif action == "nimbus-fieldkit":
            from nimbus_fieldkit import menu
            menu(self, run)
'''


PREVIOUS_MODULE = 'a2d37ba8f7f8f5074ffe1d3cd011826fcab957dd2045997019535d9853dcdd51'


def stage(root, upgrade=False):
    target = root / 'opt/hackeros'
    launcher = target / 'launcher.py'
    original = launcher.read_text()
    updated = original
    if '("SanDisk / main Wi-Fi unit", "nimbus-fieldkit")' not in original:
        if original.count(MENU) != 1 or original.count(BRANCH) != 1:
            raise ValueError('Launcher layout differs; refusing automatic modification')
        updated = original.replace(MENU, MENU + '        ("SanDisk / main Wi-Fi unit", "nimbus-fieldkit"),\n')
        updated = updated.replace(BRANCH, BRANCH + ADDITION)
    elif 'menu(self, run)' not in original:
        raise ValueError('Partial existing integration; review it manually')
    ast.parse(updated)
    module = Path(__file__).parents[1] / 'fieldkit/nimbus_fieldkit.py'
    destination = target / module.name
    if destination.exists() and destination.read_bytes() != module.read_bytes():
        if not upgrade or hashlib.sha256(destination.read_bytes()).hexdigest() != PREVIOUS_MODULE:
            raise ValueError('Existing Nimbus module differs; --upgrade accepts only the known unmodified v0.1 module')
        backup_module = destination.with_name(destination.name + '.pre-v02')
        if backup_module.exists():
            raise ValueError('Module backup already exists; review it before upgrading')
    extras = [(Path(__file__).parents[1] / 'fieldkit/tools.py', target / 'nimbus_tools.py')]
    docs = Path(__file__).parents[1] / 'docs'
    names = ('FEATURES.md', 'GAMEHACK.md', 'FIRMWARE.md', 'FIRMWARE-3.04-INSPECTION.md', 'LIVE-TEST-2026-10-11.md')
    extras += [(docs / name, target / 'nimbus-docs' / name) for name in names]
    for source, output in extras:
        if output.exists() and output.read_bytes() != source.read_bytes():
            raise ValueError('Existing staged file differs; review manually: ' + str(output))
    if updated != original:
        backup = launcher.with_name('launcher.py.pre-nimbus')
        if backup.exists():
            raise ValueError('Backup already exists; review before staging')
        shutil.copy2(launcher, backup)
    if not destination.exists():
        shutil.copy2(module, destination)
    elif destination.read_bytes() != module.read_bytes():
        shutil.copy2(destination, destination.with_name(destination.name + '.pre-v02'))
        shutil.copy2(module, destination)
    for source, output in extras:
        if not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    if updated != original:
        launcher.write_text(updated)
    return launcher


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--upgrade', action='store_true', help='Back up and replace only the known unmodified v0.1 module')
    args = parser.parse_args()
    print('Staged:', stage(args.staging, args.upgrade))
