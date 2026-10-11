# Custom firmware and USB recovery: preliminary read-only review

Reviewed 2026-10-11. No firmware scripts or ARM binaries were executed, no device configuration was changed, and no image was built or flashed.

## Outcome

A stock-based rootfs customization remains a plausible way to install one combined vendor/FieldKit dashboard at `/`. **Direct USB flashing is not established.** Normal vendor USB mode exposes media, not the system disk. A verified update container, matching rescue image, device backups and tested recovery remain release gates.

## Evidence inspected

- Local `sandiskmediafirmware-3-04.img` and its previously inspected EXT payload/rootfs archive.
- Package `fw_info.conf`, `preaction.sh`, `postaction.sh`, read as data via read-only `debugfs` commands.
- Rootfs update/recovery scripts, `platform_functions`, configuration and static strings/DWARF in `make_image`.
- Public source at `https://github.com/SanDisk-Open-Source/wireless-media-drive`: `u-boot-2009.08/include/configs/mx50_nimbus.h` and `u-boot-2009.08/common/cmd_nimbus.c` (master fetched on review date; not a pinned build dependency).
- Host USB/block inventory. No SanDisk device was identified in the current USB list. Other storage devices must not be treated as this drive.

Temporary review files are under `/tmp/opencode/nimbus-recovery-review/`; the original firmware file is unchanged.

## Normal USB mode

`nimbus_load_gadget()` in `opt/qsi/config/platform_functions` builds a list of block partitions for `g_file_storage`. It explicitly skips configured root, settings and firmware-pool partitions. Its fallback is user storage `/dev/mmcblk0p4`.

Therefore copying an update file over USB may be a delivery mechanism for the vendor updater, **not permission to write the rootfs or bootloader from the host**. This source does not establish accessible i.MX ROM USB recovery or a USB flashing protocol on this physical unit.

## Vendor update flow

- `checkfwimage.sh` scans mounted media with `make_image`, compares version values and writes the selected path to the bootloader environment. Even this apparently diagnostic script is **not read-only**; do not run it during inventory.
- `fw_upgrade.sh` checks the selected package with `make_image`, writes rescue/update environment flags, stops services, unmounts media and reboots. Do not run it as a test.
- The supplied package contains a rootfs archive and kernel, but no matching standalone rescue image or U-Boot image was observed in its top-level file list.
- `preaction.sh` can update U-Boot or rescue if matching files are present, and changes bootloader state even without them. It also backs up calibration/configuration and removes files in the firmware pool.
- `postaction.sh` restores the Wi-Fi NVS and databases, removes backup files and may remove the update package.

These scripts are not evidence of atomic updates, reliable rollback or power-loss safety. The actual rescue-side rootfs writer remains to be examined.

## Source-level SD rescue

`cmd_nimbus.c` expects a FAT SD card with files named `rescue` and `nimbus.img`. It checks a `Nimbus-rescue-V` tag in the loaded rescue image. **It then writes that rescue image to internal MMC before booting it.** This is not a non-destructive RAM boot.

The Nimbus header mentions a power-key rescue gesture, but source comments are not a verified operating procedure for the installed bootloader. No gesture or rescue command should be tried yet. Separate source support for replacing U-Boot from SD is also destructive and outside the initial customization plan.

## Image wrapper: partial understanding only

The known container has a 152-byte header. DWARF metadata in the vendor `make_image` binary describes fields at offsets:

| Offset | Field |
| --- | --- |
| 4 | `imh_head_crc` |
| 8 | `imh_data_crc` |
| 12 | `imh_time` |
| 20 | `imh_fw_version` |
| 24 | `img_name` |

The inspected binary includes CRC32 computation/check/make/extract symbols. That suggests further static analysis is useful; it does **not** prove the entire update chain accepts unsigned/custom images.

For this image, the standard zlib CRC32 of bytes after offset 152 is `0xabcbe0ca`, while the little-endian word at offset 8 is `0x40000000`. The payload checksum algorithm/range/semantics therefore cannot be assumed to be ordinary full-payload CRC32. No repacker should be declared valid on that assumption.

The public source tree provides kernel, bootloader, web client and open-source components. No `make_image` implementation was identified by filename in the complete repository tree. It should not be described as a complete reproducible vendor firmware build kit.

## Partition evidence and next gate

Vendor configuration identifies internal MMC partitions p1=settings, p2=rootfs, p3=firmware pool, p4=user media. `etc/fw_env.config` references an environment region on the whole internal MMC. These are package/source expectations, not a full verified live sector map or backup.

Next collect read-only `/proc/partitions` and sysfs start/size values from the live device; then determine an authorized method to back up system partitions, bootloader/environment, rescue and unique calibration. Do not dump credentials into chat. Root access remains unavailable, and no full-device backup or recovery test exists.

Initial custom-image scope, once gates pass: preserve vendor kernel/modules, Wi-Fi, charging support, partition layout, bootloader, rescue and device calibration; replace the homepage with the genuinely integrated UI and add a narrowly authenticated toolkit backend. The current v0.4 side dashboard is not that unified image. Retaining the legacy kernel is not a modern security upgrade.

## Live partition boundaries supplied by user

The live `/proc/partitions` and `/sys/class/block/mmcblk0p*/{start,size}` output confirms these boundaries. Sysfs values use 512-byte sectors; `/proc/partitions` reports KiB blocks.

| Internal partition | Start sector | Sector count | Start offset | Size | Role from vendor configuration |
| --- | ---: | ---: | ---: | ---: | --- |
| mmcblk0p1 | 30720 | 8192 | 15 MiB | 4 MiB | Settings |
| mmcblk0p2 | 38912 | 524288 | 19 MiB | 256 MiB | Rootfs |
| mmcblk0p3 | 563200 | 409600 | 275 MiB | 200 MiB | Firmware pool |
| mmcblk0p4 | 972800 | 121169920 | 475 MiB | 60584960 KiB | User media |

The entire internal device is reported as 61071360 KiB. The initial 15 MiB lies before p1 and must not be discarded as empty space: vendor source references bootloader/environment/kernel/rescue regions there. Their live contents and exact layout remain unverified. Partitions p1–p4 are contiguous in the reported map.

External `mmcblk1` reports 124868608 KiB, with p1 at 124852224 KiB; its start sector was not supplied. Earlier live mount output showed this SD filesystem read-only. It is not a verified backup destination.

No block-device permissions, backup readability, raw backups or recovery test have yet been established. Next check read permissions without reading block-device contents; do not change permissions, use raw writes or initiate upgrades.

## Follow-up: validator reproduced and backup permissions checked

User output establishes root:disk ownership with mode `0640` on the internal disk and p1–p3; `admin` fails read-permission tests for the disk and rootfs. Raw backups are currently blocked.

Static ARM disassembly of `make_image` reveals:

- Magic is big-endian `0x57ae2d64`.
- Header is 152 bytes. Header CRC is stored big-endian; calculate over all 152 bytes after zeroing offsets 4–7.
- Payload length at offset 16 is loaded as little-endian; firmware version at offset 20 is big-endian.
- CRC uses the reflected `0xedb88320` table, initial byte seed 255 and no final XOR.
- Payload is read in 4096-byte blocks. Each new call receives **only the low byte** of the previous result. Exact multiples include a final empty-read call, which leaves only that low byte. This is a weak integrity check, not authentication.
- The inspected check function compares magic, header CRC, total length and (in full-check mode) payload CRC. No cryptographic signature verification is visible in this function; other updater layers remain unverified.

New read-only tool: `python3 scripts/inspect-firmware.py sandiskmediafirmware-3-04.img`. It neither extracts nor modifies firmware and always reports `flash_ready: false`.

The original local 3.04 image passes all four reproduced checks: header CRC `52840f42`, payload CRC `00000040`, payload size 102027264 bytes, version word `03040000`. Original SHA-256 remains `de0737753b50408bcb1fdd1c8a1d9fd8ce7977d7eda87faa2ace1bfc83efb095`. This supersedes the earlier uncertainty about checksum calculation; it does not prove authenticity or flash readiness. Four new regression tests cover CRC arithmetic, empty-final-block behavior, length checks, input preservation and truncated headers; total suite passed 65 tests.

### Rescue search and alternative access lead

Targeted web searches and the public community repository did not locate a verified matching standalone Nimbus rescue binary. Normal update-image availability must not be confused with a full bootloader/rescue recovery kit. Reports about Wireless Stick/Flash Drive and Acronis/RescuePRO are different products or PC recovery tools and cannot be used here.

Community reports specifically for the Wireless Media Drive publish a factory root credential. Sources: `https://raw.githubusercontent.com/ysfchn/sandisk-wireless/main/wireless_media/README.md` and `http://www.gbppr.net/2600/v31n2-sandisk.html` (the second located via search excerpt; not independently fetched in this review). This is an unverified credential on this user's device, not proof of root access. A manual single authentication attempt on the user's own device could establish access for backup without flashing; no automated attempts, password cracking or device login was performed. Never put private device credentials or raw backup contents into the public media dashboard.

## Root login and first backup: subsequent live results

The user successfully logged in directly through Telnet as root and supplied `id` showing uid/gid 0. `su` from admin failed because the installed `/bin/tinylogin` lacks set-user-ID permission; no permissions were changed. A unified homepage installation is now possible with authorized root access, without a firmware flash, after off-device backup verification and a reviewed installer.

User created `/mnt/storage/nimbus-backup-20261011-024951` and reported all seven files passing device-side `sha256sum -c`:

- `boot-area.bin`: 15728640 bytes (initial 15 MiB)
- `settings.bin`: 4194304 bytes
- `rootfs.bin`: 268435456 bytes
- `fwpool.bin`: 209715200 bytes
- `wl1271-nvs.bin`: 912 bytes
- `stock-web.tar`: 18728960 bytes
- `partitions.txt`: 269 bytes

These are live raw partition reads, not quiesced filesystem snapshots or a full disk image (user media and disk tail are not included). Checksums establish copy integrity, not filesystem consistency, recoverability, vendor authenticity or boot compatibility. No restore was tested.

Host transfer destination: `.private-backups/nimbus-backup-20261011-024951/`, directory mode 0700 and files 0600. Treat the whole directory as sensitive and exclude it from source control, sharing and distribution. Device storage uses texfat and reported 0777 files despite umask; backups there may be exposed by stock HTTP/FTP. Keep management networks isolated. No device backups were removed.

At this entry's writing, boot-area and settings host copies were size/checksum verified. Initial transfer timed out during rootfs; a resumable background transfer was started, accepting continuation only on an exact HTTP Content-Range match. **Remaining host copies are not yet confirmed.** Do not treat a partial local file as a verified backup or proceed to replacement until all seven hashes/sizes pass. No homepage or firmware was changed.

Transfer completion: all seven host files subsequently passed exact size and SHA-256 verification against the device manifest. The rootfs transfer resumed successfully with the expected Content-Range. The off-device copy-integrity gate is complete; live-filesystem consistency and restore/recovery boot are still untested. No homepage or firmware changes were performed by the transfer.
