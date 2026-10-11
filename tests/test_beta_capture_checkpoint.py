from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/beta-capture-checkpoint.sh'


class BetaCheckpointTests(unittest.TestCase):
    def run_fixture(self, exported=False, wrong_root=False):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);proc=base/'proc';(proc/'self').mkdir(parents=True);(proc/'net').mkdir()
            (proc/'modules').write_text('g_file_storage 1 0\n' if exported else '')
            (proc/'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
            sys=base/'sys/class/block/mmcblk0p2';sys.mkdir(parents=True)
            (sys/'dev').write_text('179:3\n' if wrong_root else '179:2\n')
            power=base/'sys/class/power_supply/mc13892_charger';power.mkdir(parents=True)
            (power/'online').write_text('0\n')
            (proc/'net/tcp').write_text(' 0: 00000000:08B0 00000000:0000 0A\n 1: 00000000:08B1 00000000:0000 0A\n')
            stage=base/'tmp/nimbus-capture-ssh-v1';stage.mkdir(parents=True,mode=0o700)
            (stage/'listener.log').write_text('secret log content must not be printed\n');(stage/'listener.log').chmod(0o600)
            (stage/'listener.pid').write_text('999\n');(stage/'listener.pid').chmod(0o600)
            text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':')
            for root in ('/proc/','/sys/','/tmp/'):
                text=text.replace(root,str(base/root.strip('/'))+'/')
            path=base/'fixture.sh';path.write_text(text)
            before={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result=subprocess.run(['sh',str(path)],capture_output=True,text=True,timeout=10)
            after={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            return result

    def test_read_only_metadata_and_no_log_content(self):
        result=self.run_fixture()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('mc13892_charger/online: 0',result.stdout)
        self.assertIn('Port 2224: 1 listening entries',result.stdout)
        self.assertIn('Port 2225: 1 listening entries',result.stdout)
        self.assertIn('listener.log uid:gid:mode=',result.stdout)
        self.assertNotIn('secret log content',result.stdout)
        self.assertNotIn('999',result.stdout)

    def test_active_export_or_changed_root_refuses(self):
        for kwargs in ({'exported':True},{'wrong_root':True}):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(self.run_fixture(**kwargs).returncode,0)

    def test_shell_syntax(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
