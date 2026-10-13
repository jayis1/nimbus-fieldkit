import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from fixture_support import fixture_temp, fixed_paths

import test_ssh_handover_trial as handover_fixtures

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/root-restoration-trial.sh'


class RootRestorationTrialTests(unittest.TestCase):
    def fixture(self,base,old_stop=True,vendor_stop=True,ro_works=True,rw_works=True,
                ro_error_after_change=False,rw_error_after_change=False,vendor_restart=True,
                ssh_restart=True,wrong_ro_options=False,unknown_writer=False,wrong_input=False,
                signal_error='',replacement_lost=False):
        stage,proc,database,ssh=handover_fixtures.SshHandoverTrialTests().fixture(base,real_inventory=True)
        mountinfo=proc/'self/mountinfo'
        mountinfo.write_text('20 1 179:2 / / rw,relatime - ext3 /dev/root rw,errors=continue,barrier=0,data=writeback\n')
        (proc/'mounts').write_text('/dev/root / ext3 rw,relatime,errors=continue,barrier=0,data=writeback 0 0\nnone /tmp tmpfs rw 0 0\n')
        (base/'bin').mkdir();(base/'etc/rc.d/init.d/service').mkdir(parents=True);(base/'opt/qsi/config').mkdir(parents=True)
        template=stage/'new-listener'
        for fd in ('1','2'):
            (template/'fd'/fd).symlink_to(ssh/'boot.log');(template/'fdinfo'/fd).write_text('flags:\t0100001\n')
        launcher=ssh/'startup-v1/start-ssh.sh'
        launcher.write_text('#!/bin/sh\nprintf "ssh\\n" >> "'+str(stage/'starts')+'"\n'+
                            ('cp -R "'+str(template)+'" "'+str(proc/'101')+'"\nprintf "101\\n" > "'+str(ssh/'boot.pid')+'"\nprintf "0: 00000000:08B0 00000000:0000 0A 0:0 00:0 0 0 0 112\\n" >> "'+str(proc/'net/tcp')+'"\n' if ssh_restart else 'exit 4\n'))
        vendor_template=stage/'new-vendor';shutil.copytree(proc/'300',vendor_template,symlinks=True)
        (vendor_template/'start').write_text('3010\n');(vendor_template/'stat').write_text('301 (fixture) '+' '.join(['S','1']+['0']*17+['3010'])+'\n')
        (vendor_template/'fd/3').unlink();(vendor_template/'fd/3').symlink_to('socket:[334]')
        service=base/'etc/rc.d/init.d/service/S20nimbus'
        service.write_text('#!/bin/sh\n[ "$1" = start ] || exit 9\nprintf "vendor\\n" >> "'+str(stage/'starts')+'"\n'+
                           ('cp -R "'+str(vendor_template)+'" "'+str(proc/'301')+'"\nprintf "2: 00000000:0050 00000000:0000 0A 0:0 00:0 0 0 0 334\\n" >> "'+str(proc/'net/tcp')+'"\n' if vendor_restart else 'exit 4\n'))
        for path in (service,launcher):path.chmod(0o700)
        mount=base/'bin/mount'
        mount.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "STAGE/mounts"
[ "$1" = -n ] && [ "$2" = -i ] && [ "$4" = -t ] && [ "$5" = ext3 ] && [ "$6" = -o ] && [ "$8" = /dev/mmcblk0p2 ] && [ "$9" = / ] || exit 9
case "$3" in
    -r) RO_ACTION;;
    -w) RW_ACTION;;
    *) exit 9;;
esac
'''.replace('STAGE',str(stage)).replace('RO_ACTION',
            (('printf "/dev/root / ext3 ro,relatime,errors=continue,barrier='+('1' if wrong_ro_options else '0')+',data=writeback 0 0\\nnone /tmp tmpfs rw 0 0\\n" > "'+str(proc/'mounts')+'"\n'+
              'printf "20 1 179:2 / / ro,relatime - ext3 /dev/root ro,errors=continue,barrier=0,data=writeback\\n" > "'+str(mountinfo)+'"\n'+
              ('mv "'+str(proc/'200')+'" "'+str(stage/'lost-replacement')+'"\n' if replacement_lost else '')+
              ('exit 4' if ro_error_after_change else 'exit 0')) if ro_works else 'exit 4')).replace('RW_ACTION',
            (('printf "/dev/root / ext3 rw,relatime,errors=continue,barrier=0,data=writeback 0 0\\nnone /tmp tmpfs rw 0 0\\n" > "'+str(proc/'mounts')+'"\n'+
              'printf "20 1 179:2 / / rw,relatime - ext3 /dev/root rw,errors=continue,barrier=0,data=writeback\\n" > "'+str(mountinfo)+'"\n'+
              ('exit 4' if rw_error_after_change else 'exit 0')) if rw_works else 'exit 4')))
        mount.chmod(0o700)
        # Retain actual sourced inventory; replace only signal/sleep stubs.
        identity=(stage/'identity.sh').read_text().split('\nsleep()')[0]
        identity+='\nsleep() { /bin/sleep 0.02; }\nkill() {\n[ "$1" = -TERM ] || return 9\nprintf "TERM %s\\n" "$2" >> "'+str(stage/'signals')+'"\ncase "$2" in\n'
        for pid,port,exits in (('100','08B0',old_stop),('300','0050',vendor_stop)):
            action='mv "'+str(proc/pid)+'" "'+str(stage/('stopped-'+pid))+'"\n'
            action+='sed "/:'+port+' /d" "'+str(proc/'net/tcp')+'" > "'+str(stage/'tcp.new')+'"\nmv "'+str(stage/'tcp.new')+'" "'+str(proc/'net/tcp')+'"\n'
            action+='return 1\n' if signal_error==pid else 'return 0\n'
            identity+=pid+') '+(action if exits else 'return 0\n')+';;\n'
        identity+='*) return 9;;\nesac\n}\n'
        (stage/'identity.sh').write_text(identity)
        text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':')
        inputs={
            '1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c':ssh/'dropbearmulti-bound',
            '173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41':launcher,
            'b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd':base/'nimbus/nimbus',
            '2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3':service,
            '5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be':mount,
        }
        for name,digest in (('nimbus.conf','6a32518bd0e5f024a766a8cfb3f722dc4752b952b4ce629ed27fcc8bca4293f5'),
                            ('develop.conf','970a00795c0464a7e97b44d6b50d5bd9dbe6f851d51c7408b55cd058e3c93664'),
                            ('platform_functions','16bcf3ec02fc8a660256bfa37674d6dfd5ef786345d7c2ff624cf1c2b030e136')):
            path=base/'opt/qsi/config'/name;path.write_text('fixture configuration');inputs[digest]=path
        for old,path in inputs.items():text=text.replace(old,hashlib.sha256(path.read_bytes()).hexdigest())
        text=text.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'").replace("stat -c '%u:%g'","stat -c '0:0'")
        text=text.replace('/tmp/nimbus-root-restoration-trial-v1','/tmp/nimbus-ssh-handover-trial-v2')
        text=fixed_paths(text,base,('/proc/','/sys/','/root/','/tmp/','/nimbus/','/bin/mount','/etc/','/opt/'))
        text=text.replace("root_dev=$(stat -c '%d' /)","root_dev=$(stat -c '%d' '"+str(base)+"')")
        for name in ('/tmp','/root','/bin','/etc','/opt','/nimbus'):
            text=text.replace(' '+name+' ', ' "'+str(base/name.strip('/'))+'" ').replace(' '+name+';', ' "'+str(base/name.strip('/'))+'";')
        (stage/'trial.sh').write_text(text)
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('trial.sh','identity.sh')))
        if unknown_writer:
            (proc/'200/fd/9').symlink_to(database);(proc/'200/fdinfo/9').write_text('flags:\t0100002\n')
        if wrong_input:mount.write_text('tampered utility')
        return stage,proc,database

    def run_case(self,mode='--worker',**kwargs):
        with fixture_temp() as folder:
            base=Path(folder);stage,proc,database=self.fixture(base,**kwargs)
            if mode!='--worker':(stage/'started').unlink();(stage/'worker.log').unlink()
            before=database.read_bytes()
            capture=base/'tmp/nimbus-capture-ssh-v1'
            capture_before={p.name:p.read_bytes() for p in capture.iterdir()}
            result=subprocess.run(['sh',str(stage/'trial.sh'),mode],capture_output=True,text=True,
                                  env=dict(os.environ,SSH_CONNECTION='a b c 2225'),timeout=10)
            self.assertEqual(database.read_bytes(),before)
            self.assertEqual({p.name:p.read_bytes() for p in capture.iterdir()},capture_before)
            logs={name:(stage/name).read_text() if (stage/name).exists() else '' for name in ('RESULT','signals','starts','mounts','worker.log')}
            return result,logs,(proc/'mounts').read_text()

    def test_check_only_no_signal_launch_or_mount(self):
        result,logs,state=self.run_case('--check')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((logs['signals'],logs['starts'],logs['mounts'],logs['RESULT']),('','','',''))

    def test_one_ro_one_explicit_rw_and_both_service_restorations(self):
        result,logs,state=self.run_case()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(logs['RESULT'],'PASS\n')
        self.assertEqual(logs['signals'],'TERM 100\nTERM 300\n')
        self.assertEqual(logs['starts'],'vendor\nssh\n')
        self.assertEqual(len(logs['mounts'].splitlines()),2)
        self.assertIn('-n -i -r -t ext3 -o remount,ro,relatime,errors=continue,barrier=0,data=writeback',logs['mounts'])
        self.assertIn('-n -i -w -t ext3 -o remount,rw,relatime,errors=continue,barrier=0,data=writeback',logs['mounts'])
        self.assertIn('/ ext3 rw,relatime',state)

    def test_real_inventory_detached_completion(self):
        result,logs,state=self.run_case('--start')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(logs['RESULT'],'PASS\n')
        self.assertIn('Expected root read-only configuration observed',logs['worker.log'])

    def test_old_stop_refusal_no_vendor_stop_or_mount(self):
        result,logs,state=self.run_case(old_stop=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['signals'],logs['starts'],logs['mounts']),('FAIL\n','TERM 100\n','',''))

    def test_vendor_stop_refusal_restores_only_old_listener(self):
        result,logs,state=self.run_case(vendor_stop=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts'],logs['mounts']),('FAIL\n','ssh\n',''))

    def test_ro_refusal_restores_services_without_extra_mount(self):
        result,logs,state=self.run_case(ro_works=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n','vendor\nssh\n'))
        self.assertEqual(len(logs['mounts'].splitlines()),1)

    def test_error_after_ro_change_restores_rw_but_remains_fail(self):
        result,logs,state=self.run_case(ro_error_after_change=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n','vendor\nssh\n'))
        self.assertEqual(len(logs['mounts'].splitlines()),2)

    def test_rw_refusal_never_retries_or_starts_services_on_ro(self):
        result,logs,state=self.run_case(rw_works=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n',''))
        self.assertEqual(len(logs['mounts'].splitlines()),2)
        self.assertIn('/ ext3 ro,relatime',state)

    def test_rw_error_after_state_change_restores_services_without_retry(self):
        result,logs,state=self.run_case(rw_error_after_change=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n','vendor\nssh\n'))
        self.assertEqual(len(logs['mounts'].splitlines()),2)

    def test_wrong_ro_options_no_blind_rw_or_service_start(self):
        result,logs,state=self.run_case(wrong_ro_options=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n',''))
        self.assertEqual(len(logs['mounts'].splitlines()),1)

    def test_independent_ssh_recovery_even_if_vendor_restart_fails(self):
        result,logs,state=self.run_case(vendor_restart=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n','vendor\nssh\n'))

    def test_ssh_restart_failure_no_retry(self):
        result,logs,state=self.run_case(ssh_restart=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n','vendor\nssh\n'))

    def test_errors_after_each_stop_restore_only_interrupted_services(self):
        for pid,starts in (('100','ssh\n'),('300','vendor\nssh\n')):
            result,logs,state=self.run_case(signal_error=pid)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((logs['RESULT'],logs['starts'],logs['mounts']),('FAIL\n',starts,''))

    def test_changed_mount_utility_or_unknown_writer_refuses_before_signal(self):
        for kwargs in ({'wrong_input':True},{'unknown_writer':True}):
            result,logs,state=self.run_case(**kwargs)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((logs['signals'],logs['mounts']),('',''))

    def test_lost_replacement_prevents_blind_restore(self):
        result,logs,state=self.run_case(replacement_lost=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((logs['RESULT'],logs['starts']),('FAIL\n',''))
        self.assertEqual(len(logs['mounts'].splitlines()),1)

    def test_shell_syntax_and_source_only_package(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
        spec=importlib.util.spec_from_file_location('root_package',ROOT/'scripts/package-root-restoration-trial.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with fixture_temp() as folder:
            path=Path(folder)/'trial.tar';digest=package.build(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            with tarfile.open(path) as archive:self.assertEqual(set(archive.getnames()),{'trial.sh','identity.sh','SHA256SUMS'})
            with self.assertRaises(ValueError):package.build(path)
