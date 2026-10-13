import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/root-remount-preflight.sh'


class RootRemountPreflightTests(unittest.TestCase):
    def run_fixture(self,options='rw,relatime,errors=continue,barrier=0,data=writeback',
                    exported=False,wrong_hash=False,mtab='absent',power=True,connection='a b c 2225',arguments=()):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            (base/'proc/self').mkdir(parents=True)
            (base/'proc/modules').write_text('g_file_storage 1\n' if exported else '')
            (base/'proc/self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
            (base/'proc/mounts').write_text('/dev/root / ext3 '+options+' 0 0\nnone /tmp tmpfs rw 0 0\n')
            (base/'sys/class/block/mmcblk0p2').mkdir(parents=True);(base/'sys/class/block/mmcblk0p2/dev').write_text('179:2\n')
            (base/'sys/class/power_supply/mc13892_charger').mkdir(parents=True)
            (base/'sys/class/power_supply/mc13892_charger/online').write_text('1\n' if power else '0\n')
            (base/'bin').mkdir();(base/'etc').mkdir();(base/'tmp').mkdir()
            text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g'","stat -c '0:0'")
            # Executing either fixture utility would fail and create evidence.
            for name,old in (('mount','5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be'),
                             ('busybox','aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c')):
                path=base/'bin'/name;path.write_text('#!/bin/sh\necho forbidden > "'+str(base/'executed')+'"\nexit 9\n');path.chmod(0o700)
                text=text.replace(old,'0'*64 if wrong_hash else hashlib.sha256(path.read_bytes()).hexdigest())
            if mtab=='regular':(base/'etc/mtab').write_text('PRIVATE CONTENT MUST NOT BE PRINTED')
            elif mtab!='absent':(base/'etc/mtab').symlink_to(mtab)
            for path in ('/proc/','/sys/','/bin/','/etc/'):
                text=text.replace(path,str(base/path.strip('/'))+'/')
            text=text.replace('in /bin /etc;', 'in "'+str(base/'bin')+'" "'+str(base/'etc')+'";')
            text=text.replace('df -k /tmp','df -k "'+str(base/'tmp')+'"')
            # Rewrite only the known proc symlink matching arm consistently.
            if mtab.startswith('/proc/'):
                (base/'etc/mtab').unlink();(base/'etc/mtab').symlink_to(str(base/mtab.strip('/')))
            script=base/'inventory.sh';script.write_text(text)
            before={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file() and not p.is_symlink()}
            result=subprocess.run(['sh',str(script),*arguments],capture_output=True,text=True,
                                  env=dict(os.environ,SSH_CONNECTION=connection),timeout=10)
            after={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file() and not p.is_symlink()}
            self.assertEqual(before,after)
            self.assertNotIn('PRIVATE CONTENT',result.stdout)
            return result

    def test_regular_pinned_tools_and_root_options_without_execution(self):
        result=self.run_fixture()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('utility=mount sha256=matched',result.stdout)
        self.assertIn('mtab=absent',result.stdout)

    def test_mtab_variants_are_metadata_only(self):
        for mtab in ('regular','/proc/mounts'):
            result=self.run_fixture(mtab=mtab)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_changed_hash_usb_or_power_refuses(self):
        for kwargs in ({'wrong_hash':True},{'exported':True},{'power':False}):
            self.assertNotEqual(self.run_fixture(**kwargs).returncode,0)

    def test_unknown_options_or_symlink_targets_are_suppressed(self):
        for kwargs in ({'options':'rw,private-secret=value'},{'mtab':'/secret-target'}):
            result=self.run_fixture(**kwargs)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('private-secret',result.stdout);self.assertNotIn('secret-target',result.stdout)

    def test_read_only_root_wrong_connection_or_action_arguments_refuse(self):
        for kwargs in ({'options':'ro,relatime'},{'connection':''},{'connection':'a b c 2224'},{'arguments':('--start',)}):
            self.assertNotEqual(self.run_fixture(**kwargs).returncode,0)

    def test_shell_syntax(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
