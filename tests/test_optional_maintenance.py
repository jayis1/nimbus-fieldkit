from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MaintenanceTests(unittest.TestCase):
    def test_maintenance_scripts_have_valid_shell_syntax(self):
        for name in ('nimbus-sd-doctor.sh', 'retire-v04-homepage.sh'):
            subprocess.run(['sh', '-n', str(ROOT / 'device' / name)], check=True)

    def test_retirement_removes_only_legacy_entry_and_preserves_private_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dashboard = root / 'dashboard'
            dashboard.mkdir()
            page = dashboard / 'index.html'
            page.write_text('legacy standalone dashboard')
            settings = root / '.settings'
            settings.write_text('preserve settings')
            snapshot = dashboard / 'state.json'
            snapshot.write_text('preserve publisher snapshot')
            unified = root / 'unified.html'
            unified.write_text('preserve original replacement')
            retired = root / 'retired'
            script = (ROOT / 'device/retire-v04-homepage.sh').read_text()
            script = script.replace('[ "$(id -u)" = 0 ]', ':')
            script = script.replace('/mnt/storage/nimbus-fieldkit-v04/dashboard/index.html', str(page))
            script = script.replace('/root/nimbus-retired-v04-homepage', str(retired))
            path = root / 'retire.sh'
            path.write_text(script)
            subprocess.run(['sh', str(path)], check=True, capture_output=True)
            self.assertFalse(page.exists())
            self.assertEqual((retired / 'index.html').read_text(), 'legacy standalone dashboard')
            self.assertEqual(snapshot.read_text(), 'preserve publisher snapshot')
            self.assertEqual(settings.read_text(), 'preserve settings')
            self.assertEqual(unified.read_text(), 'preserve original replacement')
            self.assertEqual(retired.stat().st_mode & 0o777, 0o700)
            self.assertNotEqual(subprocess.run(['sh', str(path)], capture_output=True).returncode, 0)

    def test_retirement_refuses_symlink_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'original'
            original.write_text('never delete')
            page = root / 'index.html'
            page.symlink_to(original)
            script = (ROOT / 'device/retire-v04-homepage.sh').read_text()
            script = script.replace('[ "$(id -u)" = 0 ]', ':')
            script = script.replace('/mnt/storage/nimbus-fieldkit-v04/dashboard/index.html', str(page))
            script = script.replace('/root/nimbus-retired-v04-homepage', str(root / 'retired'))
            path = root / 'retire.sh'
            path.write_text(script)
            self.assertNotEqual(subprocess.run(['sh', str(path)], capture_output=True).returncode, 0)
            self.assertEqual(original.read_text(), 'never delete')
