# Single-drive qualification checkpoints

## Accepted constraint and approval boundaries

The owner has confirmed there is no spare and accepts that experimental work may
render the existing drive unusable; sourcing another drive would happen afterward.
Use this unit for staged qualification rather than requiring a spare first.
This accepts the hardware constraint, not proof of recovery, an installable image,
or blanket permission to execute every destructive operation. Review and approve
each exact interruption, remount, installation or recovery write separately.

No failed-boot restoration is guaranteed. If independently usable recovery cannot
be established, any proposed installation must explicitly retain that uncertainty
and the possibility of permanent loss. Never silently promote owner risk acceptance
to a safe public installation procedure for other recipients.

## Evidence ledger

Keep original/private backup and candidate artifacts unchanged. Record new evidence
under a new checkpoint/date with exact input hashes, operation, actual result,
limitations and follow-up. Never post private keys, passwords, raw backup contents,
personal filenames or full service logs. A checkpoint passes only its stated scope.

| Checkpoint | Current evidence | Next required evidence |
| --- | --- | --- |
| Clean offline beta4 | Rootfs build, selected archive/image checks, module preservation and read-only fsck passed | Native image boot is not implied |
| Regression | 263 run, 259 pass, 4 skips using compatible fixture path; see release notes | Resolve skipped dependencies and fixture portability separately |
| Fresh hardware baseline | Owner-returned expected ext3 root/inactive USB, charger online, reviewed service hashes matched | Power reserve unavailable; root holders and current listener ancestry need review |
| Existing management | Historical owner-confirmed pinned TCP 2224 works; temporary 2225 previously tested | Refresh actual listener/stage state; do not reuse old PIDs |
| Service/mount restoration | Historical supervised stop/restore and root ro/rw restoration-only trials passed | Separate current preflight and consistent capture worker; no repeated trial by default |
| Consistent rollback capture | Off-device copy integrity exists; consistent current capture/restore not established | Enforced ro-only capture with completion/restoration checks and private host destination |
| Failed-boot recovery | Rescue located offline; destructive startup hazards known | Exact usable recovery entry/access and reviewed restore path; record unresolved risks |
| Native SFTP runtime | Local ARM candidate/emulated checks; owner-approved native version and own-process select/pselect/fallback probes now passed | Full native privsep/auth/confinement/session and USB lifecycle qualification; probe success does not authorize listener work |
| SFTP / GameHack | Dedicated accounts, jail, enrollment and physical browsing not qualified | Separate approved service/USB lifecycle trial, then pinned read-only browsing/download |
| Recipient first use | Generic image has no keys; cannot promise management access | Unique identities, secure enrollment, Wi-Fi/reset/entropy/access tests |
| Installation | No approved complete update package | Audited updater/failure paths and exact write plan, then owner review |
| Native firmware matrix | Pending | Boot, management, radio, power, vendor UI, media, SD, USB and recovery results |
| Public distribution | Vendor rights unresolved | License/privacy review, supported hardware matrix and explicit publication review |

## Checkpoint 1: owner-run read-only baseline

Use the trusted **PC terminal**, not the drive's shell. Leave management services
running. Let uploads, playback and settings saves finish first. Keep stable power;
do not unplug an active USB export or change radio roles merely to make a check
pass. The helper refuses observed USB export/unknown state. If it refuses, report
that result and review the normal ownership transition separately.

Use the owner-confirmed current device endpoint on port2224. The encrypted admin key passphrase
is entered locally by the owner, never shared. This streams two already reviewed
scripts; it does not install files on the drive or read raw partitions.

```sh
cat device/beta-capture-checkpoint.sh device/root-writer-preflight.sh |
ssh -T -p 2224 -i ~/.ssh/nimbus-admin-ed25519 \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
    root@192.0.2.10 'sh -s'
```

Return the metadata output, including refusal/errors if any. No secret/log contents
are requested. A changed host-key warning is a stop: do not remove the pin or use
accept-new/disabled verification. If the address is unavailable, report it rather
than scanning arbitrary hosts or changing the drive configuration.

Observed information: expected ext3 root identity, inactive USB export, whitelisted
charger/battery fields, listener counts for 2224/2225, fixed temporary stage file
permissions/sizes, writable root fd/shared-map counts and selected script hashes.
It performs no signals, service invocation, sync, remount, watchdog access, reboot,
block-device reads/writes, updater execution or boot-environment modification.

Limits: observations are racy; listener counts are not ownership/authentication;
charger metadata is not uninterrupted-power proof; zero writable holders is not
an exhaustive remount-safety test. SSH itself may produce normal existing service
logging. If port 2225 or its old stage is absent, **do not recreate it blindly**.

After results, select the next bounded checkpoint: refresh recovery/capture input
validation and exact independent-management dependencies, or a separately scoped
native runtime probe. No firmware write command is supplied here.

## Returned checkpoint 1

Owner ran the streamed helpers through the existing strict host pin on TCP 2224
and returned:

- Expected internal ext3 root identity confirmed; USB export inactive.
- Charger `online=1`, battery `Not charging`, capacity unavailable. External power
  is detected; battery reserve/uninterrupted power are not proven.
- One listening entry on 2224, **zero on 2225**. The old temporary listener stage
  was unavailable or unsafe. Do not assume the historical fallback still exists.
- Three holder processes: observed `nimbus` PID 3437 with one writable root fd;
  `dropbearmulti-b` PID 3634 with two; `dropbear` PID 6990 with two. Total five
  writable root fds, zero shared writable root mappings and zero incomplete/raced
  observations at this scan. These PIDs are historical observations, not targets.
- All four selected service hashes matched the reviewed values in
  `CONSISTENT-CAPTURE-REVIEW.md`.

This passes the limited baseline observation, not remount eligibility or recovery.
The extra dropbear process may be a session child, but that is not established.
Do not stop any holder or run an older trial expecting the missing 2225 service.

## Checkpoint 2: refreshed management process/listener association

New first-party read-only helper:
`device/ssh/management-owner-checkpoint.sh`. It checks expected root/inactive USB,
then reports only whitelisted daemon labels, PIDs, parents, start ticks, reviewed
running-executable match status and socket-fd references to **listening** entries
on 2224/2225. Connected sockets do not count as listeners. Unknown process labels,
executable paths, arguments, socket peers and log/key contents are suppressed.
Executable bytes are hashed as data only with an 8 MiB bound. No executable is
launched by this hash check. Before/after stat identity reduces races but does not
provide pidfd protection or independently verify session ancestry.

Four fixture tests pass, covering listener versus connected-session association,
parent/start metadata, mismatch reporting, output privacy, unchanged fixture files,
USB/action refusal and shell syntax. Native execution is pending.

From the trusted PC, same local passphrase/pin rules:

```sh
ssh -T -p 2224 -i ~/.ssh/nimbus-admin-ed25519 \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
    root@192.0.2.10 'sh -s' \
    < device/ssh/management-owner-checkpoint.sh
```

Return its output. A different/unavailable executable, incomplete observation or
root/USB refusal blocks further interpretation; do not replace binaries or signal
processes to make a match. This neither recreates 2225 nor changes existing
management. Independent-listener preparation and consistent-capture lifecycle
remain separately reviewed follow-ups, not actions performed by checkpoint 2.

## Returned checkpoint 2

Owner-returned native output:

- Vendor `nimbus`: PID 3437, parent 1, start ticks 2953; reviewed executable matched;
  no listening fd references on either management port.
- `dropbearmulti-b`: PID 3634, parent 1, start ticks 3204; reviewed executable
  matched; one listening fd reference on 2224, none on 2225.
- `dropbear`: PID 7199, parent 3634, start ticks 1985431; reviewed executable
  matched; no listening references on 2224/2225. This establishes an observed
  child of the current listener, consistent with the owner SSH session, not a
  second listener. The earlier PID 6990 is not reused as a live identity.
- Three whitelisted observations, zero incomplete counts. Metadata remains racy;
  no stop/remount authorization is inferred from these matches.

The limited association checkpoint passed. Independent port 2225 remains absent.
No process was stopped, binary replaced, mount changed or firmware written.

## Checkpoint 3: temporary listener prerequisites only

Reuse reviewed `device/ssh/capture-listener.sh` with **`--check`**, not `--start`
or retry. It checks the existing key/authorization metadata, hash-pinned binary,
wlan1 availability, inactive USB, writable tmpfs and absence of an old private
stage/occupied 2225. It neither copies keys nor executes the SSH binary in this
mode. Existing log/key contents are not requested in the returned output.

```sh
ssh -T -p 2224 -i ~/.ssh/nimbus-admin-ed25519 \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
    root@192.0.2.10 'sh -s -- --check' \
    < device/ssh/capture-listener.sh
```

Return PASS/refusal output. Do not remove stages, change permissions, replace keys
or start a listener to make the check pass. Any proposed temporary start requires
separate exact review/approval and subsequent independent authenticated/pinned
login. No service interruption, remount or capture follows automatically.

## Returned checkpoint 3 and next proposed action

Owner ran strict-pinned `capture-listener.sh --check` on TCP 2224 and returned
“Temporary listener checks passed: existing keys, pinned binary, wlan1 and
RAM-backed logging”, followed by the check-only no-change message. The limited
prerequisite checkpoint passed. No staging or listener was created by this check.

Next proposed action, **pending explicit approval**: rerun the reviewed helper
with `--start` to create a root-owned 0700 RAM-backed stage and launch the pinned
Dropbear binary as a separate temporary wlan1-only TCP 2225 management listener.
It uses the existing host identity/authorized clients, without copying keys,
editing startup/firewall, replacing 2224, stopping vendor services or changing
mounts. Runtime PID/log files reside in the private tmpfs stage. This exposes one
additional management port on the existing management interface; it is not SFTP
or a new permanent firmware feature. Failed start retains its stage for review;
do not blindly retry/delete it. The preflight is rerun by --start at action time.

If approved and observed, independently authenticate to 2225 with the existing
verified host pin (explicit HostKeyAlias) before any subsequent service/capture
review. A listening socket alone is not a verified fallback. Do not stop 2224,
remount, capture, reboot or flash as part of this proposed listener-only action.

## Approved temporary start: returned result

Owner explicitly approved the listener-only start, then ran `--start` through
strict-pinned TCP 2224. Returned prerequisites passed, temporary wlan1/key-only
2225 start message and process/listening observation. Helper reported 2224,
startup hooks, keys, vendor services and mounts unchanged. No authenticated 2225
session has yet been established at this checkpoint. No stop/remount/capture/flash
approval follows from this start.

Next: from a separate trusted PC terminal, connect interactively to 2225 using
the existing port2224 host-key alias, the existing strictly verified host pin and
authorized client key. This intentionally reuses the same server identity, not
TOFU/new-port trust. Set `HISTFILE=/dev/null` for the retained remote shell so
subsequent interactive commands do not create a rootfs history writer. Retain
that session and the unchanged original management listener. A prompt proves
this authenticated path only; fresh process/writer evidence is needed before
any later interruption. If login/pinning fails, preserve both services/stages for
review rather than bypass verification or retry the listener start.

## Independent port-2225 login verified

Owner ran the separate interactive 2225 command with strict existing port-2224
host alias, authorized encrypted client key and `HISTFILE=/dev/null`, and returned
`sh-3.2#`. This establishes an authenticated independent management path while the
current OS/network remain running. It is **not failed-boot recovery** and does not
authorize stopping 2224 or changing root mounts. Retain this shell for subsequent
review; historical PIDs are never reused as action targets.

Next read-only refresh: `device/handover-identity-preflight.sh`, streamed from
another PC terminal over pinned 2225 while retaining the interactive shell. The
reviewed helper associates fixed PID records with exact pinned running binaries,
start identities and unique IPv4 listening sockets; classifies writable root
descriptors using whitelisted categories; hashes selected vendor restart inputs
as data only. No key/log contents, signals, service execution or mounts are used.
Any mismatch, unclassified holder or unavailable restart input needs review.

```sh
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
    -o HostKeyAlias='[192.0.2.10]:2224' \
    root@192.0.2.10 'sh -s' \
    < device/handover-identity-preflight.sh
```

This command goes in the PC terminal, **not** at `sh-3.2#`. Keep both listeners
and the retained independent shell running. No remount/capture/restoration trial
follows automatically, even if all metadata matches.

## Returned refreshed handover identity checkpoint

Owner-returned inventory through strictly pinned port 2225 confirmed:

- Old listener PID 3634/start ticks 3204 owns 2224; zero direct children at scan,
  matched executable, two writable known boot-log fds, no other root fds.
- Replacement listener PID 7461/start ticks 2003225 owns 2225; one direct child at
  scan, matched executable, zero writable root fds.
- Vendor writer PID 3437/start ticks 2953; matched executable, zero direct children,
  one writable root fd classified as the known settings database.
- All incomplete and unclassified descriptor counts were zero. Service,
  nimbus/develop configuration and platform-functions restart hashes matched.

The limited identity/holder-classification checkpoint passed. Counts describe the
instant of observation only. In particular, one replacement child does not prove
the earlier retained interactive shell is still alive; confirm responsiveness in
that PC terminal before relying on it. Never reuse these PIDs as signal targets.
No interruption, mount change or consistent capture occurred.

Next metadata check is `device/root-remount-preflight.sh` over pinned 2225. It
reads reviewed root mount options, root/USB/power state, utility hashes, mtab path
metadata and tmpfs free space. It does not invoke mount, source services or access
raw partitions. Existing restoration-trial success is not consistent-capture
evidence: the capture worker/completion/restoration protocol still needs offline
implementation, tests, exact review and separate live approval.

## Returned root-remount dependency refresh

Owner-returned pinned port-2225 check passed:

- Matched root identity; source `/dev/root` with exact
  `rw,relatime,errors=continue,barrier=0,data=writeback` options.
- External power detected, USB inactive, root/tmp writable.
- Reviewed regular mount and BusyBox hashes matched; mtab recognized proc symlink.
- `/tmp`: 4096 KiB total, 120 KiB used, **3976 KiB available** at this observation.

No remount, service signal or raw partition access occurred. Retained interactive
shell responsiveness has not been returned by the owner and remains a live-action
prerequisite. A 256 MiB capture cannot be staged in 4 MiB tmpfs. The next work is
offline receiver/lifecycle preparation, documented in
`ROOT-CAPTURE-PROTOCOL.md`; no capture execution command is supplied.

## Fresh independent shell confirmed after dependency refresh

Owner opened a fresh interactive TCP-2225 session with strict verification against
the existing 2224 HostKeyAlias, authorized encrypted client key and remote
`HISTFILE=/dev/null`, returning `sh-3.2#`. This refreshes authenticated interactive
fallback availability; it does not establish whether the older shell remained
connected. Keep this newly confirmed session open and idle while offline capture
worker work proceeds. Recheck responsiveness and current identities immediately
before any separately approved interruption. No remount, capture or flash has
been approved or executed by this login.

## Offline native stream preparation checkpoint

The C stream component, host synthetic integration and inactive ARM artifact are
now prepared; see `ROOT-CAPTURE-PROTOCOL.md`. Thirty-six capture-related tests
passed; compatible full regression: 303 run, 299 passed, 4 skipped. Native
coordinator/transport and live capture remain pending. The 0600 component under
`build/nimbus-root-capture-stream-v1/` is not installed on the drive or in beta4.
No further hardware action was performed or approved by the offline build.

### Offline coordinator follow-up

A separate hash-pinned coordinator preparation and fourteen synthetic tests now
exercise the compiled reader, real host receiver and simulated service/remount
restoration together. Current inactive output:
`build/nimbus-root-capture-coordinator-v2/` (earlier v1 retained, superseded).
Cancellation, abnormal helper death, lost fallback and private-record failures
are explicitly tested. No live script, reader, remount or service action ran.
Full-duplex SSH ownership/disconnect recovery and native descendant shutdown remain
blockers; this is not approval or readiness for a root capture or firmware flash.
Follow-up regression: 317 run, 313 passed, 4 existing skips; 50 capture-related
tests passed. Log: `/tmp/opencode/nimbus-coordinator-review-t1ucfkfs/regression.log`.

### Offline transport follow-up

Pinned SSH command planning and selector-based existing-process IO are now tested
locally. Valid protocol trailers followed by nonzero process exit cannot commit a
receipt; stderr is privately bounded/synced and ACK control stays separate from
script staging. Host receipt publication now retains a synced partial before
exclusive publication. These are offline prototypes, not a live launcher.
Disconnect-independent device recovery, remote-descendant observation and native
qualification remain blocked. No SSH/device action occurred during this work.
Validation: 63 capture-related tests passed; full regression 330 run, 326 passed,
4 existing skips. Log: `/tmp/opencode/nimbus-transport-review-pzjc48lo/regression.log`.

### Owner-returned read-only liveness checkpoint

Owner authenticated through strictly pinned 2225 using the existing 2224 host
alias. Returned uid/gid 0, `/dev/root` ext3 with exact original
`rw,relatime,errors=continue,barrier=0,data=writeback` options, charger online `1`,
and no `g_file_storage` output. The additional `rootfs / rootfs rw` line is the
kernel rootfs view, not a second ext3 capture target. No state-changing command
was requested or reported. This limited check does not refresh process/writer
identities, prove USB-export state comprehensively, or authorize interruptions,
remounts or raw capture; the final grep command masks errors with `|| :`.

### Offline disconnect-owner follow-up

The C relay owner survives synthetic SSH-waiter death in a detached session and
invalidates/drains on channel loss. Twelve host-only guardian tests include actual
compiled streaming and checked simulated restoration, with cancellation during
cleanup. Coordinator cleanup now resists signal interruption without leaking
ignored TERM into restarted services; current inactive output is v3, with older
v1/v2 retained. Default guardian builds refuse execution, and native staging,
identity/descendant integration and hardware qualification are still pending.
No guardian or updated coordinator was built into beta4 or run on the drive.
Validation: 76 capture-related tests passed; full regression 343 run, 339 passed,
4 existing skips. Log: `/tmp/opencode/nimbus-guardian-review-avke0pof/regression.log`.

### Explicit owned-child drain follow-up

Updated reader reports token-matched raw-reader closure/direct-hasher reap through
a separate private descriptor; coordinator requires that report before rw recovery
after any started capture. Missing evidence blocks restoration even with valid
ACK/normal process exit. Guardian fixture rejects unexpected inherited fds and
records irreversible invalidation separately. Current inactive artifacts are
stream-v2 and coordinator-v4; earlier builds retained, superseded. No guardian
native action entry has been enabled. Full descendant behavior, native launch,
resource/syscall behavior and physical recovery remain unqualified. No device
action or firmware-image change occurred during this follow-up.
Validation: 82 capture-related tests passed; full regression 349 run, 345 passed,
4 existing skips. Log: `/tmp/opencode/nimbus-child-drain-review-6aoyy45g/regression.log`.

### Pinned guardian entry and requested live-testing track

Owner requested both integration and eventual live testing. A pinned native ARM
guardian candidate is now preserved under `build/nimbus-root-capture-guardian-v2/`,
with worker-v4/stream-v2 input hashes compiled in. Default unpinned builds remain
disabled. Synthetic pin/check-only/restoration tests and ARM refusal entry passed;
no native invocation or deployment occurred. The candidate is not beta4 firmware
or a live launcher. Next owner check is kernel/RAM/tmpfs metadata only; exclusive
temporary staging/native probing and service stops/ro-rw/raw capture still require
separate exact review/approval. The current request does not bypass those gates.
Validation: 89 capture-related tests passed; full regression 356 run, 352 passed,
4 existing skips. Log: `/tmp/opencode/nimbus-pinned-guardian-review-5d33ykwr/regression.log`.

### Owner metadata and inert probe preparation

Returned kernel 2.6.35.3-899-g9b1a262, 125496 KiB RAM total/23544 KiB free,
151712 KiB swap total/free, exact writable 4096 KiB tmpfs with 3976 KiB available.
This is a snapshot, not a reservation or memory-pressure qualification. No swap
change or remount is proposed. Prepared a standalone 33812-byte inert ARM probe
under `build/nimbus-root-capture-native-probe-v1/`; host/emulated runs pass.
`ROOT-CAPTURE-NATIVE-PROBE.md` gives exact owner-review scope/command. Device
staging/execution is not yet approved or performed; no capture worker is included.
Targeted validation: 93 capture/probe tests passed. Full regression timed out in
an existing UI-performance fixture; not a full-suite pass. Logs are preserved
in `ROOT-CAPTURE-NATIVE-PROBE.md`. No native run or device upload occurred.

Owner subsequently explicitly approved the one-time inert-probe upload/run in
`/tmp/nimbus-native-probe-v1` with retained files/log on 2026-10-13. Local payload
hash reconfirmed. Command provided for owner execution; native results pending.
Approval excludes service changes, remounts, raw reads and flashing.

Owner's attempted approved probe upload returned TCP-2225 `Connection refused`
before SSH authentication/remote command execution. No upload/probe execution
occurred in that attempt. Temporary fallback responsiveness is no longer proven;
all former PID/listener observations are stale. Next proposed action is existing
pinned 2224 metadata-only liveness, not a listener restart/reboot/probe retry.

Owner-returned pinned 2224 liveness passed: uid/gid 0, uptime 14 minutes, exact
original writable ext3 root options. The short uptime is consistent with a recent
boot clearing temporary listeners/stages, but the refusal's cause is not proven.
Normal management remains reachable; no probe has run. Next proposed command is
the reviewed capture-listener helper in `--check` mode through existing 2224.
Any new 2225 listener start still requires separate explicit approval.

Owner ran the reviewed `capture-listener.sh --check` through pinned 2224 after
the refusal and returned prerequisite PASS plus explicit no-change output.
Existing keys, pinned binary, wlan1, writable tmpfs and absence of prior temporary
stage/occupied 2225 were observed by that limited check. No listener was started.
Proposed next action is a separately approved temporary wlan1/key-only 2225 start,
with existing identity/authorization and private tmpfs PID/log files, leaving
2224, startup hooks, vendor services and mounts unchanged. Independent pinned
2225 authentication remains required before retrying the approved inert probe.

Owner explicitly approved the new listener-only start and returned the reviewed
helper's prerequisite PASS, temporary key-only wlan1 2225 process/listening
observation, and unchanged 2224/hooks/keys/vendor/mount message. Private tmpfs
stage retained. This re-establishes an observed listener only; fresh independent
strictly pinned 2225 authentication has not yet been returned. No probe upload,
service interruption or mount transition was reported.

Owner returned fresh strictly pinned 2225 authentication: uid/gid 0 and uptime
54 minutes. Temporary management is authenticated again. Local inert-probe hash
reconfirmed. Returning to the previously approved one-time probe upload/run is
permitted; earlier refused SSH attempt executed no remote command. Exclusive
mkdir/size/hash checks still apply and must refuse any unexpected existing stage.
Native probe result is pending; no service interruption/remount/raw read approval.

Owner subsequently returned native inert-probe checksum OK and PASS for monotonic
time, self-FD enumeration, broken-pipe poll, detached child session, owned-child
signal/select and reaping, ending `PROBE=PASS native_capture_qualified=no`.
Approved tmpfs stage/logs remain retained. This qualifies those reported probe
operations only; no guardian disconnect test, service interruption, remount or
raw capture occurred. SSH exit status was not separately returned. Next preparation
is a strictly synthetic native guardian/disconnect trial without the real capture
worker, with separate staging/execution approval before hardware action.

### Synthetic guardian trial preparation

Prepared a separately pinned 34188-byte synthetic bundle with the unchanged
guardian relay and built-in-only fake worker, not the real reader/coordinator.
Exact scope/commands are in `ROOT-CAPTURE-SYNTHETIC-TRIAL.md`. Host tests exercise
positive control, output loss and SSH-side waiter death with retained synthetic
cleanup; bundle allowlist/hashes/boundaries are checked. No native upload/run or
client interruption occurred. Separate approval is still required for the
temporary stage, one synthetic worker start, loss of only its SSH client and
metadata-only inspection. Previous probe/listener stages remain untouched.
Validation: 99 targeted tests passed; log
`/tmp/opencode/nimbus-synthetic-trial-review-vnh1g3lz/capture.log`.
Full regression not rerun; previously recorded UI-performance timeout remains.

Owner explicitly approved the proposed synthetic-only stage/check, one fake-worker
start, interruption of only its test SSH client and separate pinned evidence
inspection, with logs retained. Local bundle hash reconfirmed. Device stage/check
results pending; no trial execution or interruption yet reported. Approval excludes
real capture workers, service changes, remounts, raw reads and flashing.

Owner returned native synthetic bundle hash OK, deterministic epoch-timestamp tar
warnings, guardian hash OK and final `SYNTHETIC-STAGE-CHECK=PASS no-worker-started`.
The warnings did not block extraction/check-only; no worker launched. Stage is
retained. Proceed only with the already approved one-shot fake-worker start and
loss of its test SSH client; native disconnect/cleanup results remain pending.

Owner returned the native fake worker's exact session-matched SYNTHETIC-READY
marker with `no-real-reader`. One-shot start is observed. Ctrl+C interruption is
not explicitly reported yet; guardian invalidation/worker cleanup evidence and
post-trial mount metadata remain pending. No restart/retry or real capture follows.

Owner's separate pinned 2225 inspection returned session-matched GUARDIAN-INVALID,
GUARDIAN-RESULT `invalidated=yes worker_exited=yes worker_status=256
restoration_certified=no`, and synthetic result `completed=no
real_reader_started=no`. Root ext3 remains rw with original exact options. Limited
native synthetic invalidation/cleanup checkpoint passed; raw wait status 256 is
the expected shell exit 1. Exact interruption cause/timing was not recorded in
the artifacts, and no real reader/hasher descendants or ro epoch were tested.
Retain stages/logs; next offline preparation is a regular-file-only native
reader/hasher pipeline trial, not permission for raw root reads or service stops.

### Regular-file reader/hasher positive-trial preparation

Prepared a separate pinned guardian + fixture-only ARM streamer bundle (78625
bytes) with 262144 synthetic regular-file bytes and fake ro/geometry metadata.
The worker uses a precomputed synthetic ACK, keeps the fake wire in private tmpfs
and requires exact drain evidence/direct helper success; no real remount/service
worker included. Scope/commands in `ROOT-CAPTURE-REGULAR-TRIAL.md` require new
approval before staging or execution. No native upload/run occurred. Existing
synthetic disconnect/probe stages remain untouched. This is a positive native
compatibility test, not host durable ACK or disconnect-under-reader-load proof.
Validation: 104 targeted tests passed; log
`/tmp/opencode/nimbus-regular-trial-review-f82zfe_6/capture.log`.
Full regression not rerun; prior unrelated UI-performance timeout still recorded.

Owner subsequently explicitly approved the exact 78625-byte regular-trial bundle
stage/check, one positive run against 262144 fake regular-file bytes and retained
wire/drain/result logs. Local bundle hash reconfirmed. Staging command uses
individual fail-fast directory/df/free-space tests; native stage/check output and
reader/hasher results pending. No real block read/service stop/remount/flash approval.

Owner returned the regular-trial stage bundle/guardian/inventory hashes OK and
`REGULAR-STAGE-CHECK=PASS no-worker-started`, after nonfatal deterministic epoch
tar warnings. Staging/free-space guards completed; no reader ran. Next approved
action is one positive synthetic regular-file run allowed to finish normally,
not the previous test's deliberate Ctrl+C/disconnect.

Owner attempted the approved one-shot regular-file run and reported silent return
to the local prompt. No PASS/exit status returned; result unknown, not successful.
Retain stage and inspect private records/logs read-only; no retry, repair, cleanup
or further execution is authorized by this observation.

Owner returned failed regular-trial evidence: `sha256sum: applet not found`,
helper_status 1, session-matched guardian invalidation/direct-worker exit 256,
and exact reader-closed/hasher-drained report. Fake wire is partial (131171 bytes),
not successful data. Root rw options unchanged; pinned 2225 remains responsive.
Known failure is the wrapper's unsupported `/bin/busybox sha256sum` invocation;
normal PATH sha256sum used for staging did work. Next is read-only executable
resolution/metadata/hash, then a new offline pinned candidate if reviewed. No
retry or failed-stage mutation; production stream-v2's same BusyBox assumption
is now explicitly blocked for native capture. No remount/block read occurred.

Owner returned functioning hasher resolution: `/usr/bin/sha256sum`, standalone
non-symlink regular file, 116878 bytes, root:root 0755, SHA-256
`c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2`.
Prepared corrected regular-trial-v2 with new stage/session/pins and explicit
hash+metadata preflight. Failed v1 untouched. Also preserved corrected inactive
stream-v3/coordinator-v5/guardian-v3 candidates; none deployed or run. The
production correction does not qualify real capture or supersede its approval
gates. New positive regular v2 trial requires separate exact approval; scope is
in `ROOT-CAPTURE-REGULAR-TRIAL-V2.md`.
Validation: 106 targeted tests passed; log
`/tmp/opencode/nimbus-standalone-hasher-review-5rdbped6/capture.log`.
Full regression not rerun; prior unrelated timeout remains documented.

Owner confirmed corrected regular-trial-v2 scope: new 78657-byte private stage,
verification/check, one 262144-byte fake-file positive run, retained logs/output.
Bundle hash reconfirmed. Native stage/check results pending; failed v1 remains
untouched. No real block read, service stop, remount or flash authorization.

Owner returned corrected regular-v2 native staging: bundle/guardian/inventory
hashes all OK, final `REGULAR-V2-STAGE-CHECK=PASS no-worker-started`, nonfatal
deterministic epoch tar warnings. No reader executed yet. Next approved action
is one positive v2 run, allowed to finish without ACK input or Ctrl+C.

Owner returned the v2 positive native marker `REGULAR-TRIAL=PASS reader-closed
hasher-drained synthetic-only native_capture_qualified=no`. Reader/hasher worker
reports success with corrected standalone hash executable. Independent records,
complete predicted fake-wire size/hash and root mount follow-up are pending;
no rerun/real capture approval follows from this marker.

Owner returned corrected v2's session-matched child drain, helper_status 0 and
guardian non-invalidated/direct-worker exit 0. Complete fake wire exactly matches
262389 bytes and predicted SHA-256. Synthetic pipeline checks pass. But the pasted
root follow-up shows only rootfs, with no expected ext3 `/dev/root /` line; real
root state is NOT reconfirmed. Hold further device actions and request complete
mount/mountinfo/uptime/module metadata read-only. No assumption that the trial
changed mounts, that copy/paste omitted a line, or that remount/reboot is needed.

Owner's complete pinned 2225 follow-up reconfirmed uptime 2h45, root ext3 original
exact rw options and matching mountinfo 179:2 VFS/superblock rw. Readable module
list has no g_file_storage; internal storage mounts rw and SD mounts ro. Current
root concern is cleared by fresh observation, not by repair/remount or an assumed
cause for the previous missing line. The limited synthetic positive pipeline
checkpoint now passes. Host durable ACK, reader-load cancellation/full descendants,
continuous real ro and physical recovery remain unqualified; retain all evidence.
