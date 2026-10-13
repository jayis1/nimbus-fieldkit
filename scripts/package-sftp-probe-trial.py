#!/usr/bin/env python3
"""Package three pinned ARM version/probe inputs locally. Never stages or runs."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PINS={'sshd':'bc10f02c3d1803bcb643448326b9579cc7c08bb25d62f0bb0e43d6565d005355',
      'rlimit-compat-probe':'0374ac9c229b371433508dbe4b97709cdf3a6396646fe9c07b2419da1f94a520',
      'rlimit-select-compat-probe':'1274e41fa34f92f1e07d84a513ef9348663617460b8b5edf3f6bf6de325531d9'}


def regular(path,limit):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)) or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size>limit:
        raise ValueError('Use bounded regular local pinned inputs')
    return path.read_bytes()


def build(output,runtime=ROOT/'build/nimbus-sftp-runtime-v1/runtime'):
    output=Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe/existing trial output')
    spec=importlib.util.spec_from_file_location('probe_runtime_audit',ROOT/'scripts/build-sftp-runtime.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    files={}
    for name,digest in PINS.items():
        path=Path(runtime)/name;data=regular(path,1048576)
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Pinned ARM input differs')
        audit.audit_elf(path)
        files[name]=data
    files['trial.sh']=regular(ROOT/'device/ssh/sftp-runtime-probe-trial.sh',16384)
    manifest={'schema':'nimbus-sftp-probe-trial/v1','status':'prepared/not executed',
              'device_stage':'/tmp/nimbus-sftp-probe-r1','runtime_bytes':sum(len(files[name]) for name in PINS),
              'commands':['sshd -V','rlimit-compat-probe (no arguments)','rlimit-select-compat-probe (no arguments)'],
              'new_files':'private tmpfs stage, three executables, script/manifest/checksums and retained CLAIM only',
              'no_listener':True,'no_account_or_key_changes':True,'no_media_or_mount_changes':True,
              'native_verified':False,'sftp_service_qualified':False,'flash_authorized':False,
              'approval_required':True,'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    files['MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    if sum(map(len,files.values()))>900000:raise ValueError('Trial exceeds tmpfs budget')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as raw:
        output.chmod(0o600)
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                for name,data in sorted(files.items()):
                    member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.uid=member.gid=0;member.mtime=1767225600
                    archive.addfile(member,io.BytesIO(data))
    return {'archive_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'archive_bytes':output.stat().st_size,**manifest}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:report=build(args.output)
    except (OSError,ValueError):raise SystemExit('Local probe packaging refused; no device changed.')
    print(json.dumps({key:report[key] for key in ('archive_sha256','archive_bytes','approval_required')},indent=2))
