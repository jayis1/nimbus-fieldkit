#!/usr/bin/env python3
"""Check tracked source for forbidden artifacts and obvious secret markers."""
import re
import subprocess
from pathlib import Path

FORBIDDEN = ('numbus-backup/', '.private-backups/', '.private-provisioning/', 'build/', 'vault/', 'System Volume Information/')
EXTENSIONS = {'.img', '.bin', '.tar', '.pem', '.key', '.pcap', '.pcapng', '.log'}
# Split markers so this checker can itself be safely included in source scans.
PATTERNS = [rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?' + rb'PRIVATE KEY-----',
            rb'\bgh[pousr]_[A-Za-z0-9]{20,}\b', rb'\bAKIA[0-9A-Z]{16}\b']


def violations(name, data, symlink=False):
    reasons = []
    if name.startswith(FORBIDDEN) or Path(name).suffix in EXTENSIONS or symlink:
        reasons.append('forbidden artifact or symlink')
    if len(data) > 2 * 1024 * 1024:
        reasons.append('unexpectedly large source file')
    if any(re.search(pattern, data) for pattern in PATTERNS):
        reasons.append('potential private key/token marker')
    return reasons


def main():
    result = subprocess.run(['git', 'ls-files', '-z'], capture_output=True, check=True)
    names = [name for name in result.stdout.decode().split('\0') if name]
    problems = []
    for name in names:
        data = subprocess.check_output(['git', 'show', ':' + name])
        reasons = violations(name, data, Path(name).is_symlink())
        problems += [name + ': ' + reason for reason in reasons]
    for problem in problems:
        print(problem)  # Never print matching secret contents.
    print(f'Checked {len(names)} tracked files; {len(problems)} issue(s). Not an exhaustive secret audit.')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
