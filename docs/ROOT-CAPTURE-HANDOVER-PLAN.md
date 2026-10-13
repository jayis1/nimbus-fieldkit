# Root capture and management handover: review checkpoint

## Authorization and evidence

Latest result: the user separately approved and executed the root-restoration
trial; it returned PASS after observed non-forced ro, immediate original-option
rw restoration and service restart, retaining temporary management. See
[the native evidence](ROOT-RESTORATION-TRIAL-REVIEW.md). Fresh post-trial pinned
authentication and basic service checks are pending. Earlier no-remount/pending
statements in this chronological review are superseded by this limited result;
no consistent capture, image write, reboot or forced operation has occurred.

The user initially asked to continue **reviewing** this plan after the supervised [vendor pause/restart trial](NIMBUS-PAUSE-RESTART-TRIAL.md) and basic browser/media/storage checks passed, then separately approved the management-only stop/restore trial. That limited approval does not authorize another vendor interruption, root remount, capture, reboot or image write. The [management-only worker/package](SSH-HANDOVER-TRIAL.md) v1 failed before worker launch; corrected v2 subsequently passed native observation, fresh pinned authentication and basic browser/storage follow-up. No remount worker is supplied at this checkpoint. Preparation has advanced to [the root-restoration utility/failure-path review](ROOT-RESTORATION-TRIAL-REVIEW.md) and a read-only native dependency helper; execution approval is still separate.

Nimbus restart has native process/socket evidence and user-reported basic service restoration. It does not prove SQLite transaction integrity, recovery after a stalled kernel operation or recovery after a failed boot. The [kernel review](CONSISTENT-CAPTURE-REVIEW.md) still rules out timed freeze/thaw as guaranteed recovery and identifies potentially blocking remount/restoration paths.

## Newly reviewed management restoration dependency

`device/ssh/install-startup.sh` appends a start-only rc.local hook launching `/root/nimbus-ssh-test/startup-v1/start-ssh.sh` with stdout/stderr appended to the private rootfs boot log. The hook is not a supervisor; rerunning rc.local would also invoke unrelated vendor behavior and is not an acceptable targeted restart.

The first-party launcher (`device/ssh/start-ssh.sh`, SHA-256 `173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41`) execs the pinned key-only, wlan1-bound Dropbear on port 2224 with the existing keys and `/root/nimbus-ssh-test/boot.pid`. It has a radio-presence wait and no arbitrary stop action. Its installed copy must be hash-matched before planning to execute it. It must not be sourced into the worker. A start request must be detached, preserve private logging, and be made only after fresh socket/process checks exclude an existing old listener.

Returning to the normal listener can recreate both writable boot-log descriptors and update its rootfs PID file. Therefore request restoration of the normal port-2224 service **only after root is verified rw again**. Do not overwrite that PID file by hand, remove the log, close descriptors externally or launch two normal listeners. If root remains ro, keep temporary port 2225 and review; do not blindly request the stock launcher, whose PID-file creation/cleanup can fail. No permanent boot-hook change is proposed.

The temporary port-2225 listener already uses private tmpfs PID/log output and the same pinned keys. Its native authentication passed, but this is not independent recovery hardware: it uses the same kernel, Wi-Fi, power and storage for binary/key reads. Keep it running throughout any separately approved experiment. Do not run from a port-2224 session when considering its termination. Idle-timeout closure of a session is different from listener failure; verify a fresh independent port-2225 session immediately before an action.

## Draft state machine (not commands to execute)

1. **Inventory only:** fresh full root-writer scan through pinned port 2225, both listener identities and socket ownership, root options/device identity, inactive USB export, external power, tmpfs free space and private-stage sizes; hash installed first-party restart launcher and pinned binary. Any unknown holder, incomplete scan, changed input or unavailable management dependency blocks preparation.
2. **Prepare and fixture-test:** a distinct source-only private tmpfs worker/stage, default check-only, explicit start, no reuse/overwrite. Preserve exact root mount options and record state transitions privately. Test failures at every transition, restoration refusal, transport loss, autonomous respawn, old-listener children, changed identity and interrupted capture. No native trial claims from fixtures.
3. **Separate explicit approval:** disclose temporary loss of port 2224 and Nimbus API, normal metadata/journal flush writes involved in a non-forced ro remount, unbounded kernel IO risk and lack of guaranteed boot recovery. Define the action as a restoration trial first, without capture, so an untested ro/rw path is not combined with a long transfer.
4. **Guarded management handover:** only a freshly identity/start/socket-checked old listener with no children may receive one TERM. Source-level parent signal/exit and PID-file cleanup review is recorded below; native stop/restoration remains untested. Observe original identity gone, old port unoccupied and all inherited root-log holders gone; do not force, kill by name, retry or kill sessions to satisfy a guard. Temporary management must remain independently accessible.
5. **Guarded vendor pause:** use the proven reviewed one-TERM/one-start semantics with fresh identity, not historical PIDs. Stop only that known writer. New/unknown writers or autonomous respawn aborts the trial and leads to restoration, not more termination.
6. **Non-forced ro/rw trial:** fresh all-process writer inventory before requesting a single non-forced root ro transition. No freeze, repair, force, watchdog access or raw writes. If remount refuses, restore only services that this worker actually stopped, after verifying root state. If ro succeeds, observe exact expected root/options, then request rw restoration preserving reviewed options. Restoration can refuse or hang: no retry loop, reboot fallback or claim of a guaranteed deadline.
7. **Restore services once:** after verified root rw, request vendor restoration and normal management restoration individually, at most once each, without duplicates. Verify expected executable identities/listeners; fresh pinned authentication on both ports and browser/settings/storage checks follow. Retain all evidence and the temporary listener until separately approved cleanup.
8. **Capture only after separate review/approval:** successful restoration trial informs a later consistent-capture procedure; it does not authorize repeating interruptions. The device has only 4MiB tmpfs and cannot stage the 256MiB image. Use a new private host destination, exact expected partition size, remote raw **read only**, and a separately reviewed transport/completion handshake. A guard returning root to rw during transfer invalidates the capture. Polling observations alone cannot prove uninterrupted ro state; the capture lifecycle and restoration ordering must enforce it, or the output remains unqualified. Never delay restoration forever waiting for a lost client.

## Qualification and preserved data

Keep all original backups and the failed journal-reviewed derivative unchanged. Use a unique private capture directory and restrictive permissions; never upload captures, keys, vendor artifacts or private candidates to GitHub. Record size, hashes, mount-state provenance, transport exit status and worker result. Host filesystem checks must be non-modifying against a completed private capture; any repair investigation needs a separately named copy. Matching hashes or clean read-only fsck do not establish an available physical restore route or flash readiness.

## Returned preflight evidence and local Dropbear review

Latest evidence: corrected v2 management-only worker returned PASS after one
old-listener TERM and one reviewed normal-listener restart, with root still rw,
old log holders absent during the observed gap, and Nimbus/port-2225 identities
retained. See [native trial evidence](SSH-HANDOVER-TRIAL.md). Fresh pinned login
to the restored port 2224 and basic post-trial service checks are still pending.
Earlier statements about no listener termination or pending v2 execution are
historical checkpoints; no root remount/capture or image write has occurred.

Subsequently, fresh pinned authentication to the restored port 2224 passed and
the user confirmed dashboard/Settings working with both internal and SD files
visible. The basic management-only trial follow-up is complete. The next design
gate is a separately reviewed non-forced root ro/rw restoration trial, without
capture; no command or execution approval for that mount change exists yet.

The subsequent native remount-dependency inventory matched the reviewed utility
hashes and exact root options, with proc-linked mtab and 3776KiB tmpfs available.
A restoration-only worker/source package and failure fixtures are now prepared
(198 tests run, 196 pass, 2 skips); see [its scope, package and risks](ROOT-RESTORATION-TRIAL-REVIEW.md).
Separate explicit root-mount-change approval is pending. No remount/capture or
image write has occurred.

The user supplied a refreshed global scan through port 2225: two root write holders, three writable descriptors total (Nimbus one, old listener two), zero shared writable root mappings, zero incomplete/raced observations reported. All four service-script hashes matched. The installed first-party restart launcher matched SHA-256 `173938b18030e9281b140a7057c664438cc1887f779a09b35cf80ac37ee15d41`. Device tmpfs was 4096KiB total, 184KiB used and 3912KiB available; charger `online=1`. The earlier PC `/tmp`/permission errors are not device evidence and were superseded by these drive-shell results. Values are checkpoint observations, not future readiness guarantees.

Local preserved build tree: `/tmp/opencode/nimbus-ssh-review/dropbear-2026.94/`. Its `dropbearmulti` hash exactly matches the installed pinned binary (`1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c`). Build-tree/source proximity and retained build logs support review relevance, but are not an independently reproducible source-to-binary attestation.

| Reviewed local file | SHA-256 |
| --- | --- |
| `src/svr-main.c` | `f671045310a57673df2d62a4bf8f098cd171fc6f0baed28634cab5ecaec25400` |
| `src/svr-session.c` | `b3fa60969d31fecbda89f7b30958e81b47e02bd06bc87aa53e429c0652b04554` |
| `config.h` | `d5a59a408e7b00eea8a74c9936e82d5aa20e69d166d3baf16dfeb3ccd542ab23` |
| `localoptions.h` | `4562e80ab8e68149685eadd8d44a0f5e8f9bf4472005797e311b81ce7b87e5e8` |

Source findings:

- `svr-main.c:442–465`: SIGTERM normally sets `ses.exitflag`; the registration has a `DEBUG_VALGRIND` build conditional. This is a source finding, not a successful native handover.
- `svr-main.c:230–235`: the parent checks the flag after `select`, requests unlink of its configured PID file, then calls `dropbear_close`. There is no checked unlink return or elapsed-time guarantee. Do not assume deletion proves exit, or missing/deleted PID metadata proves socket release.
- `svr-main.c:205–210`: PID-file creation uses `fopen(...,"w")`; failure does **not** abort the listener. A listening socket without a fresh valid PID record is therefore not acceptable restoration success. Bind setup precedes PID-file creation. Revalidate PID-file identity, executable/start ticks and socket ownership together.
- `svr-session.c:220–314`: exit performs logging/session cleanup and calls `exit`; no blanket child-process kill appears in that function. Established sessions can independently retain inherited boot-log descriptors, so requiring no old-listener children and rescanning all holders remains necessary. A new connection can race the checks; refuse when observations differ rather than claim atomicity.
- `config.h` defines `DISABLE_SYSLOG 1`, consistent with the reviewed launcher's stderr/private-log handling. Avoid the unsupported `-E` option used by the earlier failed temporary launch.

The next experiment should be a **management-only stop/restore trial while root stays rw and Nimbus stays running**, before any combined vendor pause/remount trial. That isolates the currently untested restoration path: one freshly checked old-listener TERM, no forced escalation, one targeted detached first-party launcher request after observed exit/socket release, and fresh pinned port-2224 authentication after restoration. Keep port 2225 throughout. Its [worker/package/failure fixtures](SSH-HANDOVER-TRIAL.md) are prepared locally (174 tests run, 172 pass, 2 skips); separate explicit approval is required before execution. No mutation command is supplied here.

Subsequently the user supplied a fresh strict-pinned port-2224 `id` result: `uid=0(root) gid=0(root)`. The one-shot connection returned to the PC prompt. Both management paths have now authenticated at this checkpoint, but action-time identities, no-children state, power and writer checks must be refreshed before an experiment.

The user explicitly approved the management-only trial. Its v1 invocation passed inventory but failed to launch the detached worker because the sourced identity helper overwrote a generic stage variable. No TERM/restart is shown. See [v1 failure and v2 correction](SSH-HANDOVER-TRIAL.md). v1 evidence is retained; a readonly, distinct trial-stage variable and real-inventory integration regression are now tested (176 run, 174 pass, 2 skips). Fresh native read-only identity verification is requested before supplying a v2 retry. No old-listener termination/remount/capture result has yet been returned.
