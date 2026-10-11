# Added firmware: read-only inspection

Inspected on 2026-10-11. Original image was not modified, mounted, flashed, or executed. Firmware scripts/binaries were read as data only. Temporary inspection copies are in `/tmp/opencode/sandisk-fw-3-04/`.

## Input

- File: `sandiskmediafirmware-3-04.img`
- Size: **102,027,416 bytes**
- SHA-256: `de0737753b50408bcb1fdd1c8a1d9fd8ce7977d7eda87faa2ace1bfc83efb095`
- Another added directory, `System Volume Information`, contains `IndexerVolumeGuid` and `WPSettings.dat`. These are Windows volume metadata, not firmware components; left untouched.

The hash records the local file, not vendor authenticity. No trusted vendor checksum/signature was supplied.

## Container and kernel

The image has an apparent vendor wrapper followed by an EXT-family filesystem at offset **0x98 (152 bytes)**. Its superblock reports 99,636 blocks of 1,024 bytes, exactly matching the remaining file length. The wrapper's full schema, validation rules, and cryptographic authentication remain unverified.

Read-only `debugfs` inspection lists:

| File | Size |
| --- | ---: |
| `fw_info.conf` | 84 bytes |
| `preaction.sh` | 3,065 bytes |
| `postaction.sh` | 2,414 bytes |
| `rootfs_nimbus_v3.04.tar` | 89,524,580 bytes |
| `uImage` | 2,243,048 bytes |

`fw_info.conf` declares version **3.04**, internal image name `Nimbus_FW3.04.img`, and size 102,027,416. The rootfs file is gzip-compressed despite its `.tar` name; its archive contains 4,399 entries. Files were read through `tarfile.extractfile`; no bulk extraction or execution was used.

The logical `uImage` file identifies **Linux-2.6.35.3-899-g9b1a262**, ARM, uncompressed uImage payload. Both the uImage header CRC and kernel payload CRC pass. This confirms those embedded checks, not the complete update package or safe compatibility with a particular unit. Files inside EXT can be fragmented: raw byte carving must not be substituted for reading the logical file.

## Strong evidence for the selected Wi-Fi topology

The firmware supports the *design* we want:

```text
Phone 2.4 GHz hotspot
        |
SanDisk client/uplink: wlan1
SanDisk AP/downstream: wlan0
        |
GameHack Zero controller
        |
Existing USB Pi worker (separate route configuration needed for Pi Internet)
```

Evidence from this archive:

- `opt/qsi/config/nimbus.conf`: `WLAN_AP="wlan0"`, `WLAN_STA="wlan1"`, vendor AP address **192.168.11.1**, and `FEATURE_DHCPC="true"`.
- `etc/rc.d/init.d/service/wpa_supplicant`: creates a managed `wlan1` interface with `iw` and uses the `nl80211` backend.
- `etc/rc.d/init.d/service/routing`: explicitly describes multi-role AP-through-STA Internet access; enables `/proc/sys/net/ipv4/ip_forward` and installs an iptables `MASQUERADE` rule on the station interface.
- `etc/rc.d/init.d/service/S01wifi`: invokes the routing service.
- `lib/modules/2.6.35.3-899-g9b1a262/updates/drivers/net/wireless/wl12xx/`: contains `wl12xx.ko` and `wl12xx_sdio.ko`.
- `lib/firmware/ti-connectivity/`: includes `wl1271-nvs.bin`, `wl127x-fw-4-mr.bin`, `wl127x-fw-4-sr.bin`, and calibration/test firmware. This points to the TI WL12xx/WL127x family; it does not establish the exact chip/board revision in the user's unit.
- Hostapd and wpa_supplicant binaries, `iw`, BusyBox DHCP utilities, MaraDNS, iptables links to `xtables-multi`, and NAT/masquerade kernel modules are present. A WPA2-AES hostapd template exists.

**Conclusion:** AP/client Internet sharing is not merely speculative now; this firmware contains a vendor implementation. Live interface-combination limits, channel behavior, phone compatibility, stable throughput, and current device configuration are still untested.

The existing prototype's proposed 192.168.78.1 LAN and nftables candidates are **not** the stock setup. Do not apply them blindly: stock uses 192.168.11.1 and legacy iptables/BusyBox/MaraDNS services. Check phone subnet overlap before selecting a new LAN. No Python or dnsmasq executable was found by archive filename inspection, so the host prototype must not be assumed to run unchanged on the stock rootfs.

## Security and recovery implications

- Preserve device-specific `wl1271-nvs.bin` and calibration information. The package's upgrade scripts reference backing up/restoring the NVS file; a generic replacement can damage radio operation/regulatory correctness.
- The vendor routing script contains optional HTTP forwarding and a stop/reset path that flushes iptables tables. Do not execute it casually as a diagnostic or copy its firewall policy as a secure default.
- Version 3.04 is legacy firmware, not a modern security upgrade. AP encryption templates alone do not establish the device's current security settings.
- The archive includes SSH/Dropbear service material, but this is **not** proof of enabled SSH, valid authorized access, or secure authentication on the device. No password files or keys were inspected.
- Wrapper validation, exact board compatibility, installed firmware, bootloader/partition backup, and tested recovery are still required before repacking or flashing.

## Next non-destructive test

1. Confirm the live model and firmware version. If existing authorized shell access works, collect `scripts/device-inventory.sh` output.
2. In the stock app/UI, look for its upstream Internet/network connection feature. If available, join the phone's 2.4 GHz hotspot while leaving the drive's own secured AP enabled. Do not run extracted service scripts.
3. Join the drive AP from GameHack and verify Internet access through it. Record actual AP address, AP/station interfaces, channel and route behavior. Review exposure of HTTP/FTP services to the hotspot side.
4. Keep Pi USB routing unchanged during this first test. Only after GameHack Internet works should Pi forwarding be separately configured and tested.

No hardware test has been performed by this inspection.
