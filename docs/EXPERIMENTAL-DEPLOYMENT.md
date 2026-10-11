# Single-device experimental deployment — preparation, not a flash guide

The user has elected to use the existing drive as the experimental device, accepting the possibility of a brick. That permits planning a concrete trial, not representing it as a production-ready release. **Unbricking is not guaranteed.** No spare drive or independently established boot-console/ROM recovery access is currently available.

This document contains no deployment command, updater invocation, bootloader flag write or partition-write instruction. No experimental flash has been performed.

Preparation checkpoint: **109 local tests pass**, including read-only preflight fixtures, USB-export refusal and mismatched partition-boundary refusal. The preflight script has not yet been run on the physical drive; fixture results are not hardware evidence. The previously built v4 image artifacts are unchanged by this host-streamed diagnostic addition.

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
