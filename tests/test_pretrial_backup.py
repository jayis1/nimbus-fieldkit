import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pretrial_backup', ROOT / 'scripts/backup-pretrial.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def frame(name, data):
    return ('NIMBUS-BEGIN ' + name + ' ' + str(len(data)) + '\n').encode() + data + \
        hashlib.sha256(data).hexdigest().encode() + b'  -\n' + ('NIMBUS-END ' + name + '\n').encode()


class PretrialBackupTests(unittest.TestCase):
    def test_binary_frame_verified_and_private(self):
        data = bytes(range(256)) * 8
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            records = backup.receive(io.BytesIO(frame('rootfs.bin', data)), base, [('rootfs.bin', len(data))])
            self.assertTrue((base / 'rootfs.bin').read_bytes() == data)
            self.assertEqual((base / 'rootfs.bin').stat().st_mode & 0o777, 0o600)
            self.assertEqual(records[0]['sha256'], hashlib.sha256(data).hexdigest())
            self.assertFalse((base / 'rootfs.bin.partial').exists())

    def test_bad_frames_truncation_and_hash_do_not_bless_backups(self):
        data = b'private fixture'
        good = frame('rootfs.bin', data)
        cases = [b'NIMBUS-BEGIN ../escape 1\nx', good[:20], good.replace(data, b'changedfixture!'),
                 good.replace(hashlib.sha256(data).hexdigest().encode(), b'0' * 64)]
        for payload in cases:
            with self.subTest(payload_bytes=len(payload)), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                with self.assertRaises(ValueError):
                    backup.receive(io.BytesIO(payload), base, [('rootfs.bin', len(data))])
                self.assertFalse((base / 'rootfs.bin').exists())

    def test_existing_destination_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); (base / 'rootfs.bin').write_bytes(b'previous')
            with self.assertRaises(ValueError):
                backup.receive(io.BytesIO(frame('rootfs.bin', b'new')), base, [('rootfs.bin', 3)])
            self.assertEqual((base / 'rootfs.bin').read_bytes(), b'previous')

    def test_stdout_mirror_hashes_exact_same_bytes(self):
        # Exercise the Linux fd-mirror protocol on a harmless fixture, not a device.
        result = subprocess.run(['sh', '-c', '(exec 3>&1; printf "fixture data" | tee /proc/self/fd/3 | sha256sum)'],
                                capture_output=True, check=True)
        self.assertEqual(result.stdout, b'fixture data' + hashlib.sha256(b'fixture data').hexdigest().encode() + b'  -\n')

    def test_remote_shell_syntax_and_no_public_staging(self):
        subprocess.run(['sh', '-n'], input=backup.REMOTE.encode(), check=True)
        self.assertNotIn('/mnt/storage', backup.REMOTE)
        self.assertNotIn('fw_setenv', backup.REMOTE)
        self.assertNotIn('mkfs', backup.REMOTE)
        with self.assertRaises(ValueError):
            backup.prepare_output(ROOT / 'build/unsafe-backup')

    def test_complete_remote_protocol_on_small_readonly_fixtures(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            dev = base / 'dev'; dev.mkdir()
            sys = base / 'sys'; sys.mkdir()
            proc = base / 'proc'; proc.mkdir(); (proc / 'modules').write_text('')
            for name, start, size in [('mmcblk0p1', 30720, 8192), ('mmcblk0p2', 38912, 524288),
                                      ('mmcblk0p3', 563200, 409600), ('mmcblk0p4', 972800, 121169920)]:
                (dev / name).write_bytes(b'x' * 16)
                part = sys / 'class/block' / name; part.mkdir(parents=True)
                (part / 'start').write_text(str(start)); (part / 'size').write_text(str(size))
            (dev / 'mmcblk0').write_bytes(b'b' * 16)
            (sys / 'class/block/mmcblk0').mkdir(); (sys / 'class/block/mmcblk0/size').write_text('122142720')
            nvs = base / 'nvs'; nvs.write_bytes(b'n' * 912)
            nimbus = base / 'nimbus'; (nimbus / 'data').mkdir(parents=True)
            (nimbus / 'data/index.html').write_text('fixture page')
            remote = backup.REMOTE.replace('[ "$(id -u)" = 0 ]', ':').replace('[ -b ', '[ -f ')
            for old in ['boot-area.bin 15728640 /dev/mmcblk0 15', 'settings.bin 4194304 /dev/mmcblk0p1 4',
                        'rootfs.bin 268435456 /dev/mmcblk0p2 256', 'fwpool.bin 209715200 /dev/mmcblk0p3 200']:
                fields = old.split(); fields[1] = '16'; fields[3] = '1'
                remote = remote.replace(old, ' '.join(fields))
            remote = remote.replace('bs=1048576', 'bs=16').replace('/dev/', str(dev) + '/')
            remote = remote.replace('/sys/', str(sys) + '/').replace('/proc/modules', str(proc / 'modules'))
            remote = remote.replace('/lib/firmware/ti-connectivity/wl1271-nvs.bin', str(nvs)).replace('-C /nimbus', '-C ' + str(nimbus))
            output = base / 'output'; output.mkdir(mode=0o700)
            expected = [(name, 16 if name.endswith('.bin') and name != 'wl1271-nvs.bin' else size) for name, size in backup.FILES]
            with (base / 'fixture.log').open('wb') as log, subprocess.Popen(['sh'], stdin=subprocess.PIPE,
                                                                          stdout=subprocess.PIPE, stderr=log) as process:
                process.stdin.write(remote.encode()); process.stdin.close()
                records = backup.receive(process.stdout, output, expected)
                process.stdout.close()
                self.assertEqual(process.wait(timeout=10), 0)
            self.assertEqual(len(records), 7)
            self.assertEqual((output / 'boot-area.bin').read_bytes(), b'b' * 16)
            self.assertEqual((output / 'wl1271-nvs.bin').read_bytes(), b'n' * 912)
