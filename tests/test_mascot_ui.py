import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mascot_package',ROOT/'scripts/package-mascot-ui.py')
mascot=importlib.util.module_from_spec(spec);spec.loader.exec_module(mascot)


class MascotUITests(unittest.TestCase):
    def test_installer_syntax_scope_and_no_mouse_telemetry(self):
        subprocess.run(['sh','-n'],input=mascot.installer('0'*64).encode(),check=True)
        source=(ROOT/'device/unified/mascot.js').read_text()
        for forbidden in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'WebSocket', 'setInterval'):
            self.assertNotIn(forbidden,source)
        self.assertIn('cancelAnimationFrame',source)
        self.assertIn('removeEventListener',source)
        self.assertIn('prefers-reduced-motion',source)

    def test_guarded_install_and_rollback_keeps_later_homepage(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);stage=base/'stage';stage.mkdir(mode=0o700)
            data=base/'web';data.mkdir()
            before=b'fixture old homepage';after=b'fixture new homepage'
            (data/'index.html').write_bytes(before)
            script=mascot.installer(hashlib.sha256(after).hexdigest()).replace(mascot.BEFORE,hashlib.sha256(before).hexdigest())
            (stage/'install.sh').write_text(script);(stage/'index.html').write_bytes(after)
            (stage/'mascot.js').write_bytes((ROOT/'device/unified/mascot.js').read_bytes())
            (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('install.sh','index.html','mascot.js')))
            script=script.replace('/root/nimbus-mascot-r1',str(stage)).replace('DATA=/nimbus/data','DATA="'+str(data)+'"')
            script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
            path=stage/'fixture.sh';path.write_text(script)
            subprocess.run(['sh',str(path),'install'],capture_output=True,check=True)
            self.assertEqual((data/'index.html').read_bytes(),after)
            (data/'index.html').write_bytes(b'later changes')
            self.assertNotEqual(subprocess.run(['sh',str(path),'rollback'],capture_output=True).returncode,0)
            self.assertEqual((data/'index.html').read_bytes(),b'later changes')
            (data/'index.html').write_bytes(after)
            subprocess.run(['sh',str(path),'rollback'],capture_output=True,check=True)
            self.assertEqual((data/'index.html').read_bytes(),before)

    def test_local_bundle_adds_only_one_reference_and_refuses_overwrite(self):
        baseline=ROOT/'build/nimbus-upload-progress-ui-r1.tar'
        if not baseline.exists():self.skipTest('Private baseline UI bundle unavailable')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mascot.tar';report=mascot.build(baseline,path)
            with tarfile.open(baseline) as original, tarfile.open(path) as updated:
                page=updated.extractfile('index.html').read()
                self.assertEqual(page.replace(b'\n<script src="/data/fieldkit-mascot-r1/mascot.js"></script>',b''),original.extractfile('index.html').read())
            self.assertFalse(report['public_redistribution'])
            with self.assertRaises(ValueError):mascot.build(baseline,path)
