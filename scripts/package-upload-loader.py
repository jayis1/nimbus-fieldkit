#!/usr/bin/env python3
"""Build a first-party CSS-only upload-loader patch; no device access."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BEFORE = 'd1428615bd883030f5d11089aeb4a802eb0ca448c588e076baa9db53ac700164'


def installer(after):
    # Reuse the reviewed single-asset baseline/backup/atomic replace/rollback policy.
    spec = importlib.util.spec_from_file_location('single_asset_patch', ROOT/'scripts/package-flash-warning-fix.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    script = policy.installer(after).replace(policy.BASELINE, BEFORE)
    script = script.replace('/root/nimbus-flash-warning-r1', '/root/nimbus-upload-loader-r1')
    script = script.replace('/nimbus/data/js', '/nimbus/data/fieldkit-v06').replace('t4u.controller.js', 'stock-dark.css')
    script = script.replace('nimbus-warning-new', 'nimbus-upload-new')
    script = script.replace('Only the exact vendor controller startup warning.', 'CSS-only upload/busy-loader update.')
    script = script.replace('Obsolete Flash startup warning removed. HTML5 player and all other controls unchanged.', 'Upload loader restyled. Upload/cancel handlers, homepage, music and Settings logic unchanged.')
    script = script.replace('Hard-refresh the original dashboard to discard the cached controller.', 'Hard-refresh the dashboard. Spinner is indeterminate; no byte-percentage claims.')
    script = script.replace('Later controller edits', 'Later stylesheet edits').replace('Exact original controller restored', 'Exact previous stylesheet restored')
    return script


def build(output):
    output = Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('Refusing existing artifact')
    css = (ROOT/'device/unified/stock-dark.css').read_bytes()
    marker = b'/* Upload/busy card:'
    if css.count(marker) != 1 or hashlib.sha256(css.split(marker, 1)[0]).hexdigest() != BEFORE:
        raise ValueError('Patch must extend the exact installed Settings stylesheet, not rewrite it')
    after = hashlib.sha256(css).hexdigest()
    files = {'stock-dark.css': css, 'install.sh': installer(after).encode()}
    report = {'schema':'nimbus-upload-loader/v1', 'before_sha256':BEFORE, 'after_sha256':after,
              'status':'candidate/not installed', 'scope':'one CSS asset; no upload transport changes',
              'progress':'indeterminate', 'reduced_motion':True, 'public_redistribution':True}
    files['MANIFEST.json'] = (json.dumps(report, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for name,data in sorted(files.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.mtime=1767225600
                archive.addfile(member,io.BytesIO(data))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.output),indent=2))
