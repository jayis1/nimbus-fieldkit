import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fieldkit_icon', ROOT/'scripts/package-fieldkit-icon.py')
icon=importlib.util.module_from_spec(spec);spec.loader.exec_module(icon)


class FieldKitIconTests(unittest.TestCase):
    def test_exact_append_only_css_and_installer_syntax(self):
        css=(ROOT/'device/unified/stock-dark.css').read_bytes()
        self.assertEqual(hashlib.sha256(css.split(icon.MARKER,1)[0]).hexdigest(),icon.BEFORE)
        subprocess.run(['sh','-n'],input=icon.installer('0'*64).encode(),check=True)

    def test_guarded_install_rollback_and_later_edit_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);stage=base/'stage';stage.mkdir(mode=0o700)
            package=base/'icon.tar';report=icon.build(package)
            with tarfile.open(package) as archive:
                for member in archive:(stage/member.name).write_bytes(archive.extractfile(member).read())
            new=(stage/'stock-dark.css').read_bytes();old=new.split(icon.MARKER,1)[0]
            target=base/'style.css';target.write_bytes(old)
            script=(stage/'install.sh').read_text().replace('/root/nimbus-fieldkit-icon-r1',str(stage))
            script=script.replace('TARGET=/nimbus/data/fieldkit-v06/stock-dark.css','TARGET="'+str(target)+'"')
            script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
            path=stage/'fixture.sh';path.write_text(script)
            target.write_bytes(b'unexpected baseline')
            self.assertNotEqual(subprocess.run(['sh',str(path),'install'],capture_output=True).returncode,0)
            self.assertFalse((stage/'backups').exists())
            target.write_bytes(old)
            subprocess.run(['sh',str(path),'install'],capture_output=True,check=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),report['after_sha256'])
            target.write_bytes(b'later styling')
            self.assertNotEqual(subprocess.run(['sh',str(path),'rollback'],capture_output=True).returncode,0)
            self.assertEqual(target.read_bytes(),b'later styling')
            target.write_bytes(new)
            subprocess.run(['sh',str(path),'rollback'],capture_output=True,check=True)
            self.assertEqual(target.read_bytes(),old)
