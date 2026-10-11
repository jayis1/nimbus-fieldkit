# SD validation: live device evidence and remaining image gates

## User-supplied live results

The external 128GB card is detected at approximately 119GiB, its normal binary capacity. This is not a capacity restriction requiring a partition change.

1. `/dev/mmcblk1p1` was mounted `texfat ro` at `/mnt/sdcard` and its FTP bind `/var/ftp/sdcard`.
2. `g_file_storage` was absent from `/proc/modules`; both disk sysfs and partition block read-only flags were zero. Historical gadget messages in dmesg do not mean the gadget is currently active.
3. Boot logs reported `mmcblk1 ... (ro)`. The cause of that boot-time condition is not established; current block flags do not prove the mechanical switch/sensor's boot state.
4. With USB export absent, the user ran a **non-forced** `mount -o remount,rw /mnt/sdcard`. The main mount became `rw`; the FTP bind stayed `ro`. No persistent mount setting was changed.
5. A guarded subshell confirmed the exact SD source/mount was `rw` and USB export absent, then atomically created a new test directory. It wrote one small fixed text file, synced, compared its SHA-256 with the expected content, removed only the probe file/directory, and synced again.
6. User output: `PASS: SD write, readback checksum, and cleanup`. No test data was retained.

The user considers SD data disposable and declined a data backup. Existing internal/private firmware backups remain separate and must not be discarded.

## What passed

Basic live filesystem create/write/sync/readback/checksum/delete operations on the card passed after a manual non-forced remount. There were no SD I/O errors in the supplied filtered kernel output. This advances live SD capability validation; it is not a test of the custom candidate's SD policy.

## What did not pass yet

- Power-cycle/reboot persistence of data: immediate checksum reads can be satisfied from cache despite sync. The small test file was removed, so it cannot prove reboot readback.
- Startup mount policy: no evidence yet establishes whether vendor boot remounts the card `rw` or returns it to `ro`.
- USB ownership handoff while writable: no simultaneous host/device filesystem access is permitted. A safe handoff and return must be validated before a persistent mount-policy change.
- FTP writes: the bind remains read-only, deliberately unchanged. It is not necessary to make FTP writable to prove the main filesystem works.
- Other cards/filesystems, boot-time lock/sensor behavior, endurance, full-capacity integrity, or abrupt-power-loss behavior.
- Custom image native boot, rescue/restoration or production readiness.

## Next checkpoint

Keep the USB data cable disconnected, stop uploads/playback and other writes, then perform an ordinary synced reboot of the existing firmware when convenient. Reconnect through the existing pinned SSH route and inspect SD mounts, gadget presence and read-only flags. Do not apply another remount before collecting that evidence.

A subsequent guarded retained-marker/reboot/readback test can establish persistence; it should keep one uniquely created small file with an independently recorded expected hash, then remove only that marker after successful verification. No automatic reboot, repair, format, lock override or persistent `rw` startup patch has been installed by this work.
