import json
from pathlib import Path
import subprocess
import sys
import unittest

from fieldkit import tools

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return {'schema': 'nimbus-companion-status/v1', 'scope': 'device_observation',
            'storage': {'internal': 'read_write', 'sd': 'read_only', 'sd_ftp': 'read_only',
                        'usb_export': 'inactive'},
            'management': {'port': 2224, 'listener': 'observed', 'authentication': 'not_tested',
                           'host_pin': 'not_tested', 'downstream_access': 'not_qualified'},
            'integration': {'remote_browsing': 'not_qualified', 'sftp': 'not_qualified',
                            'backup_transfer': 'not_qualified',
                            'media_playback': 'client_validation_required', 'pi_worker': 'independent'},
            'permissions': {'remote_write': False, 'configure_network': False, 'change_mounts': False}}


class CompanionClientTests(unittest.TestCase):
    def review(self, data):
        return tools.companion_report(json.dumps(data).encode())

    def test_normal_state_does_not_enable_transfers(self):
        result = self.review(fixture())
        self.assertEqual(result['state'], 'local_mounts_observed')
        self.assertFalse(result['remote_transfer_enabled'])
        self.assertFalse(result['remote_browsing_enabled'])
        self.assertEqual(result['transport_provenance'], 'not_verified_by_reader')

    def test_usb_export_blocks_even_if_mounts_claim_rw(self):
        data = fixture()
        data['storage']['usb_export'] = 'active'
        self.assertEqual(self.review(data)['state'], 'blocked_usb_export')

    def test_unknown_or_absent_storage_blocks(self):
        for name, value in (('internal', 'absent'), ('sd', 'unknown'), ('sd_ftp', 'absent'),
                            ('usb_export', 'unknown')):
            data = fixture()
            data['storage'][name] = value
            self.assertEqual(self.review(data)['state'], 'blocked_storage_unconfirmed')

    def test_invalid_schema_sections_and_enums_refused(self):
        for name, value in (('schema', 'other'), ('scope', 'authenticated'), ('storage', []),
                            ('management', None), ('permissions', {})):
            data = fixture()
            data[name] = value
            with self.assertRaises(ValueError):
                self.review(data)
        data = fixture()
        data['storage']['sd'] = 'writable_and_safe'
        with self.assertRaises(ValueError):
            self.review(data)

    def test_self_declared_authentication_and_permissions_refused(self):
        for section, name, value in (('management', 'host_pin', 'verified'),
                                     ('management', 'authentication', 'authenticated'),
                                     ('integration', 'sftp', 'ready'),
                                     ('permissions', 'remote_write', True),
                                     ('permissions', 'remote_write', 0)):
            data = fixture()
            data[section][name] = value
            with self.assertRaises(ValueError):
                self.review(data)

    def test_duplicate_fields_invalid_json_and_size_refused(self):
        for raw in (b'{"schema":"a","schema":"b"}', b'not json', b'[]', b' ' * 16385):
            with self.assertRaises(ValueError):
                tools.companion_report(raw)

    def test_extra_private_fields_are_not_echoed(self):
        data = fixture()
        data['private_notes'] = 'never_echo_this'
        data['management']['credentials'] = 'never_echo_this'
        self.assertNotIn('never_echo_this', json.dumps(self.review(data)))

    def test_cli_reviews_stdin_without_device_connection(self):
        result = subprocess.run([sys.executable, str(ROOT / 'fieldkit/tools.py'), 'companion-report'],
                                input=json.dumps(fixture()), capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'local_mounts_observed')
