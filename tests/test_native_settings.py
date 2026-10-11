import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SCRIPT = Path(__file__).parents[1] / 'device/nimbus-settings.sh'


class NativeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.env = dict(os.environ, NIMBUS_STATE_DIR=str(self.state))

    def tearDown(self):
        self.temp.cleanup()

    def run_settings(self, *arguments, check=True):
        result = subprocess.run(['sh', str(SCRIPT), *arguments], env=self.env,
                                capture_output=True, text=True, timeout=10)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_syntax_and_all_default_off_no_writes(self):
        subprocess.run(['sh', '-n', str(SCRIPT)], check=True)
        result = self.run_settings('show')
        self.assertEqual(result.stdout.count(' OFF '), 10)
        self.assertNotIn('monitor_mode', result.stdout)
        self.assertFalse(self.state.exists())

    def test_persistent_on_off_and_run_guard(self):
        self.assertNotEqual(self.run_settings('run', 'network_health', check=False).returncode, 0)
        self.run_settings('set', 'network_health', 'on')
        self.assertEqual((self.state / 'network_health').read_text(), 'on\n')
        self.assertIn('network_health      ON', self.run_settings('show').stdout)
        self.assertIn('Local network health', self.run_settings('run', 'network_health').stdout)
        self.run_settings('set', 'network_health', 'off')
        self.assertNotEqual(self.run_settings('run', 'network_health', check=False).returncode, 0)

    def test_unknown_values_and_monitor_refused(self):
        for feature, value in [('monitor_mode', 'on'), ('../escape', 'on'), ('network_health', 'yes')]:
            self.assertNotEqual(self.run_settings('set', feature, value, check=False).returncode, 0)
        self.assertFalse(self.state.exists())

    def test_menu_accepts_telnet_carriage_return(self):
        result=subprocess.run(['sh',str(SCRIPT),'menu'],input='q\r\n',env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0)
        self.assertNotIn('Select 1–10 or q',result.stdout)

    def test_unavailable_pi_jobs_refused(self):
        result = self.run_settings('set', 'pi_jobs', 'on', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no verified secure pairing', result.stderr)
        self.run_settings('set', 'pi_jobs', 'off')

    def test_watchdog_dependency_and_cascade_off(self):
        self.assertNotEqual(self.run_settings('set', 'watchdog', 'on', check=False).returncode, 0)
        self.run_settings('set', 'network_health', 'on')
        self.run_settings('set', 'watchdog', 'on')
        self.run_settings('set', 'network_health', 'off')
        self.assertEqual((self.state / 'watchdog').read_text(), 'off\n')

    def test_watchdog_stops_when_toggled_off(self):
        self.run_settings('set', 'network_health', 'on')
        self.run_settings('set', 'watchdog', 'on')
        process = subprocess.Popen(['sh', str(SCRIPT), 'run', 'watchdog', '120', '10'],
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Reading a live first report synchronizes startup without polling.
            first = process.stdout.readline()
            self.assertIsNotNone(first)
            self.run_settings('set', 'watchdog', 'off')
            output, errors = process.communicate(timeout=4)
            self.assertEqual(process.returncode, 0, errors)
            self.assertIn('Watchdog stopped', output)
        finally:
            if process.poll() is None:
                process.terminate(); process.communicate(timeout=3)

    def test_bad_bounds(self):
        self.run_settings('set', 'network_health', 'on')
        self.run_settings('set', 'watchdog', 'on')
        for count, interval in [('0', '10'), ('121', '10'), ('1', '0'), ('999999999999', '10'), ('x', '10')]:
            self.assertNotEqual(self.run_settings('run', 'watchdog', count, interval, check=False).returncode, 0)

    def test_malformed_and_symlink_state_fail_closed(self):
        self.state.mkdir()
        (self.state / 'network_health').write_text('on; touch SHOULD_NOT_EXIST\n')
        self.assertNotEqual(self.run_settings('run', 'network_health', check=False).returncode, 0)
        (self.state / 'watchdog').symlink_to(self.root)
        self.assertNotEqual(self.run_settings('set', 'watchdog', 'off', check=False).returncode, 0)

    def test_copy_requires_enabled_and_never_overwrites(self):
        source = self.root / 'report.txt'; source.write_text('reviewed data\n')
        destination = self.root / 'destination'; destination.mkdir()
        self.assertNotEqual(self.run_settings('run', 'file_sync', str(source), str(destination), check=False).returncode, 0)
        self.run_settings('set', 'file_sync', 'on')
        result = self.run_settings('run', 'file_sync', str(source), str(destination))
        self.assertIn('Verified copy:', result.stdout)
        self.assertEqual((destination / source.name).read_bytes(), source.read_bytes())
        self.assertNotEqual(self.run_settings('run', 'file_sync', str(source), str(destination), check=False).returncode, 0)
        self.assertEqual((destination / source.name).read_bytes(), source.read_bytes())

    def test_symlink_source_refused(self):
        source = self.root / 'source.txt'; source.write_text('private')
        link = self.root / 'link.txt'; link.symlink_to(source)
        self.run_settings('set', 'file_sync', 'on')
        self.assertNotEqual(self.run_settings('run', 'file_sync', str(link), str(self.root), check=False).returncode, 0)
