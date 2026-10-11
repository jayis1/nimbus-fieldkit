# Consistent rootfs capture: source review, no execution approval

## Decision

Do **not** implement the proposed timed root-freeze over SSH as a guaranteed-bounded capture method. The published kernel's freeze path can block while holding the lock required by thaw. A second process, resident static binary, shell trap or host timeout cannot guarantee recovery from that condition.

The next candidate to review is a temporary **non-forced root read-only remount**, followed by direct private SSH capture and restoration of the original read-write mount state. This is a design lead, not a safe-to-run procedure. No remount, service stop, sync command, watchdog open or recovery boot has been performed.

## Physical evidence

User-supplied extended capability inventory confirms:

- Root is ext3 read-write with `relatime,errors=continue,barrier=0,data=writeback`.
- RAM is 125496 kB; `/tmp` is tmpfs limited to 4096 kB. A 256 MiB raw image cannot be staged in RAM.
- Active file swap is backed by **`/dev/mmcblk0p3`**, not the rootfs partition p2; size 151712 kB, used 3236 kB at this observation. Do not disable swap to make space for capture.
- Freeze/thaw kernel symbols and ext3 callbacks are present.
- Watchdog configuration includes NOWAYOUT; `/dev/watchdog` exists but watchdog sysfs attributes are absent. No standard-path watchdog fd links were observed. This racy/path-based scan does not establish that the hardware timer is inactive.
- USB export was inactive. Stable external trial power was not established by this inventory.

The source-level swap default agrees with the backing-partition observation, but a filesystem check on the firmware-pool backup does not make captured swap contents consistent or non-sensitive.

## Pinned public source

Reviewed repository: <https://github.com/SanDisk-Open-Source/wireless-media-drive>, revision **`ab09fbd1194c8148131cf0a37425419253a137b0`**. Paths below are under `linux-2.6.35.3/`. Fetched files and a hash manifest are local review inputs in `/tmp/opencode/nimbus-freeze-review/`; no vendor sources/binaries are bundled with this document.

| Path | SHA-256 |
| --- | --- |
| `fs/super.c` | `731169c059c11a05b09bc0b42d56df8d65f65841618e425b8a3979c30b48d1ba` |
| `fs/ioctl.c` | `09f419ccb653da1533c7c8e8a4b4458153a10f2efb3b267ec1c57079aee18694` |
| `fs/ext3/super.c` | `7692fd2c1ac0446eca7db3805103fae9f288342ee950f15918954ce93918baa8` |
| `drivers/watchdog/mxc_wdt.c` | `c450377ddbcf892504547b3c5072d047ca5a8a79bd7a8dd6cc0323dc90f20aa4` |

This source tree has **not** been proven bit-for-bit equivalent to the installed `2.6.35.3-899-g9b1a262` kernel. Matching configuration/symbol names strengthen relevance, not binary provenance. Findings below are source-level constraints, not native test results.

### Freeze and thaw

- `fs/ioctl.c:517–540`: privileged filesystem freeze/thaw ioctls call `freeze_super` and `thaw_super`.
- `fs/super.c:959–997`: freeze takes `s_umount` for writing, transitions freeze state and performs filesystem/block sync plus the filesystem freeze callback before releasing that lock.
- `fs/super.c:1007–1037`: thaw first takes the same lock. A freeze blocked in IO while holding it can also block a separately scheduled thaw. The kernel code supplies no elapsed-time bound for those operations.
- `fs/ext3/super.c:2500–2529`: ext3 freeze locks journal updates, flushes the journal and synchronously commits the cleared recovery flag. This is **not a write-free diagnostic**.
- `fs/ext3/super.c:2536–2546`: unfreeze restores the recovery flag and commits the superblock before releasing journal updates; the callback does not propagate the return value of `ext3_commit_super`. Successful userspace return alone cannot certify every device write succeeded.

This rules out claiming that a timer makes root-freeze fail-safe. An IO hang or power loss is not something source-only tests can eliminate.

### Watchdog

- `drivers/watchdog/mxc_wdt.c:105–108`: the disable function is a no-op because disable is not supported by this chip in this implementation.
- `149–175`: opening configures/enables/pings the watchdog; closing under NOWAYOUT does not stop it.
- `207–208`: `WDIOC_GETSTATUS` returns a constant zero, not reliable active-state evidence.
- `226–229`: even `WDIOC_GETTIMEOUT` pings the timer. Neither opening the device nor querying it through that ioctl is a passive inventory operation.

Do not add watchdog open/ioctl probes or hardware-register reads to the read-only helper. No watchdog takeover is proposed.

### Non-forced read-only remount lead

- `fs/super.c:529–575`: remount first synchronizes the filesystem; a non-forced rw→ro transition rejects with `EBUSY` if `fs_may_remount_ro` fails. A successful ro transition invalidates the block-device cache as a best-effort coherency measure.
- `fs/ext3/super.c:2595–2662`: the ro transition marks journal recovery complete; rw restoration has its own refusal/error paths, including an unprocessed orphan list. Neither direction is guaranteed to succeed or finish within a fixed time.

Unlike a successful freeze, a successful read-only remount makes subsequent root writes fail rather than intentionally wait for thaw. That is useful for a stable capture, but can break services expecting writable root and does not make remount/restoration immune to IO stalls.

## Requirements before a remount trial

1. Identify rootfs write holders and exact required service stop/restart behavior without dumping process arguments, credentials or open private filenames into public logs. Do not blanket-kill services or assume stopping `fw_server` alone is enough. Preserve pinned SSH and Wi-Fi management.
2. Prepare capture and restoration logic in a small private tmpfs area, without staging the raw image there. Preserve current mount options; prohibit force, repair, format, bootloader changes and writes to raw partitions.
3. Confirm expected root-device identity and absence of USB export immediately before any state change. Treat external power as separate from USB data ownership.
4. On a non-forced ro refusal, stop and report; do not retry with force. Starting the trial already causes normal journal/metadata flush writes and may disturb services, so obtain approval for that exact temporary change.
5. Capture only while the expected root filesystem remains ro. If rw restoration occurs during transfer, invalidate the capture even if transport hashes match. A verified ro capture is still subject to host read-only filesystem checks and is not a proven restore route.
6. Review failure handling for SSH loss, capture failure, failed rw restoration and service recovery. A host-side timeout is not an independently guaranteed device restoration mechanism. No absolute kernel-operation deadline should be promised.
7. Keep the original inconsistent backup and derived journal-review copy unchanged. A new capture receives a new private destination and manifest. No replacement or repair of existing backups.

No remount trial helper is shipped by this review. Current images remain non-flash-certified, and installed rescue still automatically invokes its updater. Source review narrows the next experiment; it does not establish recoverability or authorize firmware writes.
