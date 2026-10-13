import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sftp_probe_package',ROOT/'scripts/package-sftp-probe-trial.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
NATIVE_HASH='c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2'
RAW='{"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":false,"scope":"process_compatibility_only"}'
FALLBACK=RAW.replace('"poll_with_nofile_zero":false','"poll_with_nofile_zero":true')


class SFTPProbeTrialTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/'stage';stage.mkdir(mode=0o700)
        proc=root/'proc';(proc/'self').mkdir(parents=True)
        (proc/'modules').write_text('')
        (proc/'mounts').write_text('none /tmp tmpfs rw,relatime 0 0\n')
        (proc/'self/mountinfo').write_text('1 0 179:2 / / rw - ext3 /dev/root rw\n')
        dev=root/'dev-id';dev.write_text('179:2\n')
        power=root/'power';power.write_text('1\n')
        events=root/'events'
        tools={'sshd':'[ "$#" = 1 ] && [ "$1" = -V ] || exit 9\nprintf "%s\\n" "OpenSSH_10.6p1, without OpenSSL" >&2',
               'rlimit-compat-probe':"[ \"$#\" = 0 ] || exit 9\nprintf '%s\\n' '"+RAW+"'",
               'rlimit-select-compat-probe':"[ \"$#\" = 0 ] || exit 9\nprintf '%s\\n' '"+FALLBACK+"'"}
        for name,body in tools.items():
            path=stage/name;path.write_text('#!/bin/sh\nprintf "%s\\n" '+name+' >> "'+str(events)+'"\n'+body+'\n');path.chmod(0o600)
        source=(ROOT/'device/ssh/sftp-runtime-probe-trial.sh').read_text()
        source=source.replace('/tmp/nimbus-sftp-probe-r1',str(stage))
        source=source.replace('[ "$(id -u)" = 0 ]','[ "$(id -u)" = '+str(os.getuid())+' ]')
        source=source.replace('$(uname -m)','armv7l')
        source=source.replace("stat -c '%u:%g:%a'","stat -c '0:0:%a'").replace("stat -c '%u:%g:%a:%h'","stat -c '0:0:%a:%h'")
        for old,new in (('/proc/self/mountinfo',proc/'self/mountinfo'),('/proc/mounts',proc/'mounts'),('/proc/modules',proc/'modules'),
                        ('/sys/class/block/mmcblk0p2/dev',dev),('/sys/class/power_supply/mc13892_charger/online',power)):
            source=source.replace(old,str(new))
        source=source.replace(NATIVE_HASH,hashlib.sha256(Path('/usr/bin/sha256sum').read_bytes()).hexdigest())
        for name,digest in package.PINS.items():source=source.replace(digest,hashlib.sha256((stage/name).read_bytes()).hexdigest())
        (stage/'trial.sh').write_text(source);(stage/'trial.sh').chmod(0o600)
        (stage/'MANIFEST.json').write_text('{}\n');(stage/'MANIFEST.json').chmod(0o600)
        (stage/'SHA256SUMS').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n' for path in sorted(stage.iterdir())))
        (stage/'SHA256SUMS').chmod(0o600)
        return stage,proc,power,events

    def run_trial(self,stage,mode):
        return subprocess.run(['sh',str(stage/'trial.sh'),mode],capture_output=True,text=True,timeout=10)

    def test_check_never_executes_or_changes_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,_,_,events=self.fixture(Path(temporary))
            result=self.run_trial(stage,'--check');self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('no-runtime-executed',result.stdout);self.assertFalse(events.exists());self.assertFalse((stage/'CLAIM').exists())
            self.assertTrue(all((stage/name).stat().st_mode&0o777==0o600 for name in package.PINS))

    def test_exact_three_probe_commands_only_and_no_service_certification(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,_,_,events=self.fixture(Path(temporary))
            result=self.run_trial(stage,'--run');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(events.read_text().splitlines(),list(package.PINS))
            self.assertIn('service_qualified=no flash_authorized=no',result.stdout)
            self.assertEqual((stage/'CLAIM').read_text(),'ATTEMPTED\n')
            self.assertNotEqual(self.run_trial(stage,'--run').returncode,0)
            self.assertEqual(len(events.read_text().splitlines()),3)

    def test_export_or_missing_power_refuses_before_claim_or_execution(self):
        for change in ('usb','power'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temporary:
                stage,proc,power,events=self.fixture(Path(temporary))
                if change=='usb':(proc/'modules').write_text('g_file_storage 1 0 - Live 0\n')
                else:power.write_text('0\n')
                self.assertNotEqual(self.run_trial(stage,'--run').returncode,0)
                self.assertFalse(events.exists());self.assertFalse((stage/'CLAIM').exists())

    def test_tampered_symlink_or_prior_claim_refuses(self):
        for change in ('changed','symlink','claim'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);stage,_,_,events=self.fixture(root)
                path=stage/'sshd'
                if change=='changed':path.write_bytes(b'owner edits')
                elif change=='symlink':path.rename(root/'owner');path.symlink_to(root/'owner')
                else:(stage/'CLAIM').write_text('retain prior attempt')
                self.assertNotEqual(self.run_trial(stage,'--run').returncode,0);self.assertFalse(events.exists())

    def test_invalid_action_never_executes(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage,_,_,events=self.fixture(Path(temporary))
            self.assertNotEqual(self.run_trial(stage,'--start').returncode,0);self.assertFalse(events.exists())

    def test_package_is_reproducible_pinned_allowlist_and_never_executes_arm(self):
        runtime=ROOT/'build/nimbus-sftp-runtime-v1/runtime'
        if not runtime.exists():self.skipTest('Retained ARM runtime absent')
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            root=Path(temporary);first=root/'first.tar.gz';second=root/'second.tar.gz'
            record=package.build(first);package.build(second);run.assert_not_called()
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with tarfile.open(first) as archive:
                self.assertEqual(set(archive.getnames()),set(package.PINS)|{'trial.sh','MANIFEST.json','SHA256SUMS'})
                manifest=json.load(archive.extractfile('MANIFEST.json'))
                for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(),digest)
                self.assertTrue(all(member.mode==0o600 and member.isfile() for member in archive.getmembers()))
            self.assertEqual(record['runtime_bytes'],795048);self.assertTrue(record['approval_required']);self.assertFalse(record['native_verified'])
            with self.assertRaises(ValueError):package.build(first)

    def test_changed_runtime_refuses_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);runtime=root/'runtime';runtime.mkdir()
            for name in package.PINS:(runtime/name).write_bytes(b'wrong ELF')
            with self.assertRaises(ValueError):package.build(root/'trial.tar.gz',runtime)
            self.assertFalse((root/'trial.tar.gz').exists())

    def test_trial_syntax_and_no_listener_keygen_account_mount_actions(self):
        path=ROOT/'device/ssh/sftp-runtime-probe-trial.sh'
        subprocess.run(['sh','-n',str(path)],check=True)
        text=path.read_text()
        for forbidden in ('sshd -D','sshd -f','ssh-keygen','useradd','/etc/passwd','mount -','umount ','rmmod ','kill ','setUseServices','authorized_keys'):
            self.assertNotIn(forbidden,text)
