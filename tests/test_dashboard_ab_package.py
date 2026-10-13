import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ab_ui_package',ROOT/'scripts/package-dashboard-ab.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


class DashboardPackageTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/'stage';stage.mkdir(mode=0o700)
        data=root/'web';(data/'fieldkit-v06').mkdir(parents=True);(data/'fieldkit-performance-r1').mkdir()
        original={name:('original fixture '+name).encode() for name in package.BEFORE}
        payload=package.payload()
        before={name:hashlib.sha256(value).hexdigest() for name,value in original.items()}
        after={name:hashlib.sha256(value).hexdigest() for name,value in payload.items()}
        for name,value in original.items():
            directory='fieldkit-performance-r1' if name=='bridge.js' else 'fieldkit-v06'
            path=data/directory/name;path.write_bytes(value);path.chmod(0o644)
        for name,value in payload.items():
            (stage/name).write_bytes(value);(stage/name).chmod(0o600)
        (stage/'MANIFEST.json').write_text('{}');(stage/'MANIFEST.json').chmod(0o600)
        script=package.installer(before,after).replace(package.STAGE,str(stage)).replace('DATA=/nimbus/data','DATA="'+str(data)+'"')
        script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
        script=script.replace("stat -c '%u:%g:%a:%h'","stat -c '0:0:%a:%h'")
        script=script.replace(' /nimbus "$DATA"',' "'+str(data)+'" "$DATA"')
        mounts=root/'mounts';mounts.write_text('/dev/root / ext3 rw,relatime,errors=continue,barrier=0,data=writeback 0 0\n')
        script=script.replace('/proc/mounts',str(mounts))
        # Fixture tests exercise transaction logic, not host/device durability.
        # Global host sync can wait on unrelated mounted filesystems.
        script=script.replace('    sync\n','    : # fixture-only sync stub\n')
        path=stage/'install.sh';path.write_text(script);path.chmod(0o600)
        sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(stage.iterdir()) if p.is_file())
        (stage/'SHA256SUMS').write_text(sums);(stage/'SHA256SUMS').chmod(0o600)
        return stage,data,original,payload

    def run_install(self,stage,mode):
        return subprocess.run(['sh',str(stage/'install.sh'),mode],capture_output=True,text=True,timeout=10)

    def test_check_install_and_guarded_rollback_preserve_homepage_and_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,data,old,new=self.fixture(Path(temporary))
            (data/'index.html').write_bytes(b'unmodified vendor homepage')
            original_home=(data/'index.html').read_bytes()
            result=self.run_install(stage,'--check');self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse((stage/'backups').exists());self.assertFalse((stage/'STATUS').exists())
            result=self.run_install(stage,'install');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for name,value in new.items():
                parent='fieldkit-performance-r1' if name=='bridge.js' else 'fieldkit-v06'
                self.assertEqual((data/parent/name).read_bytes(),value)
            self.assertEqual((data/'index.html').read_bytes(),original_home)
            self.assertNotEqual(self.run_install(stage,'install').returncode,0)
            result=self.run_install(stage,'rollback');self.assertEqual(result.returncode,0,result.stderr)
            for name,value in old.items():
                parent='fieldkit-performance-r1' if name=='bridge.js' else 'fieldkit-v06'
                self.assertEqual((data/parent/name).read_bytes(),value)
            self.assertFalse((data/'fieldkit-v06/battery.js').exists())
            self.assertEqual((data/'index.html').read_bytes(),original_home)
            self.assertTrue((stage/'backups').is_dir())

    def test_changed_target_or_existing_battery_refuses_before_backups(self):
        for change in ('toolkit.js','battery.js'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temporary:
                stage,data,_,_=self.fixture(Path(temporary))
                target=data/'fieldkit-v06'/change;target.write_bytes(b'owner work')
                result=self.run_install(stage,'install')
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(target.read_bytes(),b'owner work');self.assertFalse((stage/'backups').exists())

    def test_later_owner_edit_blocks_rollback_before_any_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,data,_,_=self.fixture(Path(temporary))
            self.assertEqual(self.run_install(stage,'install').returncode,0)
            target=data/'fieldkit-v06/toolkit.js';target.write_bytes(b'later owner changes')
            html=(data/'fieldkit-v06/toolkit.html').read_bytes()
            self.assertNotEqual(self.run_install(stage,'rollback').returncode,0)
            self.assertEqual(target.read_bytes(),b'later owner changes')
            self.assertEqual((data/'fieldkit-v06/toolkit.html').read_bytes(),html)

    def test_symlink_and_hardlink_targets_refused(self):
        for kind in ('symlink','hardlink','payload-symlink'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);stage,data,_,_=self.fixture(root)
                target=(stage if kind=='payload-symlink' else data/'fieldkit-v06')/'toolkit.js'
                saved=root/'owner-file';saved.write_bytes(target.read_bytes());saved.chmod(target.stat().st_mode & 0o777)
                target.unlink()
                if kind=='hardlink':os.link(saved,target)
                else:target.symlink_to(saved)
                original=saved.read_bytes()
                self.assertNotEqual(self.run_install(stage,'install').returncode,0)
                self.assertFalse((stage/'backups').exists());self.assertEqual(saved.read_bytes(),original)

    def test_failure_mid_update_restores_only_known_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,data,old,_=self.fixture(Path(temporary))
            path=stage/'install.sh'
            # Inject failure after the first rename; automatic rollback runs
            # against exact old/new hashes, never an unrelated file.
            text=path.read_text().replace('        matches "$(after "$name")" "$path"',
                                         '        [ "$name" != toolkit.html ] || exit 1\n        matches "$(after "$name")" "$path"')
            path.write_text(text)
            (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
                                                  for p in sorted(stage.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
            result=self.run_install(stage,'install');self.assertNotEqual(result.returncode,0)
            self.assertEqual((stage/'STATUS').read_text(),'FAILED\n')
            for name,value in old.items():
                parent='fieldkit-performance-r1' if name=='bridge.js' else 'fieldkit-v06'
                self.assertEqual((data/parent/name).read_bytes(),value)

    def test_read_only_root_refuses_without_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);stage,data,_,_=self.fixture(root)
            (root/'mounts').write_text('/dev/root / ext3 ro,relatime,errors=continue,barrier=0,data=writeback 0 0\n')
            self.assertNotEqual(self.run_install(stage,'install').returncode,0)
            self.assertFalse((stage/'backups').exists())

    def test_package_allowlist_hashes_reproducibility_and_no_vendor_homepage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);one=root/'one.tar.gz';two=root/'two.tar.gz'
            report=package.build(one);package.build(two)
            self.assertEqual(one.read_bytes(),two.read_bytes())
            with self.assertRaises(ValueError):package.build(one)
            with tarfile.open(one) as archive:
                self.assertEqual(set(archive.getnames()),set(package.NAMES)|{'install.sh','MANIFEST.json','SHA256SUMS'})
                manifest=json.load(archive.extractfile('MANIFEST.json'))
                for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(),digest)
                script=archive.extractfile('install.sh').read().decode()
                for forbidden in ('fw_setenv','reboot','mount -','setUseServices','/mnt/storage'):
                    self.assertNotIn(forbidden,script)
                self.assertNotIn('index.html',archive.getnames())
                path=root/'syntax.sh';path.write_text(script);subprocess.run(['sh','-n',str(path)],check=True,capture_output=True)
            self.assertFalse(report['main_homepage_changed']);self.assertFalse(report['raw_firmware_write'])
