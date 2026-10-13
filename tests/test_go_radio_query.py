from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'device/wardrive-go-radio-query.sh'


def filters():
    text=SCRIPT.read_text()
    # Exercise the exact embedded filters, not a separate imitation.
    return [part.split("\n    '",1)[0] for part in text.split("| awk '\n")[1:]]


class RadioQueryTests(unittest.TestCase):
    def filter(self,index,text):
        result=subprocess.run(['awk',filters()[index]],input=text,text=True,capture_output=True,check=True,timeout=5)
        return result.stdout

    def test_advertised_modes_are_not_live_support_or_private_strings(self):
        text='Wiphy PRIVATE_RADIO\n\tSupported interface modes:\n\t * managed\n\t * AP\n\t * monitor\n\t * PRIVATE_MODE\n\tBand 1:\n\t * 2412 MHz [1]\n\tvalid interface combinations:\n private combo\n'
        result=self.filter(0,text)
        self.assertIn('ADVERTISED_MODE managed',result);self.assertIn('ADVERTISED_MODE AP',result)
        self.assertIn('ADVERTISED_MODE monitor',result)
        self.assertNotIn('PRIVATE',result);self.assertNotIn('2412',result)
        self.assertIn('reported_not_qualified',result)

    def test_interfaces_share_radio_but_identifiers_are_suppressed(self):
        text='phy#0\n\tInterface wlan1\n\t\taddr aa:bb:cc:dd:ee:ff\n\t\tssid PRIVATE_SSID\n\t\ttype AP\n\t\tchannel 6 (2437 MHz), width: 20 MHz\n\tInterface wlan0\n\t\ttype managed\n'
        result=self.filter(1,text)
        self.assertIn('RADIO wlan0 phy_index=0',result);self.assertIn('RADIO wlan1 phy_index=0',result)
        self.assertIn('INTERFACE_TYPE wlan1 AP',result)
        self.assertIn('CHANNEL wlan1 number=6 frequency_mhz=2437',result)
        self.assertNotIn('PRIVATE',result);self.assertNotIn('aa:bb',result)

    def test_unknown_interface_and_type_are_not_echoed(self):
        text='phy#0\n Interface PRIVATE_INTERFACE\n type monitor\n channel 6 (2437 MHz)\n Interface wlan0\n type PRIVATE_TYPE\n channel PRIVATE_CHANNEL\n'
        self.assertEqual(self.filter(1,text),'RADIO wlan0 phy_index=0\nINTERFACE_TYPE wlan0 unknown\n')

    def test_query_commands_are_fixed_and_do_not_trigger_scan_or_change_radio(self):
        text=SCRIPT.read_text()
        commands='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertEqual(text.count('LC_ALL=C /usr/sbin/iw '),2)
        self.assertIn('LC_ALL=C /usr/sbin/iw list ',text);self.assertIn('LC_ALL=C /usr/sbin/iw dev ',text)
        self.assertNotIn('iw dev wlan',text);self.assertNotIn(' scan ',text)
        for forbidden in (' set ','iwconfig','iwlist','modprobe','killall','fw_server','/etc/shadow'):
            self.assertNotIn(forbidden,commands)
        subprocess.run(['sh','-n',str(SCRIPT)],check=True,timeout=5)
