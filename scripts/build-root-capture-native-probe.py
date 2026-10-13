#!/usr/bin/env python3
"""Build a small inert ARM native probe locally. Never deploys or runs on a drive."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def build(archive,output):
    spec=importlib.util.spec_from_file_location('probe_stream_builder',ROOT/'scripts/build-root-capture-stream.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    checks=module.load_checks()
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe output path.')
    source=ROOT/'device/root-capture-native-probe.c'
    if source.is_symlink() or not source.is_file() or source.stat().st_size>65536:
        raise ValueError('Expected bounded first-party probe.')
    output.mkdir(mode=0o700)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    copied=output/source.name;shutil.copyfile(source,copied);copied.chmod(0o600)
    binary=output/'native-probe.arm'
    args=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
          '-fstack-protector-strong','-static','-no-pie','-ffile-prefix-map='+str(output)+'=/nimbus-probe-build',
          '-Wl,-z,noexecstack,-z,relro,-z,now',str(copied),'-o',str(binary)]
    checks.run(args,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    for options,expected in (([],2),(['--probe'],0)):
        result=subprocess.run(['qemu-arm-static',str(binary),*options],capture_output=True,timeout=10)
        if result.returncode!=expected or result.stderr or (not options and result.stdout) or (options and not result.stdout.endswith(b'PROBE=PASS native_capture_qualified=no\n')):
            raise ValueError('ARM emulated probe differs.')
        if options: (output/'EMULATED-PROBE.txt').write_bytes(result.stdout)
    binary.chmod(0o600)
    manifest={'schema':'nimbus-inert-native-probe/v1','artifact':artifact,'source_sha256':checks.digest(copied),
              'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,'compile_arguments':args[1:],
              'emulated_probe_passed':True,'hardware_validated':False,'capture_qualified':False,'flash_authorized':False,
              'limits':'Own pipes/one child/self FD metadata only; no device reads, service/mount operations or listeners. Native execution requires separate staging approval.'}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'NOT-DEPLOYED.txt').write_text('Inert probe only, not a capture worker. No native staging/execution occurred during build.\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try: build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError): parser.error('Offline probe build failed; retain evidence. No device changed.')
    print('Inert ARM probe built locally. Native execution/staging approval still required.')
