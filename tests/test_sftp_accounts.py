import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sftp_account_plan',ROOT/'scripts/prepare-sftp-accounts.py')
accounts=importlib.util.module_from_spec(spec);spec.loader.exec_module(accounts)
spec=importlib.util.spec_from_file_location('sftp_account_audit',ROOT/'scripts/audit-sftp-account-policy.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
HEADER='#define HAVE_SHADOW_H 1\n#define HAS_SHADOW_EXPIRE 1\n#define LOCKED_PASSWD_PREFIX "!"\n#define SSH_PRIVSEP_USER "nimbus-sshd"\n'
PASSWD=b'root:x:0:0:private fixture:/root:/bin/sh\nadmin:x:1002:1002:unchanged fixture:/var/ftp:/bin/sh\n'
GROUP=b'root:x:0:\nadmin:x:1002:\n'
SHADOW=b'root:!:20000:0:99999:7:::\nadmin:PRIVATE_FIXTURE_HASH:20000:0:99999:7:::\n'


class SFTPAccountPlanTests(unittest.TestCase):
    def setUp(self):
        # Synthetic header pin for unit fixtures, never a runtime attestation.
        p=patch.object(accounts,'CONFIG_HEADER_SHA256',hashlib.sha256(HEADER.encode()).hexdigest());p.start();self.addCleanup(p.stop)

    def plan(self,**changes):
        data={'passwd':PASSWD,'group':GROUP,'shadow':SHADOW,'header':HEADER};data.update(changes)
        return accounts.plan(**data)

    def test_append_only_existing_bytes_and_distinct_roles(self):
        files,record=self.plan()
        for name,data in (('passwd',PASSWD),('group',GROUP),('shadow',SHADOW)):
            self.assertTrue(files[name].startswith(data))
            self.assertEqual(record['before'][name],hashlib.sha256(data).hexdigest())
            self.assertEqual(record['after'][name],hashlib.sha256(files[name]).hexdigest())
        self.assertIn(b'nimbus-files:x:2206:2206:',files['passwd'])
        self.assertIn(b'/internal:/bin/false\n',files['passwd'])
        self.assertIn((accounts.STAGE+'/empty:/bin/false\n').encode(),files['passwd'])
        self.assertTrue(files['shadow'].endswith(b'nimbus-files:*:1::::::\nnimbus-sshd:!:1::::::\n'))
        self.assertEqual(record['proposed_write_order'],['group','shadow','passwd'])
        self.assertEqual(record['proposed_rollback_order'],['passwd','shadow','group'])
        for flag in ('existing_accounts_modified','password_authentication_enabled','installer_supplied','device_accounts_created',
                     'native_auth_verified','reset_persistence_verified','listener_authorized','production_ready','flash_authorized'):
            self.assertFalse(record[flag])
        self.assertNotIn('PRIVATE_FIXTURE_HASH',json.dumps(record))

    def test_no_uid_gid_collision_or_root_shared_id(self):
        for change in ({'files_uid':0},{'files_uid':1002},{'files_uid':True},{'files_uid':2207},
                       {'privsep_uid':65534},{'group':GROUP+b'existing:x:2206:\n'},
                       {'passwd':PASSWD+b'existing:x:2300:2207::/existing:/bin/sh\n'}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):self.plan(**change)

    def test_explicit_alternative_collision_free_ids(self):
        files,record=self.plan(files_uid=3206,privsep_uid=3207)
        self.assertIn(b'nimbus-files:x:3206:3206:',files['passwd']);self.assertEqual(record['ids']['nimbus-sshd'],3207)

    def test_valid_empty_existing_shell_is_preserved_not_used_for_new_roles(self):
        baseline=PASSWD+b'existing:x:2300:2300::/existing:\n'
        files,_=self.plan(passwd=baseline)
        self.assertTrue(files['passwd'].startswith(baseline))
        self.assertEqual(files['passwd'][len(baseline):].count(b':/bin/false\n'),2)

    def test_existing_numeric_group_names_are_preserved_and_gid_collisions_detected(self):
        baseline=GROUP+b'2300:x:2300:\n'
        files,_=self.plan(group=baseline);self.assertTrue(files['group'].startswith(baseline))
        with self.assertRaises(ValueError):self.plan(group=GROUP+b'2206:x:2206:\n')

    def test_preexisting_roles_in_any_table_refuse_instead_of_unlock_or_repair(self):
        for change in ({'passwd':PASSWD+b'nimbus-files:x:2206:2206::/internal:/bin/false\n'},
                       {'group':GROUP+b'nimbus-sshd:x:2207:\n'},
                       {'shadow':SHADOW+b'nimbus-files:!:1::::::\n'}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):self.plan(**change)

    def test_stale_membership_and_duplicate_or_malformed_tables_refuse(self):
        for change in ({'group':GROUP+b'wheel:x:27:nimbus-files\n'}, {'passwd':PASSWD+PASSWD.splitlines()[0]+b'\n'},
                       {'shadow':SHADOW[:-1]}, {'group':GROUP+b'bad:entry\n'}, {'passwd':PASSWD+b'bad:name:uid:0::/home:/bin/sh\n'},
                       {'shadow':SHADOW+b'new:!:not-a-day::::::\n'}, {'group':GROUP+b'new:x:2300:member,,other\n'}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):self.plan(**change)

    def test_missing_root_or_changed_unreviewed_header_refuse(self):
        with self.assertRaises(ValueError):self.plan(passwd=PASSWD.splitlines(keepends=True)[1])
        with self.assertRaises(ValueError):self.plan(header=HEADER.replace('"!"','"*"'))
        with self.assertRaises(ValueError):self.plan(header=HEADER+'#define DISABLE_SHADOW 1\n')

    def test_private_stage_modes_no_overwrite_and_no_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);private=root/'private';inputs={}
            for name,data in (('passwd',PASSWD),('group',GROUP),('shadow',SHADOW)):
                path=root/name;path.write_bytes(data);path.chmod(0o600);inputs[name]=path
            with patch.object(accounts,'PRIVATE',private),patch('subprocess.run') as run:
                record=accounts.prepare(private/'new',inputs,HEADER)
                run.assert_not_called();output=private/'new'
                self.assertEqual(output.stat().st_mode&0o777,0o700)
                self.assertTrue(all(path.stat().st_mode&0o777==0o600 for path in output.iterdir()))
                self.assertEqual(set(path.name for path in output.iterdir()),{'passwd','group','shadow','ACCOUNT-PLAN.json','NOT-INSTALLED.txt'})
                self.assertFalse(record['device_accounts_created'])
                before={p.name:p.read_bytes() for p in output.iterdir()}
                with self.assertRaises(FileExistsError):accounts.prepare(output,inputs,HEADER)
                self.assertEqual(before,{p.name:p.read_bytes() for p in output.iterdir()})

    def test_private_input_link_permission_and_output_escape_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'shadow';path.write_bytes(SHADOW);path.chmod(0o644)
            with self.assertRaises(ValueError):accounts.read_private(path)
            path.chmod(0o600);alias=root/'alias';alias.symlink_to(path)
            with self.assertRaises(ValueError):accounts.read_private(alias)
            alias.unlink();os.link(path,alias)
            with self.assertRaises(ValueError):accounts.read_private(path)
            with patch.object(accounts,'PRIVATE',root/'private'):
                with self.assertRaises(ValueError):accounts.prepare(root/'public',{},HEADER)

    def test_write_failure_retains_private_stage_without_success_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs={}
            for name,data in (('passwd',PASSWD),('group',GROUP),('shadow',SHADOW)):
                path=root/name;path.write_bytes(data);path.chmod(0o600);inputs[name]=path
            with patch.object(accounts,'PRIVATE',root/'private'),patch.object(accounts.os,'fsync',side_effect=OSError('fixture failure')):
                with self.assertRaises(OSError):accounts.prepare(root/'private/new',inputs,HEADER)
            self.assertTrue((root/'private/new').is_dir());self.assertFalse((root/'private/new/ACCOUNT-PLAN.json').exists())

    def test_wrong_source_archive_or_symlink_refused_without_commands(self):
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            root=Path(temporary);path=root/'wrong-source';path.write_bytes(b'not reviewed source')
            header=root/'header';header.write_text(HEADER)
            with self.assertRaises(ValueError):audit.review(path,header)
            alias=root/'alias';alias.symlink_to(path)
            with self.assertRaises(ValueError):audit.review(alias,header)
            run.assert_not_called()


class RetainedAccountSourceTests(unittest.TestCase):
    base=ROOT/'build/nimbus-sftp-account-review-v1'

    def test_preserved_source_and_actual_runtime_header_hashes(self):
        if not self.base.exists():self.skipTest('Local account-source review absent')
        record=json.loads((self.base/'REVIEW.json').read_text())
        self.assertEqual(record['source_archive_sha256'],'a9dc9565dffe8640f64d863cd29a32bc4a3dbdec0566a7fc44c5d6ee767d5f39')
        self.assertEqual(set(record['files']),set(audit.SELECTED)|{'config.h'})
        for name in (*audit.SELECTED,'config.h'):
            self.assertEqual(hashlib.sha256((self.base/name).read_bytes()).hexdigest(),record['files'][name])
        checked=accounts.verify_build_account_rules((self.base/'config.h').read_text())
        self.assertTrue(checked['file_marker_not_locked_by_reviewed_prefix']);self.assertFalse(checked['native_auth_verified'])

    @unittest.skipUnless(shutil.which('gcc'),'Host C compiler unavailable')
    def test_exact_upstream_locked_account_function_with_synthetic_shadow(self):
        if not self.base.exists():self.skipTest('Local account-source review absent')
        record=json.loads((self.base/'REVIEW.json').read_text())
        text=(self.base/'platform.c').read_text()
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),record['files']['platform.c'])
        start=text.index('int\nplatform_locked_account(struct passwd *pw)')
        ending='return locked;\n}'
        end=text.index(ending,start)+len(ending)
        function=text[start:end]
        # Compile the exact reviewed function, not a Python imitation. Shadow
        # lookups are synthetic; this is NOT target libc/native login evidence.
        source='''#include <string.h>
#include <stdio.h>
#define USE_SHADOW 1
#define HAS_SHADOW_EXPIRE 1
#define LOCKED_PASSWD_PREFIX "!"
#define debug3_f(...) ((void)0)
struct passwd {char *pw_name;char *pw_passwd;};
struct spwd {char *sp_pwdp;};
static struct spwd shadow;
static struct spwd *getspnam(const char *name) {(void)name;return &shadow;}
static int auth_shadow_acctexpired(struct spwd *sp) {(void)sp;return 0;}
'''+function+'''
int main(int argc,char **argv) {
 struct passwd account={"fixture","x"};
 if(argc!=2)return 2;
 shadow.sp_pwdp=argv[1];
 printf("%d\\n",platform_locked_account(&account));return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'rule.c';binary=root/'rule';path.write_text(source)
            subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',str(path),'-o',str(binary)],check=True,capture_output=True,timeout=15)
            for marker,expected in (('!',1),('!!',1),('!placeholder',1),('*',0)):
                with self.subTest(marker=marker):
                    result=subprocess.run([str(binary),marker],check=True,capture_output=True,text=True,timeout=5)
                    self.assertEqual(result.stdout,str(expected)+'\n')
