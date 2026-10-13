# Dashboard A/B + battery: owner-operated UI-only update

**Installed 2026-10-13; user-visible acceptance pending.** These are retained
deployment/recovery instructions, not permission to repeat staging or installation.
No firmware image, service restart, storage
mount, USB-mode change, new key or radio action is involved. Only toolkit HTML,
CSS, JS, the existing performance bridge and a new battery asset are changed.
The stock `index.html` and its handlers are not replaced.

Package: `build/nimbus-dashboard-ab-r1.tar.gz` (26031 bytes)

SHA-256: `e600abaaeb09e06aedf44da400a5982e24b20b72c45dfc3469d98be5b6d3f3a8`

This package is guarded for the four owner-returned baseline hashes in
`scripts/package-dashboard-ab.py`. It refuses changed targets, existing battery
files, symlinks/hardlinks, non-root/incorrect metadata, unexpected root mount
options, reused stages and concurrent transaction attempts. A refusal means
**stop and inspect**, not remove locks, alter hashes or rerun. Failed/partial
stages are retained. Shell transaction recovery is not power-loss certification.

## 1. Local backup and check (no installed UI writes)

Run in a local Bash terminal from this repository. The encrypted key's passphrase
stays in your terminal. Use normal pinned port 2224; do not restart 2225.

```bash
umask 077
ssh_device() {
  ssh -p 2224 -i "$HOME/.ssh/nimbus-admin-ed25519" \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$HOME/.ssh/nimbus-test-known-hosts" \
    root@192.0.2.10 "$@"
}
printf '%s  %s\n' \
  e600abaaeb09e06aedf44da400a5982e24b20b72c45dfc3469d98be5b6d3f3a8 \
  build/nimbus-dashboard-ab-r1.tar.gz | sha256sum -c -
```

Stop if verification fails. Create a unique private PC backup before staging:

```bash
backup_dir=$(mktemp -d "$HOME/nimbus-dashboard-before.XXXXXXXX")
if ssh_device 'cd /nimbus/data && tar -cf - fieldkit-v06/toolkit.html fieldkit-v06/toolkit.js fieldkit-v06/toolkit.css fieldkit-performance-r1/bridge.js' \
  > "$backup_dir/original-ui.tar"; then
  python3 - "$backup_dir/original-ui.tar" <<'PY'
import hashlib, sys, tarfile
expected = {
 'fieldkit-v06/toolkit.html': 'ebaad09ee0834bd496e760e148c180d0f88117f82088b8987e439f2f06642f79',
 'fieldkit-v06/toolkit.js': 'a9d6678149d711656e4076045a1ceece5bf48410d997ce207bca205f2ec2813d',
 'fieldkit-v06/toolkit.css': 'ca6f72c45a75302ce50f2ffffb47a90733ce6aede27a89ecaec3b7e1366092b4',
 'fieldkit-performance-r1/bridge.js': '5a748e55be9b8334da16fe59ae1cadeecdad46f99a0e4f2119195c5fdc16ec52',
}
with tarfile.open(sys.argv[1]) as archive:
    assert set(archive.getnames()) == set(expected)
    for name, digest in expected.items():
        member = archive.getmember(name)
        assert member.isfile() and member.uid == member.gid == 0 and member.mode == 0o644
        assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == digest
print('PC-UI-BACKUP=PASS (checked saved archive, not device durability)')
PY
else
  echo 'Backup failed; stop. Retain partial archive for inspection.'
fi
```

Proceed only after `PC-UI-BACKUP=PASS`. Retain the private backup directory.
Device backups are in tmpfs and **do not survive a reboot**. The PC archive is a
recovery input, not permission to restore over later owner changes.

Stage only this reviewed first-party archive in a new tmpfs directory, then check:

```bash
ssh_device 'umask 077; test ! -e /tmp/nimbus-dashboard-ab-r1 && test ! -L /tmp/nimbus-dashboard-ab-r1 && mkdir -m 700 /tmp/nimbus-dashboard-ab-r1 && cd /tmp/nimbus-dashboard-ab-r1 && tar -xzf - && sh install.sh --check' \
  < build/nimbus-dashboard-ab-r1.tar.gz
```

Expected: `DASHBOARD-AB-CHECK=PASS no-UI-written`. Any other output: stop, retain
the stage and report it. Staging/check writes only to the new `/tmp` directory.
Do not run an older unified/runtime installer; the runtime path is absent.

## 2. UI installation

Only after a successful saved-PC-backup and device check:

```bash
ssh_device 'sh /tmp/nimbus-dashboard-ab-r1/install.sh install'
```

Expected: `DASHBOARD-AB-INSTALL=PASS`. The installer rechecks original hashes,
keeps private backups, renames verified replacement files and calls device
`sync`. If interrupted, it attempts to restore only exact known replacement
hashes; unrecognized changes are left alone and reported. No power-loss or
native durability qualification is claimed. Do not reboot or delete the stage
while inspecting a failure.

## 3. Live acceptance

Hard-refresh the current drive's `#overview` page (example: `http://192.0.2.10/#overview`):

- Overview opens; GameHack onboard Wi-Fi → pinned SSH to managed A → A USB/data
  link to B is described, without claiming automatic A→B dispatch.
- Homepage battery shows the current vendor percentage, including 0%, with
  charging status; a failed/invalid response displays **Unknown**.
- Missing snapshot clears stale metrics. Read-only `getUseServices` may explain
  that vendor USB access is enabled; it is **not proof of a physical USB host**.
  No media mount, synthetic snapshot or storage-mode change is attempted.
- Stock Files, Photos, Music, settings and web-admin behavior remain available.
  Do not test destructive settings, radio changes or format/reset operations.

Offline Chromium/fixture tests are not this live acceptance. Report observed
page/battery/errors before claiming deployment complete.

## 4. Guarded rollback (same boot, retained stage)

```bash
ssh_device 'sh /tmp/nimbus-dashboard-ab-r1/install.sh rollback'
```

Requires exact installed hashes across all five files before any restore. Later
owner edits cause refusal. Restores four originals, removes only the exact new
battery asset, retains evidence and reports `DASHBOARD-AB-ROLLBACK=PASS`.
Rollback attempts are deliberately single-use; failures require inspection.
After reboot, do not re-stage/install to obtain rollback: use the saved PC
backup for a separately reviewed recovery plan against fresh device hashes.

Next coding batch after dashboard acceptance: proposed Wardriving GO session,
capability and explicit permissioned phone-location contracts; not automatic
live surveying, monitor mode or a new running location endpoint.
