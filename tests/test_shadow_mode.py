import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from fixture_support import fixture_temp
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'device/ssh/shadow-mode-hardening.c'
spec=importlib.util.spec_from_file_location('shadow_mode_builder',ROOT/'scripts/build-shadow-mode-helper.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


@unittest.skipUnless(shutil.which('gcc'),'Host C compiler unavailable')
class ShadowModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=fixture_temp(prefix='shadow-mode-tests-')
        cls.root=Path(cls.temp.name);cls.binary=cls.root/'fixture'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DSHADOW_FIXTURE',str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True,timeout=20)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.directory=Path(tempfile.mkdtemp(dir=self.root));self.directory.chmod(0o755)
        self.shadow=self.directory/'shadow';self.data=b'fixture:*:1::::::\n'
        self.shadow.write_bytes(self.data);self.shadow.chmod(0o744)
        info=self.shadow.stat()
        self.pin=f'SHADOW-PIN {info.st_dev} {info.st_ino} {info.st_size} {hashlib.sha256(self.data).hexdigest()}\n'.encode()

    def run_helper(self,mode='--check',pin=None):
        return subprocess.run([str(self.binary),mode,str(self.directory)],input=self.pin if pin is None else pin,capture_output=True,timeout=5)

    def test_read_only_check_and_harden_change_only_permissions(self):
        before=self.shadow.stat()
        result=self.run_helper();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)
        result=self.run_helper('--harden');self.assertEqual(result.returncode,0,result.stderr)
        after=self.shadow.stat();self.assertEqual(stat.S_IMODE(after.st_mode),0o600)
        self.assertEqual((before.st_dev,before.st_ino,before.st_uid,before.st_gid,before.st_size),
                         (after.st_dev,after.st_ino,after.st_uid,after.st_gid,after.st_size))
        self.assertEqual(self.shadow.read_bytes(),self.data)
        self.assertIn(b'account-records-written=no persistence_verified=no',result.stdout)
        self.assertNotIn(self.data,result.stdout+result.stderr)
        self.assertNotIn(hashlib.sha256(self.data).hexdigest().encode(),result.stdout+result.stderr)

    def test_already_private_never_reopens_permissions(self):
        self.shadow.chmod(0o600)
        result=self.run_helper('--harden');self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o600)

    def test_only_fixed_backup_is_hardened_and_primary_untouched(self):
        backup=self.directory/'shadow-';backup.write_bytes(b'older fixture:*:1::::::\n');backup.chmod(0o744)
        info=backup.stat();pin=f'SHADOW-PIN {info.st_dev} {info.st_ino} {info.st_size} {hashlib.sha256(backup.read_bytes()).hexdigest()}\n'.encode()
        self.assertEqual(self.run_helper('--check-backup',pin).returncode,0)
        result=self.run_helper('--harden-backup',pin);self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b'target=shadow-',result.stdout)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)
        self.assertEqual(backup.read_bytes(),b'older fixture:*:1::::::\n')

    def test_backup_cannot_use_primary_pin_or_follow_symlink(self):
        backup=self.directory/'shadow-';backup.write_bytes(self.data);backup.chmod(0o744)
        self.assertNotEqual(self.run_helper('--harden-backup').returncode,0)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode),0o744)
        backup.unlink();backup.symlink_to(self.shadow)
        self.assertNotEqual(self.run_helper('--harden-backup').returncode,0)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)

    def test_changed_hash_size_inode_and_malformed_pin_refuse_before_chmod(self):
        original=self.pin.decode();fields=original.split()
        pins=[]
        for index,value in ((1,'999'),(2,'999'),(3,'999'),(4,'0'*64)):
            changed=fields.copy();changed[index]=value;pins.append((' '.join(changed)+'\n').encode())
        pins.extend((b'',b'x'*300,original.encode()+b'extra\n',original.replace('SHADOW-PIN','OTHER').encode()))
        for pin in pins:
            with self.subTest(pin_length=len(pin)):
                result=self.run_helper('--harden',pin);self.assertNotEqual(result.returncode,0)
                self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)
                self.assertEqual(self.shadow.read_bytes(),self.data)

    def test_symlink_hardlink_fifo_and_unsafe_mode_refuse(self):
        for kind in ('symlink','hardlink','fifo','unsafe-mode'):
            with self.subTest(kind=kind):
                self.shadow.unlink()
                if kind=='symlink':
                    target=self.directory/'target';target.write_bytes(self.data);target.chmod(0o744);self.shadow.symlink_to(target)
                elif kind=='fifo':os.mkfifo(self.shadow)
                else:
                    self.shadow.write_bytes(self.data);self.shadow.chmod(0o777 if kind=='unsafe-mode' else 0o744)
                    if kind=='hardlink':os.link(self.shadow,self.directory/'hardlinked')
                info=self.shadow.lstat()
                pin=f'SHADOW-PIN {info.st_dev} {info.st_ino} {info.st_size} {hashlib.sha256(self.data).hexdigest()}\n'.encode()
                self.assertNotEqual(self.run_helper('--harden',pin).returncode,0)
                if kind=='symlink':self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o744)

    def test_parent_symlink_or_writable_parent_refuses(self):
        self.directory.chmod(0o777)
        self.assertNotEqual(self.run_helper('--harden').returncode,0)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)
        self.directory.chmod(0o755)
        link=self.root/(self.directory.name+'-link');link.symlink_to(self.directory,target_is_directory=True)
        result=subprocess.run([str(self.binary),'--harden',str(link)],input=self.pin,capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0)

    def gated(self,change):
        ready_read,ready_write=os.pipe();gate_read,gate_write=os.pipe()
        env=os.environ.copy();env['SHADOW_FIXTURE_READY_FD']=str(ready_write);env['SHADOW_FIXTURE_GATE_FD']=str(gate_read)
        process=subprocess.Popen([str(self.binary),'--harden',str(self.directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 env=env,pass_fds=(ready_write,gate_read))
        os.close(ready_write);os.close(gate_read)
        try:
            process.stdin.write(self.pin);process.stdin.close();process.stdin=None
            import select
            self.assertTrue(select.select([ready_read],[],[],5)[0]);self.assertEqual(os.read(ready_read,1),b'R')
            change()
            os.write(gate_write,b'G');os.close(gate_write);gate_write=-1
            out,err=process.communicate(timeout=5)
            return process.returncode,out,err
        finally:
            os.close(ready_read)
            if gate_write>=0:os.close(gate_write)
            if process.poll() is None:process.terminate();process.communicate(timeout=5)

    def test_replaced_inode_not_chmodded_and_old_insecure_mode_not_restored(self):
        old=self.directory/'approved-old'
        def replace():
            self.shadow.rename(old);self.shadow.write_bytes(b'unrelated replacement');self.shadow.chmod(0o744)
        code,out,err=self.gated(replace)
        self.assertEqual(code,3);self.assertNotIn(b'=PASS',out)
        self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o744)
        self.assertEqual(stat.S_IMODE(old.stat().st_mode),0o600)
        self.assertEqual(self.shadow.read_bytes(),b'unrelated replacement');self.assertEqual(old.read_bytes(),self.data)
        self.assertIn(b'never restore insecure permissions',err)

    def test_concurrent_content_change_is_not_overwritten_or_reported_as_success(self):
        changed=b'fixture changed by another writer\n'
        code,out,err=self.gated(lambda:self.shadow.write_bytes(changed))
        self.assertEqual(code,3);self.assertNotIn(b'=PASS',out)
        self.assertEqual(self.shadow.read_bytes(),changed);self.assertEqual(stat.S_IMODE(self.shadow.stat().st_mode),0o600)
        self.assertIn(b'unconfirmed',err)

    def test_missing_target_and_unknown_action_refuse(self):
        self.assertEqual(self.run_helper('--restore').returncode,2)
        self.shadow.unlink();self.assertNotEqual(self.run_helper('--harden').returncode,0)

    def test_production_no_arguments_and_fixture_override_refuse(self):
        binary=self.root/'production-host'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',str(SOURCE),'-o',str(binary)],check=True,capture_output=True,timeout=20)
        for args in ([],['--harden',str(self.directory)]):
            result=subprocess.run([str(binary),*args],input=self.pin,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,2);self.assertFalse(result.stdout);self.assertFalse(result.stderr)


class ShadowBuildTests(unittest.TestCase):
    def test_wrong_sdk_refuses_before_output_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            root=Path(temporary);source=root/'wrong.tar';source.write_bytes(b'wrong')
            with self.assertRaises(ValueError):builder.build(source,root/'output')
            self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_source_has_no_content_writer_or_account_service_actions(self):
        text=SOURCE.read_text()
        for forbidden in ('O_WRONLY','O_RDWR','O_CREAT','O_TRUNC','rename(','unlink(','chmod("','system(','execv(','mount('):
            self.assertNotIn(forbidden,text)
        self.assertIn('fchmod(file,0600)',text)
