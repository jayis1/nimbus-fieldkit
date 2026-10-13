#!/usr/bin/env python3
"""Validate supplied SFTP metadata only. No filesystem, process or device actions.

Inputs are supplied collector/context assertions, not authenticated native
evidence. Success never authorizes a listener, bind mount, account or USB change.
"""
import base64
import hashlib
import re
import struct

STAGE='/root/nimbus-sftp-candidate-v1'
AUTH='/etc/nimbus-sftp-auth/nimbus-files/authorized_keys'
JAIL=STAGE+'/jail'
DIRECTORIES={
    '/':0o755, '/root':(0o700,0o755), STAGE:0o700, JAIL:0o755,
    STAGE+'/empty':0o755, '/etc':0o755,
    '/etc/nimbus-sftp-auth':0o755, '/etc/nimbus-sftp-auth/nimbus-files':0o755,
}
POLICY={
    'port':'2226', 'addressfamily':'inet', 'allowusers':'nimbus-files',
    'permitrootlogin':'no', 'pubkeyauthentication':'yes',
    'authenticationmethods':'publickey', 'passwordauthentication':'no',
    'kbdinteractiveauthentication':'no', 'permitemptypasswords':'no',
    'usepam':'no', 'strictmodes':'yes', 'authorizedkeysfile':AUTH,
    'authorizedkeyscommand':'none', 'hostkey':STAGE+'/host-ed25519',
    'chrootdirectory':JAIL, 'forcecommand':'internal-sftp -R -d /internal',
    'subsystem':'sftp internal-sftp', 'disableforwarding':'yes',
    'allowtcpforwarding':'no', 'allowstreamlocalforwarding':'no',
    'allowagentforwarding':'no', 'x11forwarding':'no', 'permittunnel':'no',
    'permittty':'no', 'permituserrc':'no', 'permituserenvironment':'no',
    'maxsessions':'1',
}


def public_key(text):
    if not isinstance(text,str) or not 1<=len(text)<=4096 or any(ord(c)<32 for c in text.rstrip('\n')):
        raise ValueError('Expected one plain public Ed25519 key')
    lines=text.strip().splitlines()
    if len(lines)!=1:raise ValueError('Exactly one client public key required')
    parts=lines[0].split()
    if len(parts)<2 or parts[0]!='ssh-ed25519':raise ValueError('Key options, certificates and non-Ed25519 keys refused')
    try:raw=base64.b64decode(parts[1],validate=True)
    except ValueError:raise ValueError('Malformed public key') from None
    prefix=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)
    if len(raw)!=len(prefix)+32 or not raw.startswith(prefix) or base64.b64encode(raw).decode()!=parts[1]:
        raise ValueError('Invalid/noncanonical Ed25519 wire key')
    fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
    return 'restrict ssh-ed25519 '+parts[1]+'\n',fingerprint


def fingerprint(value):
    if not isinstance(value,str) or not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}',value):
        raise ValueError('Expected SHA256 fingerprint')
    raw=base64.b64decode(value[7:]+'=',validate=True)
    if len(raw)!=32 or base64.b64encode(raw).decode().rstrip('=')!=value[7:]:
        raise ValueError('Noncanonical fingerprint')
    return value


def effective_policy(text,address):
    # Every required directive must appear exactly once. No last-value-wins
    # normalization: duplicate security directives are ambiguous evidence.
    import ipaddress
    ip=ipaddress.IPv4Address(address)
    if not any(ip in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('One explicit private LAN listen address required')
    if not isinstance(text,str) or len(text)>65536:raise ValueError('Invalid effective policy')
    required={**POLICY,'listenaddress':str(ip)+':2226'}
    found={}
    for line in text.splitlines():
        parts=line.split(None,1)
        if not parts:continue
        name=parts[0].lower()
        if name in required:
            if len(parts)!=2 or name in found:raise ValueError('Duplicate/incomplete restricted policy')
            found[name]=parts[1]
    if found!=required:raise ValueError('Restricted effective policy differs')
    return required


def mountinfo(text):
    if not isinstance(text,str) or len(text)>262144:raise ValueError('Invalid mount metadata')
    result=[];ids=set()
    for line in text.splitlines():
        parts=line.split()
        try:
            separator=parts.index('-')
            if separator<6 or len(parts)!=separator+4:raise ValueError()
            ident=int(parts[0]);parent=int(parts[1])
            if ident<=0 or parent<0 or ident in ids or not re.fullmatch(r'[0-9]+:[0-9]+',parts[2]):raise ValueError()
            if any(not value.startswith('/') or '\\' in value or '//' in value or '/..' in value or '/./' in value for value in parts[3:5]):raise ValueError()
        except (ValueError,IndexError):raise ValueError('Malformed/duplicate mount metadata') from None
        ids.add(ident)
        result.append({'id':ident,'parent':parent,'device':parts[2],'root':parts[3],
                       'path':parts[4],'vfs':set(parts[5].split(',')),
                       'filesystem':parts[separator+1],'source':parts[separator+2],
                       'superblock':set(parts[separator+3].split(','))})
    return result


def _metadata(row,kind,mode):
    if not isinstance(row,dict) or row.get('kind')!=kind or row.get('uid')!=0 or row.get('gid')!=0:
        raise ValueError('Root-owned regular metadata required')
    permitted=mode if isinstance(mode,tuple) else (mode,)
    if any(type(row.get(name)) is not int for name in ('uid','gid','mode')) or row['mode'] not in permitted:
        raise ValueError('Unsafe metadata permissions')
    if kind=='file' and (type(row.get('links')) is not int or row['links']!=1 or
                         type(row.get('bytes')) is not int or not 1<=row['bytes']<=16384):
        raise ValueError('Invalid authentication file metadata')


def validate(observation):
    if not isinstance(observation,dict) or observation.get('schema')!='nimbus-sftp-confinement-observation/v1':
        raise ValueError('Unsupported confinement observation')
    if observation.get('usb_state')!='inactive' or observation.get('privsep_empty') is not True:
        raise ValueError('USB export/privsep state unsafe or unknown')
    effective_policy(observation.get('effective_config'),observation.get('listen_address'))
    metadata=observation.get('metadata')
    if not isinstance(metadata,dict):raise ValueError('Missing jail/auth metadata')
    for path,mode in DIRECTORIES.items():_metadata(metadata.get(path),'directory',mode)
    _metadata(metadata.get(AUTH),'file',0o644)
    _metadata(metadata.get(STAGE+'/host-ed25519'),'file',0o600)
    authorized,client_pin=public_key(observation.get('client_public_key'))
    if observation.get('authorized_keys')!=authorized:raise ValueError('Enrollment must be exactly one restricted dedicated key')
    if observation.get('authorized_keys_sha256')!=hashlib.sha256(authorized.encode()).hexdigest():
        raise ValueError('Observed authorized-key checksum differs from enrollment')
    if metadata[AUTH]['bytes']!=len(authorized.encode()):raise ValueError('Authorized-key metadata/content length differs')
    if client_pin==fingerprint(observation.get('management_client_fingerprint')):
        raise ValueError('Do not reuse the management client identity for file access')
    if fingerprint(observation.get('host_fingerprint'))==fingerprint(observation.get('management_host_fingerprint')):
        raise ValueError('Do not reuse the management host identity')
    accounts=observation.get('accounts')
    if not isinstance(accounts,dict) or set(accounts)!={'nimbus-files','nimbus-sshd'}:
        raise ValueError('Distinct file and privilege-separation accounts required')
    identities=[]
    for name,account in accounts.items():
        if not isinstance(account,dict) or account.get('shell')!='/bin/false' or account.get('shell_executable') is not True:
            raise ValueError('Dedicated accounts need a valid non-shell executable')
        expected_home='/internal' if name=='nimbus-files' else STAGE+'/empty'
        if account.get('home')!=expected_home:raise ValueError('Dedicated account home differs from the reviewed role')
        uid,gid=account.get('uid'),account.get('gid')
        if type(uid) is not int or type(gid) is not int or not 1000<=uid<65534 or not 1000<=gid<65534:
            raise ValueError('Non-root dedicated UID/GID required')
        if account.get('supplementary_gids')!=[gid] or any(type(item) is not int for item in account['supplementary_gids']):
            raise ValueError('Supplementary/privileged group access refused')
        if type(account.get('uid_occurrences')) is not int or account['uid_occurrences']!=1 or account.get('primary_gid_accounts')!=[name]:
            raise ValueError('Dedicated identity collides with another account')
        identities.append((uid,gid))
    if identities[0][0]==identities[1][0] or identities[0][1]==identities[1][1]:
        raise ValueError('File and privsep identities must be distinct')
    mounts=mountinfo(observation.get('mountinfo'))
    if any(m['path']==JAIL or (m['path'].startswith(JAIL+'/') and m['path'] not in (JAIL+'/internal',JAIL+'/sd')) for m in mounts):
        raise ValueError('Unexpected mount inside the jail')
    for path,device,number,view in (('/mnt/storage','/dev/mmcblk0p4','179:4','internal'),
                                    ('/mnt/sdcard','/dev/mmcblk1p1',None,'sd')):
        source=[m for m in mounts if m['path']==path]
        target=JAIL+'/'+view
        bound=[m for m in mounts if m['path']==target]
        if view=='sd' and not source and not bound and observation.get('sd_placeholder_empty') is True:
            _metadata(metadata.get(target),'directory',0o755)
            continue
        if len(source)!=1 or len(bound)!=1:raise ValueError('Missing/ambiguous source or jail view')
        source,bound=source[0],bound[0]
        if view=='sd':
            devices=observation.get('block_devices')
            number=devices.get(device) if isinstance(devices,dict) else None
            if not isinstance(number,str) or not re.fullmatch(r'179:[0-9]+',number):
                raise ValueError('Missing independent SD block identity metadata')
        if source['source']!=device or source['device']!=number or source['root']!='/' or source['filesystem'] not in ('texfat','vfat','exfat','ext3'):
            raise ValueError('Unreviewed source geometry/filesystem')
        if ('rw' in source['vfs'])==('ro' in source['vfs']):raise ValueError('Ambiguous source mount flags')
        for mount in (source,bound):
            if ('rw' in mount['superblock'])==('ro' in mount['superblock']):
                raise ValueError('Ambiguous filesystem superblock flags')
        if ('ro' in source['superblock'])!=('ro' in bound['superblock']):
            raise ValueError('Source/view superblock observations disagree')
        if any(bound[key]!=source[key] for key in ('source','device','root','filesystem')) or 'ro' not in bound['vfs'] or 'rw' in bound['vfs']:
            raise ValueError('Read-only view must match the exact source root/device')
        if bound['id']==source['id']:raise ValueError('Source and view are not separate mounts')
        if any(m['path']==JAIL or m['path'].startswith(target+'/') or m['path'].startswith(path+'/') for m in mounts):
            raise ValueError('Unexpected jail/source overmount')
    return {'schema':'nimbus-sftp-confinement-check/v1','static_preconditions_pass':True,
            'native_verified':False,'listener_authorized':False,'usb_handoff_verified':False,
            'production_ready':False,'flash_authorized':False,
            'limitations':'Caller-supplied metadata; not account authentication, syscall confinement or continuous ownership evidence.'}


if __name__=='__main__':
    raise SystemExit('Library-only metadata validator. No collection, provisioning or listener action supplied by this library.')
