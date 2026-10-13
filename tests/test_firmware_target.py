import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('firmware_target_builder',ROOT/'scripts/build-custom-image.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class FirmwareTargetTests(unittest.TestCase):
    def test_64gb_model_is_intent_not_partition_geometry_or_flash_permission(self):
        target=builder.target_profile('sandisk-wireless-media-drive-64gb')
        self.assertEqual(target['advertised_internal_storage_gb'],64)
        self.assertEqual(target['rootfs_bytes'],268435456)
        self.assertFalse(target['native_compatibility_verified'])
        self.assertTrue(target['preserve_recipient_geometry'])
        self.assertFalse(target['includes_user_media'])
        self.assertFalse(target['includes_bootloader_or_calibration'])

    def test_generic_profile_cannot_claim_a_capacity(self):
        self.assertIsNone(builder.target_profile('generic')['advertised_internal_storage_gb'])

    def test_other_products_and_unknown_targets_refused(self):
        for name in ('wireless-stick-64gb','wireless-flash-drive','128gb','../64gb',None):
            with self.subTest(name=name),self.assertRaises(ValueError):builder.target_profile(name)
