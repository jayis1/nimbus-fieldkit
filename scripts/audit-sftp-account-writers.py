#!/usr/bin/env python3
"""Offline allowlisted writer evidence from a pinned clean-derived archive.

Never executes vendor code or reads live/private tables. Token absence is not
writer absence, and imported locking symbols are not proof of lock coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile

ARCHIVES={
    '4dd2907ec920443855b221b1f67c5086e369b84861fb0a486d74da2c7671b203':'reviewed-vendor-3.04',
    '70aa4be20f2db812bb504b75e8f6ab6eb8bb9c800018ef3184ae7af68be08853':'clean-derived-beta5-not-native',
}
SELECTED=('bin/busybox','lib/libc-2.11.1.so','nimbus/nimbus',
          'opt/qsi/bin/fw_server','opt/qsi/bin/event_manager',
          'opt/qsi/scripts/nimbus_resetpwn.sh',
          'opt/qsi/config/platform_functions','opt/qsi/config/config_cmd')
TOKENS=('/etc/passwd','/etc/shadow','/etc/group','/etc/.pwd.lock',
        'lckpwdf','ulckpwdf','putspent','putpwent','passwd.lock',
        'ResetAdmin','SetAdmin','ChangePassword','passwd','chpasswd')
SYMBOLS=('lckpwdf','ulckpwdf','putspent','putpwent','flock','fcntl',
         'rename','system','execve')


def evidence(data):
    if not isinstance(data,bytes) or not 0<len(data)<=16*1024*1024:
        raise ValueError('Invalid bounded source')
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'tokens_present':[token for token in TOKENS if token.encode() in data]}


def symbols(text):
    found={}
    for line in text.splitlines():
        fields=line.split()
        if len(fields)<8 or not fields[0].endswith(':'):continue
        name=fields[7].split('@')[0]
        if name in SYMBOLS:
            found.setdefault(name,set()).add('import' if fields[6]=='UND' else 'definition')
    return {name:sorted(kinds) for name,kinds in sorted(found.items())}


def audit(archive):
    archive=Path(archive)
    if archive.is_symlink() or not stat.S_ISREG(archive.lstat().st_mode):
        raise ValueError('Use a regular pinned offline archive')
    with archive.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest not in ARCHIVES:raise ValueError('Archive differs from reviewed clean input')
        stream.seek(0)
        records={}
        scratch='/tmp/opencode' if Path('/tmp/opencode').is_dir() else None
        with tarfile.open(fileobj=stream) as tar, tempfile.TemporaryDirectory(prefix='account-writer-audit-',dir=scratch) as temporary:
            for member in tar:
                if member.name not in SELECTED:continue
                if member.name in records or not member.isfile() or not 0<member.size<=16*1024*1024:
                    raise ValueError('Duplicate or unsafe selected member')
                source=tar.extractfile(member)
                with source:data=source.read(16*1024*1024+1)
                if len(data)!=member.size:raise ValueError('Incomplete selected member')
                record=evidence(data)
                if data.startswith(b'\x7fELF'):
                    target=Path(temporary)/str(len(records))
                    target.write_bytes(data);target.chmod(0o600)
                    result=subprocess.run(['readelf','--dyn-syms','--wide',str(target)],
                                          capture_output=True,text=True,check=True,timeout=10)
                    record['dynamic_symbols']=symbols(result.stdout)
                records[member.name]=record
        if set(records)!=set(SELECTED):raise ValueError('Selected input missing')
    return {'schema':'nimbus-account-writer-audit/v1','archive_sha256':digest,
            'input_kind':ARCHIVES[digest],'selected':records,
            'device_changed':False,'vendor_code_executed':False,
            'writer_exclusion_verified':False,'installation_authorized':False,
            'limits':['Selected token/symbol evidence only, not call-graph proof.',
                      'No native executable identity or writer-lock behavior verified.',
                      'libc locking support does not imply caller participation.',
                      'Indirect shell/library writers and dynamically constructed paths remain possible.',
                      'No service stop/reset/password operation performed.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    args=parser.parse_args()
    try:report=audit(args.archive)
    except (OSError,ValueError,tarfile.TarError,subprocess.SubprocessError):
        raise SystemExit('Offline writer audit refused; no device changed.')
    print(json.dumps(report,indent=2))
