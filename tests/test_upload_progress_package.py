import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('progress_package',ROOT/'scripts/package-upload-progress.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


class ProgressPackageTests(unittest.TestCase):
    def test_installer_syntax_and_rollback_scope(self):
        script=package.installer('0'*64,package.BASELINES['r1'])
        subprocess.run(['sh','-n'],input=script.encode(),check=True)
        rollback=script.split(' rollback)',1)[1]
        self.assertNotIn('cp -p',rollback)
        self.assertIn('replace_css backups/stock-dark.css',rollback)
        self.assertIn('"$CSS" > installed.sha256',script)

    def test_fixture_installs_and_restores_both_ui_assets_without_clobbering_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);stage=base/'stage';stage.mkdir(mode=0o700)
            data=base/'web';(data/'fieldkit-v06').mkdir(parents=True)
            before=b'fixture original homepage';after=b'fixture updated homepage'
            old_css=(ROOT/'device/unified/stock-dark.css').read_bytes().split(b'/* The vendor mounts',1)[0]
            new_css=(ROOT/'device/unified/stock-dark.css').read_bytes()
            (data/'index.html').write_bytes(before);css=data/'fieldkit-v06/stock-dark.css';css.write_bytes(old_css)
            script=package.installer(hashlib.sha256(after).hexdigest(),package.BASELINES['r1']).replace(package.INDEX,hashlib.sha256(before).hexdigest())
            (stage/'install.sh').write_text(script)
            (stage/'index.html').write_bytes(after);(stage/'stock-dark.css').write_bytes(new_css)
            (stage/'upload-progress.js').write_bytes((ROOT/'device/unified/upload-progress.js').read_bytes())
            (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('install.sh','index.html','stock-dark.css','upload-progress.js')))
            script=script.replace('/root/nimbus-upload-progress-r1',str(stage)).replace('DATA=/nimbus/data','DATA="'+str(data)+'"')
            script=script.replace('[ "$(id -u)" = 0 ]',':').replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'")
            path=stage/'fixture.sh';path.write_text(script)
            subprocess.run(['sh',str(path),'install'],capture_output=True,check=True)
            self.assertEqual(css.read_bytes(),new_css)
            css.write_bytes(b'user styling')
            self.assertNotEqual(subprocess.run(['sh',str(path),'rollback'],capture_output=True).returncode,0)
            self.assertEqual((stage/'backups/stock-dark.css').read_bytes(),old_css)
            css.write_bytes(new_css)
            subprocess.run(['sh',str(path),'rollback'],capture_output=True,check=True)
            self.assertEqual(css.read_bytes(),old_css);self.assertEqual((data/'index.html').read_bytes(),before)
