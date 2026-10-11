#!/usr/bin/env python3
"""First-party CSS-only FieldKit icon patch for the exact installed progress CSS."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BEFORE = 'ab67dee0dbf51360cc1593699ccb60ded6a4f277a32233a08f8bf567ac05820b'
MARKER = b'/* FieldKit navigation mark:'


def installer(after):
    spec = importlib.util.spec_from_file_location('loader_icon_policy', ROOT/'scripts/package-upload-loader.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    script = policy.installer(after).replace(policy.BEFORE, BEFORE)
    script = script.replace('/root/nimbus-upload-loader-r1', '/root/nimbus-fieldkit-icon-r1')
    script = script.replace('nimbus-upload-new', 'nimbus-icon-new')
    script = script.replace('CSS-only upload/busy-loader update.', 'CSS-only FieldKit icon and bottom upload-card placement.')
    script = script.replace('Upload loader restyled. Upload/cancel handlers, homepage, music and Settings logic unchanged.', 'FieldKit icon and bottom upload card installed. Homepage, handlers, uploads and services unchanged.')
    return script.replace('Hard-refresh the dashboard. Spinner is indeterminate; no byte-percentage claims.', 'Hard-refresh the dashboard to see the theme-aware FieldKit icon.')


def build(output):
    output = Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('Refusing existing artifact')
    css = (ROOT/'device/unified/stock-dark.css').read_bytes()
    if css.count(MARKER) != 1 or hashlib.sha256(css.split(MARKER, 1)[0]).hexdigest() != BEFORE:
        raise ValueError('Icon must extend exact installed upload-percentage stylesheet')
    after = hashlib.sha256(css).hexdigest()
    files = {'stock-dark.css': css, 'install.sh': installer(after).encode()}
    report = {'schema':'nimbus-fieldkit-icon/v1', 'before_sha256':BEFORE, 'after_sha256':after,
              'scope':'one CSS asset; decorative navigation icon and bottom upload-card placement', 'status':'candidate/not installed',
              'public_redistribution':True}
    files['MANIFEST.json'] = (json.dumps(report, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name,data in sorted(files.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.mtime=1767225600
                archive.addfile(member,io.BytesIO(data))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.output),indent=2))
