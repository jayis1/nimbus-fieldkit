import http.client
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest


def module(name, script):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / script)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


transfer = module('native_transfer', 'serve-native-kit.py')
package = module('native_bundle', 'package-native.py')


class TransferTests(unittest.TestCase):
    def test_only_valid_bundle_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / 'kit.tar'
            package.package(output)
            self.assertEqual(transfer.load_bundle(output), output.read_bytes())
            bad = root / 'bad.img'; bad.write_bytes(b'not an archive')
            with self.assertRaises(Exception): transfer.load_bundle(bad)

    def test_single_exact_path_and_client_no_directory_listing(self):
        server = transfer.HTTPServer(('127.0.0.1', 0), transfer.Handler)
        server.allowed_client = '127.0.0.1'
        server.transfer_path = '/random-token/nimbus-native-kit.tar'
        server.bundle = b'reviewed bundle'
        server.delivered = False
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def get(path):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request('GET', path)
            response = connection.getresponse()
            result = response.status, response.read()
            connection.close()
            return result
        try:
            self.assertEqual(get('/')[0], 404)
            self.assertEqual(get('/random-token/../')[0], 404)
            server.allowed_client = '192.0.2.1'
            self.assertEqual(get(server.transfer_path)[0], 404)
            self.assertFalse(server.delivered)
            server.allowed_client = '127.0.0.1'
            self.assertEqual(get(server.transfer_path), (200, server.bundle))
            self.assertTrue(server.delivered)
        finally:
            server.shutdown(); server.server_close(); thread.join()
