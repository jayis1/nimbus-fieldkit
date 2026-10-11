# Installed rescue image: offline review, not recovery approval

The verified private 15 MiB boot-area backup contains two recognizable U-Boot uImages. `scripts/inspect-boot-area.py` inventories **local regular files only**, without mounting, extraction, execution, block access or restoration. It reports header labels, offsets, lengths, CRC checks and image hashes, never arbitrary bootloader environment strings.

## Observed on this device's backup

| Offset | Payload bytes | Header label | Header/payload CRC |
| --- | ---: | --- | --- |
| 1 MiB | 2242984 | Linux-2.6.35.3-899-g9b1a262 | Both pass |
| 5 MiB | 9659626 | Nimbus-rescue-V1.0.6 | Both pass |

Both headers report Linux/ARM/kernel and outer compression 0. These labels/CRCs are integrity evidence, not signatures or proof of recoverability. The installed rescue image has now been located **inside the private backup**; no separately redistributable rescue kit or working restore procedure is established.

Private offline analysis identified a gzip stream inside the rescue payload at relative offset 2010288, decoding to a 20 MiB filesystem. Read-only `debugfs` inspection located `/opt/qsi/scripts/upgrade_firmware.sh`. Neither it nor any embedded ARM executable was run. The decompressed local review file is private and must not be committed or uploaded.

## Updater behavior found in that script

- Extracts the vendor wrapper, loop-mounts its filesystem read-only, and executes package preaction/postaction scripts when present.
- A package `installer.sh` overrides the normal kernel/rootfs installation path. This is a static integration lead, not a reviewed deployment mechanism.
- Default rootfs installation **formats the root partition**, mounts it, extracts a tar, and checks only that `bin` and `etc` directories exist. Tar failure is not independently checked; this is not an atomic A/B update or verified rollback.
- Kernel installation uses a raw write at 1 MiB, with its comparison/readback commented out and no effective write-status check in the reviewed function.
- If expected system block partitions are missing, a fallback **repartitions internal storage and formats settings/rootfs/firmware pool/user media**. Never exercise this branch as a diagnostic.
- Calibration/database backup and restoration are attempted, with many errors suppressed. Bootloader environment is changed and a reboot follows.

The raw offline ext3 candidate therefore is **not** the payload expected by the default rescue rootfs writer, which expects a tar inside a mounted vendor update package. Renaming or wrapping the ext3 artifact alone is not a correct installer.

## Remaining recovery gates

The subsequent [beta1 deployment-chain review](DEPLOYMENT-CHAIN-REVIEW.md) pins installed-rescue and stock package scripts, maps ordering/failure/preservation hazards and rejects the unchanged vendor deployment chain. In particular, package hook exit statuses are ignored and the stock pre-action changes bootloader settings even without a bootloader payload. A custom installer alone is not an established safe route.

Further read-only startup inspection found `/etc/rc.d/rc.conf` schedules `nimbus-last`, whose `start` action unconditionally invokes `/opt/qsi/scripts/upgrade_firmware.sh`. Installed rescue must not be treated as a passive backup/inspection shell: updater side effects may begin during boot, before management access. No rescue boot was performed. See [consistent-capture review](EXPERIMENTAL-DEPLOYMENT.md#consistent-capture-feasibility-review) for the normal kernel's watchdog constraints and pending read-only capability inventory.

1. Pin and verify the physical unit's installed bootloader/partition configuration and rescue invocation procedure independently.
2. Review the relevant package scripts, including failure paths and calibration/settings preservation, before building a deployment container.
3. Establish access during failed boot and validate rescue on recoverable test hardware, with stable power and an independently usable restore route.
4. Prove restore and post-restore management/vendor behavior, not just backup hashes or successful extraction.

No rescue gesture, bootloader flag write, updater execution, flashing or restoration was performed. The working device and both verified private backup copies remain intact.
