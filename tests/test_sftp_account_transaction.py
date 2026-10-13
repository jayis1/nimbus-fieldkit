import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


model=load('transaction_model','scripts/sftp-account-transaction-model.py')
audit=load('writer_audit','scripts/audit-sftp-account-writers.py')
HEADER='#define HAVE_SHADOW_H 1\n#define HAS_SHADOW_EXPIRE 1\n#define LOCKED_PASSWD_PREFIX "!"\n#define SSH_PRIVSEP_USER "nimbus-sshd"\n'


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.baseline={'passwd':b'root:x:0:0::/root:/bin/sh\nvendor:x:100:100::/home/vendor:\n',
                       'group':b'root:x:0:\nvendor:x:100:\n',
                       'shadow':b'root:!:1::::::\nvendor:!:1::::::\n'}
        # Synthetic pin for unit fixtures only, never native/build attestation.
        fixture_pin=patch.object(model.planner,'CONFIG_HEADER_SHA256',hashlib.sha256(HEADER.encode()).hexdigest())
        fixture_pin.start();self.addCleanup(fixture_pin.stop)
        self.header=HEADER
        self.proposed,_=model.planner.plan(**self.baseline,header=self.header)

    def rollback(self,current):return model.rollback_model(current,self.baseline,self.proposed,self.header)

    def test_commit_requires_exact_current_inputs_and_no_permission_to_write(self):
        result=model.commit_model(self.baseline,self.baseline,self.proposed,self.header)
        self.assertEqual(result['order'],('group','shadow','passwd'))
        self.assertFalse(result['installer_supplied']);self.assertFalse(result['writer_exclusion_verified'])
        changed={**self.baseline,'shadow':self.baseline['shadow'].replace(b'vendor:!',b'vendor:*')}
        with self.assertRaises(ValueError):model.commit_model(changed,self.baseline,self.proposed,self.header)

    def test_every_whole_table_commit_prefix_can_be_reversed(self):
        for count in range(4):
            with self.subTest(count=count):
                current=dict(self.baseline)
                for name in model.COMMIT_ORDER[:count]:current[name]=self.proposed[name]
                result=self.rollback(current)
                self.assertEqual(result['candidate_tables'],self.baseline)
                self.assertEqual(result['order'],tuple(reversed(model.COMMIT_ORDER[:count])))
                self.assertFalse(result['baseline_restored']);self.assertFalse(result['session_drain_verified'])

    def test_vendor_password_change_and_added_account_survive(self):
        current={**self.proposed,'shadow':self.proposed['shadow'].replace(b'vendor:!',b'vendor:*')+b'later:!:2::::::\n',
                 'passwd':self.proposed['passwd']+b'later:x:3000:3000::/later:/bin/false\n',
                 'group':self.proposed['group']+b'later:x:3000:vendor\n'}
        result=self.rollback(current)['candidate_tables']
        self.assertIn(b'vendor:*:',result['shadow']);self.assertIn(b'later:',result['shadow'])
        self.assertIn(b'later:',result['passwd']);self.assertIn(b'later:',result['group'])
        for name in model.NAMES:
            self.assertNotIn(b'nimbus-',result[name])
            expected=b''.join(line for line in current[name].splitlines(keepends=True) if not line.startswith((b'nimbus-files:',b'nimbus-sshd:')))
            self.assertEqual(result[name],expected)

    def test_modified_role_records_are_not_removed(self):
        for name,old,new in (('shadow',b'nimbus-files:*:',b'nimbus-files:!:'),
                             ('passwd',b':/internal:',b':/other:'),
                             ('group',b'nimbus-files:x:2206:\n',b'nimbus-files:x:2206:vendor\n')):
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.rollback({**self.proposed,name:self.proposed[name].replace(old,new)})

    def test_missing_one_role_or_nonprefix_tables_refuse(self):
        changed={**self.proposed,'group':self.proposed['group'].replace(b'nimbus-files:x:2206:\n',b'')}
        with self.assertRaises(ValueError):self.rollback(changed)
        for name in ('passwd','shadow'):
            with self.subTest(name=name),self.assertRaises(ValueError):self.rollback({**self.baseline,name:self.proposed[name]})

    def test_new_identity_references_block_role_removal(self):
        for name,extra in (('passwd',b'later:x:2206:100::/later:/bin/false\n'),
                           ('passwd',b'later:x:3000:2207::/later:/bin/false\n'),
                           ('group',b'later:x:2206:\n'),
                           ('group',b'later:x:3000:nimbus-files\n')):
            with self.subTest(name=name),self.assertRaises(ValueError):self.rollback({**self.proposed,name:self.proposed[name]+extra})

    def test_unreviewed_proposal_or_missing_root_refuse(self):
        changed={**self.proposed,'shadow':self.proposed['shadow'].replace(b'nimbus-files:*',b'nimbus-files:!')}
        with self.assertRaises(ValueError):model.rollback_model(self.proposed,self.baseline,changed,self.header)
        with self.assertRaises(ValueError):self.rollback({**self.proposed,'passwd':self.proposed['passwd'].replace(b'root:x:0:0',b'root:x:1:1')})


class WriterAuditTests(unittest.TestCase):
    def test_only_allowlisted_tokens_are_exposed(self):
        data=b'PRIVATE_PASSWORD_HASH PRIVATE_ACCOUNT\0lckpwdf\0/etc/.pwd.lock\0'
        result=audit.evidence(data)
        self.assertEqual(result['tokens_present'],['/etc/.pwd.lock','lckpwdf'])
        self.assertNotIn('PRIVATE',str(result))

    def test_symbols_distinguish_imports_from_libc_definitions(self):
        text=' 1: 00000000 0 FUNC GLOBAL DEFAULT UND lckpwdf@GLIBC_2.4 (2)\n 2: 00000001 12 FUNC GLOBAL DEFAULT 8 ulckpwdf@@GLIBC_2.4\n 3: 00000000 0 FUNC GLOBAL DEFAULT UND PRIVATE_SYMBOL\n'
        self.assertEqual(audit.symbols(text),{'lckpwdf':['import'],'ulckpwdf':['definition']})

    def test_wrong_archive_refuses_without_readelf_or_vendor_execution(self):
        with tempfile.TemporaryDirectory() as temporary,patch('subprocess.run') as run:
            path=Path(temporary)/'wrong.tar';path.write_bytes(b'wrong')
            with self.assertRaises(ValueError):audit.audit(path)
            run.assert_not_called()
