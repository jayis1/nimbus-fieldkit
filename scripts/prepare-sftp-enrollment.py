#!/usr/bin/env python3
"""Prepare dedicated public-key enrollment privately/offline; never enroll a device."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'.private-provisioning'
spec=importlib.util.spec_from_file_location('enrollment_confinement',ROOT/'scripts/sftp-confinement.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)


def read_public(path):
    path=Path(path).absolute()
    if any(parent.is_symlink() for parent in (path,*path.parents)):
        raise ValueError('Public-key input must not traverse symlinks')
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_mode&0o022 or not 1<=info.st_size<=4096:
        raise ValueError('Use an owned bounded regular public-key file without shared write access')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        opened=os.fstat(stream.fileno())
        if (info.st_dev,info.st_ino,info.st_size)!=(opened.st_dev,opened.st_ino,opened.st_size):
            raise ValueError('Public-key input changed while opening')
        data=stream.read(4097)
    try:return policy.public_key(data.decode('ascii'))
    except UnicodeError:raise ValueError('Use one plain public Ed25519 key') from None


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def prepare(output,client_public_key,management_public_key,label):
    if not isinstance(label,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',label):
        raise ValueError('Use a short non-secret enrollment label')
    output=Path(output).absolute()
    if output.parent!=PRIVATE or any(parent.is_symlink() for parent in (output,*output.parents)):
        raise ValueError('Use a new direct child of .private-provisioning without symlinks')
    authorized,client_pin=read_public(client_public_key)
    _,management_pin=read_public(management_public_key)
    if client_pin==management_pin:raise ValueError('Dedicated file-access key required; management identity reuse refused')
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    info=PRIVATE.stat()
    if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError('Private provisioning parent must be owned mode 0700')
    output.mkdir(mode=0o700)  # Exclusive; preserve failures rather than retry/reuse.
    payload=authorized.encode('ascii')
    record={'schema':'nimbus-private-sftp-enrollment/v1','label':label,
            'client_fingerprint':client_pin,'management_client_fingerprint':management_pin,
            'device_auth_path':policy.AUTH,'device_auth_owner':'root:root','device_auth_mode':'0644',
            'parent_policy':'root-owned 0755 traversable hierarchy, no group/other write access',
            'authorized_keys_sha256':hashlib.sha256(payload).hexdigest(),
            'private_client_key_included':False,'host_key_provisioned':False,
            'device_enrolled':False,'native_auth_verified':False,'listener_authorized':False,
            'production_ready':False,'flash_authorized':False,
            'required_gates':['unique pinned SFTP host identity, never management identity',
                              'reviewed account collision/locked-account/publickey login behavior',
                              'native confinement and denial tests',
                              'bounded supervision/USB-safe session drain',
                              'separate exact provisioning/listener approval']}
    files={'authorized_keys':payload,'ENROLLMENT.json':(json.dumps(record,indent=2)+'\n').encode(),
           'NOT-ENROLLED.txt':b'Private offline public-key enrollment input only. No private client/host key, account, jail or listener supplied. Not installed or authenticated on any device. Never distribute as generic firmware input.\n'}
    for name,data in files.items():
        fd=os.open(output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
    sync_directory(output);sync_directory(PRIVATE)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--client-public-key',type=Path,required=True)
    parser.add_argument('--management-public-key',type=Path,required=True)
    parser.add_argument('--label',required=True)
    args=parser.parse_args();os.umask(0o077)
    try:record=prepare(args.output,args.client_public_key,args.management_public_key,args.label)
    except (OSError,ValueError):raise SystemExit('Enrollment preparation refused; preserve private evidence. No device changed.')
    print(json.dumps({key:record[key] for key in ('client_fingerprint','device_enrolled','listener_authorized')},indent=2))
