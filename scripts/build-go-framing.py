#!/usr/bin/env python3
"""Build inactive opaque ARM GO framing probe. Never deploys or opens an endpoint."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('wardrive-go-framing-probe.c','wardrive-go-framing.h')


def build(archive,output):
    spec=importlib.util.spec_from_file_location('go_framing_checks',ROOT/'scripts/build-sftp-runtime.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    for name in SOURCES:
        path=ROOT/'device'/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:raise ValueError('Invalid bounded source')
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):raise ValueError('Unsafe output path')
    output.mkdir(mode=0o700,exist_ok=False);checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    for name in SOURCES:shutil.copyfile(ROOT/'device'/name,output/name);(output/name).chmod(0o600)
    binary=output/'go-framing-probe.arm'
    args=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror','-fstack-protector-strong','-static','-no-pie',
          '-ffile-prefix-map='+str(output)+'=/nimbus-go-framing-build','-Wl,-z,noexecstack,-z,relro,-z,now',str(output/SOURCES[0]),'-o',str(binary)]
    checks.run(args,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    refusal=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
    if refusal.returncode!=2 or refusal.stdout or refusal.stderr:raise ValueError('Emulated refusal differs')
    valid=subprocess.run(['qemu-arm-static',str(binary),'--probe-frames'],input=b'\0\0\0\1x',capture_output=True,timeout=10)
    expected=b'GO-FRAMING=OBSERVED result=framed frames=1 payload_bytes=1 auth_verified=no native_go_verified=no\n'
    if valid.returncode or valid.stdout!=expected or valid.stderr:raise ValueError('Emulated opaque framing differs')
    binary.chmod(0o600)
    report={'schema':'nimbus-go-framing-probe-build/v1','artifact':artifact,'source_sha256':{name:checks.digest(output/name) for name in SOURCES},
            'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,'compile_arguments':args[1:],'emulated_refusal_verified':True,'emulated_opaque_frame_verified':True,
            'native_verified':False,'authentication_supplied':False,'json_handler_supplied':False,'endpoint_supplied':False,'device_changed':False,'flash_authorized':False}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'NOT-AN-ENDPOINT.txt').write_text('Inactive opaque framing only. No authentication/JSON dispatch/radio/endpoint. No device run or firmware authorization.\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError):raise SystemExit('Offline GO framing build refused; retain evidence. No device changed.')
    print(json.dumps({'artifact':report['artifact'],'native_verified':False,'endpoint_supplied':False},indent=2))
