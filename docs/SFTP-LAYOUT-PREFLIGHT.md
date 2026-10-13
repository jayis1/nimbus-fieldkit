# SFTP layout collection and proposed version/probe trial

Latest: the owner-approved native **version/own-process probe trial passed**.
Earlier prepared/not-staged/power-blocked entries below are historical. Native
SFTP authentication, privilege separation, jail and USB handoff remain pending;
no listener was started. See the completed checkpoint at the end.

## Read-only collector implemented

`device/ssh/sftp-layout-preflight.sh --check` observes only fixed paths. It emits
a bounded, tagged frame that `scripts/parse-sftp-layout.py` strictly parses.
No private key contents, shadow files, unselected account names, GECOS, media
filenames or arbitrary executable/configuration commands are emitted or run.

Evidence includes before/after node types/ownership/modes/link counts/identities,
classified dedicated-account UID/GID collisions/groups, selected mount IDs and
VFS/superblock flags, SD block identity and root-only empty-directory checks.
The **public** authorization file is hashed only at the fixed expected safe path;
the host private key is only statted, never read or hashed. Mounted SD contents
are not enumerated to test placeholder emptiness. Active/unknown USB state skips
jail media-view metadata. Kernel `/proc/self` is an allowed procfs symlink;
symlink components in jail/auth paths are refused.

The collector hashes public account tables and module/mount inventories before
and after collection to detect sampled changes. This is not an atomic snapshot
or exclusive-ownership lock. Only a fresh pinned transport with checked exit and
complete frame can supply evidence for a subsequent separately approved action.
The assembler cannot override collected ownership, metadata or accounts with
caller context. Observed public-auth SHA-256 must match exactly one restricted
dedicated client enrollment; a same-sized different file is not accepted.

Host validation now accepts root-owned `/root` 0700 **or 0755**, as neither is
group/other writable. The candidate stage remains 0700, private host key 0600,
jail root 0755 and public auth hierarchy 0755/0644. No existing directory is
chmodded by the collector or validator.

## Native read-only result — 2026-10-13

Through strictly pinned management TCP 2224, the streamed collector returned exit
0 and a complete stable frame. Private host evidence:
`/tmp/opencode/sftp-layout-native-lonne7vu/layout.txt` and `stderr.txt`.

- USB export was **inactive**, unlike the earlier active-export observation.
  No module or USB mode was changed by this check.
- Internal source was `/dev/mmcblk0p4`, `179:4`, texfat rw.
- SD source was `/dev/mmcblk1p1`, `179:9`, texfat ro. Capacity does not determine
  SD minor numbering; the collector corroborated it with sysfs.
- SFTP stage/jail/privsep/auth hierarchy, host key and authorized file were absent.
  Neither dedicated account nor either jail view was present.
- Existing `/root` is root-owned 0755. It was not changed.

This is usable **absence/metadata evidence**, not a successful SFTP setup, account
authentication, source write test, bind view or USB handoff qualification. It
does not authorize creating a layout simply to satisfy the validator.

## Prepared exact probe-only package — NOT STAGED / NOT EXECUTED

`build/nimbus-sftp-probe-r1.tar.gz`, 400350 compressed bytes, SHA-256:
`cc2fac05b73996519bddcb527788e93ca8fb2b7532ca8cb5e67fff1f474694f3`

Builder: `scripts/package-sftp-probe-trial.py`.
Guarded device script: `device/ssh/sftp-runtime-probe-trial.sh`.

Only three hash-pinned ARM files (795048 bytes total) plus the script, manifest
and checksums are packaged. No `sshd-session`, `sshd-auth`, ssh-keygen, keys,
accounts, jail, bind helper, startup hook or service configuration is included.

Proposed separately approved device scope:

1. Create fresh root-owned 0700 `/tmp/nimbus-sftp-probe-r1`, extract reviewed
   mode-0600 payload into tmpfs, verify metadata/hashes and run `--check` without
   executing any candidate. Do not reuse/repair an existing stage.
2. If freshly powered and USB-inactive, create a retained private `CLAIM`, chmod
   only the three pinned files to 0700 and invoke exactly:
   - `sshd -V` (version only, never a server start);
   - `rlimit-compat-probe`, no arguments;
   - `rlimit-select-compat-probe`, no arguments.
3. Stream output to private PC evidence. The resource-limit probes open only
   `/dev/null` and limit their own process; parent SSH/shell limits are unchanged.
   Probe output uses pipes, not regular on-device logs: their FSIZE=0 limit is
   intentional. No listener, account/key, mount, USB/radio setting, service
   interruption, raw reader or firmware action is allowed.
4. Retain the used stage and evidence; failures are single-use, not repaired or
   rerun. A host timeout cannot guarantee termination of a stuck kernel call.
   Passing this trial would qualify only these process-compatibility observations,
   not pre/post-auth privilege separation, SFTP confinement or a full service.

## Fresh prerequisite blocker

A read-only check immediately after packaging reported ARMv7, root `179:2`,
3808 KiB available on the 4096 KiB tmpfs and no proposed stage. However,
`/sys/class/power_supply/mc13892_charger/online` returned **0**. No staging or
candidate execution followed. Battery percentage is not a substitute for this
trial's selected external-power prerequisite. Do not silently relax the guard,
recreate a listener or change USB mode to get a PASS.

Owner must arrange normal stable external power; recheck fresh USB state because
connecting a data cable may change ownership. Obtain exact approval for the
scope above before creating the stage or executing candidates. Existing pinned
Dropbear TCP 2224 stays untouched; port 2225 is not assumed available.

The owner then explicitly selected **Approve after power check** for exactly the
scope above. The subsequent pinned read-only power recheck still returned 0 and
exited 2 with `SFTP-PROBE-PREREQUISITE=REFUSED-external-power-not-detected`, before
the other prerequisites or staging. Approval is recorded; power remains the
blocker. No stage was created, file chmodded or ARM candidate executed. Fresh
power/USB/space checks remain mandatory after the owner arranges external power.

After the owner reported power connected, fresh pinned checks returned charger
online=1 but found `g_file_storage` loaded again. The proposed stage remained
absent and tmpfs had 3808 KiB available. The USB-inactive gate refused; no staging
or candidate execution followed. Loaded export does not itself prove physical
host attachment. A normal reviewed ownership transition is needed while keeping
power available; no module unload or USB setting was performed automatically.

## Validation

**78 SFTP tests passed, no skips**: effective-policy/config guards, ARM metadata,
confinement/enrollment/lifecycle, 16 collector/parser tests and eight trial
package/guard tests. `git diff --check` passed. Package construction executes no
ARM binaries. Trial shell tests use deliberately substituted host fixtures and
do not count as native execution. Full workspace regression was not rerun.

The owner reported bidding on a 32 GB Media Drive. That unit has not been
received or qualified and does not block current 64 GB work or imply cross-model
compatibility. No capacity target or new feature was added from that report.

## Completed native process probe — 2026-10-13

After the owner confirmed charging-only power, fresh pinned checks returned
charger online=1, no observed USB gadget module and absent proposed stage.
The approved archive hash was verified on the PC before creating the fresh
0700 tmpfs stage. Native `--check` returned
`SFTP-PROBE-CHECK=PASS no-runtime-executed`.

One `--run` attempt then returned SSH exit 0 and exactly:

```text
VERSION OpenSSH_10.6p1, without OpenSSL
RAW {"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":false,"scope":"process_compatibility_only"}
FALLBACK {"schema":"nimbus-rlimit-probe/v1","select_with_nofile_zero":true,"pselect_with_nofile_zero":true,"poll_with_nofile_zero":true,"scope":"process_compatibility_only"}
SFTP-PROBE-RESULT=PASS process-compatibility-only service_qualified=no flash_authorized=no
```

Host framing/JSON/result checks passed. Raw libc poll fails with NOFILE=0 as
anticipated; the selected upstream fallback passes on this kernel. This does not
test a pre-auth sshd child, full authentication/crypto, simultaneous sessions,
FD_SETSIZE load, confinement, media teardown or USB transition.

Retained PC evidence:
`/tmp/opencode/sftp-probe-native-kdmcebm_/check.stdout`, `check.stderr`,
`run.stdout`, `run.stderr`, and `RECEIPT.json` (private, synced locally).
The original package/export and earlier failed prerequisite evidence are not
modified. Immutable export flags remain false; the new receipt records only
the exact native probe scope.

Read-only follow-up confirmed new pinned management login, charger online=1,
root still rw, internal texfat rw and SD texfat ro, no observed USB gadget module,
zero IPv4 listening rows on 2226, vendor homepage HTTP 200, and battery level100 /
statuscharge. The three staged binaries are root-owned 0700 regular single-link
files with their expected sizes; CLAIM remains `ATTEMPTED`. Tmpfs has 3000 KiB
available. No service, account/key, media mount, USB/radio setting or firmware
write was changed by the trial. Standard existing SSH/vendor logging is separate
from the trial's new tmpfs files.

**Do not rerun `--run`, repair or delete this used stage.** Keep it as evidence;
tmpfs itself is volatile, while the private PC record persists. Next qualification
needs separately reviewed account/host identity provisioning, actual SFTP
authentication/confinement and bounded service/USB lifecycle integration. This
trial's approval authorizes none of those actions.
