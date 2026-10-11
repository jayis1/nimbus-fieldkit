#!/usr/bin/env python3
"""LOCAL-ONLY guarded UI update; includes vendor homepage, never publish archive."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BEFORE='c5247236d5ed0a5b09076bf34523807cd39f4738a194f87cee8fc533103a4d9a'
OLD_ASSETS={
    'fieldkit-v06/bridge.js':'9035367baf4d9ace5cc5f7d871700eb076ef11041c37b69af4cb8a7645bea138',
    'fieldkit-upload-progress-r1/upload-progress.js':'792fe880137c12880f75ae8dc2d7068b5149b3e4c04e8025ce1e1c2271818a4b',
    'fieldkit-mascot-r1/mascot.js':'67caede08756eb58afeb5c86d76ba354577590c40109746eef77dbe32e629d2f',
}


def installer(after):
    spec=importlib.util.spec_from_file_location('performance_policy',ROOT/'scripts/package-audio-ui.py')
    policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    script=policy.installer(BEFORE,after).replace('nimbus-audio-html5-r1','nimbus-ui-performance-r1')
    script=script.replace('fieldkit-audio-r1','fieldkit-performance-r1').replace('nimbus-audio-new','nimbus-performance-new')
    old_guard='old_assets() {\n'
    for name,digest in OLD_ASSETS.items():
        directory=name.split('/')[0]
        old_guard+='    [ -d "$DATA/'+directory+'" ] && [ ! -L "$DATA/'+directory+'" ] && [ -f "$DATA/'+name+'" ] && [ ! -L "$DATA/'+name+'" ] || return 1\n'
        old_guard+='    printf \'%s  %s\\n\' '+digest+' "$DATA/'+name+'" | sha256sum -c - || return 1\n'
    old_guard+='}\n'
    script=script.replace('replace_index() {',old_guard+'replace_index() {')
    script=script.replace('    baseline "$DATA/index.html"', '    old_assets || { echo \'Existing UI assets changed; refusing update\'; exit 1; }\n    baseline "$DATA/index.html"')
    block='''    cp audio-html5.js "$ASSETS/audio-html5.js"
    chmod 644 "$ASSETS/audio-html5.js"
    cmp audio-html5.js "$ASSETS/audio-html5.js"'''
    replacement='''    for file in bridge.js upload-progress.js mascot.js; do
        cp "$file" "$ASSETS/$file"
        chmod 644 "$ASSETS/$file"
        cmp "$file" "$ASSETS/$file"
    done'''
    if block not in script:raise ValueError('Installer template changed; review required')
    script=script.replace(block,replacement)
    script=script.replace('"$ASSETS/audio-html5.js" > installed.sha256','"$ASSETS/bridge.js" "$ASSETS/upload-progress.js" "$ASSETS/mascot.js" > installed.sha256')
    script=script.replace('    baseline backups/index.html\n    [ -f installed.sha256', '    old_assets || { echo \'Original assets changed; refusing rollback\'; exit 1; }\n    baseline backups/index.html\n    [ -f installed.sha256')
    script=script.replace('HTML5-only Music UI installed. Settings assets, services, SSH and firmware unchanged.','UI performance update installed. Audio/CSS/vendor handlers, services, SSH and mounts unchanged.')
    script=script.replace('Hard-refresh the original homepage. Browser codecs and user-gesture policy still apply.','Hard-refresh. UI work is reduced; no transfer-throughput speedup is claimed.')
    return script.replace('Unreferenced additive audio asset','Unreferenced additive performance assets')


def build(baseline_bundle,output):
    output=Path(output)
    if output.exists() or output.is_symlink():raise ValueError('Refusing existing artifact')
    with tarfile.open(baseline_bundle) as archive:
        member=archive.getmember('index.html')
        if not member.isfile() or member.size>1048576:raise ValueError('Invalid bounded homepage')
        page=archive.extractfile(member).read()
    if hashlib.sha256(page).hexdigest()!=BEFORE:raise ValueError('Exact installed mascot homepage required')
    if b'fieldkit-performance' in page:raise ValueError('Already modified homepage')
    patched=page
    for name in OLD_ASSETS:
        marker=b'<script src="/data/'+name.encode()+b'"></script>'
        if patched.count(marker)!=1:raise ValueError('Unexpected script references')
        patched=patched.replace(marker,b'<script src="/data/fieldkit-performance-r1/'+name.split('/')[-1].encode()+b'"></script>')
    after=hashlib.sha256(patched).hexdigest()
    files={'index.html':patched,'install.sh':installer(after).encode()}
    for name in ('bridge.js','upload-progress.js','mascot.js'):
        data=(ROOT/'device/unified'/name).read_bytes()
        if name=='bridge.js':data=data.replace(b'/data/fieldkit-v05/',b'/data/fieldkit-v06/')
        files[name]=data
    report={'schema':'nimbus-ui-performance/v1','status':'candidate/not installed',
            'before_sha256':BEFORE,'after_sha256':after,'public_redistribution':False,
            'contains_vendor_homepage':True,'firmware_write':False,'old_asset_sha256':OLD_ASSETS,
            'throughput_speedup_claimed':False,
            'files':[{'name':name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())]}
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.baseline_bundle,args.output)
    print('Private local UI package built; not installed. Never publish vendor-based archive.')
