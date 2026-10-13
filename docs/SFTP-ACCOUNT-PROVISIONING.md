# SFTP account provisioning — offline plan, no installed accounts

Existing native version/own-process probes passed. This next frozen-scope batch
reviews account semantics and prepares append-only **host-side** account plans.
No account, password, key, listener, jail, bind view or firmware change is made on
the drive by this work. Probe-stage evidence remains untouched.

## Exact build/source review

OpenSSH 10.6p1 source was fetched again over HTTPS and matched the already reviewed
archive SHA-256 `a9dc9565dffe8640f64d863cd29a32bc4a3dbdec0566a7fc44c5d6ee767d5f39`.
It was not built/executed. Selected source and its license are retained in
`build/nimbus-sftp-account-review-v1/`, alongside the exact retained ARM config
header and `REVIEW.json`. Tool: `scripts/audit-sftp-account-policy.py`.

The config header hash is
`7f0494e813c9ab9309af544446c31822be84eaf6ca2ecd696d6c5d1238b42432`.
Relevant settings: shadow lookup/expiry enabled, locked-password prefix `!`, no
additional locked-string/substr policy, and `nimbus-sshd` privsep identity.

`auth.c` rejects `platform_locked_account()` with `UsePAM no` before public-key
authentication. `platform.c` obtains shadow when available and applies the
compiled lock prefix; account expiry is separately checked. Therefore adding
`nimbus-files:!` is **not** a usable key-only login design for this build.

Proposed role records:

| Role | Default dedicated UID/GID | Home | Shell | Shadow marker |
| --- | --- | --- | --- | --- |
| nimbus-files | 2206 | /internal | /bin/false | `*`: no usable password hash, not the compiled `!` account-lock prefix |
| nimbus-sshd | 2207 | /root/nimbus-sftp-candidate-v1/empty | /bin/false | `!`: deliberately locked; never a login identity |

The public-key-only SFTP configuration stays unchanged: password/PAM/keyboard
authentication and root login remain disabled. Existing accounts are never
unlocked/rewritten to obtain access. No claim is made that every vendor login
implementation treats markers identically. Target libc shadow decoding, actual
account eligibility, expiry, authentication and password denials remain native
gates. Empty aging fields and last-change=1 are proposed to avoid forced-change=0
and configure no account expiry; they are not tested target shadow behavior yet.

Host tests compile the **exact** hash-reviewed upstream lock function with a
synthetic shadow lookup: `!`, `!!`, `!placeholder` are locked and `*` is not.
This is neither a native libc lookup nor a native SFTP authentication test.

## Private append-only planner

`scripts/prepare-sftp-accounts.py` validates bounded complete passwd/group/shadow
inputs and the exact pinned ARM header before creating an exclusive private
plan under a new direct child of ignored `.private-provisioning/`.

- Requires collision-free explicit non-root IDs; does not allocate/guess around
  existing names, UIDs, primary GIDs, groups or stale supplementary memberships.
- Refuses either role already present in any table: no implicit repair, overwrite,
  reuse or unlock. Existing table bytes, including valid empty existing shells
  and vendor numeric group names, remain unchanged.
- Adds only two explicit `/bin/false` roles and distinct empty-membership groups.
  Per-file baseline hashes and before/after hashes are retained **privately**; table
  contents/hashes must not be pasted into chat or included in generic firmware.
- Stores inputs/outputs in private modes with exclusive creation/fsync; failed
  stages are retained and not reused. Includes no device installer or listener.
- Proposed installation order is group → shadow → passwd, so a newly visible
  login identity never intentionally precedes its password-unusable shadow entry.
  Proposed rollback removes the passwd identity before restoring shadow/group.
  This order is a plan, not an atomic transaction or qualified recovery path.

A pure in-memory test against hash-verified **clean beta5** account tables passed;
no table outputs were saved from that check. Initial parsing conservatively
refused an empty shell and numeric group names; both valid vendor formats are now
preserved and regression-tested rather than rewriting unrelated entries.

The layout collector now emits protocol version 2 with redacted expected/other
role-home classifications. The parser retains version-1 observation support, but
old present-account records without home evidence cannot qualify. Confinement
requires each role's exact reviewed home. No live collector rerun or account edit
is implied by this source revision.

## Vendor reset / concurrent writer gate

Latest offline writer audit and pure commit/rollback byte model:
[account writer review](SFTP-ACCOUNT-WRITER-REVIEW.md). The model preserves later
unrelated edits but is not an installer or writer lock. Selected vendor libc
locking support and BusyBox/Nimbus symbol evidence do not qualify coordination.
Native role installation remains blocked; no accounts were added.

Read-only clean-image review found `nimbus_resetpwn.sh` invoking `ResetAdmin`
through `fw_server`, clearing saved uplink settings and stopping/restarting Wi-Fi.
That script must **not** be executed to inspect account behavior. The proprietary
handler's complete Linux-account synchronization/preservation behavior is not
established. A selected token scan of the clean fw_server client found `passwd`
but not direct `/etc/passwd`, `/etc/shadow` or `ResetAdmin` tokens; that is not
evidence of absence of indirect account writers.

Account installation remains blocked until fresh private baseline metadata,
complete collision checks, writer coordination, serialized commit/readback,
later-edit-safe rollback and exact operation approval are reviewed. Merely
checking hashes immediately before rename cannot rule out a concurrent vendor
password update. Reboot/reset persistence and recipient first-use access are
still release gates. The existing beta5 archive already stores both shadow files
root-owned 0600; no new permission change was needed or made.

## Next bounded preparation

A separately approved **read-only private baseline copy** may copy only
`/etc/passwd`, `/etc/group`, `/etc/shadow` via pinned encrypted SSH directly to a
new mode-0700 PC provisioning directory, with file metadata/hash checks and
mode-0600 saved files. Shadow contains password hashes: no contents should enter
tool logs/chat/public storage. This is not permission to modify those files,
generate/install keys, start a listener, read other secret files or collect a
full root capture. No live account-table contents were copied in this batch.

Source checkpoint validation: **94 SFTP tests passed, no skips**; `git diff
--check` passed. This includes the exact upstream lock-function host test,
append-only/collision/private-output cases and role-home/redaction/legacy-frame
refusals. Full workspace regression was not rerun; no new native account or
authentication evidence was obtained from these tests.

## Approved private baseline follow-up — connection blocked

After reviewing the handoff, the owner approved the exact read-only private copy
and local planning. The pinned metadata precheck could not connect; subsequent
SSH returned `No route to host` at the then-current device endpoint. Local route lookup was
present, but the peer neighbour entry was `FAILED`. No account contents were
copied, no private baseline/plan directory created, and no device/network change
performed. Approval is retained, but fresh owner-confirmed reachability and
fixed-path metadata checks are required before copying. Do not scan addresses,
remove the host pin, restart listeners or reuse probe stages to bypass this.

## Completed private baseline and per-device plan

After connectivity and the locally unlocked key were restored, strictly pinned
port2224 access worked. Fixed-path metadata found root-owned regular single-link
passwd/group/shadow, all mode **0744**, including live shadow. Clean beta5's
shadow0600 mode does not describe the live stock file. Live shadow is readable by
other local users; the source permission was **not** changed to make a check pass.

The initial private-source mode check refused. The subsequent approved read-only
copy explicitly distinguished confidentiality from write integrity: source0744
has no group/other write permission, so it was captured into private PC storage
with an unsafe-source privacy flag. This does not waive hardening/release gates.

Private baseline:
an owner-local protected directory under `.private-provisioning/`.
Only the approved three files were copied. Original archive, extracted mode0600
tables, private before/after metadata+hashes and receipt are retained under
mode0700. Archive members/sizes/ownership/modes, source hashes, saved-file readback
and local fsync checks passed. Contents/password hashes were not displayed. No
symlink/special file was followed. Equality is sampled integrity, not a database
transaction or an exclusive writer lock.

Private plan:
an owner-local protected directory under `.private-provisioning/`.
Planning against the captured tables and pinned ARM header passed. IDs2206/2207
are free in that snapshot and existing table bytes are preserved. Proposed new
records are **not installed**. Never overwrite/publish these private stages or
import their baseline-derived tables into generic firmware.

No device account/key/permission, service, media/USB or firmware change was made.
Native auth, reset persistence, account installation and flash flags remain
false. Next work is a permission-only hardening design plus actual writer
coordination and serialized account installation/readback/rollback. A permission
fix must not rewrite passwords or automatically restore the world-readable mode.
Fresh current-input checks are needed before a later write; the snapshot is not
valid indefinitely.

## Subsequent permission-only native fix

The fixed-path held-descriptor helper subsequently verified the saved private
pin and tightened live shadow to0600. New pinned readback matched every original
table hash/inode/owner/size/link count; only shadow mode changed. No new records,
keys, jail/view or listener were installed. Retained baseline/source0744 metadata
is historical, not current permissions. Never restore the insecure mode from
that backup automatically. See [native hardening evidence and staged failure](SHADOW-MODE-HARDENING.md).
Writer coordination, reboot/reset persistence and native SFTP login remain open.

The known `/etc/shadow-` backup was subsequently hardened from0744 to0600 with
fixed backup-only helper v2. Independent checks matched all four original file
hashes/inodes and confirmed both shadow modes0600; no account records changed.
No backup contents were copied/displayed. Keep the new private receipt and used
backup stage distinct; do not use the old source modes for rollback or claim
vendor reset/reboot persistence from this one checkpoint.

Related: [confinement/enrollment](SFTP-CONFINEMENT-ENROLLMENT.md),
[native probe evidence](SFTP-LAYOUT-PREFLIGHT.md),
[frozen release gates](FIRMWARE-FEATURE-FREEZE.md).
