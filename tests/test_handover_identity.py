import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/handover-identity-preflight.sh'


class HandoverIdentityTests(unittest.TestCase):
    def run_fixture(self, wrong_socket=False, wrong_hash=False, exported=False, known_vendor_log=False):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);proc=base/'proc';(proc/'self').mkdir(parents=True);(proc/'net').mkdir()
            (proc/'modules').write_text('g_file_storage 1\n' if exported else '')
            (proc/'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
            block=base/'sys/class/block/mmcblk0p2';block.mkdir(parents=True);(block/'dev').write_text('179:2\n')
            ssh=base/'root/nimbus-ssh-test';ssh.mkdir(parents=True,mode=0o700)
            stage=base/'tmp/nimbus-capture-ssh-v1';stage.mkdir(parents=True,mode=0o700)
            binary=ssh/'dropbearmulti-bound';binary.write_bytes(b'fixture SSH binary; never executed')
            nimbus=base/'nimbus/nimbus';nimbus.parent.mkdir();nimbus.write_bytes(b'fixture vendor binary; never executed')
            (ssh/'boot.pid').write_text('100\n');(stage/'listener.pid').write_text('200\n')
            (ssh/'boot.log').write_text('private boot log content')
            private=base/'secret-customer-filename';private.write_text('private data must not be read')
            if known_vendor_log:
                private=base/'nimbus/xml_log.txt';private.write_text('private vendor API log content')
            for pid,label,executable,start in (('100','dropbearmulti-b',binary,'1234'),('200','dropbearmulti-b',binary,'5678'),('300','nimbus',nimbus,'9876')):
                process=proc/pid;(process/'fd').mkdir(parents=True);(process/'fdinfo').mkdir()
                (process/'exe').symlink_to(executable);(process/'comm').write_text(label+'\n')
                (process/'stat').write_text(pid+' (arbitrary comm with ) parentheses) '+' '.join(['S','1']+['0']*17+[start])+'\n')
                (process/'status').write_text('PPid:\t1\n')
            (proc/'100/fd/3').symlink_to('socket:[999]' if wrong_socket else 'socket:[111]')
            (proc/'200/fd/3').symlink_to('socket:[222]')
            for fd in ('1','2'):
                (proc/'100/fd'/fd).symlink_to(ssh/'boot.log');(proc/'100/fdinfo'/fd).write_text('flags:\t0100001\n')
            (proc/'300/fd/5').symlink_to(private);(proc/'300/fdinfo/5').write_text('flags:\t0100002\n')
            (proc/'net/tcp').write_text(' 0: 00000000:08B0 00000000:0000 0A 0:0 00:0 0 0 0 111\n 1: 00000000:08B1 00000000:0000 0A 0:0 00:0 0 0 0 222\n')
            text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':')
            text=text.replace('1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c',hashlib.sha256(binary.read_bytes()).hexdigest() if not wrong_hash else '0'*64)
            text=text.replace('b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd',hashlib.sha256(nimbus.read_bytes()).hexdigest())
            text=text.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'").replace("stat -c '%u:%g'","stat -c '0:0'")
            text=text.replace('root_device=$(stat -c \'%d\' /)','root_device=$(stat -c \'%d\' "'+str(base)+'")')
            for root in ('/proc/','/sys/','/root/','/tmp/','/nimbus/','/etc/rc.d/','/opt/qsi/'):
                text=text.replace(root,str(base/root.strip('/'))+'/')
            text=text.replace('in /root ', 'in "'+str(base/'root')+'" ').replace(' /tmp ', ' "'+str(base/'tmp')+'" ')
            path=base/'fixture.sh';path.write_text(text)
            before={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file()}
            result=subprocess.run(['sh',str(path)],capture_output=True,text=True,timeout=10)
            after={str(p.relative_to(base)):p.read_bytes() for p in base.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            return result

    def test_identity_socket_starttime_and_private_fd_classification(self):
        result=self.run_fixture()
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertIn('role=old_listener pid=100 start_ticks=1234',result.stdout)
        self.assertIn('role=replacement_listener pid=200 start_ticks=5678',result.stdout)
        self.assertIn('role=vendor_writer pid=300 start_ticks=9876',result.stdout)
        self.assertIn('pid=100 writable_known_boot_log_fds=2 other_writable_root_fds=0',result.stdout)
        self.assertIn('pid=300 writable_known_boot_log_fds=0 other_writable_root_fds=1',result.stdout)
        for secret in ('secret-customer-filename','private data','private boot log','arbitrary comm'):
            self.assertNotIn(secret,result.stdout)

    def test_wrong_socket_hash_or_export_refuses_without_change(self):
        for kwargs in ({'wrong_socket':True},{'wrong_hash':True},{'exported':True}):
            with self.subTest(kwargs=kwargs):self.assertNotEqual(self.run_fixture(**kwargs).returncode,0)

    def test_vendor_log_classification_without_contents_or_unsafe_restart(self):
        result=self.run_fixture(known_vendor_log=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertIn('pid=300 known_vendor_debug_log_fds=0 known_vendor_api_log_fds=1 known_vendor_settings_db_fds=0 unclassified_root_fds=0',result.stdout)
        self.assertNotIn('private vendor API log content',result.stdout)
        self.assertIn('restart_input=nimbus_service status=unavailable_or_unsafe',result.stdout)

    def test_shell_syntax(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
