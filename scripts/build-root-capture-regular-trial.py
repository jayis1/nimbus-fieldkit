#!/usr/bin/env python3
"""Build an inactive regular-file-only native reader/hasher trial. Never deploys."""
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
STAGE='/tmp/nimbus-reader-regular-v2'
HASHER_SHA='c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2'
HASHER_METADATA='0:0:755:116878'
DATA=bytes(range(256))*1024


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def fixture_files():
    source=ROOT/'device/root-capture-regular-worker.sh'
    if source.is_symlink() or not source.is_file() or source.stat().st_size>8192: raise ValueError('Unexpected worker template.')
    worker=source.read_text()
    for marker,value in (('@HASHER_SHA256@',HASHER_SHA),('@HASHER_METADATA@',HASHER_METADATA),('@DATA_SHA256@',hashlib.sha256(DATA).hexdigest())):
        if worker.count(marker)!=1: raise ValueError('Worker template changed.')
        worker=worker.replace(marker,value)
    return {'worker.sh':worker.encode(),'identity.sh':b'# Synthetic metadata only; not sourced.\n',
            'fixture-hasher':b'#!/bin/sh\nexec /usr/bin/sha256sum\n',
            'fixture/dev/mmcblk0p2':DATA,'fixture/proc/modules':b'',
            'fixture/proc/mounts':b'/dev/root / ext3 ro,relatime,errors=continue,barrier=0,data=writeback 0 0\n',
            'fixture/proc/self/mountinfo':b'20 1 179:2 / / ro,relatime - ext3 /dev/root ro,errors=continue,barrier=0,data=writeback\n',
            'fixture/sys/class/block/mmcblk0p2/dev':b'179:2\n',
            'fixture/sys/class/block/mmcblk0p2/start':b'38912\n',
            'fixture/sys/class/block/mmcblk0p2/size':b'512\n'}


def build(archive,output):
    guard=load('regular_guard_builder',ROOT/'scripts/build-root-capture-guardian.py')
    checks=load('regular_stream_builder',ROOT/'scripts/build-root-capture-stream.py').load_checks()
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents): raise ValueError('Unsafe output.')
    sources={}
    for name in ('root-capture-stream.c','root-capture-guardian.c','root-capture-sha256.h'):
        path=ROOT/'device'/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536: raise ValueError('Unexpected source.')
        sources[name]=path.read_bytes()
    files=fixture_files();output.mkdir(mode=0o700)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    for name,data in sources.items(): (output/name).write_bytes(data)
    common=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
            '-fstack-protector-strong','-static','-no-pie','-ffile-prefix-map='+str(output)+'=/nimbus-regular-build',
            '-Wl,-z,noexecstack,-z,relro,-z,now']
    streamer=output/'fixture-streamer.arm'
    stream_args=[*common,'-DNIMBUS_CAPTURE_FIXTURE','-DNIMBUS_FIXTURE_HASHER="'+STAGE+'/fixture-hasher"',
                 str(output/'root-capture-stream.c'),'-o',str(streamer)]
    checks.run(stream_args,output,output/'stream-compile.log',env=env)
    strip=[str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded']
    checks.run([*strip,str(streamer)],output,output/'stream-strip.log',env=env)
    stream_artifact=checks.audit_elf(streamer);files['streamer']=streamer.read_bytes()
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    pins={name:hashlib.sha256(files[name]).hexdigest() for name in ('worker.sh','identity.sh','streamer','SHA256SUMS')}
    (output/'guardian-pins.h').write_text(guard.pins_header(pins))
    guardian=output/'regular-guardian.arm'
    guard_args=[*common,'-DNIMBUS_GUARDIAN_FIXTURE','-DNIMBUS_GUARDIAN_PINNED',str(output/'root-capture-guardian.c'),'-o',str(guardian)]
    checks.run(guard_args,output,output/'guard-compile.log',env=env)
    checks.run([*strip,str(guardian)],output,output/'guard-strip.log',env=env)
    guard_artifact=checks.audit_elf(guardian)
    for binary in (streamer,guardian):
        result=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
        if (result.returncode,result.stdout,result.stderr)!=(2,b'',b''):raise ValueError('ARM refusal differs.')
        binary.chmod(0o600)
    files['guardian']=guardian.read_bytes();session=secrets.token_hex(32)
    files['started']=(session+'\n').encode();files['worker.log']=b''
    bundle=output/'regular-trial.tar.gz'
    with bundle.open('xb') as destination:
        with gzip.GzipFile(filename='',mode='wb',fileobj=destination,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive_out:
                # Explicit private directories avoid extraction-time defaults.
                directories=sorted({str(parent) for name in files for parent in Path(name).parents if str(parent)!='.'})
                for name in directories:
                    info=tarfile.TarInfo(name);info.type=tarfile.DIRTYPE;info.mode=0o700;info.uid=info.gid=0;info.mtime=0
                    archive_out.addfile(info)
                for name,data in sorted(files.items()):
                    info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o700 if name in ('guardian','streamer','fixture-hasher') else 0o600
                    info.uid=info.gid=0;info.mtime=0;archive_out.addfile(info,io.BytesIO(data))
    if bundle.stat().st_size>196608:raise ValueError('Upload budget exceeded.')
    manifest={'schema':'nimbus-regular-file-native-trial/v1','session':session,'device_stage':STAGE,
              'bundle_bytes':bundle.stat().st_size,'bundle_sha256':checks.digest(bundle),
              'guardian':guard_artifact,'streamer':stream_artifact,'fixture_bytes':len(DATA),'fixture_sha256':hashlib.sha256(DATA).hexdigest(),
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
              'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in sources.items()},
              'stream_compile_arguments':stream_args[1:],'guard_compile_arguments':guard_args[1:],'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,
              'hasher_path':'/usr/bin/sha256sum','hasher_sha256':HASHER_SHA,'hasher_metadata':HASHER_METADATA,
              'hardware_validated':False,'capture_qualified':False,'flash_authorized':False,'real_capture_worker_included':False,
              'limits':'Positive regular-file-only trial, fake ro metadata and precomputed synthetic ACK. No real mount/service worker or block reader. Host durability/disconnect-under-reader-load not qualified.'}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'NOT-DEPLOYED.txt').write_text('Regular-file-only synthetic native trial. No deployment or native run performed; separate approval required.\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError):parser.error('Offline regular-file trial failed; retain evidence. No device changed.')
    print('Inactive regular-file-only ARM trial prepared; no native deployment.')
