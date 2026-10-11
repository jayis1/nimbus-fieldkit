#!/usr/bin/env python3
"""LOCAL-ONLY guarded homepage/CSS patch enabling genuine XHR upload progress."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
INDEX = '457f1244a7f017b080da0d475ef2c67752509f39b52f604fd34c6da98523b50b'
BASELINES = {'r1':'232c5a167045871adb8282e59b097378d27589d60953c6b6daf4a9afb6068459',
             'r2':'8fda6af14c301ffae5146afa4be8f9bda1164598c00637e92c10afe7651abf98'}


def installer(after, css_before):
    spec = importlib.util.spec_from_file_location('audio_patch_policy', ROOT/'scripts/package-audio-ui.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    script = policy.installer(INDEX, after)
    script = script.replace('nimbus-audio-html5-r1','nimbus-upload-progress-r1').replace('fieldkit-audio-r1','fieldkit-upload-progress-r1')
    script = script.replace('audio-html5.js','upload-progress.js').replace('nimbus-audio-new','nimbus-progress-new')
    helpers = '''css_baseline() { printf '%s  %s\\n' CSS_BEFORE "$1" | sha256sum -c -; }
CSS="$DATA/fieldkit-v06/stock-dark.css"
[ ! -L "$DATA/fieldkit-v06" ] && [ ! -L "$CSS" ] || exit 1
replace_css() {
    [ ! -e "$CSS.nimbus-progress-new" ] && [ ! -L "$CSS.nimbus-progress-new" ] || return 1
    (set -C; cat "$1" > "$CSS.nimbus-progress-new")
    chmod 644 "$CSS.nimbus-progress-new"
    cmp "$1" "$CSS.nimbus-progress-new"
    mv "$CSS.nimbus-progress-new" "$CSS"
}
'''.replace('CSS_BEFORE', css_before)
    script = script.replace('case "${1:-}" in', helpers + 'case "${1:-}" in')
    script = script.replace('    mkdir -m 700 backups', '    css_baseline "$CSS"\n    mkdir -m 700 backups')
    script = script.replace('    baseline backups/index.html', '    baseline backups/index.html\n    cp -p "$CSS" backups/stock-dark.css\n    css_baseline backups/stock-dark.css', 1)
    script = script.replace('    replace_index index.html', '    css_baseline "$CSS"\n    replace_css stock-dark.css\n    replace_index index.html')
    script = script.replace('sha256sum "$DATA/index.html" "$ASSETS/upload-progress.js" >', 'sha256sum "$DATA/index.html" "$ASSETS/upload-progress.js" "$CSS" >')
    script = script.replace('    replace_index backups/index.html', '    css_baseline backups/stock-dark.css\n    replace_css backups/stock-dark.css\n    replace_index backups/index.html')
    script = script.replace('HTML5-only Music UI installed. Settings assets, services, SSH and firmware unchanged.', 'Real upload-percentage UI installed. Upload transport now uses XHR; no service/mount/firmware changes.')
    script = script.replace('Hard-refresh the original homepage. Browser codecs and user-gesture policy still apply.', 'Hard-refresh. Test a small disposable file first; 100% sent is not device-save confirmation.')
    script = script.replace('Previous homepage restored. Unreferenced additive audio asset and private backups retained.', 'Previous homepage and stylesheet restored. Additive progress asset/private backups retained.')
    return script


def build(audio_bundle, output, css_baseline):
    if css_baseline not in BASELINES: raise ValueError('Choose exact installed loader r1 or r2')
    output = Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('Existing artifact; refusing overwrite')
    with tarfile.open(audio_bundle) as archive:
        member = archive.getmember('index.html')
        if not member.isfile() or member.size > 1048576: raise ValueError('Invalid bounded baseline')
        page = archive.extractfile(member).read()
    if hashlib.sha256(page).hexdigest() != INDEX: raise ValueError('Exact installed HTML5 homepage required')
    marker = b'<script src="/data/fieldkit-v06/bridge.js"></script>'
    if page.count(marker) != 1: raise ValueError('Unexpected homepage')
    patched = page.replace(marker,b'<script src="/data/fieldkit-upload-progress-r1/upload-progress.js"></script>\n'+marker)
    after = hashlib.sha256(patched).hexdigest()
    files = {'index.html':patched,'stock-dark.css':(ROOT/'device/unified/stock-dark.css').read_bytes(),
             'upload-progress.js':(ROOT/'device/unified/upload-progress.js').read_bytes(),
             'install.sh':installer(after,BASELINES[css_baseline]).encode()}
    report = {'schema':'nimbus-upload-progress/v1','status':'candidate/not installed','index_before_sha256':INDEX,
              'index_after_sha256':after,'css_before_sha256':BASELINES[css_baseline],
              'public_redistribution':False,'transport':'XHR multipart; same NimbusAPI endpoint',
              'device_contract_verified':False,'files':[{ 'name':name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())]}
    files['MANIFEST.json']=(json.dumps(report,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for name,data in sorted(files.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.mtime=1767225600
                archive.addfile(member,io.BytesIO(data))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-bundle',type=Path,required=True)
    parser.add_argument('--css-baseline',choices=BASELINES,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.audio_bundle,args.output,args.css_baseline),indent=2))
