from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SDDoctorTests(unittest.TestCase):
    def run_fixture(self, main='ro', ftp='ro', exported=False, mounted=True,
                    missing_ro=False, args=()):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc = root / 'proc'
            proc.mkdir()
            mounts = ''
            if mounted:
                mounts = (
                    f'/dev/mmcblk1p1 /mnt/sdcard texfat {main},relatime 0 0\n'
                    f'/dev/mmcblk1p1 /var/ftp/sdcard texfat {ftp},relatime 0 0\n'
                )
            (proc / 'mounts').write_text(mounts)
            (proc / 'modules').write_text('g_file_storage 1 0 - Live 0\n' if exported else '')
            (proc / 'partitions').write_text('179 9 124000000 mmcblk1p1\n')
            block = root / 'sys/class/block/mmcblk1p1'
            block.mkdir(parents=True)
            (block / 'size').write_text('248000000\n')
            if not missing_ro:
                (block / 'ro').write_text('0\n')
            script = (ROOT / 'device/nimbus-sd-doctor.sh').read_text()
            script = script.replace('/proc/', str(proc) + '/')
            script = script.replace('/sys/class/block/', str(root / 'sys/class/block') + '/')
            # Never inspect host kernel logs or storage in these fixtures.
            script = script.replace('dmesg |', "printf '%s\\n' 'fixture mmc observation' |")
            script = script.replace('df -k /mnt/sdcard', "printf '%s\\n' 'fixture capacity'")
            path = root / 'doctor.sh'
            path.write_text(script)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = subprocess.run(['sh', str(path), *args], capture_output=True, text=True)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
            return result

    def test_filesystem_ro_despite_writable_block(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0)
        self.assertIn('mount=/mnt/sdcard filesystem=texfat options=ro,', result.stdout)
        self.assertIn('ro=0', result.stdout)
        self.assertIn('does not mean the filesystem is writable', result.stdout)

    def test_main_rw_and_ftp_ro_are_reported_separately(self):
        result = self.run_fixture(main='rw')
        self.assertIn('mount=/mnt/sdcard filesystem=texfat options=rw,', result.stdout)
        self.assertIn('mount=/var/ftp/sdcard filesystem=texfat options=ro,', result.stdout)

    def test_export_active_with_absent_local_mount(self):
        result = self.run_fixture(exported=True, mounted=False)
        self.assertIn('USB export active; do not mount or write local media', result.stdout)
        self.assertIn('SD mount absent', result.stdout)
        self.assertNotIn('fixture capacity', result.stdout)

    def test_missing_block_flag_is_unknown(self):
        self.assertIn('ro=unknown', self.run_fixture(missing_ro=True).stdout)

    def test_action_argument_refused_before_inventory(self):
        result = self.run_fixture(args=('--repair',))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_shell_syntax(self):
        subprocess.run(['sh', '-n', str(ROOT / 'device/nimbus-sd-doctor.sh')], check=True)
