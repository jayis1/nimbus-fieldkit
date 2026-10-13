import base64
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout_parser',ROOT/'scripts/parse-sftp-layout.py')
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
policy=layout.policy


def pin(byte):return 'SHA256:'+base64.b64encode(bytes([byte])*32).decode().rstrip('=')


class SFTPLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fs=self.root/'fs';self.fs.mkdir(mode=0o755)
        self.proc=self.root/'proc';(self.proc/'self').mkdir(parents=True)
        self.sys=self.root/'sys';(self.sys/'class/block/mmcblk1p1').mkdir(parents=True)
        (self.sys/'class/block/mmcblk1p1/dev').write_text('179:17\n')
        for name,mode in policy.DIRECTORIES.items():
            path=self.fs/name.lstrip('/');path.mkdir(parents=True,exist_ok=True);path.chmod(mode[0] if isinstance(mode,tuple) else mode)
        for name in ('internal','sd'):(self.fs/(policy.JAIL+'/'+name).lstrip('/')).mkdir(mode=0o755)
        (self.fs/'bin').mkdir();(self.fs/'bin/false').write_text('unused fixture executable');(self.fs/'bin/false').chmod(0o755)
        self.passwd=self.fs/'etc/passwd'
        self.passwd.write_text('root:x:0:0:PRIVATE_GECOS:/root:/bin/sh\n'
                               'nimbus-files:x:2206:2206:PRIVATE_GECOS:/internal:/bin/false\n'
                               'nimbus-sshd:x:2207:2207:PRIVATE_GECOS:'+policy.STAGE+'/empty:/bin/false\n')
        self.group=self.fs/'etc/group';self.group.write_text('root:x:0:\nnimbus-files:x:2206:\nnimbus-sshd:x:2207:\n')
        raw=b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(range(32))
        self.public='ssh-ed25519 '+base64.b64encode(raw).decode()+'\n'
        authorized,_=policy.public_key(self.public)
        self.auth=self.fs/policy.AUTH.lstrip('/');self.auth.write_text(authorized);self.auth.chmod(0o644)
        self.hostkey=self.fs/(policy.STAGE+'/host-ed25519').lstrip('/')
        self.hostkey.write_text('PRIVATE_HOST_KEY_DO_NOT_READ_OR_HASH');self.hostkey.chmod(0o600)
        self.modules=self.proc/'modules';self.modules.write_text('wl12xx 123 0 - Live 0\n')
        self.mounts=self.proc/'self/mountinfo'
        self.mounts.write_text(f'41 20 179:4 / {self.fs}/mnt/storage rw,relatime - texfat /dev/mmcblk0p4 rw\n'
                              f'42 20 179:4 / {self.fs}{policy.JAIL}/internal ro,relatime - texfat /dev/mmcblk0p4 rw\n'
                              f'43 20 179:17 / {self.fs}/mnt/sdcard ro,relatime - texfat /dev/mmcblk1p1 ro\n'
                              f'44 20 179:17 / {self.fs}{policy.JAIL}/sd ro,relatime - texfat /dev/mmcblk1p1 ro\n')
        script=(ROOT/'device/ssh/sftp-layout-preflight.sh').read_text()
        script=script.replace("ROOT=''","ROOT="+str(self.fs)).replace('PROC=/proc','PROC='+str(self.proc)).replace('SYS=/sys','SYS='+str(self.sys))
        script=script.replace('[ "$(id -u)" = 0 ]','[ "$(id -u)" = '+str(os.getuid())+' ]')
        # Fixture files are user-owned. Do not confuse this stat substitution
        # with native root ownership qualification.
        script=script.replace("stat -c '%u %g %a %h %s %d %i'","stat -c '0 0 %a %h %s %d %i'")
        script=script.replace("stat -c '%u:%g:%a:%h'","stat -c '0:0:%a:%h'")
        self.script=self.root/'collector.sh';self.script.write_text(script)

    def collect(self,*args):
        return subprocess.run(['sh',str(self.script),*(args or ('--check',))],capture_output=True,text=True,timeout=10)

    def context(self):
        return {'effective_config':'\n'.join(name+' '+value for name,value in {**policy.POLICY,'listenaddress':'192.168.11.1:2226'}.items()),
                'listen_address':'192.168.11.1','client_public_key':self.public,'host_fingerprint':pin(1),
                'management_host_fingerprint':pin(2),'management_client_fingerprint':pin(3)}

    def test_collector_to_parser_to_policy_roundtrip_no_state_change_or_secret_output(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('PRIVATE_GECOS',result.stdout);self.assertNotIn('PRIVATE_HOST_KEY',result.stdout)
        self.assertNotIn(self.public.strip(),result.stdout)
        report=layout.parse(result.stdout);self.assertEqual(report['coherence'],'stable')
        self.assertFalse(report['sd_placeholder_empty'])
        observation=layout.assemble(report,self.context())
        checked=policy.validate(observation);self.assertTrue(checked['static_preconditions_pass'])
        self.assertFalse(checked['native_verified']);self.assertFalse(checked['listener_authorized'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_only_check_argument_allowed_and_syntax_valid(self):
        subprocess.run(['sh','-n',str(ROOT/'device/ssh/sftp-layout-preflight.sh')],check=True)
        for args in (('--start',),('--check','anything')):
            result=self.collect(*args);self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')

    def test_missing_unprovisioned_layout_is_observation_not_success(self):
        self.auth.unlink();self.hostkey.unlink()
        self.passwd.write_text('root:x:0:0:PRIVATE_GECOS:/root:/bin/sh\n')
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        report=layout.parse(result.stdout);self.assertIsNone(report['accounts']['nimbus-files'])
        self.assertEqual(report['metadata'][policy.AUTH]['kind'],'absent')
        with self.assertRaises(ValueError):layout.assemble(report,self.context())
        self.assertFalse(report['listener_authorized'])

    def test_export_active_skips_view_inspection_and_policy_refuses(self):
        self.modules.write_text('g_file_storage 24058 0 - Live 0\n')
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        report=layout.parse(result.stdout);self.assertEqual(report['usb_state'],'active')
        self.assertEqual(report['metadata'][policy.JAIL+'/internal']['kind'],'unknown')
        with self.assertRaises(ValueError):policy.validate(layout.assemble(report,self.context()))

    def test_proc_self_kernel_symlink_allowed(self):
        original=self.proc/'self';original.rename(self.proc/'fixture-pid');original.symlink_to('fixture-pid',target_is_directory=True)
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(layout.parse(result.stdout)['coherence'],'stable')

    def test_jail_ancestor_symlink_not_followed(self):
        stage=self.fs/policy.STAGE.lstrip('/');stage.rename(self.fs/'hidden-stage');stage.symlink_to(self.fs/'hidden-stage',target_is_directory=True)
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        report=layout.parse(result.stdout);self.assertEqual(report['metadata'][policy.STAGE]['kind'],'unsafe')
        with self.assertRaises(ValueError):policy.validate(layout.assemble(report,self.context()))

    def test_changed_module_inventory_cannot_claim_stable(self):
        script=self.script.read_text().replace('metadata_after=$(metadata)',
          'printf "g_file_storage 24058 0 - Live 0\\n" > "'+str(self.modules)+'"\nmetadata_after=$(metadata)')
        self.script.write_text(script)
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        report=layout.parse(result.stdout);self.assertEqual(report['coherence'],'changed')
        with self.assertRaises(ValueError):layout.assemble(report,self.context())

    def test_account_uid_group_collisions_and_extra_groups_refuse(self):
        cases=('uid-collision','gid-collision','extra-group','shared-group-member')
        passwd=self.passwd.read_text();group=self.group.read_text()
        for change in cases:
            self.passwd.write_text(passwd);self.group.write_text(group)
            if change=='uid-collision':self.passwd.write_text(passwd+'HIDDEN_USER:x:2206:2300:HIDDEN:/hidden:/bin/sh\n')
            elif change=='gid-collision':self.passwd.write_text(passwd+'HIDDEN_USER:x:2300:2206:HIDDEN:/hidden:/bin/sh\n')
            elif change=='extra-group':self.group.write_text(group+'HIDDEN_GROUP:x:27:nimbus-files\n')
            else:self.group.write_text(group.replace('nimbus-files:x:2206:','nimbus-files:x:2206:HIDDEN_USER'))
            result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('HIDDEN',result.stdout)
            with self.subTest(change=change),self.assertRaises(ValueError):policy.validate(layout.assemble(layout.parse(result.stdout),self.context()))

    def test_nested_mount_redacted_and_refused(self):
        with self.mounts.open('a') as stream:stream.write(f'45 20 179:4 /PRIVATE_ROOT {self.fs}/mnt/storage/PRIVATE_NAME ro - texfat /dev/mmcblk0p4 rw\n')
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('PRIVATE_ROOT',result.stdout);self.assertNotIn('PRIVATE_NAME',result.stdout)
        report=layout.parse(result.stdout);self.assertTrue(report['unexpected_mounts'])
        with self.assertRaises(ValueError):layout.assemble(report,self.context())

    def test_optional_absent_sd_requires_empty_placeholder(self):
        self.mounts.write_text('\n'.join(line for line in self.mounts.read_text().splitlines() if line.startswith(('41 ','42 ')))+'\n')
        result=self.collect();report=layout.parse(result.stdout)
        self.assertTrue(report['sd_placeholder_empty'])
        self.assertTrue(policy.validate(layout.assemble(report,self.context()))['static_preconditions_pass'])
        (self.fs/(policy.JAIL+'/sd/leftover').lstrip('/')).write_text('PRIVATE_DATA')
        report=layout.parse(self.collect().stdout);self.assertFalse(report['sd_placeholder_empty'])
        with self.assertRaises(ValueError):policy.validate(layout.assemble(report,self.context()))

    def test_private_key_never_passed_to_hasher(self):
        marker=self.root/'forbidden-private-read'
        tool=self.root/'sha-wrapper'
        tool.write_text(f'#!/bin/sh\ncase "$1" in */host-ed25519) printf forbidden > "{marker}"; exit 99;; esac\nexec /usr/bin/sha256sum "$@"\n');tool.chmod(0o755)
        self.script.write_text(self.script.read_text().replace('SHA=/usr/bin/sha256sum','SHA='+str(tool)))
        result=self.collect();self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists())

    def test_authorized_key_checksum_binds_observed_file_to_enrollment(self):
        self.auth.write_text(self.auth.read_text().replace('restrict ','no-pty '))
        report=layout.parse(self.collect().stdout)
        with self.assertRaises(ValueError):layout.assemble(report,self.context())

    def test_parser_rejects_partial_duplicate_unknown_or_forged_stable_evidence(self):
        text=self.collect().stdout
        for altered in (text.removesuffix('NIMBUS-SFTP-LAYOUT-END 2\n'),text.replace('BEFORE\n','BEFORE\nUSB inactive\n'),
                        text.replace('EMPTY privsep yes\n','EMPTY privsep yes\nEMPTY privsep yes\n'),
                        text.replace('BLOCK sd 179:17','BLOCK sd invalid'),text+'extra\n',text.replace('USB inactive','USB inactive\r')):
            with self.subTest(altered=altered[:40]),self.assertRaises(ValueError):layout.parse(altered)
        altered=text.replace('AFTER\nNODE root directory','AFTER\nNODE root absent\nNODE root directory')
        with self.assertRaises(ValueError):layout.parse(altered)

    def test_context_cannot_override_collected_metadata_or_ownership(self):
        report=layout.parse(self.collect().stdout);context=self.context();context['usb_state']='inactive'
        with self.assertRaises(ValueError):layout.assemble(report,context)
        before=copy.deepcopy(report);layout.assemble(report,self.context());self.assertEqual(report,before)

    def test_wrong_role_home_is_redacted_and_refused(self):
        text=self.passwd.read_text().replace(policy.STAGE+'/empty','/PRIVATE_WRONG_HOME')
        self.passwd.write_text(text)
        result=self.collect();self.assertNotIn('PRIVATE_WRONG_HOME',result.stdout)
        report=layout.parse(result.stdout)
        self.assertEqual(report['accounts']['nimbus-sshd']['home'],'unqualified')
        with self.assertRaises(ValueError):policy.validate(layout.assemble(report,self.context()))

    def test_legacy_present_accounts_without_home_evidence_cannot_qualify(self):
        text=self.collect().stdout.replace('NIMBUS-SFTP-LAYOUT-BEGIN 2','NIMBUS-SFTP-LAYOUT-BEGIN 1').replace('NIMBUS-SFTP-LAYOUT-END 2','NIMBUS-SFTP-LAYOUT-END 1')
        text='\n'.join(' '.join(line.split()[:-1]) if line.startswith('ACCOUNT ') and ' present ' in line else line for line in text.splitlines())+'\n'
        report=layout.parse(text)
        self.assertEqual(report['accounts']['nimbus-files']['home'],'unqualified')
        with self.assertRaises(ValueError):policy.validate(layout.assemble(report,self.context()))

    def test_malformed_or_missing_inventory_returns_no_complete_frame(self):
        self.mounts.write_text('malformed mount line\n')
        result=self.collect();self.assertNotEqual(result.returncode,0)
        with self.assertRaises(ValueError):layout.parse(result.stdout)

    def test_collector_has_no_state_changing_or_candidate_exec_actions(self):
        text=(ROOT/'device/ssh/sftp-layout-preflight.sh').read_text()
        for forbidden in ('mkdir ','chmod ','chown ','mount -','umount ','rmmod ','modprobe ','sshd -','ssh-keygen ','/etc/shadow','kill ','setUseServices'):
            self.assertNotIn(forbidden,text)
