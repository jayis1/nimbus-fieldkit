import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fieldkit import nimbus_fieldkit as nimbus
from fieldkit import wifi_plan

spec = importlib.util.spec_from_file_location('stage', Path(__file__).parents[1] / 'scripts/stage-gamehack.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class GameHackTests(unittest.TestCase):
    def test_roles_and_snapshot_private_filtered(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'pi-last-connection.json').write_text(json.dumps({'reason': 'not connected', 'private_key': 'SECRET', 'task': 'SECRET'}))
            path, digest = nimbus.snapshot(state)
            data = json.loads(path.read_text())
            self.assertIn('SanDisk', data['roles']['main_wifi'])
            self.assertNotIn('SECRET', path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(digest), 64)

    def test_metadata_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'target.json').write_text('{"reason":"secret"}')
            (state / 'pi-last-connection.json').symlink_to(state / 'target.json')
            self.assertEqual(nimbus.filtered_pi_metadata(state), {'available': False})

    def test_wifi_plan_secure_and_distinct(self):
        files = wifi_plan.render('wlan0', 'GameHack-Nimbus', 'test-password-123', 6, 'DK')
        self.assertIn('rsn_pairwise=CCMP', files['hostapd.conf'])
        self.assertIn('wpa=2', files['hostapd.conf'])
        self.assertIn('dhcp-option=3\n', files['dnsmasq.conf'])
        self.assertIn('port=0', files['dnsmasq.conf'])
        self.assertFalse(json.loads(files['plan.json'])['internet_gateway'])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'candidate'
            wifi_plan.write_plan(output, files)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            for path in output.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                wifi_plan.write_plan(output, files)

    def test_wifi_injection_invalid_credentials_and_channels(self):
        for interface, ssid, password, channel, country in [
            ('wlan0\nfoo=bar', 'nimbus', 'password123', 6, 'DK'),
            ('wlan0', 'bad\nssid', 'password123', 6, 'DK'),
            ('wlan0', 'nimbus', 'bad\npassword', 6, 'DK'),
            ('wlan0', 'nimbus', 'short', 6, 'DK'),
            ('wlan0', 'nimbus', 'password123', 99, 'DK'),
            ('wlan0', 'nimbus', 'password123', 6, 'XX\n')]:
            with self.assertRaises(ValueError):
                wifi_plan.render(interface, ssid, password, channel, country)

    def test_stage_idempotent_preserves_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'opt/hackeros'
            folder.mkdir(parents=True)
            original = 'C = [\n' + stage.MENU + ']\nclass Launcher:\n    def execute(self, action):\n        if False:\n            pass\n' + stage.BRANCH
            launcher = folder / 'launcher.py'
            launcher.write_text(original)
            stage.stage(root)
            result = launcher.read_text()
            self.assertIn('nimbus-fieldkit', result)
            self.assertEqual((folder / 'launcher.py.pre-nimbus').read_text(), original)
            stage.stage(root)
            self.assertEqual(launcher.read_text(), result)

    def test_stage_unknown_layout_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'opt/hackeros'
            folder.mkdir(parents=True)
            launcher = folder / 'launcher.py'
            launcher.write_text('# unknown layout\n')
            with self.assertRaises(ValueError):
                stage.stage(root)
            self.assertEqual(launcher.read_text(), '# unknown layout\n')

    def test_phone_hotspot_gateway_candidate(self):
        files = wifi_plan.render('ap0', 'GameHack-Nimbus', 'password123', 6, 'DK', 'wlan0')
        self.assertIn('masquerade', files['gateway.nft'])
        self.assertNotIn('flush ruleset', files['gateway.nft'])
        self.assertIn('dhcp-option=3,192.168.78.1', files['dnsmasq.conf'])
        self.assertIn('dhcp-option=6,192.168.78.1', files['dnsmasq.conf'])
        self.assertTrue(json.loads(files['plan.json'])['internet_gateway'])
        with self.assertRaises(ValueError):
            wifi_plan.render('wlan0', 'GameHack-Nimbus', 'password123', 6, 'DK', 'wlan0')

    def test_stage_upgrade_refuses_unknown_modified_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = root / 'opt/hackeros'; folder.mkdir(parents=True)
            (folder / 'launcher.py').write_text('C = [("SanDisk / main Wi-Fi unit", "nimbus-fieldkit")]\n# menu(self, run)\n')
            module = folder / 'nimbus_fieldkit.py'; module.write_text('# user changes\n')
            with self.assertRaises(ValueError): stage.stage(root, upgrade=True)
            self.assertEqual(module.read_text(), '# user changes\n')

    def test_stage_upgrade_backups_known_module(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = root / 'opt/hackeros'; folder.mkdir(parents=True)
            (folder / 'launcher.py').write_text('C = [("SanDisk / main Wi-Fi unit", "nimbus-fieldkit")]\n# menu(self, run)\n')
            module = folder / 'nimbus_fieldkit.py'; module.write_text('# known previous version\n')
            old = module.read_bytes()
            with patch.object(stage, 'PREVIOUS_MODULE', hashlib.sha256(old).hexdigest()):
                stage.stage(root, upgrade=True)
            self.assertEqual((folder / 'nimbus_fieldkit.py.pre-v02').read_bytes(), old)
            self.assertNotEqual(module.read_bytes(), old)
            self.assertTrue((folder / 'nimbus_tools.py').exists())
