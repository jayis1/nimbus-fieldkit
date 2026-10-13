import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from fixture_support import fixture_temp, fixed_paths

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/nimbus-pause-restart-trial.sh'


class PauseRestartTests(unittest.TestCase):
    def fixture(self,base,stop_exits=True,restart_works=True,wrong_input=False,root_ro=False,signal_error=False):
        proc=base/'proc';(proc/'self').mkdir(parents=True)
        (proc/'modules').write_text('')
        (proc/'self/mountinfo').write_text('20 1 179:2 / / rw - ext3 /dev/root rw\n')
        (proc/'mounts').write_text('/dev/root / ext3 '+('ro' if root_ro else 'rw')+' 0 0\nnone /tmp tmpfs rw 0 0\n')
        sys=base/'sys/class/block/mmcblk0p2';sys.mkdir(parents=True);(sys/'dev').write_text('179:2\n')
        power=base/'sys/class/power_supply/mc13892_charger';power.mkdir(parents=True);(power/'online').write_text('1\n')
        stage=base/'tmp/nimbus-pause-restart-v1';stage.mkdir(parents=True,mode=0o700)
        for name in ('etc/rc.d/init.d/service','opt/qsi/config','nimbus'):(base/name).mkdir(parents=True,exist_ok=True)
        binary=base/'nimbus/nimbus';binary.write_bytes(b'fixture vendor executable; NEVER executed')
        database=base/'nimbus/settings.db';database.write_bytes(b'private fixture database')
        for pid,comm in (('100','dropbearmulti-b'),('200','dropbearmulti-b'),('300','nimbus')):
            node=proc/pid;(node/'fd').mkdir(parents=True);(node/'fdinfo').mkdir()
            (node/'comm').write_text(comm+'\n');(node/'start').write_text(pid+'0\n')
            (node/'stat').write_text('fixture present\n');(node/'status').write_text('PPid:\t1\n')
            (node/'maps').write_text('');(node/'exe').symlink_to(binary)
        (proc/'300/fd/5').symlink_to(database);(proc/'300/fdinfo/5').write_text('flags:\t0100002\n')
        template=stage/'new-vendor';template.mkdir();(template/'fd').mkdir();(template/'fdinfo').mkdir()
        (template/'comm').write_text('nimbus\n');(template/'start').write_text('3010\n');(template/'stat').write_text('fixture present\n')
        (template/'maps').write_text('');(template/'status').write_text('PPid:\t1\n');(template/'exe').symlink_to(binary)
        (template/'fd/5').symlink_to(database);(template/'fdinfo/5').write_text('flags:\t0100002\n')
        service=base/'etc/rc.d/init.d/service/S20nimbus'
        service.write_text('#!/bin/sh\n[ "$1" = start ] || exit 7\nprintf "start\\n" >> "'+str(stage/'starts')+'"\n'+
                           ('cp -R "'+str(template)+'" "'+str(proc/'301')+'"\n' if restart_works else 'exit 4\n'))
        inputs={
            '2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3':service,
            'b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd':binary,
        }
        for name,old in (('nimbus.conf','6a32518bd0e5f024a766a8cfb3f722dc4752b952b4ce629ed27fcc8bca4293f5'),
                         ('develop.conf','970a00795c0464a7e97b44d6b50d5bd9dbe6f851d51c7408b55cd058e3c93664'),
                         ('platform_functions','16bcf3ec02fc8a660256bfa37674d6dfd5ef786345d7c2ff624cf1c2b030e136')):
            path=base/'opt/qsi/config'/name;path.write_text('fixture input '+name+'\n');inputs[old]=path
        # Protocol stubs operate ONLY on synthetic /proc records. No host signals.
        identity='''vendor=300
old=100
replacement=200
start_time() { cat "PROC/$1/start"; }
socket_owned() { [ -d "PROC/$1" ]; }
sleep() { /bin/sleep 0.02; }
kill() {
    [ "$1" = -TERM ] && [ "$2" = 300 ] || return 9
    printf 'TERM 300\\n' >> "STAGE/signals"
    STOP_ACTION
}
'''.replace('PROC',str(proc)).replace('STAGE',str(stage)).replace('STOP_ACTION',
                ('mv "'+str(proc/'300')+'" "'+str(stage/'stopped-vendor')+'"'+ ('; return 1' if signal_error else '')) if stop_exits else ':')
        (stage/'identity.sh').write_text(identity);(stage/'started').write_text('fixture approval\n')
        text=SCRIPT.read_text().replace('[ "$(id -u)" = 0 ]',':')
        for old,path in inputs.items():text=text.replace(old,hashlib.sha256(path.read_bytes()).hexdigest())
        text=text.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
        # Rewrite fixed paths, but leave semantic mountpoint fields in awk unchanged.
        text=fixed_paths(text,base,('/proc/','/sys/','/tmp/','/etc/','/opt/','/nimbus/'))
        text=text.replace("root_dev=$(stat -c '%d' /)","root_dev=$(stat -c '%d' '"+str(base)+"')")
        text=text.replace('for dir in /tmp ', 'for dir in "'+str(base/'tmp')+'" ')
        for name in ('/etc','/opt','/nimbus'):
            text=text.replace(' '+name+' ', ' "'+str(base/name.strip('/'))+'" ')
            text=text.replace(' '+name+';', ' "'+str(base/name.strip('/'))+'";')
        (stage/'trial.sh').write_text(text)
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('identity.sh','trial.sh')))
        if wrong_input:service.write_text('tampered restart input\n')
        return stage,proc,database

    def run_case(self,mode='--worker',**kwargs):
        with fixture_temp() as folder:
            stage,proc,database=self.fixture(Path(folder),**kwargs)
            if mode=='--start':(stage/'started').unlink()
            before=database.read_bytes()
            result=subprocess.run(['sh',str(stage/'trial.sh'),mode],capture_output=True,text=True,timeout=10)
            self.assertEqual(database.read_bytes(),before)
            self.assertTrue((proc/'100').exists() and (proc/'200').exists())
            return result, (stage/'RESULT').read_text().strip() if (stage/'RESULT').exists() else None, \
                (stage/'signals').read_text() if (stage/'signals').exists() else '', \
                (stage/'starts').read_text() if (stage/'starts').exists() else ''

    def test_check_only_never_signals_or_starts(self):
        result,status,signals,starts=self.run_case('--check')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIsNone(status);self.assertEqual((signals,starts),('',''))

    def test_one_targeted_term_and_one_restart_on_success(self):
        result,status,signals,starts=self.run_case()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((status,signals,starts),('PASS','TERM 300\n','start\n'))

    def test_restart_failure_never_retries_or_claims_pass(self):
        result,status,signals,starts=self.run_case(restart_works=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 300\n','start\n'))

    def test_failure_after_stop_invokes_best_effort_restore_trap(self):
        result,status,signals,starts=self.run_case(signal_error=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 300\n','start\n'))

    def test_detached_launcher_reports_completed_worker(self):
        result,status,signals,starts=self.run_case('--start')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Trial result: PASS',result.stdout)
        self.assertEqual((status,signals,starts),('PASS','TERM 300\n','start\n'))

    def test_stop_refusal_never_forces_or_starts_duplicate(self):
        result,status,signals,starts=self.run_case(stop_exits=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((status,signals,starts),('FAIL','TERM 300\n',''))

    def test_bad_input_or_root_read_only_refuses_before_signal(self):
        for kwargs in ({'wrong_input':True},{'root_ro':True}):
            with self.subTest(kwargs=kwargs):
                result,status,signals,starts=self.run_case(**kwargs)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual((signals,starts),('',''))

    def test_shell_syntax_and_source_package(self):
        subprocess.run(['sh','-n',str(SCRIPT)],check=True)
        spec=importlib.util.spec_from_file_location('pause_package',ROOT/'scripts/package-pause-restart-trial.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trial.tar';digest=package.build(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            with tarfile.open(path) as archive:self.assertEqual(set(archive.getnames()),{'trial.sh','identity.sh','SHA256SUMS'})
            with self.assertRaises(ValueError):package.build(path)
