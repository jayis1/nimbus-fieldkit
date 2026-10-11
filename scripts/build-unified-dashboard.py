#!/usr/bin/env python3
"""Build a reviewed stock-page overlay; never connect to or install on a drive."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
STAMP = 1767225600
spec = importlib.util.spec_from_file_location('native_package', ROOT / 'scripts/package-native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def build(stock_archive, output, previous_bundle=None):
    with tarfile.open(stock_archive) as archive:
        member = archive.getmember('data/index.html')
        if not member.isfile() or member.size > 1024 * 1024:
            raise ValueError('Expected regular stock homepage under 1 MiB')
        original = archive.extractfile(member).read()
    stock = original.decode('utf-8-sig')
    if 'btnNimbusFieldKit' in stock:
        raise ValueError('Input already contains an integration')
    for marker in ('</head>', '</body>', '<ul class="navi02">', '<div id="content" class="topMarginSpace">'):
        if stock.count(marker) != 1:
            raise ValueError('Unknown stock homepage structure: ' + marker)
    digest = hashlib.sha256(original).hexdigest()
    stock_digest = digest
    asset_version = 'v05'
    if previous_bundle:
        with tarfile.open(previous_bundle) as archive:
            previous = json.load(archive.extractfile('MANIFEST.json'))
            prior_page = archive.extractfile('index.html').read()
        prior_hash = hashlib.sha256(prior_page).hexdigest()
        listed = next((entry for entry in previous.get('files', []) if entry['name'] == 'index.html'), {})
        if previous.get('schema') != 'nimbus-unified/v1' or previous.get('version') != '0.5' or previous.get('expected_stock_index_sha256') != stock_digest or listed.get('sha256') != prior_hash:
            raise ValueError('Previous bundle is not a matching verified v0.5 lineage')
        digest = prior_hash
        asset_version = 'v06'
    stock = stock.replace('<title>SanDisk Wireless Media Drive</title>', '<title>SanDisk / Nimbus FieldKit</title>')
    stock = stock.replace('class="logo" title="Sandisk">Sandisk</a>', 'class="logo" title="SanDisk FieldKit">SanDisk / FieldKit</a>')
    stock = stock.replace('</head>', '<link rel="stylesheet" href="/data/fieldkit-v05/stock-dark.css" />\n</head>')
    stock = stock.replace('<ul class="navi02">', '<ul class="navi02">\n<li><a href="#fieldkit" id="btnNimbusFieldKit">FieldKit / tools</a></li>')
    stock = stock.replace('<div id="content" class="topMarginSpace">', '<div id="content" class="topMarginSpace">\n<div id="nimbus-unified-host"></div>')
    stock = stock.replace('</body>', '<script src="/data/fieldkit-v05/audio-html5.js"></script>\n<script src="/data/fieldkit-v05/upload-progress.js"></script>\n<script src="/data/fieldkit-v05/bridge.js"></script>\n</body>')
    stock = stock.replace('/data/fieldkit-v05/', f'/data/fieldkit-{asset_version}/')
    page = (ROOT / 'fieldkit/index.html').read_text()
    body = page.split('<body>', 1)[1].split('</body>', 1)[0]
    body = re.sub(r'<aside class="sidebar">.*?</aside>', '<a id="stock-link" hidden></a>', body, count=1, flags=re.S)
    tabs = '<nav class="unified-tabs" aria-label="FieldKit tools">' + ''.join(
        f'<button class="button nav-item" data-view="{view}">{label}</button>' for view, label in
        [('overview', 'Overview'), ('features', 'Switches'), ('network', 'Network'), ('vault', 'Vault & sync'), ('toolbox', 'Docs & Pi'), ('security', 'Security')]) + '</nav>'
    body = tabs + body
    css = (ROOT / 'fieldkit/dashboard.css').read_text().replace(':root[data-theme=light]', ':host([data-theme=light])').replace(':root', ':host')
    css += '\n:host{display:block;font:14px/1.5 system-ui;color:var(--text);background:var(--bg)}.workspace{margin-left:0!important}.unified-tabs{display:flex;flex-wrap:wrap;gap:8px;padding:18px 24px;border-bottom:1px solid var(--line)}.unified-tabs .nav-item{width:auto;margin:0;padding:9px 12px}.topbar{padding:16px 24px}main{padding:24px}#stock-link{display:none!important}\n'
    script = (ROOT / 'fieldkit/dashboard.js').read_text()
    script = re.sub(r'const nativeMode = [^\n]+', 'const nativeMode = true;', script, count=1)
    script = script.replace('/mnt/storage/nimbus-fieldkit-v04', '/mnt/storage/nimbus-unified-v05/native')
    script = script.replace('`state.json?v=${Date.now()}`', '`/storage/nimbus-unified-v05/native/dashboard/state.json?v=${Date.now()}`')
    script = script.replace("'../vault/'", "'/storage/nimbus-unified-v05/native/vault/'")
    script = script.replace("'../docs/'", "'/storage/nimbus-unified-v05/native/docs/'")
    script = script.replace("const docs = [", "const docs = ['UNIFIED-DASHBOARD.md', ")
    # Same controller, but all toolkit selectors are isolated from the stock DOM.
    facade = """const surface=window.NIMBUS_UNIFIED_SURFACE;
const real=window.document;
const facade={getElementById:id=>surface.getElementById(id),querySelectorAll:s=>surface.querySelectorAll(s),createElement:t=>real.createElement(t),body:surface.host,documentElement:real.documentElement,execCommand:c=>real.execCommand(c),get hidden(){return real.hidden||!real.body.classList.contains('nimbus-toolkit-open');}};
"""
    script = "(() => {\n" + facade + "((document) => {\n" + script + "\n})(facade);\n})();\n"
    prefix = f'fieldkit-{asset_version}/'
    bridge = (ROOT / 'device/unified/bridge.js').read_text().replace('/data/fieldkit-v05/', f'/data/fieldkit-{asset_version}/')
    files = {'index.html': stock.encode(), prefix+'stock-dark.css': (ROOT / 'device/unified/stock-dark.css').read_bytes(),
             prefix+'bridge.js': bridge.encode(), prefix+'audio-html5.js': (ROOT / 'device/unified/audio-html5.js').read_bytes(), prefix+'upload-progress.js': (ROOT / 'device/unified/upload-progress.js').read_bytes(), prefix+'SECURITY-PLAN.md': (ROOT / 'docs/SECURITY-PLAN.md').read_bytes(),
             prefix+'toolkit.html': body.encode(), prefix+'toolkit.css': css.encode(), prefix+'toolkit.js': script.encode()}
    files.update({'native/' + name: (ROOT / source).read_bytes() for name, source in native.SOURCES.items()})
    files['native/docs/UNIFIED-DASHBOARD.md'] = (ROOT / 'docs/UNIFIED-DASHBOARD.md').read_bytes()
    if previous_bundle:
        # UI-only upgrade: no new runtime, setting migration or vault duplication.
        files = {name: content for name, content in files.items() if not name.startswith('native/')}
    files['install.sh'] = installer(digest, upgrade=bool(previous_bundle)).encode()
    manifest = {'schema': 'nimbus-unified/v1', 'version': '0.6' if previous_bundle else '0.5', 'status': 'candidate/not installed',
                'expected_stock_index_sha256': stock_digest, 'expected_current_index_sha256': digest,
                'runtime_install': '/mnt/storage/nimbus-unified-v05/native',
                'files': [{'name': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes':len(data)} for name, data in sorted(files.items())]}
    files['MANIFEST.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(files.items())).encode()
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(data);info.mtime=STAMP;info.mode=0o644;info.uid=info.gid=0
            archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def installer(digest, upgrade=False):
    script = '''#!/bin/sh
# Explicit root-only homepage overlay. No firmware, service or radio writes.
set -eu
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd)
[ "$(id -u)" = 0 ] || { echo 'Run only in the authorized root session'; exit 1; }
[ "$BASE" = /mnt/storage/nimbus-unified-v05 ] || { echo 'Use the documented new staging directory'; exit 1; }
cd "$BASE"
sha256sum -c SHA256SUMS || exit 1
case "${1:-}" in
 install)
  [ ! -L /nimbus/data ] && [ ! -L /nimbus/data/index.html ] || exit 1
  printf '%s  %s\\n' 'EXPECTED_HASH' /nimbus/data/index.html | sha256sum -c - || exit 1
  [ ! -e /nimbus/data/fieldkit-v05 ] && [ ! -L /nimbus/data/fieldkit-v05 ] || { echo 'Existing integration; refusing overwrite'; exit 1; }
  [ ! -e "$BASE/original-index.html" ] && [ ! -L "$BASE/original-index.html" ] || exit 1
  cp -p /nimbus/data/index.html "$BASE/original-index.html"
  printf '%s  %s\\n' 'EXPECTED_HASH' "$BASE/original-index.html" | sha256sum -c - || exit 1
  # Persistent flags imported once; vendor credentials/settings are not copied.
  sh native/nimbus-dashboard.sh import-settings /mnt/storage/nimbus-fieldkit-v03
  sh native/nimbus-dashboard.sh snapshot
  mkdir /nimbus/data/fieldkit-v05
   for file in stock-dark.css bridge.js audio-html5.js upload-progress.js toolkit.html toolkit.css toolkit.js SECURITY-PLAN.md; do
   cp "fieldkit-v05/$file" "/nimbus/data/fieldkit-v05/$file"
   chmod 644 "/nimbus/data/fieldkit-v05/$file"
   filehash=$(sha256sum "fieldkit-v05/$file" | awk '{print $1}')
   printf '%s  %s\\n' "$filehash" "/nimbus/data/fieldkit-v05/$file" | sha256sum -c - || exit 1
  done
  [ ! -e /nimbus/data/.nimbus-index-v05 ] && [ ! -L /nimbus/data/.nimbus-index-v05 ] || exit 1
  cp index.html /nimbus/data/.nimbus-index-v05
  chmod 644 /nimbus/data/.nimbus-index-v05
  filehash=$(sha256sum index.html | awk '{print $1}')
  printf '%s  %s\\n' "$filehash" /nimbus/data/.nimbus-index-v05 | sha256sum -c - || exit 1
  sync
  mv /nimbus/data/.nimbus-index-v05 /nimbus/data/index.html
  echo 'Unified homepage installed. No daemon or Wi-Fi changes. Reload / in the browser.'
  ;;
 rollback)
  [ -f "$BASE/original-index.html" ] && [ ! -L "$BASE/original-index.html" ] || exit 1
  printf '%s  %s\\n' 'EXPECTED_HASH' "$BASE/original-index.html" | sha256sum -c - || exit 1
  newhash=$(sha256sum index.html | awk '{print $1}')
  printf '%s  %s\\n' "$newhash" /nimbus/data/index.html | sha256sum -c - || exit 1
  [ ! -e /nimbus/data/.nimbus-index-rollback ] && [ ! -L /nimbus/data/.nimbus-index-rollback ] || exit 1
  cp "$BASE/original-index.html" /nimbus/data/.nimbus-index-rollback
  chmod 744 /nimbus/data/.nimbus-index-rollback
  mv /nimbus/data/.nimbus-index-rollback /nimbus/data/index.html
  echo 'Stock homepage restored. Additive assets and native settings retained.'
  ;;
 *) echo 'Usage: sh install.sh install|rollback'; exit 1;;
esac
'''.replace('EXPECTED_HASH', digest)
    if upgrade:
        script = script.replace('nimbus-unified-v05', 'nimbus-unified-v06').replace('fieldkit-v05', 'fieldkit-v06').replace('.nimbus-index-v05', '.nimbus-index-v06')
        script = script.replace('  sh native/nimbus-dashboard.sh import-settings /mnt/storage/nimbus-fieldkit-v03\n  sh native/nimbus-dashboard.sh snapshot',
                                '  [ -f /mnt/storage/nimbus-unified-v05/native/nimbus-dashboard.sh ] || exit 1\n  echo "UI-only upgrade; existing v0.5 settings, vault and publisher are unchanged."')
        script = script.replace('chmod 744 /nimbus/data/.nimbus-index-rollback', 'chmod 644 /nimbus/data/.nimbus-index-rollback')
        script = script.replace('Stock homepage restored.', 'Previous v0.5 homepage restored.')
    return script


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-web', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'build/nimbus-unified-v05.tar')
    parser.add_argument('--previous-bundle', type=Path, help='Verified shipped v0.5 archive; build a UI-only v0.6 upgrade')
    args=parser.parse_args()
    if args.previous_bundle and args.output.resolve() == args.previous_bundle.resolve():
        parser.error('Refusing to overwrite the previous bundle')
    print('Candidate SHA-256:', build(args.stock_web, args.output, args.previous_bundle))
