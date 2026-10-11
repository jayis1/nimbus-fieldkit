# SD validation: live device evidence and remaining image gates

## User-supplied live results

The external 128GB card is detected at approximately 119GiB, its normal binary capacity. This is not a capacity restriction requiring a partition change.

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

The user considers SD data disposable and declined a data backup. Existing internal/private firmware backups remain separate and must not be discarded.

## What passed

Basic live filesystem create/write/sync/readback/checksum/delete operations on the card passed after a manual non-forced remount. There were no SD I/O errors in the supplied filtered kernel output. This advances live SD capability validation; it is not a test of the custom candidate's SD policy.

The retained marker additionally passed SHA-256 readback after reboot through the read-only SD mount. This establishes this bounded file's reboot persistence; it is not an endurance, abrupt-power-loss or full-capacity verification.

Vendor outbound USB handoff passed from the observed normal mount state (internal user media rw, SD ro): neither filesystem remained locally mounted while the gadget exported them. Read-only PC USB readback of the marker passed. After safe eject and physical disconnect, the vendor unloaded the gadget and restored the original mount state; device-side marker readback also matched. This does not establish handoff from a manually writable SD mount or the candidate image's behavior.

## What did not pass yet

- Abrupt-power-loss and endurance behavior: an ordinary reboot readback passed, not a destructive power-cut or stress test.
- Startup mount policy: observed to return both SD mounts to `ro` after reboot; the underlying boot-time cause and a safe writable policy remain unresolved.
- Writable-SD handoff: normal-state outbound/return and read-only PC marker readback passed. Handoff from a manually writable SD mount remains pending. No simultaneous host/device filesystem access is permitted.
- FTP writes: the bind remains read-only, deliberately unchanged. It is not necessary to make FTP writable to prove the main filesystem works.
- Other cards/filesystems, boot-time lock/sensor behavior, endurance, full-capacity integrity, or abrupt-power-loss behavior.
- Custom image native boot, rescue/restoration or production readiness.

## Next checkpoint

The reboot mount-policy, bounded persistence, normal-state USB outbound/return, PC read-only marker and post-return device readback checkpoints are complete. Next test the vendor handoff from a manually writable SD mount, with USB initially disconnected and all media writers stopped. Confirm the exact SD source, absent gadget and zero block read-only flags before a non-forced remount; verify rw before connecting USB. Do not access host volumes until device-side evidence confirms that both media filesystems are unmounted and the gadget is active. Repeat read-only host readback, safe eject, physical disconnect and device return/readback. Do not manually load a gadget or run the automount script. This is a live stock-firmware policy test, not custom-image validation.

Remove only the verified test marker/directory after the return checks, using a guarded non-forced manual remount if necessary. Keep the marker until any separately planned writable-SD handoff test has completed. No automatic reboot, repair, format, lock override or persistent `rw` startup patch has been installed by this work.
