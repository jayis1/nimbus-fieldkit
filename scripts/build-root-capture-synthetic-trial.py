#!/usr/bin/env python3
"""Prepare an inert, separately pinned guardian trial locally. Never deploys."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def synthetic_inputs():
    worker=ROOT/'device/root-capture-synthetic-worker.sh'
    if worker.is_symlink() or not worker.is_file() or worker.stat().st_size>8192:
        raise ValueError('Expected bounded first-party synthetic worker.')
    files={'worker.sh':worker.read_bytes(),
           'identity.sh':b'# Synthetic metadata only; never sourced.\n',
           'streamer':b'#!/bin/sh\n# Dummy pin input; never invoked by synthetic worker.\nexit 64\n'}
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n'
                               for name,data in sorted(files.items())).encode()
    return files


def build(archive,output):
    guard=load('synthetic_guardian_builder',ROOT/'scripts/build-root-capture-guardian.py')
    checks=load('synthetic_stream_builder',ROOT/'scripts/build-root-capture-stream.py').load_checks()
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe output path.')
    sources={}
    for name in ('root-capture-guardian.c','root-capture-sha256.h'):
        path=ROOT/'device'/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536: raise ValueError('Unexpected source.')
        sources[name]=path.read_bytes()
    files=synthetic_inputs();hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    output.mkdir(mode=0o700)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    for name,data in sources.items(): (output/name).write_bytes(data)
    (output/'guardian-pins.h').write_text(guard.pins_header(hashes))
    binary=output/'synthetic-guardian.arm'
    args=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
          '-DNIMBUS_GUARDIAN_FIXTURE','-DNIMBUS_GUARDIAN_PINNED','-fstack-protector-strong','-static','-no-pie',
          '-ffile-prefix-map='+str(output)+'=/nimbus-synthetic-build','-Wl,-z,noexecstack,-z,relro,-z,now',
          str(output/'root-capture-guardian.c'),'-o',str(binary)]
    checks.run(args,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    result=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
    if (result.returncode,result.stdout,result.stderr)!=(2,b'',b''): raise ValueError('ARM refusal differs.')
    binary.chmod(0o600)
    files['guardian']=binary.read_bytes()
    session=secrets.token_hex(32)
    files['started']=(session+'\n').encode();files['worker.log']=b''
    bundle=output/'synthetic-trial.tar.gz'
    with bundle.open('xb') as destination:
        with gzip.GzipFile(filename='',mode='wb',fileobj=destination,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive_out:
                for name,data in sorted(files.items()):
                    info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o700 if name in ('guardian','streamer') else 0o600
                    info.uid=info.gid=0;info.mtime=0
                    archive_out.addfile(info,io.BytesIO(data))
    if bundle.stat().st_size>131072: raise ValueError('Synthetic upload exceeds budget.')
    manifest={'schema':'nimbus-synthetic-guardian-trial/v1','session':session,
              'device_stage':'/tmp/nimbus-guardian-synthetic-v1','artifact':artifact,
              'bundle_bytes':bundle.stat().st_size,'bundle_sha256':checks.digest(bundle),
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
              'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in sources.items()},
              'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,'compile_arguments':args[1:],
              'emulated_no_argument_refusal':True,'hardware_validated':False,'real_capture_worker_included':False,
              'capture_qualified':False,'flash_authorized':False,
              'limits':'Synthetic built-in-only worker. No real streamer/coordinator. Native upload/exec and deliberate loss of only this SSH client require separate approval.'}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'NOT-DEPLOYED.txt').write_text('Synthetic guardian disconnect trial only; no native staging or execution performed. Do not use for a real capture.\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try: build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError): parser.error('Offline synthetic build failed; retain evidence. No device changed.')
    print('Pinned synthetic ARM trial prepared. No real capture worker or native deployment.')
