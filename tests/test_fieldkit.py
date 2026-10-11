import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'fieldkit'))
spec = importlib.util.spec_from_file_location('server', Path(__file__).parents[1] / 'fieldkit/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class FieldKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        (self.vault / 'sample.txt').write_bytes(b'fieldkit\n')
        self.http = server.HTTPServer(('127.0.0.1', 0), server.Handler)
        self.http.token = 'test-token'
        self.http.vault = self.vault
        self.http.networks = []
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method='GET', body=None, auth=True, extra=None):
        headers = {'Authorization': 'Bearer test-token'} if auth else {}
        headers.update(extra or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=15)
        connection.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_dashboard_public_api_requires_auth(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/api/status', auth=False)[0], 401)
        code, data = self.request('/api/status')
        self.assertEqual(code, 200)
        self.assertIn('HOST PROTOTYPE', json.loads(data)['mode'])

    def test_rejects_cross_origin_and_rebinding(self):
        self.assertEqual(self.request('/api/status', extra={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/api/status', extra={'Host': 'evil.example'})[0], 403)

    def test_ecosystem_roles(self):
        code, data = self.request('/api/ecosystem')
        self.assertEqual(code, 200)
        self.assertIn('SanDisk', json.loads(data)['roles']['main_wifi'])

    def test_privacy_blocks_files_and_diagnostics_but_not_docs(self):
        self.assertEqual(self.request('/api/privacy', 'POST', {'enabled': True})[0], 200)
        self.assertEqual(self.request('/api/download?name=sample.txt')[0], 403)
        self.assertEqual(self.request('/api/files')[0], 403)
        self.assertEqual(self.request('/api/node')[0], 403)
        self.assertEqual(self.request('/api/check', 'POST', {'target':'127.0.0.1', 'ports':[80], 'authorized':True})[0], 403)
        self.assertEqual(self.request('/api/docs?name=FEATURES.md')[0], 200)
        self.assertEqual(self.request('/api/privacy', 'POST', {'enabled': False})[0], 200)
        self.assertEqual(self.request('/api/files')[0], 200)

    def test_privacy_invalid_and_document_traversal(self):
        self.assertEqual(self.request('/api/privacy', 'POST', {'enabled': 'true'})[0], 400)
        self.assertEqual(self.request('/api/docs?name=..%2FREADME.md')[0], 400)

    def test_device_probe_opt_in(self):
        code, data = self.request('/api/node')
        self.assertEqual(code, 200)
        self.assertIn('--device', json.loads(data)['status'])

    def test_dashboard_static_assets_and_native_opt_in(self):
        for path in ('/dashboard.css','/dashboard.js'):
            self.assertEqual(self.request(path,auth=False)[0],200)
        self.assertEqual(self.request('/api/native-state',auth=False)[0],401)
        code,data=self.request('/api/native-state')
        self.assertEqual(code,200)
        self.assertIn('host data only',json.loads(data)['status'])

    def test_diagnostics_scope_enforced(self):
        self.assertEqual(self.request('/api/diagnostic', 'POST', {'action':'dns','target':'127.0.0.1','authorized':True})[0], 400)

    def test_vault_hash_and_download(self):
        code, data = self.request('/api/files')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)['files'][0]['name'], 'sample.txt')
        code, data = self.request('/api/hash?name=sample.txt')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)['sha256'], hashlib.sha256(b'fieldkit\n').hexdigest())
        self.assertEqual(self.request('/api/download?name=sample.txt'), (200, b'fieldkit\n'))

    def test_traversal_symlinks_directories_and_limits(self):
        (self.vault / 'link').symlink_to('/etc/passwd')
        (self.vault / 'directory').mkdir()
        with (self.vault / 'huge').open('wb') as source:
            source.truncate(server.MAX_FILE + 1)
        for name in ['..%2Fetc%2Fpasswd', '%2Fetc%2Fpasswd', 'link', 'directory', 'huge', '%00']:
            self.assertEqual(self.request('/api/download?name=' + name)[0], 400, name)

    def test_scope_and_permission_required(self):
        body = {'target': '127.0.0.1', 'ports': [80], 'authorized': True}
        self.assertEqual(self.request('/api/check', 'POST', body)[0], 400)
        self.http.networks = [server.ipaddress.ip_network('127.0.0.0/8')]
        body['authorized'] = False
        self.assertEqual(self.request('/api/check', 'POST', body)[0], 400)
        body.update(target='example.com', authorized=True)
        self.assertEqual(self.request('/api/check', 'POST', body)[0], 400)

    def test_port_validation(self):
        networks = [server.ipaddress.ip_network('127.0.0.0/8')]
        for ports in [[], [True], [0], [65536], ['22'], list(range(1, 18)), None]:
            with self.assertRaises(ValueError):
                server.check_ports('127.0.0.1', ports, networks)

    def test_authorized_open_port(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            self.http.networks = [server.ipaddress.ip_network('127.0.0.0/8')]
            code, data = self.request('/api/check', 'POST',
                                      {'target': '127.0.0.1', 'ports': [port], 'authorized': True})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(data)['results'][0]['state'], 'open')


if __name__ == '__main__':
    unittest.main()
