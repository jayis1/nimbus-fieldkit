#!/usr/bin/env python3
"""Package the first-party root restoration trial; never accesses the device."""
import hashlib
import io
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def build(output):
    output=Path(output)
    if output.exists() or output.is_symlink():raise ValueError('Refusing existing artifact')
    files={'trial.sh':(ROOT/'device/root-restoration-trial.sh').read_bytes(),
           'identity.sh':(ROOT/'device/handover-identity-preflight.sh').read_bytes()}
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    with output.open('xb') as stream:
        output.chmod(0o600)
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for name,data in sorted(files.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;member.mtime=1767225600
                archive.addfile(member,io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(build(parser.parse_args().output))
