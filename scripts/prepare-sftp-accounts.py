#!/usr/bin/env python3
"""Prepare private offline account-table additions; never edits a device or image.

Existing table bytes are preserved. There is no installer, unlock/repair action,
host key generation, listener, mount or firmware operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'.private-provisioning'
STAGE='/root/nimbus-sftp-candidate-v1'
ROLE_NAMES=('nimbus-files','nimbus-sshd')
CONFIG_HEADER_SHA256='7f0494e813c9ab9309af544446c31822be84eaf6ca2ecd696d6c5d1238b42432'


def table(data,kind):
    if not isinstance(data,bytes) or not 1<=len(data)<=65536 or not data.endswith(b'\n'):
        raise ValueError('Use bounded complete private account-table inputs')
    try:text=data.decode('ascii')
    except UnicodeError:raise ValueError('Unsupported account table encoding') from None
    if any(ord(c)<32 and c!='\n' for c in text):raise ValueError('Control characters in account table')
    width={'passwd':7,'group':4,'shadow':9}[kind]
    rows=[];names=set()
    for line in text.splitlines():
        parts=line.split(':')
        name_pattern=r'[A-Za-z0-9_][A-Za-z0-9_.-]*\$?' if kind=='group' else r'[A-Za-z_][A-Za-z0-9_.-]*\$?'
        if len(parts)!=width or not re.fullmatch(name_pattern,parts[0]) or parts[0] in names:
            raise ValueError('Malformed/duplicate account table entry')
        names.add(parts[0])
        if kind=='passwd':
            if any(not re.fullmatch('[0-9]{1,10}',parts[i]) for i in (2,3)):
                raise ValueError('Invalid existing UID/GID')
            # Empty existing fields are valid passwd syntax (an empty shell can
            # mean the platform default). Preserve them; new roles always get
            # explicit absolute homes and /bin/false.
            if (parts[5] and not parts[5].startswith('/')) or (parts[6] and not parts[6].startswith('/')):
                raise ValueError('Unsupported existing home/shell entry')
        elif kind=='group':
            if not re.fullmatch('[0-9]{1,10}',parts[2]):raise ValueError('Invalid group ID')
            if parts[3] and any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?',name) for name in parts[3].split(',')):
                raise ValueError('Malformed group membership')
        else:
            if any(value and not re.fullmatch('-?[0-9]{1,10}',value) for value in parts[2:]):
                raise ValueError('Unsupported shadow aging fields')
        rows.append(parts)
    return rows


def verify_build_account_rules(header):
    # This source-level plan is intentionally tied to the reviewed Linux build,
    # not every Unix sshd or libc. Changed macros require a new policy review.
    if not isinstance(header,str) or len(header)>65536:raise ValueError('Invalid build configuration evidence')
    if hashlib.sha256(header.encode()).hexdigest()!=CONFIG_HEADER_SHA256:
        raise ValueError('Account-policy header differs from the reviewed ARM build')
    defines={}
    for line in header.splitlines():
        match=re.match(r'^\s*#\s*define\s+(\w+)(?:\s+(.*))?$',line)
        if match:
            if match[1] in defines:raise ValueError('Duplicate build macro')
            defines[match[1]]=match[2] or ''
    if defines.get('LOCKED_PASSWD_PREFIX')!='"!"' or defines.get('SSH_PRIVSEP_USER')!='"nimbus-sshd"':
        raise ValueError('Account lock/privsep build policy differs')
    if not all(name in defines for name in ('HAVE_SHADOW_H','HAS_SHADOW_EXPIRE')) or any(name in defines for name in (
            'DISABLE_SHADOW','LOCKED_PASSWD_STRING','LOCKED_PASSWD_SUBSTR','HAVE_OSF_SIA','HAVE_LIBIAF')):
        raise ValueError('Shadow/platform account policy differs')
    return {'file_password_marker':'*','privsep_password_marker':'!',
            'file_marker_not_locked_by_reviewed_prefix':True,
            'native_shadow_lookup_verified':False,'native_auth_verified':False}


def plan(passwd,group,shadow,header,files_uid=2206,privsep_uid=2207):
    build_policy=verify_build_account_rules(header)
    identities=(files_uid,privsep_uid)
    if any(type(value) is not int or not 1000<=value<65534 for value in identities) or files_uid==privsep_uid:
        raise ValueError('Choose two distinct non-root dedicated IDs')
    parsed={'passwd':table(passwd,'passwd'),'group':table(group,'group'),'shadow':table(shadow,'shadow')}
    if any(row[0] in ROLE_NAMES for rows in parsed.values() for row in rows):
        raise ValueError('Dedicated role already present; no repair, overwrite or unlock')
    if not any(row[0]=='root' and row[2:4]==['0','0'] for row in parsed['passwd']):
        raise ValueError('Expected existing root identity missing; no alteration supplied')
    existing_uids={int(row[2]) for row in parsed['passwd']}
    existing_gids={int(row[3]) for row in parsed['passwd']}|{int(row[2]) for row in parsed['group']}
    if any(value in existing_uids or value in existing_gids for value in identities):
        raise ValueError('Selected UID/GID collides with existing account/group')
    if any(name in ROLE_NAMES for row in parsed['group'] for name in row[3].split(',')):
        raise ValueError('Stale role membership in an existing group; refuse implicit privilege inheritance')
    originals={'passwd':passwd,'group':group,'shadow':shadow}
    appended={
        'passwd':(f'nimbus-files:x:{files_uid}:{files_uid}:Nimbus read-only files:/internal:/bin/false\n'
                  f'nimbus-sshd:x:{privsep_uid}:{privsep_uid}:Nimbus SFTP privsep:{STAGE}/empty:/bin/false\n').encode(),
        'group':f'nimbus-files:x:{files_uid}:\nnimbus-sshd:x:{privsep_uid}:\n'.encode(),
        # last-change=1 avoids forced-change=0; blank max/expiry decode as -1
        # under the reviewed shadow interface. No real password hash supplied.
        'shadow':b'nimbus-files:*:1::::::\nnimbus-sshd:!:1::::::\n',
    }
    files={name:originals[name]+appended[name] for name in originals}
    # Reparse and validate only the two new roles, never expose existing hashes.
    for name,data in files.items():table(data,name)
    record={'schema':'nimbus-private-sftp-account-plan/v1',
            'build_configuration_sha256':CONFIG_HEADER_SHA256,
            'ids':{'nimbus-files':files_uid,'nimbus-sshd':privsep_uid},
            'account_policy':build_policy,
            'before':{name:hashlib.sha256(data).hexdigest() for name,data in originals.items()},
            'after':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
            'appended_bytes':{name:len(data) for name,data in appended.items()},
            'existing_accounts_modified':False,'password_authentication_enabled':False,
            'requires_shadow_install_before_passwd':True,
            'proposed_write_order':['group','shadow','passwd'],
            'proposed_rollback_order':['passwd','shadow','group'],
            'installer_supplied':False,'device_accounts_created':False,'native_auth_verified':False,
            'reset_persistence_verified':False,'listener_authorized':False,'production_ready':False,'flash_authorized':False,
            'gates':['review actual account-table ownership/links and current snapshots',
                     'guarded serialized installation and exact rollback preserving later edits',
                     'actual libc shadow lookup and non-root public-key login/denial tests',
                     'vendor reset/account-sync behavior and reboot persistence',
                     'separate exact approval before any device account change']}
    return files,record


def read_private(path,limit=65536):
    path=Path(path).absolute()
    if any(parent.is_symlink() for parent in (path,*path.parents)):raise ValueError('Private input path traverses a symlink')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1 or not 1<=info.st_size<=limit:
        raise ValueError('Use an owned bounded private regular input, mode 0600')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        opened=os.fstat(stream.fileno())
        if (info.st_dev,info.st_ino,info.st_size)!=(opened.st_dev,opened.st_ino,opened.st_size):raise ValueError('Input changed while opening')
        return stream.read(limit+1)


def prepare(output,inputs,header,files_uid=2206,privsep_uid=2207):
    output=Path(output).absolute()
    if output.parent!=PRIVATE or any(parent.is_symlink() for parent in (output,*output.parents)):
        raise ValueError('Use a new private provisioning child without symlinks')
    if set(inputs)!={'passwd','group','shadow'}:raise ValueError('Exactly three private baseline inputs required')
    files,record=plan(**{name:read_private(path) for name,path in inputs.items()},header=header,files_uid=files_uid,privsep_uid=privsep_uid)
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.stat().st_uid!=os.getuid() or stat.S_IMODE(PRIVATE.stat().st_mode)!=0o700:raise ValueError('Private parent ownership/mode differs')
    output.mkdir(mode=0o700)
    files['ACCOUNT-PLAN.json']=(json.dumps(record,indent=2)+'\n').encode()
    files['NOT-INSTALLED.txt']=b'Private baseline-derived account tables. No device installer, account/key/listener change or firmware authorization. Never redistribute or upload table contents. Preserve failed stages.\n'
    for name,data in files.items():
        fd=os.open(output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    for directory in (output,PRIVATE):
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    for name in ('passwd','group','shadow','config-header'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--files-uid',type=int,default=2206);parser.add_argument('--privsep-uid',type=int,default=2207)
    args=parser.parse_args();os.umask(0o077)
    try:
        header=read_private(args.config_header).decode('ascii')
        record=prepare(args.output,{name:getattr(args,name) for name in ('passwd','group','shadow')},header,args.files_uid,args.privsep_uid)
    except (OSError,ValueError,UnicodeError):raise SystemExit('Private account planning refused; preserve local evidence. No device changed.')
    print(json.dumps({name:record[name] for name in ('device_accounts_created','native_auth_verified','listener_authorized')},indent=2))
