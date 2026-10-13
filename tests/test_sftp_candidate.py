import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sftp_candidate', ROOT / 'scripts/prepare-sftp-candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class SFTPCandidateTests(unittest.TestCase):
    def directives(self):
        lines = candidate.config('192.168.11.1').splitlines()
        return dict(line.split(' ', 1) for line in lines if line and not line.startswith('#'))

    def test_separate_explicit_listener_and_host_identity(self):
        directives = self.directives()
        self.assertEqual(directives['Port'], '2226')
        self.assertEqual(directives['ListenAddress'], '192.168.11.1:2226')
        self.assertEqual(directives['AddressFamily'], 'inet')
        self.assertNotIn('nimbus-ssh-test', directives['HostKey'])

    def test_non_root_key_only_authentication(self):
        directives = self.directives()
        self.assertEqual(directives['AllowUsers'], 'nimbus-files')
        self.assertEqual(directives['PermitRootLogin'], 'no')
        self.assertEqual(directives['AuthenticationMethods'], 'publickey')
        self.assertEqual(directives['AuthorizedKeysFile'], '/etc/nimbus-sftp-auth/nimbus-files/authorized_keys')
        self.assertFalse(directives['AuthorizedKeysFile'].startswith('/root/'))
        for name in ('PasswordAuthentication', 'KbdInteractiveAuthentication', 'PermitEmptyPasswords', 'UsePAM'):
            self.assertEqual(directives[name], 'no')

    def test_server_side_jail_and_read_only_internal_sftp(self):
        directives = self.directives()
        self.assertEqual(directives['ChrootDirectory'], candidate.STAGE + '/jail')
        self.assertEqual(directives['ForceCommand'], 'internal-sftp -R -d /internal')
        self.assertEqual(directives['Subsystem'], 'sftp internal-sftp')
        self.assertEqual(directives['PermitTTY'], 'no')
        self.assertEqual(directives['PermitUserRC'], 'no')

    def test_no_forwarding_or_user_environment(self):
        directives = self.directives()
        self.assertEqual(directives['DisableForwarding'], 'yes')
        for name in ('AllowTcpForwarding', 'AllowStreamLocalForwarding', 'AllowAgentForwarding',
                     'X11Forwarding', 'PermitTunnel', 'PermitUserEnvironment'):
            self.assertEqual(directives[name], 'no')

    def test_invalid_address_before_any_files_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for address in ('0.0.0.0', '127.0.0.1', '8.8.8.8', '::1', '192.168.11.1\nPermitRootLogin yes'):
                with self.assertRaises(ValueError):
                    candidate.prepare(root / 'candidate', address)
                self.assertEqual(list(root.iterdir()), [])

    def test_private_manifest_and_unqualified_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'candidate'
            candidate.prepare(output, '192.168.11.1')
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            manifest = json.loads((output / 'MANIFEST.json').read_text())
            for entry in manifest['files']:
                path = output / entry['name']
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.stat().st_size, entry['bytes'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
            plan = json.loads((output / 'PLAN.json').read_text())
            self.assertFalse(plan['installable'])
            self.assertFalse(plan['hardware_validated'])
            self.assertFalse(plan['remote_write'])
            self.assertIsNone(plan['runtime']['binary_sha256'])
            self.assertTrue(all(share['mode'] == 'read_only' for share in plan['shares']))

    def test_no_overwrite_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'candidate'
            candidate.prepare(output, '192.168.11.1')
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(FileExistsError):
                candidate.prepare(output, '192.168.11.1')
            alias = root / 'alias'
            alias.symlink_to(output)
            with self.assertRaises(ValueError):
                candidate.prepare(alias, '192.168.11.1')
            with self.assertRaises(ValueError):
                candidate.prepare(alias / 'nested', '192.168.11.1')
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_prepare_never_invokes_commands(self):
        with tempfile.TemporaryDirectory() as temporary, patch('subprocess.run') as run:
            candidate.prepare(Path(temporary) / 'candidate', '192.168.11.1')
            run.assert_not_called()

    @unittest.skipUnless(shutil.which('sshd') and shutil.which('ssh-keygen'), 'Host OpenSSH tools unavailable')
    def test_host_openssh_parses_effective_policy_without_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = root / 'fixture-host-key'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                           check=True, capture_output=True, timeout=10)
            config = root / 'sshd_config'
            config.write_text(candidate.config('192.168.11.1').replace(
                candidate.STAGE + '/host-ed25519', str(key)))
            result = subprocess.run(['sshd', '-T', '-f', str(config)],
                                    check=True, capture_output=True, text=True, timeout=10)
            effective = {name.lower(): value for name, value in
                         (line.split(' ', 1) for line in result.stdout.splitlines())}
            self.assertEqual(effective['permitrootlogin'], 'no')
            self.assertEqual(effective['passwordauthentication'], 'no')
            self.assertEqual(effective['forcecommand'], 'internal-sftp -R -d /internal')
            self.assertEqual(effective['disableforwarding'], 'yes')
            self.assertEqual(effective['allowusers'], 'nimbus-files')
            self.assertEqual(effective['authorizedkeysfile'], '/etc/nimbus-sftp-auth/nimbus-files/authorized_keys')
            self.assertEqual(effective['listenaddress'], '192.168.11.1:2226')
