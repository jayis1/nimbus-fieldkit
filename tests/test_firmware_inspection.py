import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('firmware_inspector', ROOT / 'scripts/inspect-firmware.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class FirmwareInspectionTests(unittest.TestCase):
    def test_crc_matches_independent_bitwise_implementation(self):
        for seed in (0, 64, 255):
            data = bytes(range(256))
            value = seed
            for byte in data:
                value ^= byte
                for _ in range(8):
                    value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
            self.assertEqual(inspector.vendor_crc(data, seed), value)

    def test_exact_block_has_empty_final_iteration(self):
        data = b'a' * 4096
        self.assertEqual(inspector.payload_crc(io.BytesIO(data)), inspector.vendor_crc(data) & 255)

    def test_size_checks_and_no_input_modification(self):
        # Synthetic test-only container; not firmware and never deployed.
        payload = b'test-only'
        header = bytearray(152)
        struct.pack_into('>III', header, 0, inspector.MAGIC, 0, inspector.payload_crc(io.BytesIO(payload)))
        struct.pack_into('<I', header, 16, len(payload))
        struct.pack_into('>I', header, 20, 0x03040000)
        struct.pack_into('>I', header, 4, inspector.vendor_crc(header))
        original = bytes(header) + payload
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.img'
            path.write_bytes(original)
            result = inspector.inspect(path)
            self.assertTrue(result['wrapper_checks_pass'])
            self.assertFalse(result['flash_ready'])
            self.assertEqual(path.read_bytes(), original)
            path.write_bytes(original + b'extra')
            self.assertFalse(inspector.inspect(path)['checks']['size'])

    def test_truncated_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.img'
            path.write_bytes(b'incomplete')
            with self.assertRaises(ValueError):
                inspector.inspect(path)
