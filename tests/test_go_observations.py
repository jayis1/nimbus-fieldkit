import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('go_observations',ROOT/'scripts/wardrive-go-observations.py')
observations=importlib.util.module_from_spec(spec);sys.modules[spec.name]=observations;spec.loader.exec_module(observations)
FIXTURE=(b'BSS 02:11:22:33:44:55(on wlan1) -- associated\n'
         b'\tfreq: 2437\n\tsignal: -45.50 dBm\n\tlast seen: 120 ms ago\n'
         b'\tSSID: PRIVATE_SSID\\x00\n\tRSN: PRIVATE_INFORMATION_ELEMENT\n')


class CacheObservationTests(unittest.TestCase):
    def parse(self,data=FIXTURE,**changes):
        values={'interface':'wlan1','received_mono_ms':100000};values.update(changes)
        return observations.parse_cache(data,**values)

    def test_cache_record_is_private_not_a_live_scan_or_verified_location(self):
        result=self.parse();self.assertEqual(len(result),1)
        self.assertNotIn('PRIVATE',repr(result[0]));self.assertNotIn('02:11',repr(result[0]))
        record=result[0].private_record()
        self.assertEqual(record['ssid_display'],'PRIVATE_SSID\\x00')
        self.assertEqual(record['estimated_observed_mono_ms'],99880)
        self.assertEqual(record['acquisition_mode'],'unknown');self.assertIsNone(record['location'])
        self.assertFalse(record['observation_time_verified']);self.assertFalse(record['native_scan_verified'])
        self.assertNotIn('PRIVATE_INFORMATION_ELEMENT',str(record))

    def test_empty_and_hidden_ssid_are_valid_not_invented(self):
        self.assertEqual(self.parse(b''),[])
        record=self.parse(FIXTURE.replace(b'PRIVATE_SSID\\x00',b''))[0]
        self.assertEqual(record.ssid_display,'')

    def test_signal_frequency_age_and_format_bounds(self):
        for old,new in ((b'2437',b'9999'),(b'-45.50',b'NaN'),(b'-45.50',b'1'),
                        (b'120 ms',b'60001 ms'),(b'120 ms',b'-1 ms'),
                        (b'SSID: PRIVATE',b'SSID: \x01PRIVATE')):
            with self.subTest(new=new),self.assertRaises(observations.Refused):self.parse(FIXTURE.replace(old,new))
        with self.assertRaises(observations.Refused):self.parse(received_mono_ms=119)

    def test_duplicate_fields_or_identifiers_refuse_not_merge(self):
        with self.assertRaises(observations.Refused):self.parse(FIXTURE+b'\tfreq: 2412\n')
        with self.assertRaises(observations.Refused):self.parse(FIXTURE+FIXTURE)

    def test_multicast_zero_wrong_interface_and_header_refuse(self):
        for old,new in ((b'02:11:22:33:44:55',b'01:11:22:33:44:55'),
                        (b'02:11:22:33:44:55',b'00:00:00:00:00:00'),
                        (b'wlan1',b'wlan0'),(b'BSS ',b'bad ')):
            with self.subTest(new=new),self.assertRaises(observations.Refused):self.parse(FIXTURE.replace(old,new))

    def test_size_record_and_line_budgets(self):
        with self.assertRaises(observations.Refused):self.parse(b'x'*65537)
        with self.assertRaises(observations.Refused):self.parse(FIXTURE+b'\t'+b'x'*512+b'\n')
        data=b''.join(FIXTURE.replace(b'02:11:22:33:44:55',f'02:11:22:33:44:{index:02x}'.encode()) for index in range(129))
        with self.assertRaises(observations.Refused):self.parse(data)

    def test_missing_truncated_and_nul_records_refuse_without_echo(self):
        for data in (FIXTURE[:-1],FIXTURE.replace(b'\tfreq: 2437\n',b''),FIXTURE+b'\0\n'):
            with self.subTest(length=len(data)),self.assertRaises(observations.Refused) as caught:self.parse(data)
            self.assertNotIn('PRIVATE',str(caught.exception));self.assertNotIn('02:11',str(caught.exception))

    def test_input_type_and_receipt_clock_validation(self):
        for now in (True,-1,1.5):
            with self.assertRaises(observations.Refused):self.parse(received_mono_ms=now)
        with self.assertRaises(observations.Refused):self.parse(FIXTURE.decode())
        with self.assertRaises(observations.Refused):self.parse(interface='other')

    def test_parser_has_no_command_transport_or_storage(self):
        source=(ROOT/'scripts/wardrive-go-observations.py').read_text()
        for forbidden in ('import subprocess','import socket','open(','write_text(','write_bytes(','eval(','exec('):
            self.assertNotIn(forbidden,source)
