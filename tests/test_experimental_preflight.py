from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExperimentalPreflightTests(unittest.TestCase):
    def fixture(self, base, exported=False, wrong_layout=False):
        proc = base / 'proc'; proc.mkdir()
        (proc / 'modules').write_text('g_file_storage 1 0 - Live 0\n' if exported else '')
        (proc / 'mounts').write_text('/dev/mmcblk0p2 / ext3 rw 0 0\n')
        sys = base / 'sys'; sys.mkdir()
        dev = base / 'dev'; dev.mkdir()
        partitions = [('mmcblk0p1', 30720, 8192), ('mmcblk0p2', 38912, 524288),
                      ('mmcblk0p3', 563200, 409600), ('mmcblk0p4', 972800, 121169920)]
        for name, start, size in partitions:
            (dev / name).write_text('fixture block node')
            part = sys / 'class/block' / name; part.mkdir(parents=True)
            (part / 'start').write_text(str(start + (1 if wrong_layout and name == 'mmcblk0p2' else 0)))
            (part / 'size').write_text(str(size))
        (sys / 'class/block/mmcblk0').mkdir()
        (sys / 'class/block/mmcblk0/size').write_text('122142720')
        (sys / 'class/power_supply/mc13892_charger').mkdir(parents=True)
        (sys / 'class/power_supply/mc13892_charger/online').write_text('0')
        script = (ROOT / 'device/experimental-flash-preflight.sh').read_text()
        script = script.replace('[ "$(id -u)" = 0 ]', ':')
        script = script.replace('uname -m', "printf armv7l").replace('uname -r', "printf fixture-kernel")
        script = script.replace('[ ! -b ', '[ ! -f ')
        script = script.replace('/proc/', str(proc) + '/').replace('/sys/', str(sys) + '/').replace('/dev/', str(dev) + '/')
        path = base / 'preflight.sh'; path.write_text(script)
        return path

    def test_readonly_inventory_does_not_authorize_flash(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); path = self.fixture(base)
            before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result = subprocess.run(['sh', str(path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('NOT FLASH AUTHORIZATION', result.stdout)
            self.assertIn('External power online: 0', result.stdout)
            after = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_usb_export_and_wrong_geometry_fail_closed(self):
        for exported, wrong_layout in [(True, False), (False, True)]:
            with self.subTest(exported=exported, wrong_layout=wrong_layout), tempfile.TemporaryDirectory() as folder:
                path = self.fixture(Path(folder), exported, wrong_layout)
                result = subprocess.run(['sh', str(path)], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('FAIL:', result.stdout)

    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(ROOT / 'device/experimental-flash-preflight.sh')], check=True)
