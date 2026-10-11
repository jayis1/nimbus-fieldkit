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

The user considers SD data disposable and declined a data backup. Existing internal/private firmware backups remain separate and must not be discarded.

## What passed

Basic live filesystem create/write/sync/readback/checksum/delete operations on the card passed after a manual non-forced remount. There were no SD I/O errors in the supplied filtered kernel output. This advances live SD capability validation; it is not a test of the custom candidate's SD policy.

The retained marker additionally passed SHA-256 readback after reboot through the read-only SD mount. This establishes this bounded file's reboot persistence; it is not an endurance, abrupt-power-loss or full-capacity verification.

## What did not pass yet

- Abrupt-power-loss and endurance behavior: an ordinary reboot readback passed, not a destructive power-cut or stress test.
- Startup mount policy: observed to return both SD mounts to `ro` after reboot; the underlying boot-time cause and a safe writable policy remain unresolved.
- USB ownership handoff while writable: no simultaneous host/device filesystem access is permitted. A safe handoff and return must be validated before a persistent mount-policy change.
- FTP writes: the bind remains read-only, deliberately unchanged. It is not necessary to make FTP writable to prove the main filesystem works.
- Other cards/filesystems, boot-time lock/sensor behavior, endurance, full-capacity integrity, or abrupt-power-loss behavior.
- Custom image native boot, rescue/restoration or production readiness.

## Next checkpoint

The reboot mount-policy and bounded persistence checkpoints are complete: startup returns the SD to read-only, but the marker survives and reads correctly. Next verify the vendor USB handoff, with uploads/playback and other writers stopped. After connecting to the trusted PC, do not open/write host volumes until device-side mount/module evidence confirms internal user media and SD are no longer locally mounted and the USB storage gadget is active. Do not manually load a gadget or run the automount script.

Once exclusive ownership is verified, host-side read-only SHA-256 of the retained SD marker can test USB readback. Then safely eject all exported volumes on the PC, disconnect data, and inspect the device-side gadget/mount state before any device write. Remove only the verified test marker/directory after the handoff checks, using a guarded non-forced manual remount if necessary. No automatic reboot, repair, format, lock override or persistent `rw` startup patch has been installed by this work.
