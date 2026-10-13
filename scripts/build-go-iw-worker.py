#!/usr/bin/env python3
"""Build inactive fixed read-only ARM iw worker. Never deploys/queries/scans."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('wardrive-go-iw-worker.c','wardrive-go-supervisor.c','root-capture-sha256.h')


def build(archive,output):
    spec=importlib.util.spec_from_file_location('go_iw_runtime_checks',ROOT/'scripts/build-sftp-runtime.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    for name in SOURCES:
        source=ROOT/'device'/name
        if source.is_symlink() or not source.is_file() or source.stat().st_size>65536:
            raise ValueError('Invalid bounded first-party source')
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe output directory')
    output.mkdir(mode=0o700,exist_ok=False)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    for name in SOURCES:
        shutil.copyfile(ROOT/'device'/name,output/name);(output/name).chmod(0o600)
    binary=output/'go-iw-readonly-worker.arm'
    args=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
          '-fstack-protector-strong','-static','-no-pie','-ffile-prefix-map='+str(output)+'=/nimbus-go-iw-build',
          '-Wl,-z,noexecstack,-z,relro,-z,now',str(output/SOURCES[0]),'-o',str(binary)]
    checks.run(args,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    refused=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
    if refused.returncode!=2 or refused.stdout or refused.stderr:raise ValueError('Emulated no-argument refusal differs')
    binary.chmod(0o600)
    report={'schema':'nimbus-go-iw-readonly-worker-build/v1','artifact':artifact,
            'source_sha256':{name:checks.digest(output/name) for name in SOURCES},
            'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,'compile_arguments':args[1:],
            'fixture_build':False,'fixture_diagnostics':False,'emulated_no_argument_refusal':True,
            'native_verified':False,'descendant_containment_verified':False,'scan_worker_supplied':False,
            'device_changed':False,'installable':False,'flash_authorized':False,
            'limits':['Only pinned non-root iw list/dev GET queries; output discarded, no scan/cache dump.',
                      'No dedicated native identity/enrollment/transport supplied.',
                      'NPROC blocks ordinary unprivileged fork, not malicious exec escalation or a full sandbox.',
                      'Dynamic iw dependencies and descriptor execution on the legacy kernel still need review.',
                      'No native real-worker or driver abort/coexistence qualification.']}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'NOT-A-SCAN-WORKER.txt').write_text('Inactive fixed read-only worker. Refuses root; dedicated identity/native qualification pending. No scan, native execution or firmware authorization. Do not weaken gates to use root management.\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError):raise SystemExit('Offline GO iw worker build refused; retain evidence. No device changed.')
    print(json.dumps({'artifact':report['artifact'],'native_verified':False,'scan_worker_supplied':False},indent=2))
