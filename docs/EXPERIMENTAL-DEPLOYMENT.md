# Single-device experimental deployment — preparation, not a flash guide

The user has elected to use the existing drive as the experimental device, accepting the possibility of a brick. That permits planning a concrete trial, not representing it as a production-ready release. **Unbricking is not guaranteed.** No spare drive or independently established boot-console/ROM recovery access is currently available.

This document contains no deployment command, updater invocation, bootloader flag write or partition-write instruction. No experimental flash has been performed.

Initial preparation checkpoint: **109 local tests passed**, including read-only preflight fixtures, USB-export refusal and mismatched partition-boundary refusal. At that checkpoint the script had not been run on the physical drive; fixture results are not hardware evidence. The previously built v4 image artifacts are unchanged by these host-streamed diagnostic/backup additions.

Subsequent user-supplied physical preflight passed with zero inventory failures: kernel `2.6.35.3-899-g9b1a262`, architecture `armv7l`, all four reviewed partition boundaries and 122142720 whole-disk sectors. Root was `/dev/root` mounted ext3 rw with writeback/barrier=0; USB export was inactive and vendor services were present. External power was 0, battery status Discharging, voltage 4113872 microvolts. Voltage alone is not a trustworthy battery-percent or stable-power certification; trial power remains unresolved. No block writes were performed by this preflight.

## Staged trial

### 1. Read-only hardware preflight

`device/experimental-flash-preflight.sh` checks the expected internal partition boundaries, disk size, hardware architecture, root mount, USB export state and available power evidence. It uses fixed read-only kernel metadata paths and does not read settings, keys, bootloader environment or raw partition contents.

From the trusted host workspace, stream this source through the existing pinned SSH connection:

```sh
ssh -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2224 root@172.16.10.178 'sh -s' \
  < device/experimental-flash-preflight.sh
```

Run from the SanDisk project on the PC, not the drive's root prompt. The key passphrase is entered locally; do not send it to chat. Use the actual current address if DHCP changes, preserving verified host identity. Do not bypass pinning on a mismatch. Success only confirms selected inventory predicates; it does not authorize flashing or prove recoverability. External power `online=0` is reported, not a recommendation to write on battery; stable trial power must be arranged separately without concurrent PC media access.

### 2. Refresh private rollback material

Keep both earlier verified backup sets. They predate important live SSH/UI/network changes and must not be mistaken for a current rollback state. Before any write, collect a separately named current boot area, settings, rootfs, firmware pool, calibration and web backup through a private authenticated route, verify byte sizes/SHA-256 off-device, and inspect filesystem consistency offline.

Rootfs/settings backups can contain private keys and credentials. Do not put new backups in publicly served storage or attach them to GitHub. Do not overwrite the existing backup sets. Live raw reads are not quiesced recovery images; consistency limits must remain explicit.

The host-only helper `scripts/backup-pretrial.py` streams seven artifacts over a single strictly pinned, key-authenticated SSH connection to a fresh ignored `.private-backups/nimbus-pretrial-<UTC timestamp>/` directory. It hashes the exact remote bytes mirrored to SSH, checks the same hash while receiving, and re-reads/fsyncs the private host file. It never stages credentials-bearing data on HTTP/FTP media, runs firmware helpers, changes mounts or writes source partitions.

The backup commands perform reads, but the running OS can still update access times/logs and unrelated services can write during capture. This is why same-stream integrity does not certify a quiesced or mutually consistent partition set.

```sh
python3 scripts/backup-pretrial.py --host 172.16.10.178
```

Run this from the PC's SanDisk project directory while USB data remains disconnected and uploads/settings/media writes are stopped. Enter the SSH key passphrase locally if requested. Defaults use the existing dedicated `~/.ssh/nimbus-admin-ed25519` identity and `~/.ssh/nimbus-test-known-hosts`; no password fallback or host-check bypass is allowed. At least 1 GiB free PC storage is required. The overall transfer has a 30-minute bound; incomplete files/staging are retained for private inspection, not overwritten or silently resumed.

Artifacts are `boot-area.bin`, `settings.bin`, `rootfs.bin`, `fwpool.bin`, `wl1271-nvs.bin`, `stock-web.tar`, and `partitions.txt`, plus private transfer log/checksums/manifest. The first four include 475 MiB of raw system regions; user media and the rest of the disk are not a full-disk backup. Stream frame/size/hash mismatches stop the transfer. A complete manifest explicitly retains `filesystem_consistency_verified: false`, `restore_tested: false` and `flash_authorized: false` until independent offline/recovery checks establish otherwise.

Backup-helper checkpoint: **115 local tests pass**, including the complete seven-artifact shell protocol on small regular-file fixtures, binary framing/hash/truncation checks, private file modes and refusal to overwrite earlier backups. These fixtures never read hardware.

#### Physical backup review — 2026-10-11

The user completed the new seven-artifact transfer into private host directory `.private-backups/nimbus-pretrial-20261011-062537/`. Independent host review verified every artifact's manifest size, SHA-256 and mode 0600. Local read-only `e2fsck -f -n` checks returned 0 for settings and firmware pool, but 4 for rootfs, with skipped journal recovery and allocation-count mismatches. These are checks on regular host files, not live block devices.

To distinguish pending journal state from deeper snapshot inconsistency, the original rootfs backup was copied to a new private regular file `rootfs-journal-review-v1.bin`. Journal-only replay (`e2fsck -p -E journal_only`) on that copy returned 0. A subsequent read-only full check returned **12** (uncorrected errors plus operational failure), reporting multiply-claimed blocks, invalid inode metadata and an invalid `.` directory inode before aborting. This derived copy is **not a validated restore image**, and no additional repair was attempted. The original backup hash was reverified unchanged; all original artifacts and earlier backup sets remain preserved. Private logs and `ROOTFS-JOURNAL-REVIEW-v1.json` retain the review evidence locally.

Both kernel and installed rescue uImages in the fresh boot-area backup passed header/payload CRC checks and matched the previously observed labels, offsets and lengths. That is integrity evidence, not recovery or authenticity validation.

**Rollback blocker:** transferred bytes are verified, but the current raw rootfs capture is not a consistent, tested restoration artifact. A live capture can produce these findings; they do not establish that the running drive has the same errors. Do not run repair against the live root partition or treat further host-copy repair as evidence of recoverability. Review a quiesced capture route (including whether freeze/unfreeze is safely supported) or a separately reviewed offline recovery capture before relying on rootfs rollback. Neither route has been established or authorized for execution. Stable trial power and the update/recovery path remain unresolved. No firmware write, live filesystem repair or deployment occurred.

#### Consistent-capture feasibility review

Offline decoding of the installed normal kernel's embedded config found `CONFIG_IKCONFIG=y`, `CONFIG_IKCONFIG_PROC=y`, `CONFIG_EXT3_FS=y`, `CONFIG_JBD=y`, `CONFIG_WATCHDOG=y`, `CONFIG_WATCHDOG_NOWAYOUT=y` and `CONFIG_MXC_WATCHDOG=y`. The stock 3.04 rootfs archive includes `/sbin/fsfreeze`. This establishes build/tool presence, **not** whether the watchdog is active, its timeout, or whether a freeze is safe. A nowayout watchdog cannot be disabled once activated through its ordinary close path. Do not open `/dev/watchdog` to inspect it: opening can activate it.

The installed rescue's `/etc/rc.d/rc.conf` includes `nimbus-last` in its startup sequence; `/etc/rc.d/init.d/nimbus-last start` invokes `/opt/qsi/scripts/upgrade_firmware.sh` unconditionally. Rescue is therefore **not an established passive capture shell**. Booting it for inventory can execute the destructive updater path before an operator gains access. No rescue boot is proposed as a diagnostic.

`device/capture-capability-preflight.sh` reports only selected RAM/mount/config/symbol metadata, tool hashes, watchdog node presence and available watchdog sysfs attributes, and process names without arguments. It never invokes `fsfreeze`, opens a watchdog device, changes mounts or executes rescue/updater code. Kernel symbol addresses are suppressed. Missing metadata/process names cannot certify the watchdog inactive. Run from the trusted PC project:

```sh
ssh -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2224 root@172.16.10.178 'sh -s' \
  < device/capture-capability-preflight.sh
```

A future freeze-based capture would need an independently bounded native thaw path with its executable/data resident outside the frozen filesystem, watchdog handling that does not assume it can be disabled, and tests for SSH loss, blocked IO, signals and failed thaw. A remote shell `trap` plus a host timeout is insufficient: host timeout can terminate SSH while leaving the filesystem frozen, and thaw processes can themselves block on frozen-root IO. Available RAM must be evaluated before suggesting tmpfs staging of the 256 MiB rootfs; reported free/cache totals are not reserved memory. No freeze helper or capture command is authorized or implemented here. Review these constraints against the physical capability output before selecting a capture route.

Initial capability-helper checkpoint: **118 local tests passed**, including non-execution of a fixture freeze tool, unchanged fixture files, suppressed kernel symbol addresses and refusal on active USB export. Physical capability output was pending at that checkpoint; v4 image artifacts are unchanged.

Subsequent physical capability output reports 125496 kB total RAM, 2352 kB free, 151712 kB swap with 148220 kB free, and `/tmp` as tmpfs limited to 4096 kB. A complete 256 MiB rootfs cannot be staged in RAM on this device; swap is not a substitute for independently resident capture/thaw code. `/dev/shm` is tmpfs but its presence does not reserve sufficient memory. Live kernel config confirms the selected offline config values; `freeze_super`, `thaw_super`, `ext3_freeze` and `ext3_unfreeze` symbols are present. The installed regular-file tool hashes are `6c947a05973c1a86cff20f555468b2fae540489f0f64b11445fc7a92ea834f5f` for `/sbin/fsfreeze` and `aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c` for `/bin/busybox`. The watchdog device node exists, but watchdog sysfs attributes were absent; selected process names did not resolve its activity/timeout. USB export was inactive. No freeze/thaw was attempted.

Offline vendor source review found `SWAP_FILE` defaults to `/opt/qsi/fwpool/swap/swap_file`, size 150 MiB, with `every/S10swap` mounting the firmware pool and enabling that file. Do not source or execute these scripts during inventory. The firmware-pool snapshot can include swapped private process memory, not only firmware; keep it private even when its filesystem check passes. The default location does not prove current swap placement.

The capability helper now additionally maps active swap entries to backing mount sources (without printing swap filenames) and reads `/proc/<pid>/fd` **symlink targets only** to report descriptors naming `/dev/watchdog` or `/dev/watchdog0`. It does not read through those descriptors or open devices. This is a racy, path-based observation, not an alias-complete watchdog activity test. Zero links cannot establish that a nowayout watchdog is inactive. Re-run the same host-streamed command above for this extended evidence; it remains inventory-only. Swap on root would add a freeze deadlock risk; swap on another partition still requires a reviewed resident thaw/IO path and bounded watchdog strategy.

Extended-helper checkpoint: **119 local tests pass**, including fixture watchdog descriptor detection and swap backing-mount mapping without exposing unrelated descriptor targets or swap filenames. Extended physical results remain pending. No device state change or image rebuild occurred.

### 3. Review the complete deployment path

Prepare a **rootfs-only payload** that contains no U-Boot, rescue, kernel update or system-partition-layout replacement. Existing per-device settings/calibration must be preserved, and native SSH access must be provisioned before Telnet remains disabled.

Important: a rootfs-only payload does **not** make the surrounding vendor updater rootfs-only. The installed rescue framework can write bootloader environment, clear firmware-pool scratch data, run hooks and, if expected partitions are missing, repartition/format storage before a package installer runs. These effects must be enumerated and reviewed. A package-level installer cannot retroactively prevent that earlier fallback.

The current ext3 candidate is not a vendor package. Default rescue installation expects a rootfs tar inside a mounted update payload. Wrapper CRCs are weak integrity checks, not a signature or evidence of safe installation. Do not rename/wrap the current image and treat that as a validated deployment.

### 4. Concrete experimental-write review

Before initiating the trial, identify the exact package SHA-256, version behavior, target partition, surrounding environment/scratch changes, expected duration, private restore artifacts and likely failure modes. Explicitly separate:

- Rollback after a bootable-but-broken image, where pinned management may still work.
- Rescue after a failed rootfs boot, where vendor rescue entry may be required.
- Recovery after bootloader/rescue damage or power loss, where external programming/console access may be necessary and remains unproven.

No self-update from the currently mounted root partition, broad raw whole-disk overwrite, blind bootloader write or forced filesystem repair is part of the proposed first trial. Risk acceptance does not establish that any of these is an appropriate deployment path.

### 5. Trial validation and failure handling

After a reviewed experimental deployment, validate pinned key-only management, rejected wrong credentials, charging, AP/uplink, original media/UI/Settings, storage/USB transitions and reboot behavior. Keep all evidence scoped to this device/image. Stop on unexpected partition or identity changes; do not stack additional unreviewed flashes on a failed trial.

A successful boot alone is not production readiness. Matching restoration/failure-path evidence, broader security/account/API review and redistribution licensing are still required before a public production image.
