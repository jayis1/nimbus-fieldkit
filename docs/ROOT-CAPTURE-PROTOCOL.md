# Consistent-root capture protocol — offline preparation only

Latest frozen-scope follow-up (2026-10-13): ten transport tests passed, including
a full **268435456-byte synthetic** stream at unchanged production geometry.
The fixture used real host file/directory fsync, receiver readback, same-stream
ACK, an independent synthetic-producer readback after ACK and exclusive receipt
promotion. No SSH/device/raw partition/service/remount was involved. Instrumented
fsync calls executed the real operation, not a success stub. This demonstrates
the full-size host protocol path on this host filesystem, not power-loss
durability, native controlled-ro lifetime, native cancellation/drain or recovery.
Native 256 MiB durable-ACK integration remains pending; receipt certification
flags stay false. Earlier status text below is historical where superseded by
later checkpoints. The normal 2224 management path last worked; 2225 last refused
connections and must not be assumed available or restarted blindly.

Full capture-specific regression after this addition: **107 tests passed**, no
skips. This is the scoped host/emulated/fixture suite, not a full workspace pass
or evidence of newly executed native drive actions.

## Status

Latest owner-returned root/tool/power/USB/tmpfs checkpoint passed. The original
working root remains writable; no capture has occurred. Temporary pinned SSH 2225
works, and the owner returned a fresh strictly pinned interactive shell after the
dependency refresh. Responsiveness must still be refreshed at live-action time.
Prior restoration-only ro/rw success does not establish backup consistency or
failed-boot recovery. Do not rerun the old restoration trial to collect a backup.

New `scripts/receive-root-capture.py` is a **host receiver prototype**, not a live
backup program: no SSH launcher, device worker, mount/service invocation or raw
device reader. Its direct command-line entry refuses execution. It is tested with
synthetic streams only and is not integrated into beta4 or any installer.

The goal is a separately approved 256 MiB root-only private capture streamed to a
trusted PC, never staged in the drive's 4 MiB tmpfs. It does not replace the
separate boot/settings/calibration backup or include user media. Its contents will
be private rollback material, never a shareable firmware input.

## Strict wire contract under development

Future controller chooses a fresh random 256-bit token, prepares a new mode-0700
direct child of `.private-backups/`, validates local free space and establishes
strict existing host pin/client authentication on 2225. No accept-new, media-share
backup, arbitrary destination, caller-selected geometry or resume is supported.

Device stdout contains only:

1. `NIMBUS-ROOT-BEGIN <token> 268435456 179:2 ro` followed by LF.
2. Exactly 268435456 raw rootfs bytes.
3. `NIMBUS-ROOT-END <token> <same-stream-sha256>` followed by LF.
4. After the host acknowledgment and worker restoration, one final status:
   `NIMBUS-ROOT-RESULT <token> ro-until-ack rw-restored ssh-restored vendor-restored`
   followed by LF and EOF.

Host control channel sends only
`NIMBUS-HOST-VERIFIED <token> <sha256>` plus LF, and only after streaming to an
exclusive 0600 partial file, file fsync, independent file readback/hash and parent
directory fsync. Tokens/hashes and exact-size framing bind the acknowledgment to
that attempt. Device diagnostics must not contaminate binary stdout.

Host promotes using an exclusive hardlink rather than overwrite-capable rename,
and records a private receipt only after exact final status and EOF. Failed or
incomplete attempts retain partial evidence, are not reused and have no successful
protocol receipt. A receipt never says `filesystem_consistency_verified`,
`restore_tested`, `production_ready` or `flash_authorized` is true. Device-reported
state is still an assertion, not independently verified native consistency.
The source model's metadata/readback checks are not a defense against a hostile
same-user/root host process changing files concurrently.

Prototype tests cover successful receipt without certification, acknowledgment
ordering, fsync/readback failure, wrong token/geometry/root/rw, truncated/wrong-hash
stream, premature-rw/failed-restoration/missing-result/trailing-data, failed ACK,
existing evidence/symlinks/permissions and insufficient space. These are protocol
fixtures, not a tested capture lifecycle or physical backup.

## Device worker requirements — not implemented yet

The receiver must **not** be connected to the old live-rw `backup-pretrial.py`
stream or a bare dd command. No approval or lifecycle logic is embedded in it.

Before any interruption, a future detached first-party coordinator must repeat
all validated identity/start/socket/no-children/writer/tool/options/power/USB gates
from the restoration-only design, plus exact root partition geometry and private
stage/dependency hashes. Preserve original stage/evidence and the independent
responsive shell. No PID from chat is a signal target.

Coordinator owns the entire lifecycle:

1. At most one fresh targeted normal-listener TERM and one Nimbus TERM; refuse
   replacement, respawn, children, incomplete/unknown writers or stop refusal.
2. No observed writable root descriptors/shared mappings before one **non-forced**
   ro request using the full reviewed options and no helper/mtab updates.
3. Verify expected VFS **and** superblock ro, unchanged root identity/options and
   exclusive media ownership before opening the exact partition read-only.
4. Stream exact-size bytes and compute the source digest from that same stream,
   not a second partition pass. Propagate reader, transport and hasher failures;
   shell pipeline exit status alone does not prove all components succeeded.
5. Hold the coordinator's ro epoch until exact token/hash ACK. Unexpected state,
   USB export, disconnect, short reads, hash failure or early rw restoration must
   irrevocably invalidate the attempt. Before/after sampling alone cannot rule out
   an intervening rw transition; the controlled lifecycle needs explicit review
   of autonomous mount actors and concurrent privileged actions.
6. Stop/close all capture readers and hash/transport children before a permitted
   restoration attempt. Never let a timer restore rw while a reader can continue
   and still publish a success marker. Model late ACK and cancellation races.
7. At most one explicit guarded rw restoration with exact original options;
   distinguish actual rw, actual ro and unknown state even after utility failure.
   Restore only interrupted services, independently/once, after verified rw;
   keep 2225 unchanged. Failed restoration prevents success and requires review.
8. Deliver final report only after verified restoration, and let the controller
   separately inspect worker exit/result and authenticated post-trial services.

Use separate staged source and control input: an SSH stdin pipe cannot safely be
both a `sh -s` script upload and a live ACK channel. Stage validation/execution,
detached evidence, stream/control ownership and disconnect recovery still need
implementation and integration tests. If private FIFOs are selected, their owner,
mode, peer lifetime, cancellation and no-stale-token rules must be reviewed too.

Detached traps/watchdogs/host timeouts cannot guarantee recovery from a stuck
kernel read or remount. No freeze, force, filesystem repair, swap disable,
watchdog-device open, raw write, reboot or firmware install is part of this design.

## Remaining offline/native gates

- Implement/test coordinator and transport with real first-party inventory in
  synthetic fixtures, including disconnect, truncation, ACK timeout, worker death,
  reader failure, premature rw, lost management and every restoration failure.
- Resolve controller SSH exit and private manifest commit handling; a successful
  parser return alone must never certify a live transfer or service restoration.
- Review scratch/RAM budget; shell pipeline buffers are not a 256 MiB staging area.
- Review exact native operations and failure paths with the owner and obtain
  specific interruption/remount/raw-read approval. Current approval covered only
  temporary listener start, not this capture.
- After capture, independently run read-only filesystem checking on the private
  host file and retain the original bytes if any problem is found. No repair to
  bless an inconsistent capture. Successful fsck still is not restore/boot proof.
- Require authenticated normal-management and basic vendor/storage follow-up;
  retain the fallback and all evidence until separately reviewed cleanup.

No live capture command/package is supplied at this checkpoint.

## Validation checkpoint

Ten receiver fixture tests passed. Full workspace regression using the documented
compatible private no-space fixture directory: **277 run, 273 passed, 4 skipped**.
Skips remain two Node checks, unavailable trusted host Dropbear key tool and the
older candidate-v1 vendor comparison's removed temporary input path. Private
synthetic-test log is retained at
`/tmp/opencode/nimbus-capture-protocol-review-073itcnj/regression.log`.
No device capture, remount, interruption or firmware action was executed during
these tests. Beta4 and previous backups/builds remain unchanged.

## Offline lifecycle model follow-up

`scripts/root-capture-lifecycle.py` implements a testable **decision model**, not
an on-device worker. It emits abstract next-action labels, never commands, and
has no process/device/network/mount access. No Python runtime is assumed on the
SanDisk. Native coordinator and transport integration are still unimplemented.

Twelve model tests passed. They exercise one-request limits, exact stream/ACK
requirements, reader draining before restoration, irreversible invalidation on
premature rw/disconnect, late ACK refusal, actual-ro/actual-rw utility failures,
unknown root/lost fallback refusal and independent SSH recovery after vendor
restart failure. Lost fallback state is retained during reader draining rather
than implicitly assumed healthy afterward. A complete model still marks
filesystem consistency, physical restoration and flash authorization false.

Model facts are caller assertions, not a kernel monitor or security boundary.
The fresh dependency/identity observations and actions must later be wired to
reviewed native checks; model tests do not establish capture lifetime, reader
termination or native failure recovery. Any out-of-order/terminal attempt event
refuses rather than resuming the same attempt. No live capture package or approval
request is supplied by this model checkpoint.

Full regression with the compatible private fixture path: **289 run, 285 passed,
4 skipped**, with the same documented dependency/input skips. Log:
`/tmp/opencode/nimbus-capture-lifecycle-review-_kyohh7j/regression.log`.

## Native stream component and inactive ARM build

New first-party `device/root-capture-stream.c` implements **only** read/hash/stream/
ACK handling, not the service/remount coordinator. It cannot emit a ROOT-RESULT
restoration marker. No live command or installation package is supplied.

Production build fixes the source to `/dev/mmcblk0p2`, opens it read-only/no-follow
and checks block-device major/minor 179:2, reviewed start/size, VFS/superblock ro
and exact options, and inactive USB. Metadata reads are bounded. Root state is
rechecked per chunk and before the end marker and ACK acceptance; sampling cannot
exclude transient external rw changes and must not be called epoch proof.

Memory is bounded: 64 KiB data buffer plus bounded metadata/line buffers. It
forks/execs fixed `/bin/busybox sha256sum` (coordinator must first verify the pinned
BusyBox hash). It forwards the same bytes to stdout and the hash child's stdin,
validates exact hash output and child exit, closes the raw reader and reaps the
hasher **before** waiting for a token/hash-matched host ACK. Reader/hasher errors
prevent the end marker; later ACK/state errors prevent helper success. No
restoration marker is emitted by this component. SIGPIPE/output loss and cooperative TERM/HUP/INT
invalidate; cleanup closes the raw fd and waits for only its unreaped direct
child, not a name-matched/historical PID. Kernel IO/hasher waits can still stall;
SIGKILL/power loss bypass cleanup. Coordinator must separately observe helper and
children/descriptor lifetimes before any writable restoration.

Fixture builds are compile-time marked, use only a fixed-size **regular synthetic
file**, refuse block devices and cannot override production paths at runtime.
Tests compile both production and fixture variants with warnings as errors.
Hasher fault injection is fixture-only. Ten host-native tests cover exact emitted
bytes/hash, real integration with the receiver ACK (only coordinator's final
restoration marker mocked), rw/export/geometry/VFS disagreement, malformed/failed
hasher, short/symlink input, bounded/symlink metadata, invalid/missing ACK,
state change while waiting for ACK, output disconnect and cooperative cancel.
These do not exercise a device remount/service lifecycle.

First-party offline builder: `scripts/build-root-capture-stream.py`, accepting an
already downloaded hash-pinned Bootlin SDK archive, no downloads or device access.
It uses a controlled compiler environment, no fixture defines, exclusive private
output, static ELF audit and ARM-emulated **no-argument refusal only**. SDK
relocation runs only inside the new local extracted SDK. SHA matching establishes
archive consistency, not independent SDK build reproduction or license permission.

Inactive artifact: `build/nimbus-root-capture-stream-v1/root-capture-stream.arm`:

- 74772 bytes; SHA-256
  `fb32a53c265b0e5b2db9d79643fad3b8576af8c01cb5b4dca80a2c3523b8cbd3`.
- C source SHA-256:
  `7a7c3bddd1f5f17b72d6ef80f3ed569c1e7cab8a79223c310aa58bd4e06b27b4`.
- ARM EABI5 static EXEC, stack protector, GNU_RELRO, non-executable stack, no
  interpreter/dynamic segment; **not PIE/ASLR**.
- Mode 0600, source/manifest/warning retained; not installed in beta4 or the drive.
- Native old-kernel syscall/hash/cancellation behavior untested; installable,
  hardware-qualified and flash flags remain false.

Next: implement the native coordinator and transport, source-stage/control-channel
separation and detached failure recovery with actual inventory integration in
fixtures. A standalone streamer is not a safe consistent-capture workflow and
does not supersede the approval and restoration requirements above.

Validation for this component checkpoint: **36 capture-related tests passed**
(receiver, lifecycle, native streamer and offline build). Full workspace run with
compatible private fixture path: **303 run, 299 passed, 4 skipped**, same previously
documented dependency/input skips. Log:
`/tmp/opencode/nimbus-native-stream-review-yzxgcizw/regression.log`.
The inactive 0600 ARM export is not chmodded for testing; QEMU validation uses a
hash-identical temporary executable copy and exercises no-argument refusal only.
No native raw read, service stop, mount change, installation or firmware write
was performed. Existing firmware, beta4 and private backups remain untouched.

## Offline coordinator checkpoint

`scripts/prepare-root-capture-worker.py` now prepares a separate shell coordinator
from the whole-file hash-pinned restoration worker and identity helper. It also
requires the exact inactive ARM streamer hash. Exclusive output directories,
strict single-occurrence transformation anchors and shell syntax checks refuse
changed inputs rather than silently adapting them. The old restoration worker is
unchanged. Current inactive output is `build/nimbus-root-capture-coordinator-v2/`;
v1 is retained as an earlier, superseded preparation snapshot. Neither output is
a launch kit or an installer. The streamer stays 0600 in the host output; native
staging/700 permission and executable tmpfs remain unqualified prerequisites.

The generated coordinator retains actual first-party process/socket/writer and
restart-input checks. It removes the old detached `--start` path; check-only
performs no raw read, signal, mount or service start. Its proposed worker requires
a fresh session marker in a private stage and one token. It sends protocol bytes
on fd3, diagnostics on stderr, and reserves stdin for ACK control, never script
upload. The proposed transport must stage the verified script separately.

After the reviewed one-time service interruptions and non-forced ro transition,
it starts only the checked streaming helper. It waits for normal helper completion
and scans raw block-reader descriptors before allowing rw restoration. Cooperative
coordinator cancellation freshly checks the helper identity, requests TERM and
waits for completion before restoration. Abnormal helper termination deliberately
blocks rw/service restoration because descendant cleanup is not established.
There is no force/escalation or second remount/start request. A vendor restart
failure does not suppress an otherwise safe normal-SSH restart attempt.

Signals irreversibly clear success. Missing/incorrect ACK or disconnect can
produce a failure record with observed restoration, never a ROOT-RESULT success
marker. Lost fallback prevents writable restoration. Failure to create the
exclusive private RESULT record also withholds protocol success and returns
nonzero. That device record is **not** fsync-verified durable/immutable evidence;
private host receipt commit and transport exit qualification remain separate.

Fourteen new coordinator/generator tests use synthetic `/proc`, block metadata,
power, services and mounts with the compiled native regular-file fixture reader.
They cover check-only, exact binary-output separation, real receiver/streamer/
coordinator round trip, wrong/missing ACK, output disconnect, coordinator TERM,
abnormal helper death, lost fallback, private-result commit failure, stop refusal,
ro/rw/options failure, vendor restore failure, pinned-input and output-reuse refusal.
Native services/mounts are never invoked by these fixtures.

Remaining blockers include a separately reviewed pinned full-duplex SSH transport,
stderr drain/backpressure and worker-exit-before-final-host-commit handling,
disconnect-independent coordinator ownership, complete descendant lifetime checks,
midstream fallback-loss monitoring, concurrent launch exclusion, tmpfs/RAM/native
tool budget and old-kernel validation. Read-only-state sampling cannot prove an
unbroken ro epoch against autonomous actors. Native hardware action still needs
fresh checkpoints and separate exact approval. Do not manually run the prototype.

Coordinator checkpoint regression: **317 run, 313 passed, 4 skipped** using the
documented compatible private fixture directory. Capture-related coverage is now
**50 tests** (36 earlier plus 14 coordinator/generator tests). Full log:
`/tmp/opencode/nimbus-coordinator-review-t1ucfkfs/regression.log`.
`git diff --check` passed. No drive action or firmware-image change occurred.

## Offline host transport checkpoint

`scripts/root-capture-transport.py` supplies **only** a fixed SSH argv planner and
an adapter for an already started, caller-owned process. Its CLI refuses live
execution; it never launches SSH, stages files, starts services or changes mounts.
The planner requires an explicit current device IPv4 address and pins port2225
to that device's existing port2224 known-hosts alias,
requires strict Ed25519 host checking and public-key-only batch authentication,
disables user/system SSH config and global/dynamic known-host alternatives, host
key updates, multiplex reuse, forwarding and TTY allocation. An eventual launcher
must freshly verify the expected key/pin files and identity fingerprints. Batch
mode requires the owner to unlock the passphrase-protected key locally (e.g. into
their agent); no passphrase handling is added. The argv is not a launch approval.

The adapter requires unbuffered binary pipes. ACK stdin is separate from stdout;
the script is never uploaded over ACK input. Selector-based reads multiplex
binary stdout and stderr with 64 KiB reads and bounded protocol buffering.
Diagnostics go to an exclusive private 0600 `TRANSPORT-STDERR.log`, capped at
1 MiB; exceeding the cap irreversibly invalidates the attempt. There is a shared
monotonic IO/process deadline and one bounded, nonblocking ACK write. It does not
promise time bounds for host fsync/readback or a stalled filesystem operation.

The adapter exposes final EOF to the receiver only after both output pipes close,
the supplied process exits zero and diagnostics are fsynced. Consequently the
receiver cannot promote the image or publish its receipt before process exit.
This proves the **supplied host process** exited, not that remote descendants
closed, the filesystem remained continuously ro or hardware recovery is possible.

On failure it closes ACK input and drains remaining output within the remaining
budget to avoid pipe backpressure blocking cooperative cleanup. It never sends
TERM/KILL to SSH. Deadline exhaustion leaves remote state **unknown**; the caller
must retain the independently pinned fallback and evidence, not declare recovery
or rerun. Control EOF or SSH exit is not shutdown/restoration proof. No detached
device coordinator or disconnect-independent recovery owner has been implemented.

Receiver receipt publication now writes/fsyncs an exclusive
`CAPTURE-MANIFEST.json.partial`, syncs the directory, then hardlinks it to the final
name without overwriting. Partial receipt and image evidence are retained. An
observed publication-directory fsync failure attempts to withdraw only its own
final receipt link, never an unrelated inode. Filesystem failure, SIGKILL or power
loss cannot guarantee withdrawal durability; partial receipts are **not** completion
evidence. A promoted image without a completed receipt is also not a successful
capture. Existing consistency, recovery and flash flags remain false.

New local-process tests cover pinned argv/no launch, full-duplex ACK with large
diagnostics, nonzero exit after a valid trailer, diagnostic overflow/sync failure,
truncation/trailing data, deadline after trailer without kill, prior diagnostic
evidence and buffered-pipe refusal. A full round trip includes the real host
transport/receiver and compiled native fixture streamer with the synthetic shell
coordinator. Receipt tests add fsync/publication failure and partial-receipt reuse
refusal. All source data and mounts/services remain synthetic.

Next gates remain device-side disconnect-independent coordinator ownership,
complete descendant observation, persistent midstream invalidation/fallback loss,
exclusive one-shot staging, transport preflight and native RAM/tmpfs/tool checks.
The proposed SSH plan runs a foreground worker and is therefore **not** a safe
disconnect-independent capture launcher. No live command or deployment is offered.

Transport checkpoint validation: **63 capture-related tests passed**. Compatible
full regression: **330 run, 326 passed, 4 existing skips**. Log:
`/tmp/opencode/nimbus-transport-review-pzjc48lo/regression.log`.
`git diff --check` passed. The ARM streamer/coordinator artifacts, beta4 firmware
and device remain unchanged; no native raw read, interruption or remount occurred.

## Offline disconnect-owner checkpoint

`device/root-capture-guardian.c` now implements the disconnect-owner relay core
under an explicit **host fixture-only** build define. Default builds return 2 for
every invocation; there is no enabled native entry, deployed binary or live
launcher. Fixture mode accepts a private local stage containing a caller-supplied
synthetic shell worker; it is not a security boundary for untrusted worker source.
Only the first-party test harness supplies that worker, with synthetic mounts,
processes and a regular-file capture fixture. No ARM guardian artifact is built.

The core forks an owner into a new session before spawning the worker. The
SSH-side waiter retains no data/control/log descriptors; its death does not kill
the detached owner. The owner relays bounded output and one bounded ACK stream,
keeps worker stderr on a separate pipe with a private 128 KiB log cap, and drains
both worker output channels during invalidation. Output hangup is sampled with
poll even when no further image bytes are queued (e.g. while awaiting ACK).
Input EOF, output loss, excess ACK data, diagnostic overflow, owner HUP/INT/TERM
or its monotonic deadline irreversibly invalidate. Cancellation closes ACK input
and requests one cooperative TERM only for its unreaped direct worker child.
It never signals a process group, historic PID or inferred descendant.

The deadline is a cancellation request, **not** a cleanup time guarantee. The
owner waits/drains without escalation, forced remount or service launch; blocked
kernel IO or an uncooperative worker/descendant can still prevent completion.
Reaping the direct shell and seeing channel EOF cannot by themselves prove all
remote descendants are gone. Full descendant identity/lifetime observation
remains a native integration gate. SIGKILL/power loss still bypass recovery.

An exclusive persistent claim prevents a second fixture worker in the same stage,
even after failure. Private guardian logs and outcome evidence are preserved, not
removed to permit retry. Outcome evidence records invalidation and direct-worker
exit status and always states `restoration_certified=no`. It does not certify
continuous ro, filesystem consistency, physical recovery or power-loss durability.

The separate coordinator generator now protects already-running checked cleanup
from HUP/INT/TERM interruption. Restored vendor/SSH launcher subshells explicitly
reset those signal dispositions before exec, so ignored TERM is not leaked into
restarted services. Current coordinator output is
`build/nimbus-root-capture-coordinator-v3/`; v1/v2 remain retained, superseded
snapshots. The old restoration-only trial and ARM streamer remain unchanged.

Twelve guardian tests exercise the compiled relay, including full real host
transport/receiver + native fixture streamer + synthetic coordinator integration,
disconnect during fixture reading, output loss with still-open ACK input, input
EOF, killing the SSH-side waiter, owner TERM, deadline while withholding ACK,
excess input, actual diagnostic-cap overflow, persistent one-shot claim, disabled
default build and cancellation during cleanup. The waiter-death fixture runs in
a separate local subreaper process to collect detached test children without
leaving orphan zombies or altering the main test process's adoption behavior.
A coordinator test also verifies reset TERM behavior in an actual local shell
service subprocess.

Next: integrate a fixed hash-pinned native worker entry and reviewed staging,
inherited-descriptor census, detached-owner identity/evidence and complete child
tracking. Wire persistent midstream fallback/root invalidation, and validate
native poll/clock/session/signal behavior, executable tmpfs and combined RAM/tmpfs
budget before considering any live test. The host SSH planner still names the
old foreground worker: it must not be treated as a disconnect-safe live launcher.

Disconnect-owner checkpoint validation: **76 capture-related tests passed**.
Compatible full regression: **343 run, 339 passed, 4 existing skips**. Log:
`/tmp/opencode/nimbus-guardian-review-avke0pof/regression.log`.
`git diff --check` passed. No native SSH, raw read, service interruption, mount
transition, firmware update or deployment was performed.

## Explicit owned-child drain checkpoint

`device/root-capture-stream.c` adds `--stream-evidence` for the proposed
coordinator only. It requires an already-open fd4 referencing an empty owned
0600 regular file, distinct from binary stdout and ACK stdin. The coordinator
creates that file exclusively in its private stage, passes the fd to the reader
and closes its own copy. The hash child closes inherited fd3/fd4 before exec;
only the reader parent can issue the cleanup report.

The reader closes the raw partition descriptor and waits for its owned hasher
before reporting exact token-matched `reader-closed hasher-drained` evidence.
Cancellation or output failure invalidates capture but does not suppress checked
cleanup evidence. Reader-close/wait/evidence failures return status 70 (unknown
cleanup), never success. The report is separate from ROOT-END/ROOT-RESULT and
cannot itself certify a valid image, restoration or continuous ro. The existing
standalone `--stream` fixture interface remains for synthetic protocol tests; it
is not a live coordinator or an alternative to mandatory drain evidence.

The coordinator accepts restoration after a started helper only for a permitted
normal status (0 or 1), exact private evidence metadata/size/token/text and the
existing no-raw-reader observation. Missing evidence, abnormal/unknown exit,
argument refusal or lost management all block writable restoration. A valid ACK
with deliberately removed fixture evidence now leaves the synthetic root ro and
services stopped, rather than inferring safety from the helper's exit alone.
The report concerns the **owned reader and direct hash child**, not arbitrary
descendants. Fixed hash-app behavior and complete native descendant observation
remain qualification gates; this is not general descendant-tracking proof.

Updated inactive ARM stream artifact:
`build/nimbus-root-capture-stream-v2/root-capture-stream.arm`, 74772 bytes, SHA-256
`3de1c4ccd527ff47e494d4c579508dae7ee2f7bb5995530fe7742318d8c4fa40`.
Source SHA-256:
`8820f948f005315ffb57c895c21dec9f4f441e1209d533f90cb0f696182e0de2`.
It was built with the same verified local SDK, audited as static ARM EABI5 and
validated only for no-argument refusal under emulation. Export remains 0600;
hardware/install/flash flags remain false. V1 is preserved, superseded. The
updated coordinator is `build/nimbus-root-capture-coordinator-v4/`, pinned to v2;
v1/v2/v3 coordinator outputs are retained, superseded. No artifact was deployed.

The guardian fixture core now enumerates inherited descriptors through
`/proc/self/fd` before claiming a stage: only the three standard pipe/socket
descriptors and its temporary enumeration fd are accepted. Extra inherited fds
cause refusal before worker launch or claim, including descriptors above the
previous close-loop range. Native descriptor types/proc behavior remain untested.
The core records an exclusive token-marked `GUARDIAN-INVALID` on observed
invalidation before its cooperative cancellation request. Failure to record does
not clear in-memory invalidation; tmpfs records are not power-loss durability.
Default guardian builds are **still disabled**. No pinned native launch path has
been enabled by these changes.

Six additional tests cover native fixture drain evidence, cancellation, output
loss/hasher termination, missing/unsafe report fd, missing report after valid ACK
and inherited-descriptor refusal. Existing disconnect/cleanup and transport tests
now also exercise required drain evidence. Next is fixed native guardian entry,
hash-pinned staging, persistent midstream root/fallback checks and complete child
tracking, followed by native syscall/resource qualification. No live capture
command is supplied or authorized.

Owned-child drain validation: **82 capture-related tests passed**. Compatible
full regression: **349 run, 345 passed, 4 existing skips**. Log:
`/tmp/opencode/nimbus-child-drain-review-6aoyy45g/regression.log`.
`git diff --check` passed; no native SSH/read/interruption/remount occurred.

## Pinned native entry build checkpoint

Owner requested both continued integration and eventual live testing. This does
not replace the separate exact approval/checkpoint before staging, service stops,
mount transitions or raw capture. No device action has occurred in this step.

The guardian now has a compile-time pinned native candidate entry. Unpinned default
builds still refuse all execution. A pinned native build requires root, a port-2225
SSH environment and the fixed `/tmp/nimbus-root-capture-v1` stage; runtime path
overrides and fixture flags are not accepted. A no-follow directory fd anchors
the stage before checks. Unexpected inherited descriptors are rejected. The
guardian verifies owned regular-file modes, bounded sizes and compile-time hashes
of worker, identity helper, streamer and SHA256SUMS before any stage claim or
worker launch. A fresh token marker and empty private worker log are required;
prior claim/outcome/invalidation/drain artifacts prevent reuse.

Pin verification uses new first-party `device/root-capture-sha256.h`, hashing at
most 1 MiB per regular input, without launching vendor hash tools. Host vectors
against hashlib cover empty/abc inputs, SHA padding boundaries, multiple blocks,
the maximum input and over-limit refusal. These tests are not a cryptographic
audit or a statement of compiler/source trust beyond recorded provenance.

The native candidate offers a check-only entry that performs no stage claim,
log creation or worker action, and a separately gated supervise entry. Owner
signal masks are reset before spawning the worker, and SIGCHLD automatic reaping
is reset so direct-child wait semantics are not silently inherited. Native
old-kernel behavior is still unqualified. The compiled supervise entry is not a
launcher approval and must not be invoked manually.

`scripts/build-root-capture-guardian.py` verifies the SDK archive and compares the
coordinator against the current reviewed generator/identity/streamer pins, rather
than trusting a supplied manifest. It builds exclusively into a new private local
directory. Current inactive artifact:
`build/nimbus-root-capture-guardian-v2/root-capture-guardian.arm`, 58240 bytes,
SHA-256 `664129234c794521ecd0c3d40dd3b80f59e7613de2759cff7398c8ac585e75e3`.
V1 is retained, superseded. The binary is mode 0600, ARM EABI5 static non-PIE EXEC
with non-executable stack/GNU_RELRO. Emulator validation exercises no-argument and
runtime-override refusal only, never the fixed real stage. It pins coordinator-v4
and stream-v2 and is not included in beta4. Hardware/install/flash flags stay false.

New tests cover first-party hashes, exact pin refusal before action, pinned
synthetic coordinator restoration, check-only/no-reuse, reviewed-builder input
provenance, bad-SDK refusal, ARM artifact/source/pin auditing and refusal entry.
No check-only or supervise invocation has run on the device.

The live-testing track starts with a fresh **metadata-only** owner checkpoint of
kernel, RAM and `/tmp` mount/free space. Then prepare/review exclusive temporary
staging and an inert native syscall/session/FD probe, with exact owner permission
for temporary files/execution, before any interrupting capture. Complete native
child behavior, persistent fallback/root checks and raw-capture approval remain
pending. The old foreground SSH planner is still not a safe capture launcher.

Pinned-entry validation: **89 capture-related tests passed**. Compatible full
regression: **356 run, 352 passed, 4 existing skips**. Log:
`/tmp/opencode/nimbus-pinned-guardian-review-5d33ykwr/regression.log`.
`git diff --check` passed. No drive change or raw read occurred.

## Inert native probe preparation

Owner-returned metadata: kernel `2.6.35.3-899-g9b1a262`, MemTotal 125496 KiB,
MemFree 23544 KiB, SwapTotal/SwapFree 151712 KiB, tmpfs exact
`none /tmp tmpfs rw,relatime,size=4096k 0 0`, 120 KiB used/3976 KiB available.
These snapshots show apparent room for the small probe, not reserved capacity,
native allocation success, zero future swap use or a capture RAM-budget pass.

Prepared an inert 33812-byte ARM probe, independently compiled from first-party
source, not a guardian/streamer or mount/service worker. Host/emulated tests pass;
no native run has occurred. Exact temporary staging/execution scope, hash and
owner-reviewed command are in `ROOT-CAPTURE-NATIVE-PROBE.md`. Approval to prepare
the probe is not treated as approval to upload it, run it or perform capture.

Probe preparation validation: 93 capture-related tests passed (four new probe
tests); targeted log `/tmp/opencode/nimbus-native-probe-targeted-g_7vj6kk/capture.log`.
Full regression timed out in an existing UI-performance fixture, not recorded
as a pass; log `/tmp/opencode/nimbus-native-probe-review-6yz7cdjg/regression.log`.
No device upload or execution occurred. Approval of exact staging/run scope is
still required; see the probe review document.

Owner-returned native probe now reports staged checksum OK and all six limited
syscall/session/signal/FD checks PASS, explicitly retaining
`native_capture_qualified=no`. See `ROOT-CAPTURE-NATIVE-PROBE.md` for exact evidence
and boundaries. The native guardian, real worker shutdown and hardware recovery
remain unqualified. Next is preparing a synthetic guardian disconnect test that
cannot invoke the real capture worker, before considering any interruption/read.

Prepared the separate, synthetic-hash-pinned guardian fixture profile and seven
regular-file bundle, 34188 bytes; no real reader/worker included. The relay source
is unchanged. Host positive-control/output-loss/waiter-death and bundle boundary
tests pass; native trial remains pending. Exact staging/run/only-test-SSH-client
interruption scope and owner-reviewed commands are in
`ROOT-CAPTURE-SYNTHETIC-TRIAL.md`, requiring separate approval before execution.
99 targeted tests passed; log
`/tmp/opencode/nimbus-synthetic-trial-review-vnh1g3lz/capture.log`. No device upload,
execution, connection loss or service change occurred during this preparation.

Subsequent owner-approved native synthetic trial returned pinned stage/hash check,
fake readiness and session-matched invalidation/direct-worker exit/fake cleanup
records. Separate pinned management remains responsive and root stays at original
rw options. See `ROOT-CAPTURE-SYNTHETIC-TRIAL.md` for exact evidence and limits.
This passes the limited synthetic abort/cleanup checkpoint only; actual native
reader/hasher lifetimes, midstream fallback/root invalidation and recovery remain
pending. No real capture worker, remount or block read ran in this trial.

Prepared the subsequent **positive regular-file-only** native pipeline trial:
separate fixture guardian/streamer, fixed pinned hasher wrapper, known fake
262144-byte data and fake metadata in private tmpfs. A precomputed synthetic ACK
tests matching/direct hasher reaping but explicitly cannot establish host durable
readback or real ro. Real guardian/stream sources remain unchanged; the profile
uses compile-time fixture defines and refuses block devices. Exact new staging
and one-shot approval scope is in `ROOT-CAPTURE-REGULAR-TRIAL.md`. No native
upload/run has occurred. 104 targeted tests passed; log
`/tmp/opencode/nimbus-regular-trial-review-f82zfe_6/capture.log`.

Owner's native regular trial subsequently **failed** because `/bin/busybox
sha256sum` reports applet not found. It invalidated and returned direct-owned
reader/hasher drain evidence with a truncated synthetic wire, never success;
root rw remained unchanged. The production stream candidate's identical BusyBox
launcher assumption is also blocked. Resolve the functioning PATH sha256sum's
actual executable/hash and prepare new pinned inputs offline, not a retry or
modification of retained failed evidence. Details: `ROOT-CAPTURE-REGULAR-TRIAL.md`.

Owner resolved and hashed the working standalone `/usr/bin/sha256sum` (116878
bytes, root:root 0755, hash recorded in `ROOT-CAPTURE-REGULAR-TRIAL-V2.md`). New
regular fixture v2 pins that hash/metadata and direct executable wrapper in a
new stage/session. Production source now execs the fixed standalone hasher, and
the coordinator verifies its hash/metadata before reading. Corrected inactive
artifacts: stream-v3, coordinator-v5, guardian-v3; old artifacts retained and
superseded. No corrected native execution, deployment or capture occurred.
New v2 staging/execution approval remains pending; this correction is not native
reader/hash/host-durability or recovery qualification.
Validation: 106 targeted tests passed; log
`/tmp/opencode/nimbus-standalone-hasher-review-5rdbped6/capture.log`.
No native correction deployment/run; failed original evidence retained.

Subsequent approved native regular-v2 trial/inspection reports a successful fake
reader/hasher pipeline: exact drain, helper/direct-worker exit 0, no invalidation,
complete predicted fake-wire bytes/hash. No real host readback or raw capture.
Real-root follow-up is currently **unresolved**: pasted mount output lacks the
expected ext3 root line and shows only rootfs. Block further execution/capture
pending complete read-only mount/mountinfo/uptime/module checkpoint. Do not infer
a cause, automatically remount/repair/reboot, or erase retained trial evidence.

Subsequent complete owner-returned pinned follow-up reconfirmed original root
ext3 rw options with matching 179:2 VFS/superblock mountinfo and no g_file_storage
in the readable module list. No repair/remount was performed to restore a view.
Limited regular-v2 synthetic positive pipeline/drain/wire checkpoint passes;
host durable acknowledgment and native cancellation during active reader/hasher
work remain next integration gates, not permission for a real raw-root capture.
