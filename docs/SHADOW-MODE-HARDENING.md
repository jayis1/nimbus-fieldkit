# Shadow permission-only hardening — native checkpoint

**Current `/etc/shadow` and `/etc/shadow-` modes are verified 0600. Password/account
table bytes were not changed.** This closes the observed world-readable-mode defects at this
checkpoint, not vendor reset/reboot persistence, account writer coordination or
the remaining SFTP/firmware gates.

Changing mode does not revoke previously opened descriptors, erase prior copies
of hashes or prove they were never accessed. No password rotation or process
termination is performed automatically; historic exposure/legacy-service review
remains separate from current file-mode verification.

## Source and build

`device/ssh/shadow-mode-hardening.c` is first-party, fixed-path and permission-only.
It accepts only `--check`/`--harden`, plus a bounded private stdin identity/digest
pin. It checks root-owned non-writable directory ancestry, the exact regular
single-link inode/size, owner/group and hash. No private values are printed or
placed in argv. It opens with no-follow/nonblocking flags and operates on a held
descriptor. `fchmod(fd,0600)` is the only target modification; there is no table
content writer, account/key operation, command launcher or insecure-mode rollback.

Readback checks hash, identity, pathname/parent identity and mode after file and
directory fsync. Replacement or concurrent content changes prevent a success
marker; a partially hardened approved inode is left private rather than restoring
0744. These are sampled observations, not exclusion of a privileged writer or
guaranteed power-loss recovery. The helper's hash reader is bounded even if the
file grows unexpectedly. It supplies no persistence watcher/startup installation.

The SDK was reacquired over HTTPS and matched the existing hash pin. No vendor
script/binary was used as a compiler or executed by the build.

Builder: `scripts/build-shadow-mode-helper.py`.
Retained output: `build/nimbus-shadow-mode-helper-v1/`.

- ARM EABI5 static EXEC, non-executable stack, GNU_RELRO, no PIE.
- `shadow-mode-helper.arm`: 38056 bytes.
- SHA-256: `8e18cdf4c1e514e527e83072886a359f93087f45a52ff9048949dd141ba6a0ed`.
- SDK SHA-256:
  `a7db571eaa0f1ba2eea9a3932e8ad64bfaf33bfb7e7b96dd09702fe3ecedcf1a`.
- No-argument ARM-emulated refusal passed. Production excludes host fixture hooks
  and arbitrary-target arguments. Build flags remain immutable historical evidence.

11 helper/build tests passed, including unchanged bytes/inode/ownership, already
private mode, stale pins, unsafe metadata, symlink/hardlink/FIFO refusal, parent
refusal, inode replacement, concurrent content change and no permission reopening.
Host fixture behavior is not native qualification; the exact native checks below
are separate evidence. `git diff --check` passed; full regression not rerun.

## Failed initial staging — retained, no target change

Uncompressed tar streamed to `/tmp/nimbus-shadow-mode-r1` failed with tar format/
short-read errors. No helper was executed and shadow remained0744. Only the
expected manifest/checksum files were observed; helper.arm was absent/unsafe.
The local reconstructed archive parsed correctly (51200 bytes). The exact cause
of the streamed extraction failure was **not established**; do not label it a
fixed transport bug or repair/retry the failed stage.

New staging used a fresh `/tmp/nimbus-shadow-mode-r2`, an explicitly saved
compressed archive, and **archive SHA-256 verification before extraction**.
23172 compressed bytes, SHA-256:
`e93b3f289d256a9d278061b64cce91ce04b97dd9d8fd03c227bc52eff7b2cc81`.
Transferred archive and extracted payload hashes/modes passed before any helper
execution. Neither stage is automatically cleaned or reused.

## Completed native operation — 2026-10-13

Within the owner's continuing hardening request/broader approval, strictly pinned
normal SSH2224, observed external power and the saved private baseline were used.
No account-table write, new credentials/listener, service stop, USB/media change,
remount, raw reader or firmware operation was involved.

1. One read-only helper check returned exit0:
   `SHADOW-CHECK=PASS identity-and-bytes-matched no-mode-change native_auth_verified=no`.
2. Fresh power/binary/stage checks passed; a retained `HARDEN_CLAIM=ATTEMPTED`
   marked the single change attempt, separate from control stdin.
3. One `--harden` invocation returned exit0:
   `SHADOW-HARDEN=PASS mode=0600 bytes-verified-unchanged=yes account-records-written=no persistence_verified=no`.
4. New pinned management login independently checked all three tables against
   private baseline hashes/metadata. Every byte hash, inode, owner/group, size and
   link count matched; **only shadow mode changed from0744 to0600**. Passwd/group
   stayed unchanged. Zero IPv4 2226 listeners were observed.
5. Vendor homepage returned HTTP200; read-only battery RPC returned100/full.
   This is basic follow-up, not exhaustive FTP/web authentication validation.

Private evidence:
an owner-local protected `.private-provisioning/` directory, including staged/check/run/
postcheck stdout/stderr, input archives and `HARDENING-RECEIPT.json`.
No password/hash contents were displayed. The original private baseline and
account plan are unchanged; their source0744 privacy flag remains historical.
Current permission evidence is the new receipt, not a rewritten old baseline.

**Retain failed r1 and used r2. Do not rerun hardening or restore0744 automatically.**
The helper/check stages, previous probe stage and all private records are distinct.
Tmpfs is volatile; the PC record retains the scoped evidence independently.

## Next gate

Future account installation must require current private shadow permissions and
fresh exact input checks, not restore the old source mode from backup. It still
needs a reviewed vendor-writer coordination/serialization mechanism and safe
commit/readback/rollback. Root-owned table permission changes are not a writer
lock. Native account authentication, jail/privsep/session operation, reset/reboot
behavior, USB lifecycle and a complete installable firmware remain unqualified.

## Fixed backup-path follow-up

Read-only metadata found `/etc/shadow-` root-owned, regular, single-link, mode0744
and 1245 bytes; `/etc/gshadow` and `/etc/gshadow-` were absent. No unknown backup
directories were searched and no backup table contents were copied/displayed.
Leaving a readable shadow backup could still expose password hashes.

Helper v2 adds only fixed `--check-backup` / `--harden-backup` variants for the
literal `shadow-` entry under the same verified `/etc` directory. No arbitrary
target/environment override or new content writer exists. Primary/backup pins
cannot be interchanged, and backup symlinks/hardlinks are refused.

Retained build: `build/nimbus-shadow-mode-helper-v2/`, 38056 bytes, SHA-256
`25cab53a6cb7889d7ca9209802d8bc092384127205c622510368e92e0b3637d5`.
Production code is fixture-free; no-argument ARM-emulated refusal and ELF audit
passed. New native stage `/tmp/nimbus-shadow-backup-mode-r1` used checksum-verified
saved compressed input before extraction, never the failed/used primary stages.

The backup's before metadata/digest were stored privately. Its native read-only
check passed; fresh power/stage/binary checks and one retained HARDEN_CLAIM
preceded one successful permission-only operation:
`SHADOW-HARDEN=PASS target=shadow- mode=0600 bytes-verified-unchanged=yes account-records-written=no persistence_verified=no`.

New pinned SSH readback checked passwd, group, shadow and shadow-: both shadow
modes0600, all four hashes/inodes/owners/sizes/link counts unchanged from their
respective before observations. No password/account record was written. Private
evidence is in the same protected PC directory, including
`BACKUP-SOURCE-BEFORE.json`, backup check/run/postcheck logs and
`BACKUP-HARDENING-RECEIPT.json`. No table digest/contents were displayed.

Current scoped regression: **13 helper/build tests plus 94 SFTP tests passed,
zero skips**. Full regression was not run. Keep v1/v2 builds, failed r1, used
primary r2 and used backup r1 distinct and retained; do not rerun or restore0744.
Vendor reset/reboot persistence and general legacy-service confidentiality remain
unqualified. The earlier build manifests/baseline receipts are not rewritten to
claim later native success or retroactively private source modes.
