import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flash_warning', ROOT/'scripts/package-flash-warning-fix.py')
fix = importlib.util.module_from_spec(spec); spec.loader.exec_module(fix)
STOCK = ROOT/'numbus-backup/stock-web.tar'


class WarningFixTests(unittest.TestCase):
    def test_unknown_controller_refused_and_installer_syntax(self):
        with self.assertRaises(ValueError): fix.patch_controller(b'user modified controller')
        subprocess.run(['sh', '-n'], input=fix.installer('0'*64).encode(), check=True)

    @unittest.skipUnless(STOCK.exists(), 'Private stock fixture unavailable')
    def test_exact_patch_install_and_guarded_rollback_on_fixture(self):
        with tarfile.open(STOCK) as archive: original = archive.extractfile('data/js/t4u.controller.js').read()
        patched = fix.patch_controller(original)
        self.assertNotIn(b'FlashDetect', patched)
        self.assertNotIn(b'Your browser needs Flash', patched)
        self.assertEqual(patched.count(b'this.bind();'), original.count(b'this.bind();'))
        self.assertTrue(original.endswith(patched[patched.index(b'\t\t\tthis.bind();'):]))
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); stage = base/'stage'; stage.mkdir(mode=0o700)
            target = base/'controller.js'; target.write_bytes(original)
            package = base/'package.tar'; report = fix.build(STOCK, package)
            with tarfile.open(package) as archive:
                for member in archive: (stage/member.name).write_bytes(archive.extractfile(member).read())
            script = (stage/'install.sh').read_text().replace('/root/nimbus-flash-warning-r1', str(stage))
            script = script.replace('TARGET=/nimbus/data/js/t4u.controller.js', 'TARGET="'+str(target)+'"')
            script = script.replace('[ "$(id -u)" = 0 ]', ':').replace("stat -c '%u:%g:%a'", "stat -c '0:0:%a'")
            path = stage/'fixture.sh'; path.write_text(script)
            subprocess.run(['sh', str(path), 'install'], capture_output=True, check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), report['after_sha256'])
            target.write_bytes(b'later user edit')
            self.assertNotEqual(subprocess.run(['sh', str(path), 'rollback'], capture_output=True).returncode, 0)
            self.assertEqual(target.read_bytes(), b'later user edit')
            target.write_bytes(patched)
            subprocess.run(['sh', str(path), 'rollback'], capture_output=True, check=True)
            self.assertEqual(target.read_bytes(), original)
