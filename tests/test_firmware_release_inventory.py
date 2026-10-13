import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_inventory', ROOT / 'scripts/inventory-firmware-release.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class ReleaseInventoryTests(unittest.TestCase):
    def fixture(self, root, omit=(), extra=None):
        source, candidate = root / 'source', root / 'candidate'
        source.mkdir()
        candidate.mkdir()
        recorded = {}
        entries = {}
        for feature, (name, destination) in inventory.FEATURES.items():
            data = (name + '\n/data/fieldkit-v05/\n').encode()
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            recorded[name] = hashlib.sha256(data).hexdigest()
            if feature not in omit:
                entries[destination] = inventory.expected_payload(source, name)
        for name in inventory.BUILD_SOURCES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'build fixture')
            recorded[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.update(extra or {})
        with tarfile.open(candidate / 'rootfs.tar', 'w') as archive:
            for name, data in entries.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        manifest = {'schema': 'nimbus-custom-rootfs/v1', 'overlay_source_sha256': recorded,
                    'artifacts': {'rootfs.tar': inventory.checksum(candidate / 'rootfs.tar')}}
        (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
        return source, candidate, manifest

    def test_current_archive_stays_unqualified_even_if_claimed_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, candidate, manifest = self.fixture(Path(temporary))
            manifest.update(flash_ready=True, boot_tested=True, redistribution_reviewed=True)
            (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
            report = inventory.inventory(candidate, source)
            self.assertFalse(report['source_rebuild_required'])
            self.assertFalse(report['production_ready'])
            self.assertFalse(report['flash_authorized'])
            self.assertEqual(len(report['features']), len(inventory.FEATURES))
            self.assertTrue(all(row['archive_comparison'] == 'current' for row in report['features']))

    def test_changed_missing_and_unrecorded_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, candidate, manifest = self.fixture(Path(temporary), omit=('companion-status',))
            (source / 'device/nimbus-agent.sh').write_bytes(b'new agent')
            (source / 'device/nimbus-settings.sh').unlink()
            del manifest['overlay_source_sha256']['device/nimbus-companion-status.sh']
            (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
            report = inventory.inventory(candidate, source)
            rows = {row['feature']: row for row in report['features']}
            self.assertTrue(report['source_rebuild_required'])
            self.assertEqual(rows['native-agent']['archive_comparison'], 'different')
            self.assertEqual(rows['settings']['manifest_comparison'], 'source_missing')
            self.assertEqual(rows['companion-status']['archive_comparison'], 'absent')
            self.assertEqual(rows['companion-status']['manifest_comparison'], 'not_recorded')

    def test_bridge_transform_exact_not_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, candidate, _ = self.fixture(Path(temporary))
            row = next(row for row in inventory.inventory(candidate, source)['features']
                       if row['feature'] == 'web-settings-bridge')
            self.assertEqual(row['archive_comparison'], 'current')
            self.assertNotEqual(row['current_sha256'], row['expected_payload_sha256'])
            (source / row['path']).write_bytes(b'other bridge')
            changed = next(row for row in inventory.inventory(candidate, source)['features']
                           if row['feature'] == 'web-settings-bridge')
            self.assertEqual(changed['archive_comparison'], 'different')

    def test_tampered_archive_and_private_manifest_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, candidate, manifest = self.fixture(Path(temporary))
            for value in (True, 'false', 1):
                manifest['private_per_device'] = value
                (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    inventory.inventory(candidate, source)
            manifest['private_per_device'] = False
            (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
            with (candidate / 'rootfs.tar').open('ab') as stream:
                stream.write(b'tamper')
            with self.assertRaises(ValueError):
                inventory.inventory(candidate, source)

    def test_identity_and_path_escape_refused_without_contents_in_error(self):
        for name in ('etc/nimbus/host-ed25519', 'etc/nimbus/authorized_keys',
                     'etc/ssh/ssh_host_rsa_key', 'etc/nimbus-sftp-auth/user/authorized_keys', '../escape'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                source, candidate, _ = self.fixture(Path(temporary), extra={name: b'PRIVATE FIXTURE'})
                with self.assertRaises(ValueError) as error:
                    inventory.inventory(candidate, source)
                self.assertNotIn('PRIVATE FIXTURE', str(error.exception))

    def test_symlink_input_or_source_parent_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, candidate, _ = self.fixture(root)
            alias = root / 'alias'
            alias.symlink_to(candidate, target_is_directory=True)
            with self.assertRaises(ValueError):
                inventory.inventory(alias, source)
            path = source / 'device/nimbus-agent.sh'
            original = source / 'original'
            path.rename(original)
            path.symlink_to(original)
            with self.assertRaises(ValueError):
                inventory.inventory(candidate, source)

    def test_report_exclusive_private_no_symlink_or_device_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'report.json'
            inventory.save_report(path, {'safe': True})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                inventory.save_report(path, {'safe': False})
            self.assertEqual(json.loads(path.read_text()), {'safe': True})
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                inventory.save_report(alias / 'new', {})
            with self.assertRaises(ValueError):
                inventory.save_report('/dev/no-nimbus-test-write', {})

    def test_only_allowlisted_source_paths_are_inspected_and_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, candidate, manifest = self.fixture(Path(temporary))
            manifest['overlay_source_sha256']['../../private'] = '0' * 64
            (candidate / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest))
            before = {path: path.read_bytes() for path in candidate.iterdir()}
            report = inventory.inventory(candidate, source)
            self.assertNotIn('../../private', json.dumps(report))
            self.assertEqual(before, {path: path.read_bytes() for path in candidate.iterdir()})

    def test_invalid_cli_inputs_cannot_create_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'report'
            with patch('sys.argv', ['inventory', '--candidate', str(root / 'missing'), '--output', str(output)]), \
                    patch('builtins.print') as printed:
                self.assertEqual(inventory.main(), 1)
            self.assertFalse(output.exists())
            self.assertIn('"flash_authorized": false', printed.call_args.args[0])


class Beta4ArtifactTests(unittest.TestCase):
    candidate = ROOT / 'build/nimbus-custom-rootfs-beta4'

    def setUp(self):
        if not self.candidate.exists():
            self.skipTest('Local generic beta4 artifact unavailable')

    def test_beta4_archive_historical_sources_and_fail_closed_policy(self):
        report = inventory.inventory(self.candidate)
        self.assertTrue(report['source_rebuild_required'])
        rows={row['feature']:row for row in report['features']}
        self.assertEqual(rows['homepage-battery']['archive_comparison'],'absent')
        self.assertFalse(report['flash_authorized'])
        policy = inventory.module('rootfs-policy').audit(self.candidate / 'rootfs.tar')
        self.assertTrue(policy['offline_policy_pass'])
        manifest = json.loads((self.candidate / 'BUILD-MANIFEST.json').read_text())
        for name in ('flash_ready', 'boot_tested', 'recovery_tested', 'vendor_update_container'):
            self.assertIs(manifest[name], False)
        self.assertNotIn('private_per_device', manifest)
        stored = json.loads((self.candidate / 'ROOTFS-POLICY.json').read_text())
        self.assertTrue(stored['vendor_module_hashes_match'])

    @unittest.skipUnless(shutil.which('debugfs'), 'Read-only debugfs unavailable')
    def test_beta4_filesystem_matches_retained_archive_not_new_sources(self):
        image = self.candidate / 'rootfs.ext3.candidate'
        with tarfile.open(self.candidate/'rootfs.tar') as archive:
            nodes={inventory.module('rootfs-policy').canonical(m.name):m for m in archive.getmembers()}
            historical={destination:archive.extractfile(nodes[destination]).read() if destination in nodes else b''
                        for _,destination in inventory.FEATURES.values()}
        for feature, (source, destination) in inventory.FEATURES.items():
            with self.subTest(feature=feature):
                result = subprocess.run(['debugfs', '-R', 'cat /' + destination, str(image)],
                                        capture_output=True, check=True, timeout=15)
                self.assertEqual(result.stdout, historical[destination])
        # New observations are present, but experimental SFTP is not started.
        startup = subprocess.run(['debugfs', '-R', 'cat /opt/nimbus/image-start.sh', str(image)],
                                 capture_output=True, check=True, timeout=15).stdout
        self.assertNotIn(b'2226', startup)
        self.assertNotIn(b'nimbus-sftp-candidate', startup)

    @unittest.skipUnless(shutil.which('e2fsck'), 'Read-only filesystem checker unavailable')
    def test_beta4_independent_read_only_filesystem_check(self):
        result = subprocess.run(['e2fsck', '-f', '-n', str(self.candidate / 'rootfs.ext3.candidate')],
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


class Beta5ArtifactTests(unittest.TestCase):
    candidate=ROOT/'build/nimbus-custom-rootfs-64gb-beta5'

    def setUp(self):
        if not self.candidate.exists():self.skipTest('Local 64 GB beta5 artifact unavailable')

    def test_retained_beta5_needs_media_guard_rebuild_and_keeps_unqualified_target(self):
        report=inventory.inventory(self.candidate)
        self.assertTrue(report['source_rebuild_required'])
        rows={row['feature']:row for row in report['features']}
        self.assertEqual(rows['homepage-battery']['archive_comparison'],'current')
        self.assertEqual(rows['media-ownership-guard']['archive_comparison'],'absent')
        self.assertFalse(report['flash_authorized']);self.assertFalse(report['production_ready'])
        manifest=json.loads((self.candidate/'BUILD-MANIFEST.json').read_text())
        target=manifest['target_hardware']
        self.assertEqual(target['id'],'sandisk-wireless-media-drive-64gb')
        self.assertFalse(target['native_compatibility_verified'])
        policy=inventory.module('rootfs-policy').audit(self.candidate/'rootfs.tar')
        self.assertTrue(policy['offline_policy_pass'])

    @unittest.skipUnless(shutil.which('debugfs'),'Read-only debugfs unavailable')
    def test_generated_toolkit_contains_current_battery_loader_and_ab_roles(self):
        builder=inventory.module('build-unified-dashboard')
        html,css,js=builder.toolkit_assets()
        for name,value in (('toolkit.html',html),('toolkit.css',css),('toolkit.js',js)):
            result=subprocess.run(['debugfs','-R','cat /nimbus/data/fieldkit-v06/'+name,
                                   str(self.candidate/'rootfs.ext3.candidate')],capture_output=True,check=True,timeout=15)
            self.assertEqual(result.stdout,value.encode())
        self.assertIn("new URL('battery.js'",js)
        self.assertIn('Pi A',html);self.assertIn('Pi B',html)

    @unittest.skipUnless(shutil.which('debugfs'),'Read-only debugfs unavailable')
    def test_retained_feature_bytes_match_archive_in_filesystem_image(self):
        with tarfile.open(self.candidate/'rootfs.tar') as archive:
            nodes={inventory.module('rootfs-policy').canonical(m.name):m for m in archive.getmembers()}
            historical={destination:archive.extractfile(nodes[destination]).read() if destination in nodes else b''
                        for _,destination in inventory.FEATURES.values()}
        for feature,(source,destination) in inventory.FEATURES.items():
            with self.subTest(feature=feature):
                result=subprocess.run(['debugfs','-R','cat /'+destination,str(self.candidate/'rootfs.ext3.candidate')],capture_output=True,check=True,timeout=15)
                self.assertEqual(result.stdout,historical[destination])
