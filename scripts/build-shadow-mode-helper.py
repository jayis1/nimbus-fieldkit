#!/usr/bin/env python3
"""Build an inactive pinned-SDK ARM permission-only helper. Never deploys/runs it."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def build(archive,output):
    spec=importlib.util.spec_from_file_location('shadow_runtime_checks',ROOT/'scripts/build-sftp-runtime.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    checks.verify_archive(archive,checks.TOOLCHAIN_SHA256)
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)) or any(p in (Path('/dev'),Path('/proc'),Path('/sys')) for p in output.parents):
        raise ValueError('Unsafe output directory')
    sources=('device/ssh/shadow-mode-hardening.c','device/root-capture-sha256.h')
    for name in sources:
        source=ROOT/name
        if source.is_symlink() or not source.is_file() or source.stat().st_size>65536:raise ValueError('Invalid bounded first-party source')
    output.mkdir(mode=0o700,parents=False,exist_ok=False)
    checks.extract(archive,output/'sdk')
    sdk=output/'sdk/armv5-eabi--musl--stable-2026.08-1'
    env={'PATH':str(sdk/'bin')+':/usr/bin:/bin','HOME':str(output),'LC_ALL':'C'}
    checks.run(['sh',str(sdk/'relocate-sdk.sh')],sdk,output/'sdk-relocation.log',env=env)
    for name in sources:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        target.chmod(0o600)
    binary=output/'shadow-mode-helper.arm'
    arguments=[str(sdk/'bin/arm-buildroot-linux-musleabi-gcc'),'-std=c99','-Os','-Wall','-Wextra','-Werror',
               '-fstack-protector-strong','-static','-no-pie','-ffile-prefix-map='+str(output)+'=/nimbus-shadow-build',
               '-Wl,-z,noexecstack,-z,relro,-z,now',str(output/sources[0]),'-o',str(binary)]
    checks.run(arguments,output,output/'compile.log',env=env)
    checks.run([str(sdk/'bin/arm-buildroot-linux-musleabi-strip'),'--strip-unneeded',str(binary)],output,output/'strip.log',env=env)
    artifact=checks.audit_elf(binary)
    result=subprocess.run(['qemu-arm-static',str(binary)],capture_output=True,timeout=10)
    if result.returncode!=2 or result.stdout or result.stderr:raise ValueError('Emulated no-argument refusal differs')
    binary.chmod(0o600)
    report={'schema':'nimbus-shadow-mode-helper-build/v1','artifact':artifact,
            'sdk_archive_sha256':checks.TOOLCHAIN_SHA256,
            'source_sha256':{name:checks.digest(output/name) for name in sources},
            'compile_arguments':arguments[1:],'fixture_build':False,'emulated_no_argument_refusal':True,
            'native_verified':False,'device_permission_changed':False,'account_records_written':False,
            'installable':False,'flash_authorized':False,
            'limits':'Explicit permission-only operation; no table contents written. Requires fresh private identity/digest and native review. Sampled checks, not writer exclusion or reset/reboot persistence.'}
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'NOT-DEPLOYED.txt').write_text('Inactive helper. No native execution or permission change occurred during this build. Never restore insecure shadow permissions or reuse unrelated trial stages.\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--toolchain-archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    try:report=build(args.toolchain_archive,args.output)
    except (OSError,ValueError,subprocess.SubprocessError):raise SystemExit('Offline helper build refused; retain evidence. No device changed.')
    print(json.dumps({'artifact':report['artifact'],'native_verified':False,'device_permission_changed':False},indent=2))
