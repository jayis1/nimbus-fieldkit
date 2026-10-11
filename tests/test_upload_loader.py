import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upload_loader',ROOT/'scripts/package-upload-loader.py')
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)


class UploadLoaderTests(unittest.TestCase):
    def test_append_only_and_reduced_motion_and_no_transport(self):
        css=(ROOT/'device/unified/stock-dark.css').read_bytes()
        self.assertEqual(hashlib.sha256(css.split(b'/* Upload/busy card:',1)[0]).hexdigest(),loader.BEFORE)
        self.assertIn(b'prefers-reduced-motion:reduce',css)
        self.assertNotIn(b'display:flex!important',css) # Must not override the vendor hidden state.
        self.assertNotIn(b'progressbar',css)
        subprocess.run(['sh','-n'],input=loader.installer('0'*64).encode(),check=True)

    def test_install_rollback_and_later_style_refusal_on_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);stage=base/'stage';stage.mkdir(mode=0o700)
            package=base/'package.tar';report=loader.build(package)
            with tarfile.open(package) as archive:
                for member in archive:(stage/member.name).write_bytes(archive.extractfile(member).read())
            new=(stage/'stock-dark.css').read_bytes();old=new.split(b'/* Upload/busy card:',1)[0]
            target=base/'styles.css';target.write_bytes(old)
            script=(stage/'install.sh').read_text().replace('/root/nimbus-upload-loader-r1',str(stage))
            script=script.replace('TARGET=/nimbus/data/fieldkit-v06/stock-dark.css','TARGET="'+str(target)+'"')
            script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
            path=stage/'fixture.sh';path.write_text(script)
            subprocess.run(['sh',str(path),'install'],capture_output=True,check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),report['after_sha256'])
            target.write_bytes(b'later user styling')
            self.assertNotEqual(subprocess.run(['sh',str(path),'rollback'],capture_output=True).returncode,0)
            self.assertEqual(target.read_bytes(),b'later user styling')
            target.write_bytes(new)
            subprocess.run(['sh',str(path),'rollback'],capture_output=True,check=True)
            self.assertEqual(target.read_bytes(),old)

    def test_r2_uses_exact_r1_baseline_and_separate_stage(self):
        css=(ROOT/'device/unified/stock-dark.css').read_bytes()
        self.assertEqual(hashlib.sha256(css.split(b'/* The vendor mounts',1)[0]).hexdigest(),loader.R1)
        with tempfile.TemporaryDirectory() as folder:
            report=loader.build(Path(folder)/'r2.tar',from_r1=True)
        self.assertEqual(report['before_sha256'],loader.R1)
        script=loader.installer(report['after_sha256'],from_r1=True)
        self.assertIn('/root/nimbus-upload-loader-r2',script)
        self.assertIn(loader.R1,script)
        self.assertNotIn(loader.BEFORE,script)
