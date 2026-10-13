#!/usr/bin/env python3
"""Parse bounded fixed-path layout evidence; never collect, provision or launch."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout_confinement',ROOT/'scripts/sftp-confinement.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
PATHS={'root':'/','root_home':'/root','stage':policy.STAGE,'jail':policy.JAIL,
       'privsep':policy.STAGE+'/empty','etc':'/etc','auth_root':'/etc/nimbus-sftp-auth',
       'auth_account':'/etc/nimbus-sftp-auth/nimbus-files','authorized':policy.AUTH,
       'hostkey':policy.STAGE+'/host-ed25519','internal_view':policy.JAIL+'/internal','sd_view':policy.JAIL+'/sd'}
MOUNTS={'internal_source':'/mnt/storage','sd_source':'/mnt/sdcard',
        'internal_view':policy.JAIL+'/internal','sd_view':policy.JAIL+'/sd'}
CONTEXT={'effective_config','listen_address','client_public_key','host_fingerprint',
         'management_host_fingerprint','management_client_fingerprint'}


def number(text,base=10):
    if not isinstance(text,str) or not re.fullmatch('[0-7]{1,6}' if base==8 else '[0-9]{1,20}',text):
        raise ValueError('Malformed bounded metadata number')
    return int(text,base)


def parse(text):
    if not isinstance(text,str) or len(text)>65536 or not text.endswith('\n') or any(ord(c)>126 or (ord(c)<32 and c!='\n') for c in text):
        raise ValueError('Expected bounded ASCII/LF layout evidence')
    lines=text.splitlines()
    version=lines[0][-1:] if lines else ''
    if version not in ('1','2') or len(lines)>128 or lines[:1]!=['NIMBUS-SFTP-LAYOUT-BEGIN '+version] or lines[-1:]!=['NIMBUS-SFTP-LAYOUT-END '+version]:
        raise ValueError('Incomplete/unsupported layout frame')
    before={};after={};accounts={};mounts=[];single={};section='initial'
    for line in lines[1:-1]:
        parts=line.split()
        if line in ('BEFORE','MOUNTS','AFTER'):
            expected={'initial':'BEFORE','before':'MOUNTS','mounts':'AFTER'}.get(section)
            if line!=expected:raise ValueError('Duplicate/out-of-order layout section')
            section=line.lower();continue
        if not parts:raise ValueError('Empty layout record')
        kind=parts[0]
        if kind=='NODE':
            if section not in ('before','after') or len(parts)<3 or parts[1] not in PATHS:raise ValueError('Unknown/out-of-order metadata node')
            target=before if section=='before' else after
            if parts[1] in target:raise ValueError('Duplicate metadata node')
            state=parts[2]
            if state in ('absent','unsafe','unknown','special') and len(parts)==3:
                target[parts[1]]={'kind':state}
            elif state in ('directory','file') and len(parts)==10:
                row={'kind':state}
                for key,value in zip(('uid','gid','mode','links','bytes','device','inode'),parts[3:]):
                    row[key]=number(value,8 if key=='mode' else 10)
                target[parts[1]]=row
            else:raise ValueError('Malformed metadata node')
        elif kind=='MOUNT':
            if section!='mounts' or len(parts)!=10 or parts[1] not in MOUNTS or len(mounts)>=16:
                raise ValueError('Malformed selected mount record')
            _,tag,ident,parent,device,root,vfs,fs,source,sb=parts
            number(ident);number(parent)
            if not re.fullmatch(r'[0-9]{1,10}:[0-9]{1,10}',device) or root not in ('/','/__unreviewed_root__'):
                raise ValueError('Malformed mount identity')
            if vfs not in ('ro','rw','ro,rw','unknown') or sb not in ('ro','rw','ro,rw','unknown') or fs not in ('texfat','vfat','exfat','ext3','unreviewed') or source not in ('/dev/mmcblk0p4','/dev/mmcblk1p1','unreviewed'):
                raise ValueError('Unexpected selected mount field')
            mounts.append(f'{ident} {parent} {device} {root} {MOUNTS[tag]} {vfs} - {fs} {source} {sb}')
        elif kind=='ACCOUNT':
            if section!='mounts' or len(parts)<3 or parts[1] not in ('nimbus-files','nimbus-sshd') or parts[1] in accounts:
                raise ValueError('Malformed/duplicate account record')
            name,state=parts[1:3]
            if state in ('absent','unknown','ambiguous') and len(parts)==3:
                accounts[name]=None
            elif state=='present' and len(parts)==(12 if version=='2' else 11):
                _,_,_,uid,gid,shell,executable,uid_count,gid_count,exclusive,gids=parts[:11]
                home=parts[11] if version=='2' else 'unqualified'
                if home not in ('expected','other','unqualified'):raise ValueError('Unreviewed account home classification')
                if shell not in ('non_shell','other') or executable not in ('yes','no') or exclusive not in ('yes','no'):
                    raise ValueError('Unreviewed account classification')
                supplementary=[number(value) for value in gids.split(',')]
                if len(supplementary)>32 or len(set(supplementary))!=len(supplementary):raise ValueError('Ambiguous supplementary groups')
                accounts[name]={'uid':number(uid),'gid':number(gid),'shell':'/bin/false' if shell=='non_shell' else 'unqualified',
                                'home':('/internal' if name=='nimbus-files' else policy.STAGE+'/empty') if home=='expected' else 'unqualified',
                                'shell_executable':executable=='yes','uid_occurrences':number(uid_count),
                                'primary_gid_accounts':[name] if number(gid_count)==1 and exclusive=='yes' else [],
                                'supplementary_gids':sorted(supplementary)}
            else:raise ValueError('Malformed account record')
        else:
            if kind=='EMPTY':
                if section!='mounts' or len(parts)!=3 or parts[1] not in ('privsep','sd') or parts[2] not in ('yes','no','unknown'):
                    raise ValueError('Malformed empty-directory record')
                key='empty_'+parts[1];value=parts[2]
            elif kind=='BLOCK':
                if section!='mounts' or len(parts)!=3 or parts[1]!='sd' or (parts[2]!='unknown' and not re.fullmatch(r'[0-9]{1,10}:[0-9]{1,10}',parts[2])):
                    raise ValueError('Malformed block identity record')
                key='block_sd';value=parts[2]
            else:
                key=kind.lower()
                allowed={'USB':('initial',('active','inactive','unknown')),
                         'OVERMOUNT':('mounts',('present','none')),
                         'COHERENCE':('after',('stable','changed','unknown'))}
                if kind=='AUTHORIZED_SHA256':
                    if section!='mounts' or len(parts)!=2 or (parts[1]!='unknown' and not re.fullmatch('[a-f0-9]{64}',parts[1])):
                        raise ValueError('Malformed public-authorization checksum')
                elif kind not in allowed or section!=allowed[kind][0] or len(parts)!=2 or parts[1] not in allowed[kind][1]:
                    raise ValueError('Unknown/out-of-order layout record')
                value=parts[1]
            if key in single:raise ValueError('Duplicate layout fact')
            single[key]=value
    if section!='after' or set(before)!=set(PATHS) or set(after)!=set(PATHS) or set(accounts)!={'nimbus-files','nimbus-sshd'} or set(single)!={'usb','overmount','empty_privsep','empty_sd','authorized_sha256','block_sd','coherence'}:
        raise ValueError('Missing required layout evidence')
    if single['coherence']=='stable' and before!=after:raise ValueError('Stable marker contradicts node identities')
    # Re-run common mount syntax validation, not only protocol token validation.
    mount_text='\n'.join(mounts)+'\n' if mounts else ''
    policy.mountinfo(mount_text)
    return {'schema':'nimbus-sftp-layout-evidence/v1','usb_state':single['usb'],
            'coherence':single['coherence'],'unexpected_mounts':single['overmount']!='none',
            'metadata':{PATHS[tag]:value for tag,value in after.items()},'accounts':accounts,
            'privsep_empty':single['empty_privsep']=='yes','sd_placeholder_empty':single['empty_sd']=='yes',
            'authorized_keys_sha256':single['authorized_sha256'],
            'block_devices':{} if single['block_sd']=='unknown' else {'/dev/mmcblk1p1':single['block_sd']},
            'mountinfo':mount_text,'native_auth_verified':False,'listener_authorized':False,
            'usb_handoff_verified':False,'production_ready':False,'flash_authorized':False}


def assemble(report,context):
    if not isinstance(report,dict) or report.get('schema')!='nimbus-sftp-layout-evidence/v1' or report.get('coherence')!='stable' or report.get('unexpected_mounts') is not False:
        raise ValueError('Incoherent/unsafe layout evidence')
    if not isinstance(context,dict) or set(context)!=CONTEXT:raise ValueError('Explicit bounded policy/identity context required; no metadata overrides')
    authorized,_=policy.public_key(context['client_public_key'])
    if report.get('authorized_keys_sha256')!=hashlib.sha256(authorized.encode()).hexdigest():
        raise ValueError('Observed public authorization file differs from dedicated enrollment')
    return {'schema':'nimbus-sftp-confinement-observation/v1',**context,
            **{key:report[key] for key in ('usb_state','metadata','accounts','privsep_empty','sd_placeholder_empty','block_devices','mountinfo','authorized_keys_sha256')},
            'authorized_keys':authorized}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args()
    try:
        path=args.input.absolute()
        if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or path.stat().st_size>65536:
            raise ValueError('Use bounded regular saved evidence')
        report=parse(path.read_text(encoding='ascii'))
    except (OSError,ValueError,UnicodeError):raise SystemExit('Layout evidence refused; preserve source. No device action.')
    print(json.dumps({'schema':report['schema'],'usb_state':report['usb_state'],'coherence':report['coherence'],
                      'missing_or_unsafe_nodes':sum(row.get('kind') not in ('directory','file') for row in report['metadata'].values()),
                      'accounts_observed':sum(row is not None for row in report['accounts'].values()),
                      'listener_authorized':False,'native_auth_verified':False},indent=2))
