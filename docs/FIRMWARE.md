# Device direction and firmware bring-up

## What we have

The original project contains a product description, consumer specifications, and a source link, but no firmware image, board dump, toolchain, or application code.

From the supplied specs: 32/64 GB storage, SD slot, 2.4 GHz 802.11 b/g/n, USB 2.0, 1500 mAh battery. These do **not** establish RAM size, USB host/gadget capability, Wi-Fi monitor mode, or modern driver support.

Source reviewed on 2026-10-11:

- https://github.com/SanDisk-Open-Source/wireless-media-drive
- https://github.com/SanDisk-Open-Source/wireless-media-drive/blob/master/linux-2.6.35.3/config_nimbus_rescue_20120822_104

The repository includes `linux-2.6.35.3`, `u-boot-2009.08`, and `nimbus_source`. The rescue configuration enables `CONFIG_ARCH_MX50`, `CONFIG_MACH_MX50_NIMBUS`, and `CONFIG_MACH_MX50_NIMBUS_RESCUE`. Its command line references `ttymxc0,115200` and a RAM root filesystem. This is source evidence for an i.MX50/Nimbus platform, not confirmation of the exact board in your unit or its recovery procedure. Do not use a generic i.MX50 image.

## The hacker-device concept

**Nimbus FieldKit**: battery-powered, pocket-size Linux lab companion operated from a phone browser.

Updated GameHack direction: **SanDisk is the main Wi-Fi unit**, GameHack Zero is the controller, and the existing Pi is the USB worker. The phone/desktop browser is a secondary interface; a native controller menu is implemented. See `GAMEHACK.md` for staged integration and inactive AP candidates. The intended SanDisk LAN is distinct from the Pi USB subnet. Internet routing is not assumed.

| Function | v0.1 host prototype | Device version |
| --- | --- | --- |
| Offline dashboard | Implemented, no CDN | Serve over secured management Wi-Fi |
| System/network inventory | Actual host data | Board-specific metrics and battery driver |
| File/evidence vault | Read-only files and SHA-256 | SD-backed storage, quotas, optional encryption |
| TCP connectivity checks | One scoped IP, bounded port list | Same permission boundary |
| Wi-Fi survey / passive capture | Not implemented | Only if chipset/driver capabilities are verified |
| SSH administration | Not implemented | Key-only, disabled until configured |
| USB serial/Ethernet | Not implemented | Only if hardware and controller permit |

No claims of Kali compatibility, modern kernel support, WPA3, simultaneous AP/client mode, radio injection, or USB HID are made. Avoid WEP. Use WPA2-AES if supported; use WPA3 only after verification. Old firmware remains unsafe on untrusted networks even with a new dashboard.

## Delivery path

1. **Inventory and recovery first.** Confirm model/revision, SoC, RAM, flash layout, bootloader environment, Wi-Fi chipset/driver, boot logs, battery interface, and update format. Use the read-only inventory script only via existing authorized access. Identify UART pinout and voltage electrically; never assume pin assignments or connect 5 V TTL. Preserve vendor firmware and verified backups of bootloader/environment/calibration/partitions after the layout is understood. A source tree is not a recovery image.
2. **Disposable host prototype (this release).** Exercise the UI/API locally. Python is a convenient host implementation, not a promise that it runs on Linux 2.6.35.3. No embedded toolchain or image is generated yet.
3. **SD/RAM application proof.** After recovery is proven, determine a supported runtime/toolchain. Prefer a small cross-compiled service and BusyBox utilities, launched manually from removable storage; keep vendor bootloader and calibration untouched. Do not replace system services yet.
4. **Modern platform feasibility.** Evaluate maintained Buildroot and kernel support against actual board peripherals and available memory. Determine whether Wi-Fi, PMIC, SD, USB and battery drivers need porting. A legacy-kernel userspace refresh is not a 2026 security upgrade.
5. **Reproducible firmware.** Only after a bootable board port and tested recovery: pin dependencies, document licensing/SBOM, create authenticated updates and a recovery/rollback design appropriate to the verified flash layout. Validate power failure, battery charging, filesystem integrity, and radio regulations.

## Release gate

Do not flash until we have a known-good backup and tested recovery, exact partition map, verified image format, successful non-destructive boot, and a rollback test. No flash commands are supplied because these prerequisites are missing.

Next useful input: the drive's model/revision, firmware version, whether shell/serial access already exists, and reviewed output from `device-inventory.sh`. Do not post keys, passwords, or private captures.
