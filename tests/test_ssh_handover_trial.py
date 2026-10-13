import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from fixture_support import fixture_temp, fixed_paths

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/ssh/handover-trial.sh'


class SshHandoverTrialTests(unittest.TestCase):
    def fixture(self,base,stop_exits=True,restart_works=True,missing_pid=False,
                wrong_launcher=False,root_ro=False,children=False,unknown_writer=False,
                signal_error=False,occupied_after=False,power=True,real_inventory=False):
        proc=base/'proc';(proc/'self').mkdir(parents=True);(proc/'net').mkdir()
        (proc/'modules').write_text('')
        (proc/'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
        (proc/'mounts').write_text('/dev/root / ext3 '+('ro' if root_ro else 'rw')+' 0 0\nnone /tmp tmpfs rw 0 0\n')
        retained_sockets='1: 00000000:08B1 00000000:0000 0A 0:0 00:0 0 0 0 222\n2: 00000000:0050 00000000:0000 0A 0:0 00:0 0 0 0 333\n'
        (proc/'net/tcp').write_text('0: 00000000:08B0 00000000:0000 0A 0:0 00:0 0 0 0 111\n'+retained_sockets)
        block=base/'sys/class/block/mmcblk0p2';block.mkdir(parents=True);(block/'dev').write_text('179:2\n')
        charger=base/'sys/class/power_supply/mc13892_charger';charger.mkdir(parents=True);(charger/'online').write_text('1\n' if power else '0\n')
        (base/'sys/class/net/wlan1').mkdir(parents=True)
        stage=base/'tmp/nimbus-ssh-handover-trial-v2';stage.mkdir(parents=True,mode=0o700)
        capture=base/'tmp/nimbus-capture-ssh-v1';capture.mkdir(mode=0o700)
        (capture/'sentinel').write_text('existing temporary listener stage: preserve unchanged')
        ssh=base/'root/nimbus-ssh-test';(ssh/'startup-v1').mkdir(parents=True);(ssh/'auth').mkdir(mode=0o700);ssh.chmod(0o700)
        for name in ('boot.log','host-ed25519','auth/authorized_keys','boot.pid'):
            path=ssh/name;path.write_text('100\n' if name=='boot.pid' else 'fixture private material\n');path.chmod(0o600)
        binary=ssh/'dropbearmulti-bound';binary.write_bytes(b'fixture SSH binary, NEVER executed');binary.chmod(0o700)
        vendor=base/'nimbus/nimbus';vendor.parent.mkdir();vendor.write_bytes(b'fixture Nimbus binary, NEVER executed')
        database=base/'nimbus/settings.db';database.write_bytes(b'fixture database, must remain unchanged')
        for pid,comm,executable in (('100','dropbearmulti-b',binary),('200','dropbearmulti-b',binary),('300','nimbus',vendor)):
            node=proc/pid;(node/'fd').mkdir(parents=True);(node/'fdinfo').mkdir()
            (node/'comm').write_text(comm+'\n');(node/'start').write_text(pid+'0\n')
            (node/'stat').write_text(pid+' (fixture) '+' '.join(['S','1']+['0']*17+[pid+'0'])+'\n')
            (node/'status').write_text('PPid:\t1\n');(node/'maps').write_text('');(node/'exe').symlink_to(executable)
        for pid,inode in (('100','111'),('200','222'),('300','333')):(proc/pid/'fd/3').symlink_to('socket:['+inode+']')
        for fd in ('1','2'):
            (proc/'100/fd'/fd).symlink_to(ssh/'boot.log');(proc/'100/fdinfo'/fd).write_text('flags:\t0100001\n')
        (proc/'300/fd/5').symlink_to(database);(proc/'300/fdinfo/5').write_text('flags:\t0100002\n')
        if children:(proc/'200/status').write_text('PPid:\t100\n')
        if unknown_writer:
            secret=base/'secret-file';secret.write_text('private must not be printed')
            (proc/'200/fd/5').symlink_to(secret);(proc/'200/fdinfo/5').write_text('flags:\t0100001\n')
        template=stage/'new-listener';template.mkdir();(template/'fd').mkdir();(template/'fdinfo').mkdir()
        (template/'start').write_text('1010\n');(template/'stat').write_text('101 (fixture) '+' '.join(['S','1']+['0']*17+['1010'])+'\n');(template/'maps').write_text('')
        (template/'status').write_text('PPid:\t1\n');(template/'exe').symlink_to(binary)
        (template/'fd/3').symlink_to('socket:[112]')
        launcher=ssh/'startup-v1/start-ssh.sh'
        launcher.write_text('#!/bin/sh\nprintf "start\\n" >> "'+str(stage/'starts')+'"\n'+
                            ('cp -R "'+str(template)+'" "'+str(proc/'101')+'"\n'+
                             ('' if missing_pid else 'printf "101\\n" > "'+str(ssh/'boot.pid')+'"\n')+
                             'printf "0: 00000000:08B0 00000000:0000 0A 0:0 00:0 0 0 0 112\\n'+retained_sockets.replace('\n','\\n')+'" > "'+str(proc/'net/tcp')+'"\n'
                             if restart_works else 'exit 4\n'))
        launcher.chmod(0o700)
        # No host signals or SSH service: only synthetic metadata moves.
        stop='mv "'+str(proc/'100')+'" "'+str(stage/'stopped-listener')+'"\n'
        stop+=(':' if occupied_after else 'printf "'+retained_sockets.replace('\n','\\n')+'" > "'+str(proc/'net/tcp')+'"')+'\n'
        stop+='return 1\n' if signal_error else 'return 0\n'
        # The real sourced inventory uses the generic global `stage` too.
        # Model that side effect, not just its function protocol.
        identity='''stage=CAPTURE
old=100
replacement=200
vendor=300
start_time() { cat "PROC/$1/start"; }
socket_owned() {
    [ -d "PROC/$1" ] || return 1
    case "$2" in
        08B0) grep -q ':08B0 ' "PROC/net/tcp";;
        08B1) [ "$1" = 200 ];;
        0050) [ "$1" = 300 ];;
        *) return 1;;
    esac
}
sleep() { /bin/sleep 0.02; }
kill() {
    [ "$1" = -TERM ] && [ "$2" = 100 ] || return 9
    printf 'TERM 100\\n' >> "STAGE/signals"
    STOP_ACTION
}
'''.replace('PROC',str(proc)).replace('STAGE',str(stage)).replace('CAPTURE',str(capture)).replace('STOP_ACTION',stop if stop_exits else 'return 0')
        if real_inventory:
            (capture/'listener.pid').write_text('200\n');(capture/'listener.pid').chmod(0o600)
            real=(ROOT/'device/handover-identity-preflight.sh').read_text().replace('[ "$(id -u)" = 0 ]',':')
            for old,path in (('1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c',binary),
                             ('b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd',vendor)):
                real=real.replace(old,hashlib.sha256(path.read_bytes()).hexdigest())
            real=real.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'").replace("stat -c '%u:%g'","stat -c '0:0'")
            real=fixed_paths(real,base,('/proc/','/sys/','/root/','/tmp/','/nimbus/','/etc/rc.d/','/opt/qsi/'))
            real=real.replace("root_device=$(stat -c '%d' /)","root_device=$(stat -c '%d' '"+str(base)+"')")
            real=real.replace('in /root ', 'in "'+str(base/'root')+'" ').replace(' /tmp ', ' "'+str(base/'tmp')+'" ')
            # Keep real start/socket functions and real global variable effects;
            # mock ONLY signal and sleep so no host process can be signalled.
            identity=real+'\n'+identity[identity.index('sleep()'):]
        (stage/'identity.sh').write_text(identity)
        for name in ('started','worker.log'):(stage/name).write_text('fixture approval\n');(stage/name).chmod(0o600)
        text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':')
        for old,path in (('1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c',binary),
                         ('173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41',launcher),
                         ('b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd',vendor)):
            text=text.replace(old,hashlib.sha256(path.read_bytes()).hexdigest())
        text=text.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
        text=fixed_paths(text,base,('/proc/','/sys/','/root/','/tmp/','/nimbus/'))
        text=text.replace("root_dev=$(stat -c '%d' /)","root_dev=$(stat -c '%d' '"+str(base)+"')")
        text=text.replace('in /tmp ', 'in "'+str(base/'tmp')+'" ').replace(' /root ', ' "'+str(base/'root')+'" ')
        (stage/'trial.sh').write_text(text)
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('trial.sh','identity.sh')))
        if wrong_launcher:launcher.write_text('tampered\n')
        return stage,proc,database,ssh

    def run_case(self,mode='--worker',connection='127.0.0.1 1234 127.0.0.1 2225',**kwargs):
        with fixture_temp() as folder:
            stage,proc,database,ssh=self.fixture(Path(folder),**kwargs)
            if mode!='--worker':
                (stage/'started').unlink();(stage/'worker.log').unlink()
            before=database.read_bytes();vendor_start=(proc/'300/start').read_text()
            capture=Path(folder)/'tmp/nimbus-capture-ssh-v1'
            capture_before={p.name:p.read_bytes() for p in capture.iterdir()}
            env=dict(os.environ,SSH_CONNECTION=connection)
            result=subprocess.run(['sh',str(stage/'trial.sh'),mode],capture_output=True,text=True,env=env,timeout=10)
            self.assertEqual(database.read_bytes(),before)
            self.assertEqual((proc/'300/start').read_text(),vendor_start)
            self.assertTrue((proc/'200').exists())
            self.assertEqual({p.name:p.read_bytes() for p in capture.iterdir()},capture_before)
            status=(stage/'RESULT').read_text().strip() if (stage/'RESULT').exists() else None
            signals=(stage/'signals').read_text() if (stage/'signals').exists() else ''
            starts=(stage/'starts').read_text() if (stage/'starts').exists() else ''
            return result,status,signals,starts

    def test_check_only_no_signal_or_launch(self):
        result,status,signals,starts=self.run_case('--check')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((status,signals,starts),(None,'',''))

    def test_success_one_targeted_term_and_one_launch(self):
        result,status,signals,starts=self.run_case()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((status,signals,starts),('PASS','TERM 100\n','start\n'))

    def test_detached_launcher(self):
        result,status,signals,starts=self.run_case('--start')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Trial result: PASS',result.stdout)
        self.assertEqual((status,signals,starts),('PASS','TERM 100\n','start\n'))

    def test_sourced_inventory_stage_collision_does_not_redirect_worker_or_result(self):
        result,status,signals,starts=self.run_case('--start')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((status,signals,starts),('PASS','TERM 100\n','start\n'))

    def test_real_inventory_detached_worker_and_result_stage(self):
        result,status,signals,starts=self.run_case('--start',real_inventory=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('role=old_listener pid=100',result.stdout)
        self.assertEqual((status,signals,starts),('PASS','TERM 100\n','start\n'))

    def test_stop_refusal_no_force_or_duplicate(self):
        result,status,signals,starts=self.run_case(stop_exits=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 100\n',''))

    def test_restart_failure_no_retry(self):
        result,status,signals,starts=self.run_case(restart_works=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 100\n','start\n'))

    def test_missing_fresh_pid_never_claims_success(self):
        result,status,signals,starts=self.run_case(missing_pid=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 100\n','start\n'))

    def test_error_after_exit_restores_once(self):
        result,status,signals,starts=self.run_case(signal_error=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 100\n','start\n'))

    def test_occupied_port_after_exit_no_duplicate(self):
        result,status,signals,starts=self.run_case(occupied_after=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 100\n',''))

    def test_bad_inputs_children_writers_or_power_refuse_before_action(self):
        for kwargs in ({'wrong_launcher':True},{'root_ro':True},{'children':True},{'unknown_writer':True},{'power':False}):
            with self.subTest(kwargs=kwargs):
                result,status,signals,starts=self.run_case(**kwargs)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual((signals,starts),('',''))
                self.assertNotIn('secret-file',result.stdout)

    def test_wrong_connection_refuses_before_action(self):
        for connection in ('','127.0.0.1 1234 127.0.0.1 2224'):
            result,status,signals,starts=self.run_case(connection=connection)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((signals,starts),('',''))

    def test_prior_stage_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            stage,proc,database,ssh=self.fixture(Path(folder))
            result=subprocess.run(['sh',str(stage/'trial.sh'),'--start'],capture_output=True,text=True,
                                  env=dict(os.environ,SSH_CONNECTION='a b c 2225'),timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((stage/'signals').exists())

    def test_syntax_and_first_party_package(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
        spec=importlib.util.spec_from_file_location('handover_package',ROOT/'scripts/package-handover-trial.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trial.tar';digest=package.build(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            with tarfile.open(path) as archive:
                self.assertEqual(set(archive.getnames()),{'trial.sh','identity.sh','SHA256SUMS'})
                for member in archive:self.assertEqual(member.mode,0o600)
            with self.assertRaises(ValueError):package.build(path)
