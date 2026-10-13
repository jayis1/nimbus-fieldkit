# Non-forced root ro/rw restoration trial: tool review, no execution approval

## Current boundary

**Latest native checkpoint:** the user explicitly approved the restoration-only
root trial and returned `Trial result: PASS`. One non-forced ro remount was
observed, followed immediately by one explicit rw restoration with the original
options and one reviewed restart each for Nimbus and normal SSH. Original
temporary port-2225 identity/socket was retained. Fresh post-trial pinned login
and basic browser/Settings/storage checks remain pending. No capture, flash,
reboot or forced retry occurred. Earlier pending statements below are historical
preparation checkpoints, superseded only within this observed trial's scope.

Vendor pause/restart and management-only stop/restore now have native process/socket observations, fresh pinned normal SSH authentication and user-confirmed basic dashboard/Settings/storage restoration. Neither test changed root mount state. The user requested continuing preparation; **no root remount/capture/flash is authorized**. No remount worker/package is ready for execution.

The next proposed experiment would be restoration-only: retain temporary port 2225; freshly validate and gracefully stop normal SSH and Nimbus once each; scan for unexpected root writers; attempt one non-forced root read-only transition; immediately attempt restoration to the original writable configuration; restore the stopped services once each only after verified root rw. No capture, media remount, raw partition read/write command, swap teardown, freeze, watchdog takeover, boot edits or reboot. Native failure recovery is not guaranteed. Normal kernel filesystem/journal IO is inherent to a remount; this is not a write-free experiment.

## Offline utility evidence and upstream review

Read the selected members of the retained local beta2 candidate archive as data only, without extraction/execution of vendor code:

| Member | Observation |
| --- | --- |
| `bin/mount` | Regular ELF, 170199 bytes, SHA-256 `5504415dbef818acda95dff859eb5baa5375e9aa858de37769f1010b6347a9be` |
| `bin/busybox` | Regular ELF, 576540 bytes, SHA-256 `aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c` |
| `etc/fstab` | Regular file, hash `19eabead6d59b8f4a00c24078848098afdfb63d1f0f22ebbe6da80f95ccc3dcf`; contents not printed |
| `etc/mtab` | No member observed; this does not establish the live path's state |

The mount ELF contains `util-linux-ng 2.13` and a corresponding build-path string. This is not a BusyBox mount symlink and should not be treated as one. Live mount binary hash/type still needs comparison. Version strings and archive proximity do not prove exact upstream build/source equivalence.

Reviewed public upstream `util-linux/util-linux` v2.13, annotated tag object `35ed77a17b136d91cdec760527d3924f2555c73d`, commit **`49ef7acdf77066ed05a6c828c261d332c4f54644`**, file [`mount/mount.c`](https://github.com/util-linux/util-linux/blob/49ef7acdf77066ed05a6c828c261d332c4f54644/mount/mount.c). The downloaded review-text SHA-256 is `230638ad07b4373d0a05aa33442b8189a82444f6aa101a088d3b6927a8eca71f`. GitHub reports the historical tag signature as unknown-key/unverified; no independent signature validation is claimed. These are reference-code findings, not proof of installed vendor behavior.

Key source findings:

1. **Suppress mtab mutation:** `-n` sets `nomtab`. Normal utility startup may create an absent `/etc/mtab`; successful mounts can update it. Both paths are gated by `nomtab`. Any candidate invocation must explicitly suppress those paths so the utility does not create/update/lock the root mount table during the experiment.
2. **Suppress external mount helpers:** `-i` sets `external_allowed=0`; otherwise a matching `/sbin/mount.TYPE` can be executed. Specify the known ext3 type, not probing a list of filesystems, and do not execute arbitrary helpers.
3. **Avoid implicit fstab merge:** the single-target form consults fstab/mtab and combines options. Explicit source **and** target uses the two-argument form without fstab options. Device identity and exact current root mount configuration must already be established, not guessed from `/dev/root` spelling.
4. **Writable restoration needs explicit `-w`:** on `EACCES`/`EROFS`, a writable request without the `readwrite` flag can recursively retry as read-only. Merely having `rw` in the options string does not set that flag. `-w` sets it and turns that path into refusal. The future trial must not count a read-only fallback as successful writable restoration; verify actual mount state/options regardless of exit status.
5. **Preserve original options:** `parse_opts` initializes numeric flags to zero, so a shorthand remount is not a proven way to preserve all flags. Record and validate supported live root flags/filesystem options, pass the complete reviewed option set with only rw/ro changed, and compare the resulting kernel view. Do not source/evaluate saved option strings or take caller-supplied arbitrary options. Reject unreviewed options before stopping anything.
6. **Do not confuse flags:** `-f` is fake mounting, not a recovery method; `-F` is fork behavior, not an authorization to force. Neither is proposed. Existing kernel review confirms that normal remount can flush journal/metadata and can block; no utility option or shell timeout guarantees bounded restoration.

Use [the kernel constraints](CONSISTENT-CAPTURE-REVIEW.md) alongside this utility review. The source code blocks signals around the mount call; detached-worker traps cannot be advertised as able to interrupt an unresponsive syscall. Avoid concurrent recovery remounts that can wait on the same kernel locks. If a mount change refuses or fails, inspect actual state rather than assuming root remained rw from the utility exit code.

## Read-only native dependency inventory

`device/root-remount-preflight.sh` accepts **no action arguments**, requires a root session through port 2225 and verifies expected ext3 root identity, writable root/tmp, inactive USB export, detected external power, regular root-owned hash-matched mount/BusyBox utilities. It prints only allowlisted root-source/options metadata, classifies mtab without reading its contents, and reports tmpfs space. Unknown root options and unexpected mtab link targets are suppressed and refuse review. It never invokes mount, service scripts, signals, sync, watchdog devices, raw partition reads/writes or reboot. Ordinary data/metadata reads are not a promise of zero kernel atime activity on a writable filesystem.

Live binary match does not resolve kernel-IO/recovery safety. A PASS here is tool/state evidence only, not permission or a ready remount procedure. Fresh full writer and service-identity scans remain action-time gates.

Offline checkpoint: **182 tests run, 180 pass, 2 Node-dependent skips**. Six new fixtures cover accepted root/options/tool hashes without executing either fixture utility, metadata-only mtab absence/regular/proc-link handling, changed utility/USB/power refusals, suppressed unknown options/link targets, root-ro/wrong-session/action-argument refusals, syntax and unchanged fixture file contents. The earlier handover integration/regression tests remain in the full suite. Native inventory/result is pending.

## Required worker failure handling before any approval request

- Separate readonly namespaced trial directory/state variables; do not repeat the sourced-helper `stage` collision. Include real first-party inventory integration tests, not only protocol mocks.
- Record exactly which service termination requests occurred and which original identities actually exited. Refuse children, new holders, ambiguous vendor/socket state or autonomous respawn; no name-based killing or forced escalation.
- Recovery must distinguish verified original rw, verified expected ro and unknown/unexpected state. Never start root-PID/log-dependent normal SSH or Nimbus while root is still ro. Best-effort service restoration may proceed only for services this worker interrupted, without duplicates, after root rw is established.
- At most one ro request and one rw restoration request. If a rw request has already been attempted, the EXIT trap must not silently issue a second one; a failure leaves private evidence for review through port 2225. No automatic reboot/repair/force fallback.
- Remount refusal is a FAIL even if service restoration succeeds. Preserve real failure exit/result, and do not disguise it as a successful restoration trial. Unknown state, option mismatch, unexpected process replacement or lost management observation also prevents PASS.
- Retain detached private tmpfs evidence and all earlier trial stages. No long capture wait, background scheduler or apparent hard timeout should be included. Polling progress is not a kernel-operation deadline.
- Fixture-test no-change preflight, both-service graceful exit/refusal, errors after each stop, unknown writers, ro refusal with rw preserved, ro success followed by rw success, rw refusal, wrong observed options/state, unchanged temporary SSH, no duplicate launches/remount retries, and explicit partial-restoration reporting. Native tool and failure-path behavior is not proven by these fixtures.

Only after dependency evidence, implementation review and fixtures are complete should an explicit remount-trial approval request describe its kernel/journal writes, temporary vendor/normal-management interruption, lack of guaranteed recovery and absence of capture/flash. A successful trial still does not supply an independent physical restore route or approve a later capture.

## Subsequent live evidence and prepared worker (approval pending)

The user returned a successful dependency inventory: expected root identity, source `/dev/root`, exact `rw,relatime,errors=continue,barrier=0,data=writeback` options; power detected, USB export inactive, root/tmp writable; matched mount/BusyBox hashes; recognized proc-linked mtab; tmpfs 4096KiB total, 320KiB used, 3776KiB available. These are checkpoint observations, not future readiness guarantees.

First-party worker: `device/root-restoration-trial.sh`. Builder: `scripts/package-root-restoration-trial.py`. Local source-only archive: `build/nimbus-root-restoration-trial-v1.tar`, SHA-256 **`e02167e30ab2206a8bdc86092423c46fc5cc5f0b97ec6b4004e20e30aa95a654`**. Contents are only `trial.sh`, the first-party read-only `identity.sh` and checksums, with 0600 member/archive modes. Distinct device stage: `/tmp/nimbus-root-restoration-trial-v1`, root-owned 0700 tmpfs; no prior trial/listener stage is overwritten or removed. No vendor image/binary/script copy, key, credential or backup is packaged.

The default `--check` performs no signal, launch or mount. Separately approved `--start` detaches a worker and repeats private stage/source, root/device/options, power/USB/tmp, management keys/launcher/binary, Nimbus start/config hashes, fresh process/start/socket, no-children and all-process writer checks. Namespaced readonly trial state avoids the earlier sourced-helper collision. It requires a port-2225 session; keep a freshly responsive independent pinned shell open. Operator flags/markers are not an authentication boundary against root.

One freshly checked normal-listener TERM and one freshly checked Nimbus TERM are permitted. Stop refusal, ambiguous/respawn state, new holders or missing metadata aborts; no forced escalation. Before remount, no writable regular root fd or shared writable root mapping may be observed. The worker requests one internal-only/no-mtab ext3 non-forced ro remount with the full fixed known options, verifies both mountinfo VFS and superblock ro plus matching `/proc/mounts` options, then **immediately** requests one explicit `-w` restoration with the original fixed rw options. No arbitrary targets/options, capture wait, timer-based freeze, raw partition command or automatic retry exists.

EXIT/signal recovery distinguishes exact rw, exact ro and unknown state. An error after a ro request that actually changed state permits one guarded rw request, but result remains FAIL. A rw request is never repeated by cleanup. If root is actually rw despite a utility error, interrupted services may be restored once, still with FAIL. Unknown root state/options/identity, lost replacement management or persistent ro prevents blind remount/service launch. Service starts are only attempted after verified rw; normal SSH restoration is independent if Nimbus restart fails, with no duplicate/repeated start. Kernel remount/journal and normal service log/PID/database writes are expected.

The launcher waits up to forty-five polling intervals. Stop/restoration polls and detached traps are not hard kernel-operation deadlines or independent recovery hardware. IO stalls, killed worker, power/network loss or failed rw restoration can leave root ro and services unavailable. No reboot/repair/force fallback is supplied. Current inconsistent backup and failed derivative do not establish a physical restore route. Failed/missing result means retain evidence and review through port 2225, not rerun. PASS still needs fresh pinned authentication and browser/Settings/storage follow-up.

**198 tests run, 196 pass, 2 Node-dependent skips.** Sixteen new root-worker fixtures cover default no action; real-inventory detached completion/stage isolation; one ro/explicit rw with full options and service restoration; old/vendor stop refusal; ro refusal without extra mount; utility error after actual ro or rw changes; rw refusal without retry or starts on ro; wrong observed ro options; independent SSH restoration if vendor fails; failed SSH restoration without retry; errors after each stop; changed mount utility/unknown writer refusal; replacement loss; syntax and source-only/no-overwrite packaging. Fixtures source the actual inventory rewritten to synthetic paths/hashes/ownership, mocking signal/sleep only. A harmless fake mount edits **fixture metadata**, never host/device mounts; fake service launchers copy records, never run real servers. Database bytes and preexisting temporary-listener stage remain unchanged. Native remount/restoration and failure recovery remain untested.

Additional reference review at the same pinned commit (`mount/fsprobe.c`, `mount/fsprobe_blkid.c`) supports explicit literal device path/type: canonicalization instead of LABEL/UUID lookup, no filesystem guessing with specified type, and an initially uninitialized blkid cache. This narrows reference-code probing/cache side effects, not exact vendor-build attestation.

Separate explicit approval for the **first actual root mount change** is now requested. No live remount command/trial has been supplied or executed. Earlier pending statements above are historical checkpoints.

## Returned native restoration-only evidence

The user approved the specific root trial after disclosure of journal/metadata
writes, temporary service interruption and unguaranteed recovery, then supplied
the verified package run. Preflight and detached worker reported the fresh
normal-listener identity PID 1432/start ticks 1877495, replacement PID 6701/start
ticks 648093, and Nimbus PID 3235/start ticks 1742980; these are historical
observations, never future signal targets. Hashes/socket ownership matched and
targets had no observed children.

The worker output showed one TERM per freshly checked target, one non-forced ro
request, expected root read-only configuration observed, immediate one explicit
rw restoration, and one reviewed start request each for Nimbus and normal SSH.
Final result was PASS with root rw, normal SSH/Nimbus present and the original
replacement retained. No raw capture/read/write command, force, freeze,
watchdog access, boot edit, media remount, reboot or firmware flash was performed.
The command returned after about 39 seconds on the PC; this observation is not
a future completion deadline or native failure-path recovery proof.

The new normal-listener/Nimbus PID/start identities were not printed in the
restoration excerpt. A fresh read-only inventory and pinned port-2224 login can
verify their current state; pre-trial authentication cannot substitute. Browser,
Settings and internal/SD visibility need post-trial user confirmation. Retain
the trial stage/log/archive and all earlier backups unchanged. This successful
ro/rw observation informs a separately reviewed consistent-capture design, not
authorization to repeat interruptions/capture or assurance of physical boot
recovery, full database integrity or image flash readiness.

Subsequent follow-up completed the basic gates: a fresh strictly pinned
port-2224 `id` returned root identity, and the user confirmed that dashboard,
Settings and both storage views still work. No post-trial upload content-hash
validation, native failure recovery or consistent capture was supplied. The
next user request concerns speed improvements; see [the local UI performance
work](UI-PERFORMANCE.md). No repeat remount or capture is authorized by that
request.
