import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sftp_enrollment',ROOT/'scripts/prepare-sftp-enrollment.py')
enrollment=importlib.util.module_from_spec(spec);spec.loader.exec_module(enrollment)


class SFTPEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.private=self.root/'private'
        self.patcher=patch.object(enrollment,'PRIVATE',self.private);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.client=self.root/'client.pub';self.management=self.root/'management.pub'
        for path,byte in ((self.client,1),(self.management,2)):
            raw=b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes([byte])*32
            path.write_text('ssh-ed25519 '+base64.b64encode(raw).decode()+' stripped comment\n');path.chmod(0o644)

    def prepare(self):return enrollment.prepare(self.private/'new',self.client,self.management,'test-fixture')

    def test_dedicated_restricted_public_key_only_and_unqualified_manifest(self):
        record=self.prepare();output=self.private/'new'
        self.assertEqual(set(path.name for path in output.iterdir()),{'authorized_keys','ENROLLMENT.json','NOT-ENROLLED.txt'})
        text=(output/'authorized_keys').read_text();self.assertTrue(text.startswith('restrict ssh-ed25519 '));self.assertNotIn('stripped comment',text)
        self.assertEqual(record,json.loads((output/'ENROLLMENT.json').read_text()))
        self.assertNotEqual(record['client_fingerprint'],record['management_client_fingerprint'])
        for name in ('private_client_key_included','host_key_provisioned','device_enrolled','native_auth_verified','listener_authorized','production_ready','flash_authorized'):
            self.assertFalse(record[name])
        self.assertEqual(output.stat().st_mode&0o777,0o700)
        self.assertTrue(all(path.stat().st_mode&0o777==0o600 for path in output.iterdir()))
        self.assertEqual(record['device_auth_mode'],'0644')

    def test_management_identity_reuse_refused_before_output(self):
        self.client.write_bytes(self.management.read_bytes())
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.private.exists())

    def test_private_key_or_key_options_refused_before_output(self):
        for text in ('-----BEGIN OPENSSH PRIVATE KEY-----','command="sh" '+self.client.read_text()):
            self.client.write_text(text)
            with self.assertRaises(ValueError):self.prepare()
            self.assertFalse(self.private.exists())

    def test_existing_stage_and_symlink_refuse_without_overwrite(self):
        self.prepare();output=self.private/'new';before={p.name:p.read_bytes() for p in output.iterdir()}
        with self.assertRaises(FileExistsError):self.prepare()
        alias=self.private/'alias';alias.symlink_to(output,target_is_directory=True)
        with self.assertRaises(ValueError):enrollment.prepare(alias,self.client,self.management,'fixture')
        self.assertEqual(before,{p.name:p.read_bytes() for p in output.iterdir()})

    def test_input_symlinks_hardlinks_and_group_write_refuse(self):
        alias=self.root/'alias.pub';alias.symlink_to(self.client)
        with self.assertRaises(ValueError):enrollment.prepare(self.private/'new',alias,self.management,'fixture')
        alias.unlink();os.link(self.client,alias)
        with self.assertRaises(ValueError):self.prepare()
        alias.unlink();self.client.chmod(0o664)
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.private.exists())

    def test_output_escape_and_invalid_label_refuse_before_parent_creation(self):
        with self.assertRaises(ValueError):enrollment.prepare(self.root/'public',self.client,self.management,'fixture')
        with self.assertRaises(ValueError):enrollment.prepare(self.private/'new',self.client,self.management,'../escape')
        self.assertFalse(self.private.exists())

    def test_insecure_private_parent_refused_and_no_commands_invoked(self):
        self.private.mkdir(mode=0o755)
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse((self.private/'new').exists());self.private.chmod(0o700)
        with patch('subprocess.run') as run:
            self.prepare();run.assert_not_called()

    def test_failed_sync_keeps_private_incomplete_stage_for_inspection(self):
        with patch.object(enrollment.os,'fsync',side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):self.prepare()
        self.assertTrue((self.private/'new').is_dir())
        self.assertTrue((self.private/'new/authorized_keys').is_file())
        with self.assertRaises(FileExistsError):self.prepare()
