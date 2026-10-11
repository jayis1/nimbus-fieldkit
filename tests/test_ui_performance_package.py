import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('performance_package',ROOT/'scripts/package-ui-performance.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


class UIPerformancePackageTests(unittest.TestCase):
    def fixture(self,base):
        stage=base/'stage';stage.mkdir(mode=0o700)
        web=base/'web';web.mkdir()
        before=b'fixture installed homepage';after=b'fixture performance homepage'
        (web/'index.html').write_bytes(before)
        script=package.installer(hashlib.sha256(after).hexdigest()).replace(package.BEFORE,hashlib.sha256(before).hexdigest())
        for name,digest in package.OLD_ASSETS.items():
            data=('fixture original '+name).encode();path=web/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
            script=script.replace(digest,hashlib.sha256(data).hexdigest())
        script=script.replace('/root/nimbus-ui-performance-r1',str(stage)).replace('DATA=/nimbus/data','DATA="'+str(web)+'"')
        script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
        (stage/'install.sh').write_text(script);(stage/'index.html').write_bytes(after)
        for name in ('bridge.js','upload-progress.js','mascot.js'):(stage/name).write_bytes((ROOT/'device/unified'/name).read_bytes())
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('install.sh','index.html','bridge.js','upload-progress.js','mascot.js')))
        return stage,web,before,after

    def run_install(self,stage,mode='install'):
        return subprocess.run(['sh',str(stage/'install.sh'),mode],capture_output=True,text=True,timeout=10)

    def test_install_and_rollback_preserve_original_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            stage,web,before,after=self.fixture(Path(folder))
            originals={name:(web/name).read_bytes() for name in package.OLD_ASSETS}
            result=self.run_install(stage);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((web/'index.html').read_bytes(),after)
            for name,data in originals.items():self.assertEqual((web/name).read_bytes(),data)
            self.assertEqual(len(list((web/'fieldkit-performance-r1').iterdir())),3)
            result=self.run_install(stage,'rollback');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((web/'index.html').read_bytes(),before)
            self.assertTrue((web/'fieldkit-performance-r1').exists())

    def test_changed_original_asset_or_homepage_refuses_before_install(self):
        for target in ('index.html',*package.OLD_ASSETS):
            with tempfile.TemporaryDirectory() as folder:
                stage,web,before,after=self.fixture(Path(folder));(web/target).write_bytes(b'later user work')
                self.assertNotEqual(self.run_install(stage).returncode,0)
                self.assertFalse((stage/'backups').exists())
                self.assertFalse((web/'fieldkit-performance-r1').exists())

    def test_rollback_refuses_later_ui_edits_or_changed_original_assets(self):
        for target in ('index.html','fieldkit-performance-r1/mascot.js','fieldkit-v06/bridge.js'):
            with tempfile.TemporaryDirectory() as folder:
                stage,web,before,after=self.fixture(Path(folder))
                self.assertEqual(self.run_install(stage).returncode,0)
                (web/target).write_bytes(b'later user work')
                self.assertNotEqual(self.run_install(stage,'rollback').returncode,0)
                self.assertEqual((web/target).read_bytes(),b'later user work')

    def test_syntax_and_bounded_private_package_scope(self):
        subprocess.run(['sh','-n'],input=package.installer('0'*64).encode(),check=True)
        baseline=ROOT/'build/nimbus-mascot-ui-r1.tar'
        if not baseline.exists():self.skipTest('Private installed baseline unavailable')
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'performance.tar';report=package.build(baseline,output)
            self.assertFalse(report['public_redistribution']);self.assertFalse(report['throughput_speedup_claimed'])
            with tarfile.open(baseline) as old,tarfile.open(output) as new:
                page=new.extractfile('index.html').read()
                for name in package.OLD_ASSETS:
                    page=page.replace(b'/data/fieldkit-performance-r1/'+name.split('/')[-1].encode(),b'/data/'+name.encode())
                self.assertEqual(page,old.extractfile('index.html').read())
                self.assertEqual(set(new.getnames()),{'index.html','install.sh','bridge.js','upload-progress.js','mascot.js','MANIFEST.json','SHA256SUMS'})
                self.assertIn(b'/data/fieldkit-v06/',new.extractfile('bridge.js').read())
            with self.assertRaises(ValueError):package.build(baseline,output)
