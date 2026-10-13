import base64
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sftp_confinement',ROOT/'scripts/sftp-confinement.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
spec=importlib.util.spec_from_file_location('sftp_confinement_profile',ROOT/'scripts/prepare-sftp-candidate.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)


def pin(byte):return 'SHA256:'+base64.b64encode(bytes([byte])*32).decode().rstrip('=')


class SFTPConfinementTests(unittest.TestCase):
    def fixture(self):
        raw=b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(range(32))
        public='ssh-ed25519 '+base64.b64encode(raw).decode()+' fixture comment\n'
        authorized,_=policy.public_key(public)
        metadata={path:{'kind':'directory','uid':0,'gid':0,'mode':mode[0] if isinstance(mode,tuple) else mode} for path,mode in policy.DIRECTORIES.items()}
        metadata[policy.AUTH]={'kind':'file','uid':0,'gid':0,'mode':0o644,'links':1,'bytes':len(authorized.encode())}
        metadata[policy.STAGE+'/host-ed25519']={'kind':'file','uid':0,'gid':0,'mode':0o600,'links':1,'bytes':411}
        accounts={name:{'uid':uid,'gid':uid,'supplementary_gids':[uid],
                        'uid_occurrences':1,'primary_gid_accounts':[name],
                        'home':'/internal' if name=='nimbus-files' else policy.STAGE+'/empty',
                        'shell':'/bin/false','shell_executable':True}
                  for name,uid in (('nimbus-files',2206),('nimbus-sshd',2207))}
        return {'schema':'nimbus-sftp-confinement-observation/v1','usb_state':'inactive',
                'privsep_empty':True,'listen_address':'192.168.11.1',
                'effective_config':'\n'.join(name+' '+value for name,value in {**policy.POLICY,'listenaddress':'192.168.11.1:2226'}.items()),
                'metadata':metadata,'accounts':accounts,'client_public_key':public,'authorized_keys':authorized,
                'authorized_keys_sha256':hashlib.sha256(authorized.encode()).hexdigest(),
                'host_fingerprint':pin(1),'management_host_fingerprint':pin(2),'management_client_fingerprint':pin(3),
                'block_devices':{'/dev/mmcblk1p1':'179:17'},
                'mountinfo':f'41 20 179:4 / /mnt/storage rw,relatime - texfat /dev/mmcblk0p4 rw\n'
                            f'42 20 179:4 / {policy.JAIL}/internal ro,relatime - texfat /dev/mmcblk0p4 rw\n'
                            f'43 20 179:17 / /mnt/sdcard ro,relatime - texfat /dev/mmcblk1p1 ro\n'
                            f'44 20 179:17 / {policy.JAIL}/sd ro,relatime - texfat /dev/mmcblk1p1 ro\n'}

    def test_good_static_observation_never_authorizes_a_service_or_firmware(self):
        observation=self.fixture();before=copy.deepcopy(observation)
        result=policy.validate(observation)
        self.assertTrue(result['static_preconditions_pass'])
        for flag in ('native_verified','listener_authorized','usb_handoff_verified','production_ready','flash_authorized'):
            self.assertIs(result[flag],False)
        self.assertEqual(observation,before)

    def test_generated_config_matches_required_policy(self):
        text=profile.config('192.168.11.1')
        text='\n'.join(line for line in text.splitlines() if not line.startswith('#'))
        self.assertEqual(policy.effective_policy(text,'192.168.11.1'),{**policy.POLICY,'listenaddress':'192.168.11.1:2226'})

    def test_duplicate_missing_or_weakened_policy_refuses(self):
        for name in policy.POLICY:
            with self.subTest(name=name):
                observation=self.fixture()
                observation['effective_config']+='\n'+name+' '+policy.POLICY[name]
                with self.assertRaises(ValueError):policy.validate(observation)
                observation=self.fixture()
                observation['effective_config']=observation['effective_config'].replace(name+' '+policy.POLICY[name],name+' unsafe')
                with self.assertRaises(ValueError):policy.validate(observation)

    def test_public_or_wildcard_listen_address_refuses(self):
        for address in ('0.0.0.0','127.0.0.1','8.8.8.8','::1'):
            with self.subTest(address=address),self.assertRaises(ValueError):policy.effective_policy('',address)

    def test_jail_and_auth_directory_permissions_and_symlinks_refuse(self):
        for path in policy.DIRECTORIES:
            for field,value in (('uid',2206),('gid',2206),('mode',0o777),('kind','symlink')):
                with self.subTest(path=path,field=field):
                    observation=self.fixture();observation['metadata'][path][field]=value
                    with self.assertRaises(ValueError):policy.validate(observation)

    def test_private_host_key_and_readable_public_auth_file_have_distinct_modes(self):
        for path,mode in ((policy.AUTH,0o600),(policy.AUTH,0o666),(policy.STAGE+'/host-ed25519',0o644)):
            with self.subTest(path=path,mode=mode):
                observation=self.fixture();observation['metadata'][path]['mode']=mode
                with self.assertRaises(ValueError):policy.validate(observation)
        for path in (policy.AUTH,policy.STAGE+'/host-ed25519'):
            observation=self.fixture();observation['metadata'][path]['links']=2
            with self.assertRaises(ValueError):policy.validate(observation)

    def test_nonwritable_root_home_755_does_not_require_an_unrelated_permission_change(self):
        observation=self.fixture();observation['metadata']['/root']['mode']=0o755
        self.assertTrue(policy.validate(observation)['static_preconditions_pass'])
        observation['metadata']['/root']['mode']=0o775
        with self.assertRaises(ValueError):policy.validate(observation)

    def test_key_options_multiple_keys_private_material_and_wrong_wire_refuse(self):
        public=self.fixture()['client_public_key']
        for text in ('restrict '+public,public+public,'-----BEGIN OPENSSH PRIVATE KEY-----',
                     'ssh-rsa AAAA','ssh-ed25519 !@#$', 'ssh-ed25519 '+base64.b64encode(b'bad wire').decode()):
            with self.subTest(text=text[:30]),self.assertRaises(ValueError):policy.public_key(text)
        normalized,fingerprint=policy.public_key(public)
        self.assertTrue(normalized.startswith('restrict ssh-ed25519 '));self.assertTrue(fingerprint.startswith('SHA256:'))
        self.assertNotIn('fixture comment',normalized)

    def test_management_identity_reuse_and_unrestricted_key_file_refuse(self):
        for change in ('client','host','unrestricted','additional-key'):
            observation=self.fixture()
            if change=='client':observation['management_client_fingerprint']=policy.public_key(observation['client_public_key'])[1]
            elif change=='host':observation['management_host_fingerprint']=observation['host_fingerprint']
            elif change=='unrestricted':observation['authorized_keys']=observation['authorized_keys'].replace('restrict ','')
            else:observation['authorized_keys']+=observation['authorized_keys']
            with self.subTest(change=change),self.assertRaises(ValueError):policy.validate(observation)

    def test_root_shared_and_privileged_group_accounts_refuse(self):
        for change in ('root','shared-uid','shared-gid','supplementary','shell','shell-not-executable','bool-uid','uid-collision','gid-collision'):
            observation=self.fixture();account=observation['accounts']['nimbus-files']
            if change=='root':account['uid']=0
            elif change=='shared-uid':account['uid']=2207
            elif change=='shared-gid':account['gid']=2207;account['supplementary_gids']=[2207]
            elif change=='supplementary':account['supplementary_gids']=[2206,0]
            elif change=='shell':account['shell']='/bin/sh'
            elif change=='shell-not-executable':account['shell_executable']=False
            elif change=='uid-collision':account['uid_occurrences']=2
            elif change=='gid-collision':account['primary_gid_accounts']=['nimbus-files','another-user']
            else:account['uid']=True
            with self.subTest(change=change),self.assertRaises(ValueError):policy.validate(observation)

    def test_usb_unknown_and_nonempty_privsep_refuse(self):
        for field,value in (('usb_state','active'),('usb_state','unknown'),('privsep_empty',False),('privsep_empty',None)):
            observation=self.fixture();observation[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):policy.validate(observation)

    def test_view_vfs_ro_required_even_if_superblock_is_ro(self):
        observation=self.fixture()
        observation['mountinfo']=observation['mountinfo'].replace(policy.JAIL+'/internal ro,relatime',policy.JAIL+'/internal rw,relatime')
        with self.assertRaises(ValueError):policy.validate(observation)
        # A writable source superblock is valid with an independently ro view.
        self.assertTrue(policy.validate(self.fixture())['static_preconditions_pass'])
        observation=self.fixture()
        observation['mountinfo']=observation['mountinfo'].replace(f'{policy.JAIL}/internal ro,relatime - texfat /dev/mmcblk0p4 rw',
                                                               f'{policy.JAIL}/internal ro,relatime - texfat /dev/mmcblk0p4 ro')
        with self.assertRaises(ValueError):policy.validate(observation)

    def test_wrong_mount_device_subdirectory_and_nested_or_extra_view_refuse(self):
        for change in ('wrong-device','subdirectory','nested','extra','over-jail','duplicate'):
            observation=self.fixture();text=observation['mountinfo']
            if change=='wrong-device':text=text.replace(f'42 20 179:4 / {policy.JAIL}',f'42 20 179:5 / {policy.JAIL}')
            elif change=='subdirectory':text=text.replace(f'42 20 179:4 / {policy.JAIL}',f'42 20 179:4 /private {policy.JAIL}')
            elif change=='duplicate':text+=text.splitlines()[0]+'\n'
            else:
                path={'nested':policy.JAIL+'/internal/secret','extra':policy.JAIL+'/extra','over-jail':policy.JAIL}[change]
                text+=f'45 20 179:2 / {path} ro - ext3 /dev/root rw\n'
            observation['mountinfo']=text
            with self.subTest(change=change),self.assertRaises(ValueError):policy.validate(observation)

    def test_sd_optional_only_with_empty_root_owned_unmounted_placeholder(self):
        observation=self.fixture()
        observation['mountinfo']='\n'.join(line for line in observation['mountinfo'].splitlines() if line.startswith(('41 ','42 ')))
        with self.assertRaises(ValueError):policy.validate(observation)
        observation['sd_placeholder_empty']=True
        observation['metadata'][policy.JAIL+'/sd']={'kind':'directory','uid':0,'gid':0,'mode':0o755}
        self.assertTrue(policy.validate(observation)['static_preconditions_pass'])
        observation['metadata'][policy.JAIL+'/sd']['kind']='symlink'
        with self.assertRaises(ValueError):policy.validate(observation)

    def test_sd_identity_is_corroborated_not_assumed_from_capacity(self):
        observation=self.fixture();observation['block_devices']['/dev/mmcblk1p1']='179:9'
        with self.assertRaises(ValueError):policy.validate(observation)
        del observation['block_devices']
        with self.assertRaises(ValueError):policy.validate(observation)

    def test_validator_never_executes_or_reads_host_paths(self):
        observation=self.fixture()
        with patch('subprocess.run') as run,patch.object(Path,'open') as opened:
            policy.validate(observation)
            run.assert_not_called();opened.assert_not_called()
        result=subprocess.run(['python3',str(ROOT/'scripts/sftp-confinement.py')],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('No collection',result.stderr)
