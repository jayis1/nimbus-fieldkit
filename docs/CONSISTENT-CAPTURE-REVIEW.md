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

## Service/management review and next evidence

The hash-pinned stock 3.04 rootfs archive (`4dd2907ec920443855b221b1f67c5086e369b84861fb0a486d74da2c7671b203`) was inspected as data only. The live copies of these scripts are not yet hash-matched:

| Script under `/etc/rc.d/init.d/` | Stock SHA-256 | Observed stop/reload behavior |
| --- | --- | --- |
| `nimbus-service` | `14575fc3734fafc823b5b6440fb04e42e8cdc51478b840a7f5ac1a525610db3b` | `stop` is empty; not a service quiesce operation |
| `service/S00eventmanager` | `99347d094b3c4150815ffe8b2dc80ec61f8a88befa3c17fbe1da158bff5c9001` | Sends a signal to name-matched PIDs; does not wait for exit or certify closure of files |
| `service/S15fwserver` | `225d9f386a3562a55a56a9133a289743105be0083bff719ae8d3b72107d2ed1c` | Stop signals name-matched PIDs without exit verification; reload contains an unbounded process-presence loop |
| `service/S20nimbus` | `2dc2ed86ca1936b41e7183f425dcd6794ceed52c8139b852564d29cc24af74a3` | Stop/reload contain unbounded process-presence loops; use broad process-list matching |

Crash helpers invoke service reload asynchronously. Opaque native daemons' exit/restart/charging behavior is not established by shell-source inspection. Never use `fw_upgrade.sh` as a convenient quiesce helper: it changes bootloader state, tears down storage/swap and reboots.

The live SSH startup integration described in `SSH-STARTUP-CANDIDATE.md` redirects the foreground server's stdout/stderr to `/root/nimbus-ssh-test/boot.log`. A writable rootfs log descriptor held by SSH or its descendants can prevent a non-forced ro remount. Do not kill the working management server to release it without an independently tested replacement session. A temporary same-key/same-host-identity listener restricted to `wlan1`, with private tmpfs logging and a separately reviewed port, is a potential handover design—not a deployed listener or a reason to bypass existing pinning. All relevant old server/session descriptors would need to be accounted for; closing only a terminal window is insufficient evidence.

`device/root-writer-preflight.sh` is **read-only metadata inventory**, not a remount trial. It checks expected root major/minor through mountinfo/sysfs and USB state, then counts writable regular-file fd flags and shared writable mappings on root. It outputs numeric PIDs, whitelisted process labels, counts and hashes of the four selected service scripts. Arbitrary process names, file/mapping paths, addresses, arguments and file contents are not printed. It uses stat on fd targets for metadata, never opens those targets for data or executes service scripts. Unknown process labels are `other`; process races/missing fdinfo are reported. This does not enumerate every VFS reference capable of blocking a remount (for example a retained writable file reference behind a now-read-only mapping).

Run the new targeted check from a trusted PC terminal:

```sh
ssh -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2224 root@172.16.10.178 'sh -s' \
  < device/root-writer-preflight.sh
```

Do not run this shell script from an untrusted modified file. It performs no signal, service stop, sync, mount change, watchdog open, firmware helper or reboot. Physical writer counts/service hashes remain pending. Fixture tests exercise octal read/write fd flags, shared writable root mappings, missing metadata, USB/root-identity refusal and unchanged local files without exposing fixture private names.

Initial writer-helper checkpoint: **123 local tests passed**. Physical writer inventory, management handover and remount had not yet been performed at that checkpoint. v4 image artifacts are unchanged.

### Subsequent physical writer evidence

User inventory reports `nimbus` PID 3288 with one writable root fd, the existing `dropbearmulti-b` parent PID 3423 with two, and the current SSH `dropbear` session PID 6475 with two. Total: three holder processes, five writable root fds, zero shared writable root mappings, zero incomplete/raced observations reported in that scan. All four live service-script hashes exactly match the stock review table. PIDs are transient, **not stop targets**. The scanner suppresses fd paths, so the observed SSH fds are consistent with—but not path-proven to be—the inherited boot log. No services were stopped.

### Optional temporary management listener: first handover stage only

`device/ssh/capture-listener.sh` defaults to `--check` with no staging/launch. Explicit `--start` adds **one additional temporary listener** on `wlan1` IPv4 TCP **2225**, using the installed hash-pinned fail-closed/key-only Dropbear and the existing host/admin keys. No credentials are copied or regenerated. Root-owned private directory/key metadata, writable tmpfs `/tmp`, interface presence, inactive USB export and unoccupied port are checked. It refuses an existing stage rather than overwrite or silently resume it.

Only the explicit start action creates mode-0700 `/tmp/nimbus-capture-ssh-v1/` and launches the foreground server with `nohup setsid`, stdin `/dev/null`, stdout/stderr in a mode-0600 private tmpfs log and PID file in that stage. No rootfs log is deliberately opened by this launcher. An observed live PID/listening-table entry is **not authenticated management verification or exclusive socket-ownership proof**. Failure retains private staging and does not stop any old process; inspect rather than rerun blindly. No port-2224 stop, vendor-service action, boot-hook change, remount or reboot occurs. Existing inherited descriptors still need the writer scan through the new connection.

From the trusted PC, the optional start is:

```sh
ssh -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2224 root@172.16.10.178 'sh -s -- --start' \
  < device/ssh/capture-listener.sh
```

This command is **not read-only**: it adds a temporary network listener and private RAM-backed staging. It does not change the existing management listener. Treat it as a short supervised trial, not an unattended install; logging is not rotated/capped and `/tmp` is only 4 MiB. The new listener/stage do not survive reboot; normal boot still starts the unchanged port-2224 service. No automatic shutdown timer is promised and no teardown has yet been performed.

After reported startup, verify a fresh connection using the **existing port-2224 host pin**, not a newly trusted key:

```sh
ssh -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[172.16.10.178]:2224' \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2225 root@172.16.10.178 'id'
```

`HostKeyAlias` looks up the already pinned identity under the old endpoint; it does not disable host verification, change the key, or edit the known-hosts file. If the old pin is unavailable or a mismatch occurs, stop rather than accept an unfamiliar key. A changed DHCP address needs a separately validated existing-pin lookup, not blindly substituting an alias.

Then run the root-writer inventory through port 2225 with that same alias, and keep an independent interactive port-2225 session available. Only after fresh pinned login and no writable root fds from the replacement server/session are demonstrated should a reviewed handover consider stopping the exact old management processes. Unknown holders or failures stop the plan; neither stale PIDs nor broad process-name killing is acceptable. Native new-listener launch, password rejection, root-descriptor absence, handover and cleanup results remain pending.

Temporary-listener helper checkpoint: **128 local tests pass**, including check-only no-launch/no-staging behavior, refusal of unsafe key metadata, changed binary hash, occupied port and prior staging, and private retained staging after a failed harmless fixture launch. No fixture launches an SSH server or touches the drive. These tests do not establish native handover or remount safety.

### First launch failure and guarded correction

The user's first explicit `--start` passed checks and created private tmpfs staging, but did not verify a live PID/listening entry within the helper's wait. Do not treat this as a successful management handover or blindly rerun `--start`. Port 2224 and vendor services were not stopped.

Offline review identified a helper mistake: it supplied **`-E`**, which is absent from the option parser when `DISABLE_SYSLOG` is defined. The local reviewed build's `config.h` defines `DISABLE_SYSLOG 1`; its binary SHA-256 exactly matches the installed pinned binary hash used by the helper. In this configuration stderr logging is already the default. The corrected launcher uses **`-F` without `-E`**. Initial fixture tests checked the launcher protocol but did not catch this native build-option incompatibility; those tests were not native validation.

The opt-in `--retry-invalid-E` action is narrowly guarded: it requires a real root-owned mode-0700 stage, a real private mode-0600 log containing the exact `Invalid option -E` diagnostic, **no PID artifact**, no existing failure-archive destination, and no port-2225 listener in IPv4/IPv6 tables. All original binary/key/interface/tmpfs/USB checks still apply. Only then it renames the failed stage to `/tmp/nimbus-capture-ssh-v1.invalid-E` (retaining it rather than deleting/overwriting), creates a fresh private stage and attempts the corrected listener. Unrelated failures, PID artifacts and occupied ports refuse without archive/launch. No old management process is signalled.

From the trusted PC, use the same start command above with remote command `'sh -s -- --retry-invalid-E'` instead of `'sh -s -- --start'`. This is an explicit temporary-listener retry, not read-only inventory. A refusal requires inspection, not loosening a guard. A corrected launch still needs the fresh pinned port-2225 login and root-writer checks before any subsequent handover. No live retry or remount has yet occurred.

Correction checkpoint: **130 local tests pass**, including preservation of the exact failure stage on a fixture retry and refusal of unrelated failures, PID artifacts and occupied ports. Native corrected-launch results remain pending.

Subsequent user retry passed the exact-failure guards, preserved the original failed stage as `/tmp/nimbus-capture-ssh-v1.invalid-E` and reported a temporary live PID/listening entry on port 2225. Existing port 2224, hooks, keys, services and mounts were unchanged. This is startup evidence only: fresh pinned port-2225 login and writer inventory remain pending. Do not stop port 2224 based on this report alone. The additionally requested [HTML5 Music UI](HTML5-MUSIC.md) is prepared offline, not installed; it does not change the current capture/handover state.

No remount trial helper is shipped by this review. Current images remain non-flash-certified, and installed rescue still automatically invokes its updater. Source review narrows the next experiment; it does not establish recoverability or authorize firmware writes.
