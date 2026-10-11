# SD validation: live device evidence and remaining image gates

## User-supplied live results

The external 128GB card is detected at approximately 119GiB, its normal binary capacity. This is not a capacity restriction requiring a partition change.

Later upload investigation again showed internal `/mnt/storage` writable and both SD mounts read-only, with ample SD space, block `ro=0`, and no currently loaded USB-export module. After a guarded user-run non-forced remount of **only** `/mnt/sdcard`, the returned mount table showed both internal and SD main mounts `rw` simultaneously. The user reported SD uploading appears to work. This is a temporary mount change; FTP was not changed, persistence was not enabled, and file-content/checksum/native failure/cancel tests were not returned. Historical USB gadget log entries were not treated as current export state. No formatting, repair or lock override occurred.

1. `/dev/mmcblk1p1` was mounted `texfat ro` at `/mnt/sdcard` and its FTP bind `/var/ftp/sdcard`.
2. `g_file_storage` was absent from `/proc/modules`; both disk sysfs and partition block read-only flags were zero. Historical gadget messages in dmesg do not mean the gadget is currently active.
3. Boot logs reported `mmcblk1 ... (ro)`. The cause of that boot-time condition is not established; current block flags do not prove the mechanical switch/sensor's boot state.
4. With USB export absent, the user ran a **non-forced** `mount -o remount,rw /mnt/sdcard`. The main mount became `rw`; the FTP bind stayed `ro`. No persistent mount setting was changed.
5. A guarded subshell confirmed the exact SD source/mount was `rw` and USB export absent, then atomically created a new test directory. It wrote one small fixed text file, synced, compared its SHA-256 with the expected content, removed only the probe file/directory, and synced again.
6. User output: `PASS: SD write, readback checksum, and cleanup`. No test data was retained.
7. After an ordinary synced reboot, the user reconnected successfully through the existing SSH route. Both SD mounts returned to `texfat ro`; `g_file_storage` remained absent and both block read-only flags remained zero. The runtime remount did not persist across reboot. This does not establish why boot selects read-only mode.
8. A second small marker was retained at `/mnt/sdcard/.nimbus-persistence-v1/probe.txt`. After another reboot, the user read it without remounting. Its SHA-256 matched the independently recorded expected hash `ca685d18d7584c3523d2d28840f9758f014f2ab8bc451ae4db6897b1709d08c0`. Both SD mounts again reported `ro`. Reboot readback has passed for this marker on the existing firmware. Cleanup is not yet confirmed; retain it for the USB readback checkpoint.
9. Initial USB diagnosis found `CFG_FUNC_MSC:true`, charger online, and both `event_manager` and `fw_server` running. Plain `ps` omitted these daemons; `ps -A` confirmed them. After the direct PC connection enumerated, user output established `g_file_storage` present and no internal-user-media or SD local mounts. No service/config/gadget override was used.
10. On the PC, USB vendor/product `0781:7600` and model `Media_Drive_Card` identified the SD LUN independently of its transient block name. Both exported media disks were initially unmounted. The agent mounted only the SD export with explicit `ro` via UDisks, verified the mount options, and read only the small retained marker. Its SHA-256 matched the expected reboot checksum. The agent unmounted that mount, verified both SanDisk exports were unmounted, and safely powered off/ejected the USB device via UDisks. No media filesystem writes were performed on the PC.
11. After PC eject alone, the drive still reported charger online and an active gadget, with media unmounted. This was not evidence of a completed physical disconnect or marker deletion. After physical cable removal, user output established charger `online=0`, gadget absent, internal user media and its FTP bind restored `rw`, and both SD mounts restored `ro`. Normal-state USB return passed without manual module/mount changes.
12. User subsequently read the retained marker through the restored SD mount. Its SHA-256 again matched `ca685d18d7584c3523d2d28840f9758f014f2ab8bc451ae4db6897b1709d08c0`. Post-return device readback passed. The retained marker remains available for the separately planned writable-SD handoff test; cleanup is not yet confirmed.
13. With the SD main mount manually remounted `rw` and its FTP bind left `ro`, the user connected USB and confirmed `g_file_storage` active with both local media filesystems unmounted. The agent independently identified both PC LUNs using USB vendor/product, model and their shared USB short serial (full UDisks/udev `ID_SERIAL` values differ per LUN). An initial sibling-identity guard stopped before mounting; the corrected shared-device check verified both exports unmounted. Read-only PC access to the retained marker again matched the expected SHA-256. The agent unmounted the SD and safely ejected the whole SanDisk USB device with both exports unmounted. Writable-SD outbound handoff and PC readback passed.
14. After physically unplugging the second cycle's cable, user output confirmed charger `online=0`, gadget absent, internal media/FTP bind restored `rw`, and SD/FTP bind restored `ro`. The retained marker's device-side checksum again matched the expected SHA-256. Writable-SD outbound/return and post-return data readback are complete for this live device. The marker has not yet been removed.

The user considers SD data disposable and declined a data backup. Existing internal/private firmware backups remain separate and must not be discarded.

## What passed

Basic live filesystem create/write/sync/readback/checksum/delete operations on the card passed after a manual non-forced remount. There were no SD I/O errors in the supplied filtered kernel output. This advances live SD capability validation; it is not a test of the custom candidate's SD policy.

The retained marker additionally passed SHA-256 readback after reboot through the read-only SD mount. This establishes this bounded file's reboot persistence; it is not an endurance, abrupt-power-loss or full-capacity verification.

Vendor USB outbound/return passed from both the normal mount state (internal user media rw, SD ro) and a manually writable SD state: neither filesystem remained locally mounted while the gadget exported them. Read-only PC USB readback of the marker passed in both cycles. After safe eject and physical disconnect, the vendor unloaded the gadget and restored internal media rw / SD ro; device-side marker readback also matched. These results do not establish the candidate image's behavior or a persistent writable-mount policy.

## What did not pass yet

- Abrupt-power-loss and endurance behavior: an ordinary reboot readback passed, not a destructive power-cut or stress test.
- Startup mount policy: observed to return both SD mounts to `ro` after reboot; the underlying boot-time cause and a safe writable policy remain unresolved.
- Candidate policy: both live USB cycles passed, but an image-level persistent writable-SD policy has not been implemented or tested. No simultaneous host/device filesystem access is permitted.
- FTP writes: the bind remains read-only, deliberately unchanged. It is not necessary to make FTP writable to prove the main filesystem works.
- Other cards/filesystems, boot-time lock/sensor behavior, endurance, full-capacity integrity, or abrupt-power-loss behavior.
- Custom image native boot, rescue/restoration or production readiness.

## Next checkpoint

The reboot mount-policy, bounded persistence and both live USB-cycle/readback checkpoints are complete. No more repetitions of these live checkpoints are required on the current evidence. Continue the separate live Settings validation and image boot/recovery work, and design the SD access policy without silently overriding a boot-time read-only condition. Do not manually load a gadget or run the automount script. These are live stock-firmware tests, not custom-image validation.

The retained marker can be kept temporarily or removed separately using a guarded non-forced manual remount and exact checksum/path verification; no recursive cleanup is needed. Cleanup is not yet confirmed. No automatic reboot, repair, format, lock override or persistent `rw` startup patch has been installed by this work.
