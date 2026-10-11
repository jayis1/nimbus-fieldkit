import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boot_inventory', ROOT / 'scripts/inspect-boot-area.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def image(payload):
    h = struct.pack('>7I4B32s', 0x27051956, 0, 0, len(payload), 0, 0,
                    zlib.crc32(payload) & 0xffffffff, 5, 2, 2, 0, b'Fixture-rescue')
    return h[:4] + struct.pack('>I', zlib.crc32(h) & 0xffffffff) + h[8:] + payload


class BootInventoryTests(unittest.TestCase):
    def test_valid_images_and_no_recovery_claim(self):
        data = bytes(512) + image(b'kernel fixture') + bytes(128) + image(b'rescue fixture')
        result = inventory.inspect(data)
        self.assertEqual(len(result['images']), 2)
        self.assertEqual(result['images'][0]['offset_bytes'], 512)
        self.assertTrue(all(i['header_crc_ok'] and i['payload_crc_ok'] for i in result['images']))
        self.assertFalse(result['recovery_tested'])
        self.assertFalse(result['flash_authorized'])

    def test_corrupt_payload_and_truncation(self):
        data = image(b'payload')
        self.assertFalse(inventory.inspect(data[:-1] + b'!')['images'][0]['payload_crc_ok'])
        self.assertEqual(inventory.inspect(data[:63])['images'], [])
        self.assertEqual(inventory.inspect(data[:-1])['images'], [])

    def test_no_environment_contents_reported(self):
        result = inventory.inspect(b'private environment data' + image(b'fixture'))
        self.assertNotIn('private environment', str(result))
