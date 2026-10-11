import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_ui_package', ROOT/'scripts/package-audio-ui.py')
package = importlib.util.module_from_spec(spec); spec.loader.exec_module(package)


class AudioPackageTests(unittest.TestCase):
    def baseline(self, path):
        page = b'<html><script src="/data/fieldkit-v06/bridge.js"></script></html>'
        manifest = {'schema': 'nimbus-unified/v1', 'version': '0.6', 'files': [{'name': 'index.html', 'sha256': hashlib.sha256(page).hexdigest()}]}
        with tarfile.open(path, 'w') as archive:
            for name, data in [('index.html', page), ('MANIFEST.json', json.dumps(manifest).encode())]:
                member = tarfile.TarInfo(name); member.size = len(data); archive.addfile(member, io.BytesIO(data))
        return page

    def test_guarded_install_rollback_and_later_edit_refusal_on_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); baseline = base/'baseline.tar'; before = self.baseline(baseline)
            stage = base/'stage'; stage.mkdir(mode=0o700); output = base/'package.tar'
            report = package.build(baseline, output)
            self.assertFalse(report['public_redistribution'])
            with self.assertRaises(ValueError): package.build(baseline, output)
            with tarfile.open(output) as archive:
                for member in archive:
                    (stage/member.name).write_bytes(archive.extractfile(member).read())
            data = base/'web'; data.mkdir(); (data/'index.html').write_bytes(before)
            script = (stage/'install.sh').read_text().replace('/root/nimbus-audio-html5-r1', str(stage))
            script = script.replace('DATA=/nimbus/data', 'DATA="'+str(data)+'"').replace('[ "$(id -u)" = 0 ]', ':')
            script = script.replace("stat -c '%u:%g:%a'", "stat -c '0:0:%a'")
            path = stage/'fixture-install.sh'; path.write_text(script)
            subprocess.run(['sh', '-n', str(path)], check=True)
            subprocess.run(['sh', str(path), 'install'], capture_output=True, check=True)
            patched = (data/'index.html').read_bytes(); self.assertIn(b'fieldkit-audio-r1', patched)
            (data/'index.html').write_bytes(b'later-user-edit')
            result = subprocess.run(['sh', str(path), 'rollback'], capture_output=True)
            self.assertNotEqual(result.returncode, 0); self.assertEqual((data/'index.html').read_bytes(), b'later-user-edit')
            (data/'index.html').write_bytes(patched)
            subprocess.run(['sh', str(path), 'rollback'], capture_output=True, check=True)
            self.assertEqual((data/'index.html').read_bytes(), before)

    def test_unexpected_live_baseline_refuses_before_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data = base/'web'; data.mkdir(); stage = base/'stage'; stage.mkdir(mode=0o700)
            (data/'index.html').write_text('user homepage')
            script = package.installer('0'*64, '1'*64).replace('/root/nimbus-audio-html5-r1', str(stage)).replace('DATA=/nimbus/data', 'DATA="'+str(data)+'"')
            script = script.replace('[ "$(id -u)" = 0 ]', ':')
            script = script.replace("stat -c '%u:%g:%a'", "stat -c '0:0:%a'")
            (stage/'SHA256SUMS').write_text(hashlib.sha256(b'fixture').hexdigest()+'  fixture\n'); (stage/'fixture').write_bytes(b'fixture')
            path = stage/'install.sh'; path.write_text(script)
            result = subprocess.run(['sh', str(path), 'install'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((stage/'backups').exists()); self.assertFalse((data/'fieldkit-audio-r1').exists())
            self.assertEqual((data/'index.html').read_text(), 'user homepage')
