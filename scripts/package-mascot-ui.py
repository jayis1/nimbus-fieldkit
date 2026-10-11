#!/usr/bin/env python3
"""LOCAL-ONLY guarded additive mascot/homepage patch. No service or mount changes."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BEFORE='cef815fab959980289889a2fb99a0bb9619617d1052bdbd860850699f0491410'


def installer(after):
    spec=importlib.util.spec_from_file_location('mascot_policy',ROOT/'scripts/package-audio-ui.py')
    policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    script=policy.installer(BEFORE,after)
    script=script.replace('nimbus-audio-html5-r1','nimbus-mascot-r1').replace('fieldkit-audio-r1','fieldkit-mascot-r1')
    script=script.replace('audio-html5.js','mascot.js').replace('nimbus-audio-new','nimbus-mascot-new')
    script=script.replace('HTML5-only Music UI installed. Settings assets, services, SSH and firmware unchanged.','Nib desktop buddy installed. Music/uploads/CSS/Settings/services unchanged.')
    return script.replace('Hard-refresh the original homepage. Browser codecs and user-gesture policy still apply.','Hard-refresh. Show / hide buddy toggles the decorative companion; no AI/network service.')


def build(baseline_bundle,output):
    output=Path(output)
    if output.exists() or output.is_symlink():raise ValueError('Refusing existing artifact')
    with tarfile.open(baseline_bundle) as archive:
        member=archive.getmember('index.html')
        if not member.isfile() or member.size>1048576:raise ValueError('Invalid bounded homepage')
        page=archive.extractfile(member).read()
    if hashlib.sha256(page).hexdigest()!=BEFORE:raise ValueError('Exact installed upload-progress homepage required')
    marker=b'<script src="/data/fieldkit-v06/bridge.js"></script>'
    if page.count(marker)!=1 or b'mascot.js' in page:raise ValueError('Unexpected homepage')
    patched=page.replace(marker,marker+b'\n<script src="/data/fieldkit-mascot-r1/mascot.js"></script>')
    files={'index.html':patched,'mascot.js':(ROOT/'device/unified/mascot.js').read_bytes(),
           'install.sh':installer(hashlib.sha256(patched).hexdigest()).encode()}
    report={'schema':'nimbus-mascot-ui/v1','status':'candidate/not installed','before_sha256':BEFORE,
            'after_sha256':hashlib.sha256(patched).hexdigest(),'public_redistribution':False,
            'network_or_ai_service':False,'scope':'additive first-party script and one homepage reference',
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
    args=parser.parse_args();print(json.dumps(build(args.baseline_bundle,args.output),indent=2))
