import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from fieldkit import tools
from fieldkit import nimbus_fieldkit as nimbus


class ToolTests(unittest.TestCase):
    def test_sync_verified_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.txt'; source.write_bytes(b'reviewed report')
            dest = root / 'dest'; dest.mkdir()
            result = tools.sync_file(source, dest)
            self.assertTrue(result['verified'])
            self.assertEqual(result['sha256'], hashlib.sha256(b'reviewed report').hexdigest())
            self.assertEqual((dest / source.name).read_bytes(), source.read_bytes())
            with self.assertRaises(FileExistsError): tools.sync_file(source, dest)
            self.assertEqual((dest / source.name).read_bytes(), b'reviewed report')

    def test_sync_symlinks_and_oversized_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'; source.write_bytes(b'data')
            link = root / 'link'; link.symlink_to(source)
            dest = root / 'dest'; dest.mkdir()
            with self.assertRaises(OSError): tools.sync_file(link, dest)
            folder_link = root / 'folder-link'; folder_link.symlink_to(dest)
            with self.assertRaises(ValueError): tools.sync_file(source, folder_link)
            with source.open('wb') as stream: stream.truncate(tools.MAX_FILE + 1)
            with self.assertRaises(ValueError): tools.sync_file(source, dest)
            self.assertEqual(list(dest.iterdir()), [])

    def test_manifest_excludes_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'a.txt').write_bytes(b'a')
            (root / 'link').symlink_to(root / 'a.txt')
            result = tools.vault_manifest(root)
            self.assertEqual([item['name'] for item in result['files']], ['a.txt'])
            saved = Path(tools.save_manifest(root))
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(saved.read_text())['schema'], 'nimbus-vault/v1')

    def test_queue_quoting_and_ids(self):
        import shlex
        task = "printf 'hello'; echo test"
        self.assertEqual(shlex.split(tools.queue_command('submit', task)), ['gamehack-companion', 'submit', task])
        self.assertEqual(tools.queue_command('jobs'), 'gamehack-companion jobs')
        for value in ('1', 'z'*32, 'a'*32+'; reboot'):
            with self.assertRaises(ValueError): tools.queue_command('cancel', value)
        self.assertIn('a'*32, tools.queue_command('result', 'a'*32))

    def test_dns_response_against_fake_server(self):
        # Patch the socket transport, never query a real external resolver.
        from unittest.mock import MagicMock
        connection = MagicMock()
        def send(packet):
            connection.recv.return_value = packet[:2] + struct.pack('!HHHHH', 0x8180, 1, 2, 0, 0)
        connection.send.side_effect = send
        with patch.object(tools.socket, 'socket') as factory:
            factory.return_value.__enter__.return_value = connection
            result = tools.dns_query('127.0.0.1', 'example.com')
        self.assertEqual(result['rcode'], 0)
        self.assertEqual(result['answer_count'], 2)

    def test_dns_invalid_inputs(self):
        for name in ('', 'x..com', '-bad.com', 'a'*64+'.com', 'x; reboot', None):
            with self.assertRaises(ValueError): tools.dns_query('127.0.0.1', name)

    def test_native_snapshot_path_validation(self):
        self.assertEqual(tools.native_snapshot_path('/storage/nimbus-fieldkit-v04/dashboard/state.json'), '/storage/nimbus-fieldkit-v04/dashboard/state.json')
        for path in ('/etc/passwd','/storage/../../dashboard/state.json','http://example.com/a','/storage/x/dashboard/state.json?x=1'):
            with self.assertRaises(ValueError): tools.native_snapshot_path(path)

    def test_native_snapshot_proxy_schema_and_size(self):
        from unittest.mock import MagicMock
        connection=MagicMock()
        response=connection.getresponse.return_value
        response.status=200
        response.read.return_value=json.dumps({'schema':'nimbus-dashboard/v1','scope':'device'}).encode()
        with patch.object(tools.http.client,'HTTPConnection',return_value=connection):
            result=tools.native_snapshot('127.0.0.1','/storage/kit/dashboard/state.json')
            self.assertEqual(result['scope'],'device')
            connection.request.assert_called_with('GET','/storage/kit/dashboard/state.json')
            response.read.return_value=b'x'*(512*1024+1)
            with self.assertRaises(ValueError): tools.native_snapshot('127.0.0.1','/storage/kit/dashboard/state.json')
            response.read.return_value=b'{"schema":"other","scope":"device"}'
            with self.assertRaises(ValueError): tools.native_snapshot('127.0.0.1','/storage/kit/dashboard/state.json')

    def test_no_fabricated_telemetry_or_hardening(self):
        with patch.object(tools.socket, 'socket') as factory:
            factory.return_value.__enter__.return_value.connect_ex.return_value = 111
            result = tools.node_status('127.0.0.1')
        self.assertIn('Unknown', result['battery'])
        self.assertFalse(result['web_identity']['verified_sandisk_web_page'])
        self.assertIn('blocked', tools.privacy_plan()['status'])

    def test_offline_docs_exist(self):
        for name in tools.DOCUMENTS:
            self.assertTrue((tools.DOCS / name).is_file(), name)

    def test_controller_queue_uses_existing_client(self):
        from unittest.mock import MagicMock
        ui = MagicMock()
        ui.select.side_effect = ['Pi queue: list jobs', None]
        run = MagicMock(return_value='[]')
        nimbus.menu(ui, run)
        run.assert_called_once_with(['/usr/bin/python3', '/opt/hackeros/pi_worker.py', 'task', 'gamehack-companion jobs'], 40)

    def test_cancel_requires_confirmation(self):
        from unittest.mock import MagicMock
        ui = MagicMock()
        ui.select.side_effect = ['Pi queue: cancel job', None]
        ui.keyboard.return_value = 'a'*32
        ui.confirm.return_value = False
        run = MagicMock()
        nimbus.menu(ui, run)
        run.assert_not_called()

    def test_native_agent_syntax_and_help(self):
        agent = Path(__file__).parents[1] / 'device/nimbus-agent.sh'
        subprocess.run(['sh', '-n', str(agent)], check=True)
        result = subprocess.run(['sh', str(agent), 'help'], capture_output=True, text=True, check=True)
        self.assertIn('candidate; not installed', result.stdout)

    def test_native_capture_requires_permission(self):
        agent = Path(__file__).parents[1] / 'device/nimbus-agent.sh'
        result = subprocess.run(['sh', str(agent), 'capture', 'lo', '/tmp/opencode/never-created-by-test.pcap'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('permission required', result.stderr)
