# Beta1 deployment-chain review — unchanged vendor path rejected

## Scope and private inputs

Offline review only. The installed rescue filesystem was decoded anew from the retained fresh boot-area backup, selecting `Nimbus-rescue-V1.0.6` with valid header/payload CRCs. The known embedded gzip stream decoded to 20MiB with a 32MiB output bound. Read-only `debugfs cat` retrieved selected scripts; no filesystem mount, ARM executable, sourced vendor config, updater, block-device access or device change occurred.

Local review material: ignored mode-0700 `.private-backups/beta1-deployment-chain-review/`, files mode 0600. `INPUT-HASHES.json` records boot/rescue/script fingerprints. These vendor-derived scripts and rescue filesystem remain private; only this analysis and first-party checkpoint helper are public. CRCs/hashes are not authenticity or recovery evidence.

| Reviewed file | SHA-256 |
| --- | --- |
| Installed rescue `upgrade_firmware.sh` | `8e30e02605c764e226f12b548ee77b8dac4ecc6fc4bcd981503aa5b6298693fd` |
| Vendor 3.04 `preaction.sh` | `41697822392cfd7ddfbf57c7c14e6a6f44858433407f338aed032266c0b90020` |
| Vendor 3.04 `postaction.sh` | `6f4f6c3f97302071f5df9a1589863004ec46f28f62b67c597f91fdf9519e2317` |
| Stock normal-mode `fw_upgrade.sh` | `0ef3c19206bfaea0dca89417e10f70f336da798295be8886fc673acd81a98b37` |
| Stock normal-mode `checkfwimage.sh` | `01019c1bf85ef227a13afc20c21c5e446fc8724750b56eee78d70e3c939ef540` |

Line references below refer to these exact privately retained scripts. Normal-mode stock scripts are not newly hash-matched to the current live device.

## Execution order and hazards

1. **Normal-mode scanning is not read-only.** `checkfwimage.sh:50–58` writes the selected-image bootloader environment (or clears it on no match). It scans multiple mounts and chooses versions using `make_image`; version selection/development exceptions require review. `every/S99fwupgrade:19` invokes this scanner on startup. Its direct `fw_upgrade.sh` invocation is commented out, but its scan still changes environment. Never execute it as an inventory tool.
2. **Upgrade entry changes boot state before restart.** `fw_upgrade.sh:44–66` sets/clears rescue/result environment, syncs, stops a service, tears down mounts, disables/deletes swap and reboots. This is not a capture/quiesce helper. The source has a suspicious `/dev/nll` redirection; no execution was used to explore it.
3. **Rescue startup is not passive.** Its `nimbus-last` invokes the updater unconditionally. `upgrade_firmware.sh:23–27` already creates/clears extraction staging before package selection or hooks.
4. **Destructive fallback precedes all package hooks.** If any expected system block partition is absent (`240–323`), rescue zeros a disk header, repartitions and formats settings/rootfs/firmware pool/user media. A rootfs-only `installer.sh` cannot veto this earlier branch. `325–329` deletes the swap directory before extraction.
5. **Extraction can use internal user media.** `83–98` falls back to `/mnt/storage/.database/.fw_tmp` when firmware-pool free space is insufficient. This is not solely a rootfs write path; it needs private staging/space/ownership review. Extract status is inferred from matching `.img` files, not robustly propagated from the extractor.
6. **Stock pre-action is unsuitable unchanged.** `preaction.sh:25–45` conditionally writes U-Boot/rescue if matching files exist, but sets **`bootdelay=1` unconditionally** even without them. `97–134` attempts backup mounts/copies and deletes swap and top-level firmware-pool files. Its `mount_parition` accepts a device argument but executes root-device mount/unmount commands (`75–80`); it compares an entire `mount` line with a mountpoint. The same defective helper appears in rescue and post-action. Backup success is not rigorously checked.
7. **Hook failure is not fail-closed.** Rescue invokes pre-action (`386–391`), custom installer (`394–398`) and post-action (`468–473`) without checking their exit statuses. A failed custom installer can therefore fall through to final success messaging/reboot. The default-path `update_firmwae_result 0` is inside the `else` branch (`464–465`), not automatically applied to the custom-installer branch. A custom script must not assume the surrounding framework correctly propagates success/failure.
8. **Default writes are not sufficiently verified.** Kernel programming `174–182` ignores write status and has readback commented out. Rootfs programming `199–225` lazily unmounts, formats, mounts and extracts; tar status is not checked and existence of `bin`/`etc` is treated as success. It is not an atomic update, hash-verified installation or rollback system.
9. **Preservation and cleanup are best-effort.** Default calibration/database backup/restore (`417–462`) suppresses failures; stock post-action also restores with suppressed errors, deletes backups (`67`) and usually deletes the selected update file (`97–106`). Rescue cleanup (`475–487`) removes scratch/backup directories and invokes reboot. Retained Wi-Fi/SSH/calibration and database state cannot be promised based on these copy calls alone.

## Decision and possible next route

**Do not wrap beta1 with unchanged stock hooks and call it safe or rootfs-only.** Do not reuse the default kernel/rootfs programmer. Do not execute rescue or change boot flags merely to discover access. The plain ext3 beta artifact is not an updater package.

A future local deployment container would need minimal first-party hooks and a separately audited installer plus a plan for the surrounding rescue behavior. That installer cannot retroactively prevent rescue's earlier disk fallback, swap/scratch effects or version-selection environment writes. Required conditions include exact partition geometry and identities checked **before entering rescue**, pinned package/version handling, explicit exclusion of bootloader/rescue/kernel payloads, private verified preservation of calibration/settings/access, strict target validation and readback, independent failure signaling/management access, and verified restoration. Native errors/IO hangs cannot be made safe by a shell timeout alone. No such installer/container is approved or produced by this review.

Recovery access and a current consistent backup remain the immediate hardware blockers. An alternative independent recovery/programming route may be needed; none is established. The single-drive risk acceptance does not establish it. Full-image public distribution additionally remains blocked by proprietary component license permissions; source/overlay publication continues independently.

## Next hardware checkpoint — metadata only

`device/beta-capture-checkpoint.sh` checks expected root identity and inactive USB export; reports whitelisted power metadata, listening-entry counts for 2224/2225 and temporary listener-stage/log/PID **metadata**, not their contents. Missing power metadata and listener counts are not a stable-power or authenticated-management certificate. It changes nothing and opens no watchdog/device node. Pair it with the existing `device/root-writer-preflight.sh` to refresh writable-root fd/mapping counts and service-script fingerprints. No PID in the output is authorization to signal it.

Run from the trusted PC with uploads/media/settings writes stopped and USB data disconnected:

```sh
cat '/home/jais/Projects/sandisk wifi dims/device/beta-capture-checkpoint.sh' \
    '/home/jais/Projects/sandisk wifi dims/device/root-writer-preflight.sh' |
ssh -T -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[172.16.10.178]:2224' \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2225 root@172.16.10.178 'sh -s'
```

If root identity or USB checks fail, the first helper exits before the writer scan. The SSH passphrase is entered locally, never posted. Keep both listeners running; do not blindly recreate the tmpfs stage or reuse historical PIDs. Separately confirm an independent interactive pinned port-2225 session before any eventual old-listener handover. Hardware output and exact stop/restart/restoration review are still required before proposing a non-forced root read-only capture. No service stop, remount, freeze, raw write, repair, format, reboot or flashing is part of this checkpoint.

### Returned live checkpoint

The user ran the combined check through strictly pinned port 2225. Expected ext3 root identity and inactive USB export passed. Charger `online=1`, battery status `Not charging`, capacity unavailable: external power is now detected, but uninterrupted power and battery reserve are not certified. Both management ports had one listening entry. Temporary staging metadata was root:root 0700, log/PID root:root 0600, log 4619 bytes and PID file 5 bytes; contents were not printed.

Fresh writer scan again observed only `nimbus` (reported PID 3288, one writable root fd) and the old `dropbearmulti-b` (reported PID 3423, two writable root fds). Zero shared writable root mappings and zero incomplete observations were reported. No replacement-listener/session writable root holder was observed. All four selected service hashes matched the reviewed stock versions. These PIDs are observations, **not authorized signal targets**; identity and start-time/socket/descriptor checks are still needed immediately before any handover.

Next requirement: independently open and retain an interactive pinned port-2225 session, with shell history directed to `/dev/null`, then review exact old-listener and vendor-writer exit/restart/restoration handling. Neither listener nor vendor daemon has been stopped; no root remount/capture/firmware write occurred. The later UI additions must be included in any new consistent capture rather than relying on older raw snapshots.

### Independent shell verified; identity inventory prepared

The user opened the separately requested strict-existing-pin interactive port-2225 session with `HISTFILE=/dev/null`, returning `sh-3.2#`. Keep this shell open; that verifies independent access, not a stop/remount/restore trial.

`device/handover-identity-preflight.sh` is the next read-only helper. It reads fixed private PID records for the old and replacement listeners, checks expected executable paths and pinned running-executable hashes, records start ticks and direct-child counts, and links each PID's socket descriptors to the expected unique IPv4 listening entry. It finds a unique vendor `nimbus` process and compares its executable against the reviewed vendor hash `b2472e7c34c22b2bb7dbda2d58ce8836cedccf5b10680047d60eaf10956220dd`. A mismatch/ambiguity stops review; no fallback name-based signaling exists.

For these three processes it classifies writable regular root descriptors as the **known boot log** versus **other root files**, printing only counts. The vendor file's private path/content is not exposed. Root identity, inactive USB export, private stage directories and PID-record metadata are checked first. It does not read key/log/file contents, print command arguments or socket peers, execute vendor scripts, or send signals. All observations are racy and not pidfd-protected; they must not be repurposed as a stop command using recorded PIDs. Native results remain pending.

From the **other PC terminal**, not the retained device shell:

```sh
ssh -T -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[172.16.10.178]:2224' \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2225 root@172.16.10.178 'sh -s' \
  < '/home/jais/Projects/sandisk wifi dims/device/handover-identity-preflight.sh'
```

Fixture tests verify exact executable/socket association, parenthesized process names in stat parsing, bounded start identity reporting, known-log/unknown-file count classification, output privacy, refusal of wrong socket/hash/USB state and unchanged fixture files. The helper never stops a process; exact stop/restart and service recovery logic still require separate review and approval. No rootfs remount/capture, handover or image deployment has been performed.

Validation checkpoint: **153 tests run, 151 pass, 2 Node-dependent skips**, using the documented host-only fixture sync isolation. Beta2 image artifacts are unchanged by this metadata helper.

### Returned identity evidence and vendor-writer follow-up

The user returned a successful identity scan: old listener PID 3423/start ticks 2835 owned port 2224 with zero direct children; replacement PID 6701/start ticks 648093 owned port 2225 with two direct children; vendor `nimbus` PID 3288/start ticks 2692 had zero direct children. All three running executable hashes matched. The old listener's two writable root descriptors were classified as the known boot log; replacement had none; vendor retained one other writable root descriptor. These numbers remain historical observations, not stop targets. No signals or mount changes occurred.

Offline inspection of the pinned vendor executable's static path strings identified three possible known root files: debug log, API/XML log and settings database. Presence of these strings is not proof that the observed live descriptor points to one. The identity helper now reports counts for these exact known categories and an unclassified count, without printing actual private filenames or reading descriptor contents. It additionally hashes the reviewed restart service and its three sourced configuration/function files as data only; status is matched/different/unavailable-or-unsafe. Any non-matching restart input requires review, not execution or replacement. No vendor service/configuration is sourced by this check.

Run the same identity command again from the other PC terminal while retaining the independent port-2225 shell. This refreshes identities and narrows the remaining vendor descriptor/restart-input questions. A separate supervised pause/restart trial on the still-writable root may be considered only after these results and exact recovery behavior are reviewed; no such trial is yet authorized or shipped. Never invoke the stock unbounded stop/reload routines as a diagnostic. Latest validation: **154 tests run, 152 pass, 2 skips** with fixture sync isolation; new fixture verifies known vendor-log classification, output privacy and unavailable restart inputs. Beta2 artifacts remain unchanged.

Returned follow-up: the vendor's single writable root descriptor matched the known **settings database**, with zero unclassified descriptors; it is not merely a log. All four restart inputs matched. Listener identities/start ticks/socket associations and child counts matched the earlier observation, and the replacement again had no writable root descriptors. The user also obtained another independent interactive port-2225 prompt. No stop/restart/remount was performed by these checks. A graceful vendor shutdown is required for further capture planning; do not close its database descriptor externally or use forced termination to make a remount succeed. Any proposed supervised pause/restart is a separate device change with temporary vendor API/UI availability impact and unproven native recovery behavior. Host-streamed commands must be run from the PC terminal, not the device's `sh-3.2#` prompt.

The user clarified that no PC command was executed inside the drive shell and explicitly approved the vendor-only pause/restart interruption. The [guarded trial](NIMBUS-PAUSE-RESTART-TRIAL.md) is now prepared and fixture-tested (162 run, 160 pass, 2 skips), with a default no-change preflight, one targeted TERM request, one reviewed start request and detached best-effort recovery. Its normal termination request is not proof of database transaction flushing. Native execution/result remains pending; neither SSH listener, root mount nor image has been changed by this preparation. Separate capture/remount/flash approval is still required.
