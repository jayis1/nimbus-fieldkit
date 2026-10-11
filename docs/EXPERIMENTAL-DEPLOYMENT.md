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

Artifacts are `boot-area.bin`, `settings.bin`, `rootfs.bin`, `fwpool.bin`, `wl1271-nvs.bin`, `stock-web.tar`, and `partitions.txt`, plus private transfer log/checksums/manifest. The first four include 475 MiB of raw system regions; user media and the rest of the disk are not a full-disk backup. Stream frame/size/hash mismatches stop the transfer. A complete manifest explicitly retains `filesystem_consistency_verified: false`, `restore_tested: false` and `flash_authorized: false` until independent offline/recovery checks establish otherwise. New physical backup results are still pending.

Backup-helper checkpoint: **115 local tests pass**, including the complete seven-artifact shell protocol on small regular-file fixtures, binary framing/hash/truncation checks, private file modes and refusal to overwrite earlier backups. These fixtures never read hardware. The helper has not yet transferred the physical drive's new backup set.

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
