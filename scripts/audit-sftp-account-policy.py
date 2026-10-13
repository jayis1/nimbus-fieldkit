#!/usr/bin/env python3
"""Review pinned OpenSSH account rules as data; no server, compiler or device IO."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA256='a9dc9565dffe8640f64d863cd29a32bc4a3dbdec0566a7fc44c5d6ee767d5f39'
SELECTED=('auth.c','auth-shadow.c','platform.c','defines.h','README.privsep','LICENCE')
spec=importlib.util.spec_from_file_location('account_review_plan',ROOT/'scripts/prepare-sftp-accounts.py')
accounts=importlib.util.module_from_spec(spec);spec.loader.exec_module(accounts)


def regular(path,limit):
    path=Path(path).absolute()
    if any(parent.is_symlink() for parent in (path,*path.parents)):
        raise ValueError('Review path must not traverse symlinks')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>limit:raise ValueError('Expected bounded regular review input')
    return path.read_bytes()


def review(source_archive,config_header):
    source=regular(source_archive,8*1024**2)
    if hashlib.sha256(source).hexdigest()!=SOURCE_SHA256:raise ValueError('OpenSSH source pin differs')
    header=regular(config_header,65536)
    account_policy=accounts.verify_build_account_rules(header.decode('ascii'))
    files={'config.h':header}
    with tarfile.open(fileobj=io.BytesIO(source)) as archive:
        members={}
        for member in archive:
            if member.name in {'openssh-10.6p1/'+name for name in SELECTED}:
                if member.name in members:raise ValueError('Duplicate selected source member')
                members[member.name]=member
        for name in SELECTED:
            member=members.get('openssh-10.6p1/'+name)
            if member is None or not member.isfile() or not 1<=member.size<=524288:
                raise ValueError('Required source review member missing/unsafe')
            files[name]=archive.extractfile(member).read()
    snippets={'auth.c':'if (!options.use_pam && platform_locked_account(pw)) {',
              'platform.c':'strncmp(passwd, LOCKED_PASSWD_PREFIX,',
              'defines.h':'#if defined(HAVE_SHADOW_H) && !defined(DISABLE_SHADOW)',
              'auth-shadow.c':'if (spw->sp_expire == -1) {'}
    if any(files[name].decode().count(text)!=1 for name,text in snippets.items()):raise ValueError('Pinned account-rule layout differs')
    record={'schema':'nimbus-sftp-account-source-review/v1','source_archive_sha256':SOURCE_SHA256,
            'config_header_sha256':accounts.CONFIG_HEADER_SHA256,'account_policy':account_policy,
            'source_and_macro_review_pass':True,'native_auth_verified':False,
            'shadow_lookup_verified':False,'vendor_reset_review_complete':False,
            'listener_authorized':False,'flash_authorized':False,
            'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
            'limits':'Source/macros only; not libc password rejection, shadow parsing, PAM/vendor accounts or native login.'}
    return files,record


def save(output,files,record):
    output=Path(output).absolute()
    if any(parent.is_symlink() for parent in (output,*output.parents)) or any(parent in (Path('/dev'),Path('/proc'),Path('/sys')) for parent in output.parents):
        raise ValueError('Unsafe review output')
    output.mkdir(mode=0o700,parents=False,exist_ok=False)
    contents={**files,'REVIEW.json':(json.dumps(record,indent=2)+'\n').encode()}
    for name,data in contents.items():
        if Path(name).name!=name:raise ValueError('Unsafe review filename')
        fd=os.open(output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive',type=Path,required=True);parser.add_argument('--config-header',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:
        files,record=review(args.source_archive,args.config_header);save(args.output,files,record)
    except (OSError,ValueError,UnicodeError,tarfile.TarError):raise SystemExit('Account source review refused; preserve local evidence. No device changed.')
    print(json.dumps({name:record[name] for name in ('source_and_macro_review_pass','native_auth_verified','listener_authorized')},indent=2))
