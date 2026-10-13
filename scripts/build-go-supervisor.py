#!/usr/bin/env python3
"""Build inactive ARM synthetic supervisor probe; never deploys or scans."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def build(archive,output):
    spec=importlib.util.spec_from_file_location('go_runtime_checks',ROOT/'scripts/build-sftp-runtime.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    source=ROOT/'device/wardrive-go-supervisor.c'
    if source.is_symlink() or not source.is_file() or source.stat().st_size>65536:
        raise ValueError('Expected bounded first-party source')
    output=Path(output).absolute()
    if any(parent.is_symlink() for parent in (output,*output.parents)) or any(parent in (Path('/dev'),Path('/proc'),Path('/sys')) for parent in output.parents):
        raise ValueError('Unsafe output path')
    output.mkdir(mode=0o700,exist_ok=False)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    copied=output/source.name;shutil.copyfile(source,copied);copied.chmod(0o600)
    binary=output/'go-supervisor-probe.arm'
    args=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
          '-fstack-protector-strong','-static','-no-pie',
          '-ffile-prefix-map='+str(output)+'=/nimbus-go-build',
          '-Wl,-z,noexecstack,-z,relro,-z,now',str(copied),'-o',str(binary)]
    checks.run(args,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    refused=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
    if refused.returncode!=2 or refused.stdout or refused.stderr:raise ValueError('Emulated refusal differs')
    normal=subprocess.run(['qemu-arm-static',str(binary),'--probe','normal'],capture_output=True,timeout=10)
    expected=b'GO-SUPERVISOR=OBSERVED result=completed bytes=128 child_reaped=yes pipe_drained=yes descendant_containment_verified=no native_scan_verified=no\n'
    if normal.returncode or normal.stdout!=expected or normal.stderr:raise ValueError('Emulated synthetic normal probe differs')
    controlled=subprocess.run(['qemu-arm-static',str(binary),'--probe-controlled','ignore-term'],input=b'',capture_output=True,timeout=10)
    expected_closed=b'GO-SUPERVISOR=OBSERVED result=control_closed bytes=0 child_reaped=yes pipe_drained=yes descendant_containment_verified=no native_scan_verified=no\n'
    if controlled.returncode!=7 or controlled.stdout!=expected_closed or controlled.stderr:
        raise ValueError('Emulated control-close cancellation differs')
    (output/'emulated-normal.stdout').write_bytes(normal.stdout)
    (output/'emulated-control-closed.stdout').write_bytes(controlled.stdout)
    binary.chmod(0o600)
    report={'schema':'nimbus-go-supervisor-probe-build/v1','artifact':artifact,
            'source_sha256':checks.digest(copied),'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,
            'compile_arguments':args[1:],'emulated_refusal_verified':True,'emulated_synthetic_normal_verified':True,
            'emulated_control_close_verified':True,'parent_death_guard_supplied':True,
            'native_verified':False,'descendant_containment_verified':False,'scan_worker_supplied':False,
            'device_changed':False,'installable':False,'flash_authorized':False,
            'limits':['Own synthetic child only, no radio/network/storage executor.',
                      'Host/emulator evidence is not legacy kernel/driver qualification.',
                      'Signals cannot guarantee a deadline for uninterruptible kernel work.',
                      'Full scan-worker descendant containment, authentication and shared-radio restoration remain open.']}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'NOT-A-SCAN-WORKER.txt').write_text('Inactive own-process probe only. Never scans or executes external commands. Native staging/execution needs separate review; no scan or firmware authorization.\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError):raise SystemExit('Offline GO probe build refused; retain evidence. No device changed.')
    print(json.dumps({'artifact':report['artifact'],'native_verified':False,'scan_worker_supplied':False},indent=2))
