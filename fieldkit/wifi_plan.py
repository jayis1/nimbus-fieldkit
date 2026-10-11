#!/usr/bin/env python3
"""Generate private, INACTIVE SanDisk main-Wi-Fi configuration candidates."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re


def render(interface, ssid, password, channel, country, uplink=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', interface):
        raise ValueError('Invalid interface name')
    if not 1 <= len(ssid.encode()) <= 32 or not ssid.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in ssid):
        raise ValueError('SSID must be 1–32 printable ASCII bytes')
    if not 8 <= len(password) <= 63 or not password.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in password):
        raise ValueError('WPA2 passphrase must be 8–63 printable ASCII characters')
    if channel not in range(1, 12):
        raise ValueError('Select a 2.4 GHz channel from 1 to 11; hardware/regulatory checks still required')
    if not re.fullmatch('[A-Z]{2}', country):
        raise ValueError('Supply your actual two-letter country code')
    if uplink is not None and (not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', uplink) or uplink == interface):
        raise ValueError('Uplink must be a separate verified interface from the AP')
    # Hex SSID avoids config-line parsing ambiguity. WPA2-AES only, no WEP/TKIP/WPS.
    hostapd = f'''# INACTIVE CANDIDATE: requires verified driver and recovery
interface={interface}
driver=nl80211
ssid2={ssid.encode().hex()}
country_code={country}
ieee80211d=1
hw_mode=g
channel={channel}
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase={password}
ap_isolate=1
'''
    dnsmasq = f'''# INACTIVE CANDIDATE: address 192.168.78.1/24 must be assigned separately
interface={interface}
bind-interfaces
port=0
dhcp-range=192.168.78.20,192.168.78.60,255.255.255.0,1h
# Control LAN only: no default gateway and no DNS advertisement
dhcp-option=3
dhcp-option=6
'''
    if uplink:
        dnsmasq = dnsmasq.replace('port=0', 'port=53\nno-resolv\n# EXAMPLE resolvers; review privacy/reachability for your phone carrier\nserver=1.1.1.1\nserver=9.9.9.9')
        dnsmasq = dnsmasq.replace('dhcp-option=3\n', 'dhcp-option=3,192.168.78.1\n')
        dnsmasq = dnsmasq.replace('dhcp-option=6\n', 'dhcp-option=6,192.168.78.1\n')
        dnsmasq = dnsmasq.replace('# Control LAN only: no default gateway and no DNS advertisement', '# Gateway candidate: advertise SanDisk as router and DNS')
    files = {'hostapd.conf': hostapd, 'dnsmasq.conf': dnsmasq,
            'plan.json': json.dumps({'status': 'inactive/unverified', 'role': 'main Wi-Fi unit',
                                    'controller': 'GameHack Zero', 'worker': 'Pi Zero W over USB',
                                    'interface': interface, 'address': '192.168.78.1/24',
                                    'pi_usb_network': '192.168.77.0/24', 'internet_gateway': bool(uplink),
                                    'uplink_interface': uplink, 'uplink_source': 'phone hotspot' if uplink else None,
                                    'requirements': ['verified nl80211 AP support', 'tested recovery',
                                                     'DHCP/AP binaries', 'static address and firewall review',
                                                     'TLS/authenticated file service', 'regulatory channel verification']
                                    + (['verified simultaneous AP+client support', 'non-overlapping phone subnet',
                                        'DHCP client/default route on uplink', 'working phone Internet/tethering',
                                        'reviewed DNS resolvers', 'modern nftables support',
                                        'explicit IPv4 forwarding activation'] if uplink else [])}, indent=2) + '\n'}
    if uplink:
        # New isolated tables, no flush ruleset. NEVER applied by this generator.
        files['gateway.nft'] = f'''# INACTIVE modern-kernel candidate; NOT compatible with stock Linux 2.6.35
# Review existing rules, interface names, overlap and forwarding before activation.
# IPv4 only. No inbound port forwards, IPv6 routing or Pi route changes.
table ip nimbus_nat {{
  chain postrouting {{
    type nat hook postrouting priority srcnat; policy accept;
    ip saddr 192.168.78.0/24 oifname "{uplink}" masquerade
  }}
}}
table inet nimbus_firewall {{
  chain input {{
    type filter hook input priority filter; policy drop;
    iifname "lo" accept
    ct state invalid drop
    ct state established,related accept
    iifname "{interface}" udp dport {{ 53, 67 }} accept
    iifname "{interface}" tcp dport {{ 53, 443 }} accept
    iifname "{uplink}" udp sport 67 udp dport 68 accept
    ip protocol icmp accept
  }}
  chain forward {{
    type filter hook forward priority filter; policy drop;
    ct state invalid drop
    iifname "{interface}" oifname "{uplink}" ip saddr 192.168.78.0/24 accept
    iifname "{uplink}" oifname "{interface}" ip daddr 192.168.78.0/24 ct state established,related accept
  }}
}}
'''
    return files


def write_plan(output, files):
    # Refuse existing output entirely so no configs or credentials are overwritten.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, contents in files.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(contents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', required=True)
    parser.add_argument('--ssid', default='GameHack-Nimbus')
    parser.add_argument('--country', required=True)
    parser.add_argument('--channel', type=int, default=6)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--uplink', help='Separate, verified phone-hotspot client interface; generates inactive IPv4 gateway candidates')
    args = parser.parse_args()
    password = getpass.getpass('New WPA2 passphrase (not saved in command history): ')
    try:
        files = render(args.interface, args.ssid, password, args.channel, args.country, args.uplink)
        write_plan(args.output, files)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f'Inactive candidates written privately to {args.output}; nothing started or installed.')


if __name__ == '__main__':
    main()
