# Restricted SFTP — confinement, enrollment and lifecycle source checkpoint

This finishes another source-only portion of the frozen firmware scope, **not a
working SFTP service or native qualification**. Management Dropbear is unchanged.
No device account, key, jail, bind mount, listener or USB setting was changed.
These host-side tools are not ARM applications installed in the firmware.

Later follow-up: the [read-only native collector and probe package](SFTP-LAYOUT-PREFLIGHT.md)
are now implemented/tested. Collection confirmed the layout is absent and current
USB export inactive; proposed ARM execution remains blocked by the external-power
check and needs exact approval. Earlier collector-pending statements below record
the preceding source checkpoint, not current collector availability.

## Implemented

### Confinement metadata validation

`scripts/sftp-confinement.py` validates a supplied
`nimbus-sftp-confinement-observation/v1` record without opening host/device files
or executing anything. It checks:

- Exact effective non-root/key-only/read-only/internal-sftp policy, one explicit
  RFC1918 listen address, no forwarding/shell/PTY/user RC/environment. Duplicate
  required directives are rejected instead of silently choosing the last value.
- Root-owned, non-writable jail ancestry and an empty privilege-separation
  directory; private host key 0600 versus publicly readable authorized key 0644
  in root-owned traversable 0755 authentication directories. Symlink/hardlinked
  auth files and unsafe modes are refused.
- One dedicated restricted Ed25519 client key; no arbitrary key options,
  certificates, private material, appended keys or management identity reuse.
- Distinct non-root file/privsep UIDs/GIDs, no extra groups, no identity collisions,
  and a valid executable non-shell `/bin/false` account shell.
- Expected internal-media block identity and independently supplied SD identity,
  exact source-root/device/filesystem agreement and **VFS read-only** jail views.
  Superblock read-only alone is insufficient; source/view superblock observations
  must agree. Nested, duplicate and unexpected jail mounts are rejected.
- Internal media is required. SD may be absent only with an explicitly observed
  empty root-owned unmounted placeholder; this is not substitute storage.

Inputs are caller assertions from a **not-yet-implemented trusted native
collector**. This does not verify file contents or syscalls, authenticate an
account, prove absence of all aliases, or hold continuous ownership. Success
keeps native verification, listener authorization, USB handoff, production and
flash flags false. Account collision counts/membership must come from fresh
complete native inventory, not a hand-edited success record. Host key fingerprints
must later be checked against the actual private key with reviewed tooling.

### Private offline public-key enrollment preparation

`scripts/prepare-sftp-enrollment.py` takes explicitly selected dedicated client
and management **public** key files. It refuses reuse, private keys, options,
symlinks/hardlinks, shared writable inputs and output escapes. It writes only to
a new direct child of ignored `.private-provisioning/`, using private modes,
exclusive creation and file/directory fsync. Failures retain evidence.

Output is `authorized_keys`, `ENROLLMENT.json` and `NOT-ENROLLED.txt`. Client key
comments are stripped and the only inserted option is `restrict`. Host-side
staging mode is 0600; the separately reviewed device installation must use
root-owned 0644 for the public authorization file, with its root-owned hierarchy.
No client private key or SFTP host identity is generated/copied. No real owner
enrollment was prepared in this checkpoint; tests used synthetic public keys in
disposable fixtures.

Example interface for a later approved local preparation (not run here):

```bash
python3 scripts/prepare-sftp-enrollment.py \
  --client-public-key /absolute/path/to/dedicated-files.pub \
  --management-public-key /absolute/path/to/management.pub \
  --output .private-provisioning/sftp-recipient-01 \
  --label recipient-01
```

No account/shadow entry is supplied. OpenSSH `UsePAM no` can reject a locked
account before key authentication; simply adding `!` to shadow is **not** a tested
key-only enrollment procedure. Password disabling, account expiry, shell checks
and successful dedicated-key login require review against the exact ARM build
and actual vendor account synchronization/reset behavior. Never weaken password
or root-login denial to get a successful fixture.

### Offline shutdown / USB decision model

`scripts/sftp-service-lifecycle.py` emits abstract action labels only. It requires
explicit runtime/enrollment/confinement/ownership/address/supervision approval
facts before a modeled start. Order is:

1. Stop only the identity-bound listener; a changed/replacement listener blocks.
2. Cancel/drain all enrolled sessions; incomplete descendant/handle inventory
   prevents detaching views or releasing media.
3. Detach only reviewed read-only views, with freshly inactive USB state.
4. Verify exact views absent before requesting separate vendor-transition review.

Observed active/unknown ownership is sticky: a later inactive observation does
not revive that attempt. On ownership loss the model permits session shutdown,
but preserves view state for explicit review rather than suggesting unmounts
while export may own the media. Deadlines never skip drain checks. No automatic
restart, process signal, unmount or vendor USB operation is implemented.

`MaxSessions 1` is **per SSH connection**, not a total-client cap. The model treats
more than one observed session as invalid and requires a separately implemented
bounded supervisor. This is sampled intent, not enforced global admission or a
proof of all descendants. Fresh native process identities, closure/reaping,
mount-state integration and actual handoff tests remain open.

## Retained ARM runtime review

All 29 files in `build/nimbus-sftp-runtime-v1/EXPORT-MANIFEST.json` matched their
recorded sizes/hashes. Six ARM EABI5 static ELF metadata audits passed. No binary
was executed in that audit; native flags remain false. Earlier emulated/host
policy/probe evidence is retained, not promoted to physical-device success.

The temporary source/SDK workspace named in older build notes is absent. The
immutable export retains its binaries/review inputs; rebuilding requires reviewed
inputs again, not execution of a guessed stock sshd. The latest drive observation
still had USB export loaded and no local media mounts. No listener trial proceeds
from this source work.

## Remaining native gates

Scoped regression after this source checkpoint: **53 SFTP tests passed, no
skips**, including existing host `sshd -T` parsing without a listener, runtime
metadata guards, new confinement/refusal cases, enrollment collision/path/sync
failures and lifecycle ordering/ownership loss. `git diff --check` passed.
Full workspace regression was not rerun. Tests generated no real recipient
identities and provide no new native runtime/authentication/handoff evidence.

Native version/probe-only qualification comes first, under separately reviewed
exact approval and fresh management/power/space/ownership checks. Then implement
the trusted metadata collector, account/host-identity provisioning, supervised
service/view executor, confinement/denial/readback tests and USB lifecycle tests.
Do not create accounts, keys, binds or a listener from an offline success record.
The generic firmware does not include these experiments or recipient identities.

Related: [runtime and native gates](RESTRICTED-SFTP-CANDIDATE.md),
[media ownership limits](MEDIA-OWNERSHIP-GUARD.md),
[feature freeze](FIRMWARE-FEATURE-FREEZE.md).
